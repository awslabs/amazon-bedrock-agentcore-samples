"""Create the Cognito users that correspond to the traveller fixtures.

    uv run python -m seed.users --user-pool-id us-east-1_XXXX

**Derived from `travelers.py`, never restated.** The opaque traveller id is the
join between the token and the profile store, so a second hand-maintained copy
would eventually drift — and the failure mode is nasty: the user authenticates
fine, then resolves to no profile, which reads like a broken backend rather than a
stale fixture.

A script rather than CDK because CloudFormation cannot set a password, and
`AdminSetUserPassword` is what turns a `FORCE_CHANGE_PASSWORD` user into one that
can actually sign in. Idempotent: an existing user is updated rather than
duplicated, so re-running after a fixture change is the normal way to fix drift.

The token these users receive carries **identity only** — tenant, traveller id,
role. Not `can_book_for`: an arranger relationship belongs to the travel platform
and is resolved live (`app/service/arrangers.py`), because a corporate directory
has no concept of who may book for whom.
"""

import argparse
import os
import secrets
import string
import sys

import boto3
from botocore.exceptions import ClientError

from .travelers import TRAVELERS

# Only these three sign in. The other fixtures exist to make name resolution and
# cross-tenant checks meaningful, and giving every one of them a login would imply
# the demo needs six passwords when it needs three.
DEMO_USERNAMES = {
    "Priya Raghunathan": "priya",
    "Adaeze Okonkwo": "adaeze",
    "Sam Whitfield": "sam",
}

# Cognito custom attributes are addressed with this prefix; the pool declares them
# without it.
CUSTOM = "custom:"

# **Where the shared demo password lives, so a re-run does not rotate it.**
#
# It used to be generated, printed once and stored nowhere — which reads as careful until you rerun
# the seed. Then every existing user's password is silently reset, the value the operator wrote down
# stops working, and the two verification suites fail authentication for a reason that looks like a
# broken deployment.
#
# A `SecureString` rather than a plain one, and a parameter rather than a stack output: an output is
# readable by anyone with `DescribeStacks` and appears in the console in plaintext. Secrets Manager
# was the other candidate, rejected at $0.40/month for a fixture credential in a sample people
# deploy once to try. This is still a demo credential for three fictional users, not a secret worth
# a KMS key of its own.
PASSWORD_PARAM = "/multi-tenant-travel/identity/demo-password"


def _password() -> str:
    """A password satisfying the pool's policy.

    Generated rather than hardcoded: a committed credential is a committed
    credential even in a sample, and readers copy samples.
    """
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(16))
    # Guarantee one of each required class rather than relying on chance.
    return f"Wk{body}9!"


def _stored_password() -> str | None:
    """The password a previous run stored, or `None`.

    Absent is the normal first-deploy case, so it is not an error. Any other failure is left to
    raise: a denied `GetParameter` means the caller cannot read what it is about to overwrite, and
    guessing past that would rotate a password it could not see.
    """
    client = boto3.client("ssm")
    try:
        got = client.get_parameter(Name=PASSWORD_PARAM, WithDecryption=True)
    except client.exceptions.ParameterNotFound:
        return None
    return got["Parameter"]["Value"]


def _store_password(password: str) -> None:
    """Record the shared password for the verification suites to read."""
    boto3.client("ssm").put_parameter(
        Name=PASSWORD_PARAM,
        Value=password,
        Type="SecureString",
        Overwrite=True,
        Description="Shared password for the three demo users; created by seed.users",
    )


# **Cognito fixes mutability at pool creation, and two of these are deliberately immutable.**
#
# `tenant_id` and `traveler_id` cannot be edited — see `infra/lib/identity.ts`, and the reasoning in
# the agent's `memory.py`, which relies on a traveller being unable to reshape their own namespace.
# So a re-run cannot send them to `AdminUpdateUserAttributes`: it rejects the whole call with
# `InvalidParameterException`, which is what made `./deploy.sh --seed` crash on an existing pool
# with a botocore traceback and no explanation.
IMMUTABLE_ATTRS = frozenset({f"{CUSTOM}tenant_id", f"{CUSTOM}traveler_id"})


def _update_existing(client, user_pool_id: str, username: str, traveler, attributes) -> None:
    """Bring an existing demo user in line with the fixtures.

    Re-running after a fixture change is the intended way to fix drift, so an existing user is
    updated rather than treated as an error. Only the mutable attributes are sent; the immutable
    ones are read back and compared, because a difference there cannot be fixed by an update and
    the operator needs to know that rather than watch a call fail.
    """
    current = {
        a["Name"]: a["Value"]
        for a in client.admin_get_user(UserPoolId=user_pool_id, Username=username)["UserAttributes"]
    }
    conflicts = {
        a["Name"]: (current.get(a["Name"]), a["Value"])
        for a in attributes
        if a["Name"] in IMMUTABLE_ATTRS and current.get(a["Name"]) != a["Value"]
    }
    if conflicts:
        detail = ", ".join(
            f"{name}: {was!r} -> {wants!r}" for name, (was, wants) in conflicts.items()
        )
        raise SystemExit(
            f"{username} already exists with different immutable claims ({detail}).\n"
            "Cognito fixes these at creation, so this cannot be updated in place — delete the user "
            "and re-run, or tear the pool down with ./cleanup.sh."
        )

    client.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[a for a in attributes if a["Name"] not in IMMUTABLE_ATTRS],
    )
    print(f"  updated {username} ({traveler.tenant_id}, {traveler.role.value})")


def _attributes(traveler, username: str) -> list[dict[str, str]]:
    """The three identity claims, plus the standard profile fields.

    `email_verified` is set because these are administratively onboarded users —
    the employer vouched for the address. Without it Cognito treats the address as
    unconfirmed and blocks password recovery.
    """
    return [
        {"Name": "email", "Value": traveler.email},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "name", "Value": traveler.full_name},
        {"Name": f"{CUSTOM}tenant_id", "Value": traveler.tenant_id},
        {"Name": f"{CUSTOM}traveler_id", "Value": traveler.traveler_id},
        {"Name": f"{CUSTOM}role", "Value": traveler.role.value},
    ]


def seed_users(user_pool_id: str, *, password: str | None = None) -> list[tuple[str, str]]:
    """Create or update the demo users. Returns (username, password) pairs.

    A shared password across the three is deliberate for a demo: three separate
    generated secrets is friction with no security benefit when every account is
    fictional and the pool is disposable.
    """
    client = boto3.client("cognito-idp")
    # An explicit password wins; then whatever a previous run stored; only then a new one. The
    # middle branch is what makes a re-run safe — without it, seeding again to pick up a fixture
    # change also invalidated the password the operator was using.
    shared_password = password or _stored_password() or _password()
    created: list[tuple[str, str]] = []

    by_name = {t.full_name: t for t in TRAVELERS}

    for full_name, username in DEMO_USERNAMES.items():
        traveler = by_name.get(full_name)
        if traveler is None:
            # A renamed fixture must fail loudly rather than silently skip a user
            # the two-tenant contrast depends on.
            raise SystemExit(
                f"no traveller fixture named {full_name!r} — "
                "seed/travelers.py and DEMO_USERNAMES have drifted"
            )

        attributes = _attributes(traveler, username)

        try:
            client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=attributes,
                # Nothing to email: these are fictional addresses, and a delivery
                # attempt would fail noisily for no reason.
                MessageAction="SUPPRESS",
            )
            print(f"  created {username} ({traveler.tenant_id}, {traveler.role.value})")
        except ClientError as error:
            if error.response["Error"]["Code"] != "UsernameExistsException":
                raise
            _update_existing(client, user_pool_id, username, traveler, attributes)

        # Without this the user sits in FORCE_CHANGE_PASSWORD and cannot complete
        # the password flow the terminal demo uses.
        client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=username,
            Password=shared_password,
            Permanent=True,
        )
        created.append((username, shared_password))

    # Written after the users exist, so a failure part-way through does not advertise a password
    # that nothing accepts.
    _store_password(shared_password)

    return created


def verify_claims(user_pool_id: str) -> None:
    """Read the users back and confirm the claims are present and correct.

    Reading back rather than trusting the writes: the specific failure this
    catches is a custom attribute that silently did not apply, which produces a
    token missing `tenant_id` and an authorization layer with nothing to enforce.
    """
    client = boto3.client("cognito-idp")
    required = {f"{CUSTOM}tenant_id", f"{CUSTOM}traveler_id", f"{CUSTOM}role"}

    for username in DEMO_USERNAMES.values():
        user = client.admin_get_user(UserPoolId=user_pool_id, Username=username)
        present = {a["Name"]: a["Value"] for a in user["UserAttributes"]}

        missing = required - present.keys()
        if missing:
            raise SystemExit(f"{username} is missing claims: {sorted(missing)}")

        # The token must carry no authorization data. If a `can_book_for` attribute
        # ever appears here, the design has drifted back to the thing we rejected.
        forbidden = [name for name in present if "can_book_for" in name]
        if forbidden:
            raise SystemExit(
                f"{username} carries authorization data in its claims: {forbidden} — "
                "the token is for identity only"
            )

        print(
            f"  {username}: tenant={present[f'{CUSTOM}tenant_id']} "
            f"traveler={present[f'{CUSTOM}traveler_id']} "
            f"role={present[f'{CUSTOM}role']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-pool-id",
        default=os.environ.get("TRAVEL_USER_POOL_ID"),
        help="Cognito user pool id; defaults to $TRAVEL_USER_POOL_ID",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TRAVEL_DEMO_PASSWORD"),
        help="Shared demo password; generated and printed if omitted",
    )
    args = parser.parse_args()

    if not args.user_pool_id:
        parser.error("--user-pool-id is required (or set TRAVEL_USER_POOL_ID)")

    print(f"Seeding users into {args.user_pool_id}...")
    created = seed_users(args.user_pool_id, password=args.password)

    print("Verifying claims...")
    verify_claims(args.user_pool_id)

    password = created[0][1]
    print(f"\n{len(created)} users ready. Shared password: {password}")
    print(f"Stored at {PASSWORD_PARAM} — the suites read it, so `--password` is optional.")
    print("Sign in as `priya` (globex) or `sam` (initech) to see the two-tenant contrast.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
