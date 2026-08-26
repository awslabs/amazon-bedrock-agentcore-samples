"""Tenant isolation: does a cross-tenant probe fail at **each layer independently**?

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_isolation.py
The claim worth proving is not "cross-tenant access fails" — one control could be carrying all
the weight and nobody would know. It is that **several independent controls each refuse it**, so
removing any one still leaves a refusal. This script checks them one at a time.

  1. **Cognito / pre-token trigger** — a token cannot be minted without tenant claims at all, so
     the fail-closed path fires before any of our code runs.
  2. **Cedar at the gateway** — the read-tool permit *requires* `custom:tenant_id`; a call with no
     verified tenant matches no permit and is denied before the target Lambda is invoked.
  3. **The interceptor** — a caller who presets `X-Tenant-Id` has it stripped and replaced from
     verified claims, so the header the tools trust cannot be chosen by the caller.
  4. **The tool layer** — `tenant_id` is not in any tool schema, so the model has no field to put
     another tenant in even if it wanted to.
  5. **IAM row-scoping** — `dynamodb:LeadingKeys` pinned to the session tag refuses a query for
     another tenant's partition regardless of what our code intended.
  6. **The backend** — a traveller in another tenant is a 404, indistinguishable from one that
     does not exist.
  7. **KB metadata filter** — retrieval is filtered server-side from verified context, so one
     tenant's question cannot reach another's documents.

Layers 1, 2, 3, 5 and 6 were each additionally verified **with the control removed** while they
were built — the only way to know a control was doing anything. Those runs are not repeated here,
because disabling a live control needs a deliberate decision rather than a script anyone can run.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

import boto3

sys.path.insert(0, "..")
from deployed_refs import refs

from scripts.verify_guardrails import call_tool, token_for

# **Read from the deployment, not pasted from one.** These were hardcoded ids, which made the
# suite pass in one account and fail in every other — reporting a broken isolation layer when the
# only thing wrong was the pool it was pointed at. See `deployed_refs.py`.
REGION = refs.region
USER_POOL_ID = refs.user_pool_id
CLIENT_ID = refs.cli_client_id
GATEWAY_URL = refs.gateway_mcp_url
# **No `BACKEND_URL` any more.** The API is `PRIVATE` since the VPC migration, so no URL reaches it
# from outside the VPC — see `backend_probe_status`, which invokes the function instead.
DATA_ROLE_ARN = refs.tenant_data_role_arn
MCP_PROTOCOL_VERSION = "2025-03-26"

# Globex's cap is $250; Initech's is €150. Seeing the *other* number is the leak.
INITECH_TRAVELER = "trv_bbc2e338c41a"  # Sam Whitfield, initech
TRAVELERS_TABLE = "multi-tenant-travel-travelers"
# Taken from the role ARN we already resolve, so the simulator needs no second source of truth.
ACCOUNT_ID = DATA_ROLE_ARN.split(":")[4] if DATA_ROLE_ARN else ""

BACKEND_FUNCTION = "multi-tenant-travel-mock-tmc"


def backend_probe_status(path: str, *, tenant: str) -> int:
    """Status code from calling the backend **directly**, bypassing every layer above it.

    **Why a Lambda invoke rather than an HTTPS request.** This check's whole value is that it tests
    the backend *independently* — no gateway, no Cedar, no interceptor, no tool code — so that a
    refusal here proves the backend refuses on its own rather than being protected by something in
    front of it. Routing the probe through a tool would conflate the layers and quietly weaken the
    claim the suite exists to make.

    Since the VPC migration the API is `PRIVATE`, so an HTTPS request from a laptop has no route at
    all (`URLError: nodename nor servname provided`) — which is the point of the migration, and also
    breaks a test that reached it that way. Invoking the function is the same probe against the same
    code path, from the one direction still available.

    The event is a hand-built API Gateway proxy event because the handler is Mangum, which parses
    exactly that shape. `requestContext.path` carries the stage-prefixed form the gateway sends.
    """
    event = {
        "resource": "/{proxy+}",
        "path": path,
        "httpMethod": "GET",
        "headers": {"X-Tenant-Id": tenant, "Accept": "application/json", "Host": "probe"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {"proxy": path.lstrip("/")},
        "stageVariables": None,
        "requestContext": {
            "resourcePath": "/{proxy+}",
            "httpMethod": "GET",
            "path": f"/v1{path}",
            "stage": "v1",
            "requestId": "isolation-probe",
            "identity": {"sourceIp": "127.0.0.1"},
            "protocol": "HTTP/1.1",
        },
        "body": None,
        "isBase64Encoded": False,
    }
    response = boto3.client("lambda", region_name=REGION).invoke(
        FunctionName=BACKEND_FUNCTION, Payload=json.dumps(event).encode()
    )
    return int(json.loads(response["Payload"].read()).get("statusCode", 0))


def tool_schemas(token: str) -> dict[str, list[str]]:
    """Every tool's argument names, from the gateway's own `tools/list`.

    Read from the live gateway rather than the repo's schema files: the question is what the model
    is actually offered, which is what the gateway advertises — not what we intended to publish.
    """
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    try:
        tools = json.loads(raw).get("result", {}).get("tools", [])
    except json.JSONDecodeError:
        return {}
    return {
        t["name"]: sorted((t.get("inputSchema") or {}).get("properties", {}).keys()) for t in tools
    }


def leading_keys_condition() -> tuple[str, str] | None:
    """The `(operator, value)` of `dynamodb:LeadingKeys` on the deployed data role.

    `None` if the policy is unreadable. **Returns the operator as well as the value, and that is the
    point:** the value alone cannot tell you whether the boundary is exact. `StringLike` with
    `TENANT#${aws:PrincipalTag/tenant}*` and `StringEquals` with
    `TENANT#${aws:PrincipalTag/tenant}` differ by one character and one word, and the first lets any
    tenant read every tenant whose id extends its own.

    **Read from the deployed policy rather than inferred from a refusal.** An operator cannot
    assume this role — the trust policy admits only the backend's execution role — so the live
    cross-tenant read that would exercise `LeadingKeys` is unavailable from here.
    `simulate_leading_keys()` closes that gap without credentials.
    """
    iam = boto3.client("iam", region_name=REGION)
    role_name = DATA_ROLE_ARN.rsplit("/", 1)[-1]
    try:
        names = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
        for name in names:
            document = iam.get_role_policy(RoleName=role_name, PolicyName=name)["PolicyDocument"]
            for statement in document.get("Statement", []):
                for operator, keys in (statement.get("Condition") or {}).items():
                    found = (keys or {}).get("dynamodb:LeadingKeys")
                    if found:
                        value = found[0] if isinstance(found, list) else found
                        return operator, value
    except iam.exceptions.ClientError:
        # No `iam:GetRolePolicy`. Reported as unverified rather than as a failure: the caller's
        # permissions are not the control under test.
        return None
    return "", ""


def simulate_leading_keys(tenant: str, leading_key: str) -> str | None:
    """Would the deployed role allow `tenant` to Query `leading_key`? `None` if unsimulatable.

    **`iam:SimulatePrincipalPolicy` is how this gets tested at all.** The trust policy correctly
    refuses to issue these credentials outside the backend, so there is no way to probe the boundary
    live from here — which is why it went unprobed, and why a prefix collision survived in it. The
    simulator applies the real policy to a hypothetical request, including the
    `aws:PrincipalTag/tenant` and `dynamodb:LeadingKeys` context the condition reads. No credentials
    minted, no rows touched, and it answers the exact question.
    """
    iam = boto3.client("iam", region_name=REGION)
    try:
        response = iam.simulate_principal_policy(
            PolicySourceArn=DATA_ROLE_ARN,
            ActionNames=["dynamodb:Query"],
            ResourceArns=[f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{TRAVELERS_TABLE}"],
            ContextEntries=[
                {
                    "ContextKeyName": "aws:PrincipalTag/tenant",
                    "ContextKeyValues": [tenant],
                    "ContextKeyType": "string",
                },
                {
                    "ContextKeyName": "dynamodb:LeadingKeys",
                    "ContextKeyValues": [leading_key],
                    "ContextKeyType": "stringList",
                },
            ],
        )
        return response["EvaluationResults"][0]["EvalDecision"]
    except iam.exceptions.ClientError:
        return None


def data_role_exists() -> bool | None:
    """Whether the tenant data role is there. `None` if the caller cannot tell.

    Needed because a refused `AssumeRole` and a nonexistent role are the same `AccessDenied`, so
    check 5's fallback arm cannot distinguish a working control from a stale ARN on its own.
    """
    iam = boto3.client("iam", region_name=REGION)
    try:
        iam.get_role(RoleName=DATA_ROLE_ARN.rsplit("/", 1)[-1])
        return True
    except iam.exceptions.NoSuchEntityException:
        return False
    except Exception:  # noqa: BLE001 — no iam:GetRole; say so rather than guess
        return None


def unsigned_backend_status() -> tuple[int, str]:
    """Call the mock TMC with a tenant header and no signature. Expect 403.

    **This is the regression test for the hole every other layer was sitting behind.** The backend
    trusts `X-Tenant-Id`, because layer 3 is what puts it there from verified claims. That trust is
    only sound if nobody can send the header themselves — and the API was public, so they could:
    `curl` with no headers returned 401, and `curl -H "X-Tenant-Id: globex"` returned 200 with
    full profile PII. Cedar, the interceptor, the session tag and `LeadingKeys` all sit *in front
    of* this API, so a direct call walked around all seven layers at once.

    Deliberately **unsigned**, and deliberately carrying a plausible tenant header: the question is
    whether asserting a tenant is enough, which is what an attacker would try. A 403 means the
    request had no principal and never reached the handler.

    Distinguished from 404 for the reason `verify_network`'s equivalent check learned the hard
    way: a mistyped path also fails, looks like a refusal, and proves nothing. `/v1/health` carries
    the stage prefix once because it is mounted on the app rather than on a router.
    """
    url = f"{refs.backend_api_url.rstrip('/')}/health"
    request = urllib.request.Request(
        url, method="GET", headers={"X-Tenant-Id": "globex", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, (
                f"{url}\nreturned {response.status} — the API accepts unsigned callers, so every "
                "layer above can be bypassed by calling it directly"
            )
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return error.code, f"{url}\nHTTP 404 — wrong path, so this proves nothing either way"
        return error.code, (
            f"{url}\nHTTP {error.code} — no principal, refused before the handler ran"
            + ("" if error.code == 403 else " (expected 403 from AWS_IAM authorization)")
        )
    except (urllib.error.URLError, TimeoutError) as error:
        # Only reachable in the private topology, where there is no public route at all. A different
        # fact from "refused", and the one `verify_network` is the right place to assert.
        return 0, f"{url}\nno route: {error} — private topology, so nothing to refuse publicly"


def report(layer: str, passed: bool, detail: str) -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {layer}")
    for line in detail.splitlines():
        if line:
            print(f"        {line}")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--password",
        help="shared demo password; read from Parameter Store when omitted",
    )
    args = parser.parse_args()

    results: list[bool] = []
    # Read rather than required, so the password does not have to travel through shell history — and
    # so a stale one cannot be passed after a re-seed and read as a broken deployment.
    globex = token_for("priya", args.password or refs.demo_password)

    print("\n1. Cognito — a token without tenant claims cannot be minted")
    # The pre-token-generation trigger raises for a user with no tenant attributes, so Cognito
    # itself refuses. That was verified directly with a throwaway user; asserted here by confirming
    # the claims are present on a *valid* token, which is the same mechanism seen from the front.
    claims = json.loads(
        __import__("base64").urlsafe_b64decode(globex.split(".")[1] + "==").decode()
    )
    results.append(
        report(
            "the access token carries custom:tenant_id",
            claims.get("custom:tenant_id") == "globex",
            f"tenant={claims.get('custom:tenant_id')} traveler={claims.get('custom:traveler_id')}\n"
            "The pre-token trigger refuses to issue a token at all for a user without these, so "
            "the fail-closed path fires before Cedar.",
        )
    )

    print("\n2. Cedar at the gateway — no verified tenant, no permit")
    garbage = call_tool("not-a-real-token", "policy___get_travel_policy", {"topic": "hotel"})
    denied = "error" in garbage or garbage.get("http_error") is not None
    results.append(
        report(
            "an unverifiable token is refused before the target runs",
            denied,
            f"response: {json.dumps(garbage)[:160]}",
        )
    )

    print("\n3. The interceptor — a caller cannot preset the tenant header")
    # Send a forged X-Tenant-Id alongside a *valid* Globex token. The interceptor strips inbound
    # copies and injects from verified claims, so the tool must still act for globex.
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "policy___get_travel_policy", "arguments": {"topic": "hotel"}},
        }
    ).encode()
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {globex}",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "X-Tenant-Id": "initech",  # the forgery
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    # $250 is Globex's cap; €150 would be Initech's.
    results.append(
        report(
            "a forged X-Tenant-Id is ignored — the answer is still Globex's",
            "250" in raw and "150" not in raw,
            "The interceptor strips inbound copies of the identity headers and injects from "
            "verified claims, so the header the tools trust is never caller-chosen.",
        )
    )

    print("\n4. The tool layer — there is no tenant field to forge")
    # **Assert the ARGUMENT schema, not the response.** An earlier version checked the tool's
    # response for the string `tenant_id` and failed — correctly, because a response *should*
    # carry it in `provenance`: that is how a reader confirms which tenant was served. What
    # matters is that no tenant field exists in any tool's **inputSchema**, since that is the only
    # surface the model can fill in.
    schemas = tool_schemas(globex)
    tenant_args = [
        f"{tool}.{arg}"
        for tool, properties in schemas.items()
        for arg in properties
        if "tenant" in arg.lower()
    ]
    results.append(
        report(
            "no tool accepts a tenant argument",
            not tenant_args and bool(schemas),
            f"inspected {len(schemas)} tool(s): "
            + ", ".join(f"{t}({', '.join(p) or 'no args'})" for t, p in schemas.items())
            + (f"\nFOUND: {tenant_args}" if tenant_args else "")
            + "\nIdentity travels in the Lambda client context, a channel the model cannot "
            "reach — stronger than merely omitting the field from a schema.",
        )
    )

    # **The headline says what this section proves, which is not always the same thing.** It used
    # to read "LeadingKeys refuses another tenant's partition" unconditionally, and then — in the
    # normal case, where an operator cannot assume the role at all — the arm underneath reported the
    # trust policy. A true statement about a different control, under a heading promising scoping.
    print("\n5. IAM row-scoping — the data role reaches one tenant's partitions and no other")
    sts = boto3.client("sts", region_name=REGION)
    try:
        # Assume the data role tagged for globex, then try to read an initech row.
        creds = sts.assume_role(
            RoleArn=DATA_ROLE_ARN,
            RoleSessionName="multi-tenant-travel-exit-probe",
            Tags=[{"Key": "tenant", "Value": "globex"}],
            TransitiveTagKeys=["tenant"],
        )["Credentials"]
        ddb = boto3.client(
            "dynamodb",
            region_name=REGION,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
        try:
            ddb.get_item(
                TableName="multi-tenant-travel-travelers",
                Key={
                    "pk": {"S": "TENANT#initech"},
                    "sk": {"S": f"TRAVELER#{INITECH_TRAVELER}"},
                },
            )
            results.append(report("cross-tenant read refused by IAM", False, "the read SUCCEEDED"))
        except ddb.exceptions.ClientError as error:
            code = error.response["Error"]["Code"]
            results.append(
                report(
                    "cross-tenant read refused by IAM",
                    code == "AccessDeniedException",
                    f"{code} — LeadingKeys is pinned to TENANT#${{aws:PrincipalTag/tenant}}, so "
                    "the refusal does not depend on our code being correct",
                )
            )
    except Exception as error:  # noqa: BLE001
        # A refused assume is itself a control — the trust policy admits only the backend's
        # execution role — but **`AccessDenied` is also what STS returns for a role that does not
        # exist**, deliberately, so as not to disclose existence. Without confirming the role is
        # there, a wrong or stale ARN would make this arm report a healthy control while proving
        # nothing about `LeadingKeys`. Two suites in this repo have already gone green that way.
        exists = data_role_exists()
        if exists is False:
            results.append(
                report(
                    "IAM row-scoping",
                    False,
                    f"{DATA_ROLE_ARN} does not exist, so nothing here was tested. The ARN comes "
                    "from the infrastructure stack's TenantDataRoleArn output — check the deploy.",
                )
            )
        else:
            unverified = "" if exists else " (could not confirm the role exists: no iam:GetRole)"
            results.append(
                report(
                    "the data role cannot be assumed from outside the backend" + unverified,
                    "AccessDenied" in str(error),
                    f"{str(error)[:180]}\nThe trust policy admits only the backend's execution "
                    "role — an operator cannot borrow tenant-scoped credentials.",
                )
            )

    # **The row-scoping claim itself, asserted against the deployed policy.** The arm above proves
    # the trust policy, which is a real control and a different one; without this, the section's own
    # heading was the only thing saying anything about `LeadingKeys`.
    found = leading_keys_condition()
    if found is None:
        print("     (skipped the policy check: no iam:GetRolePolicy for this caller)")
    else:
        operator, condition = found
        # **The operator is half the control, and this check used to assert the broken value.** It
        # pinned `TENANT#${aws:PrincipalTag/tenant}*` under `ForAllValues:StringLike` — a trailing
        # wildcard on a tag-derived prefix. `TenantId` permits `-` and `_`, so `globex` and
        # `globex-eu` are both valid ids and the first could read the second's partitions. A test
        # asserting the exact broken string is worse than no test: it makes the hole load-bearing.
        results.append(
            report(
                "the role's policy pins DynamoDB to the tenant in the session tag, exactly",
                operator == "ForAllValues:StringEquals"
                and condition == "TENANT#${aws:PrincipalTag/tenant}",
                f"{operator} dynamodb:LeadingKeys = {condition!r}\n"
                "`StringEquals` and no trailing wildcard, so a tenant whose id extends another's "
                "cannot reach it. Read from the deployed policy, so a refactor that drops or "
                "loosens the condition fails here.",
            )
        )
        # And the same property probed rather than read, since the value alone is easy to get wrong.
        own = simulate_leading_keys("globex", "TENANT#globex")
        collisions = {
            key: simulate_leading_keys("globex", key)
            for key in ("TENANT#globex-eu", "TENANT#globex_eu", "TENANT#globexeu")
        }
        if own is None:
            print("     (skipped the collision probe: no iam:SimulatePrincipalPolicy)")
        else:
            refused = [k for k, v in collisions.items() if v != "allowed"]
            results.append(
                report(
                    "a tenant cannot read a tenant whose id merely extends its own",
                    own == "allowed" and len(refused) == len(collisions),
                    f"globex -> TENANT#globex is {own}; "
                    + ", ".join(f"{k.split('#')[1]} is {v}" for k, v in collisions.items())
                    + "\nSimulated rather than probed live, because the trust policy refuses these "
                    "credentials outside the backend — which is why this boundary went untested "
                    "long enough for a wildcard to survive in it.",
                )
            )

    print("\n6. The backend — another tenant's traveller is a 404")
    status = backend_probe_status(f"/v1/travelers/{INITECH_TRAVELER}", tenant="globex")
    results.append(
        report(
            "a cross-tenant traveller is indistinguishable from a nonexistent one",
            status == 404,
            f"HTTP {status} — the 404 leaks nothing about whether the id is real elsewhere",
        )
    )

    print("\n7. Knowledge base — retrieval is filtered from verified context")
    kb = call_tool(
        globex,
        "knowledge___search_policy_knowledge",
        {"question": "what is the hotel nightly cap and are there city exceptions?"},
    )
    text = json.dumps(kb)
    results.append(
        report(
            "only this tenant's policy prose is retrieved",
            "initech" not in text.lower() and "error" not in kb,
            "The filter is built server-side from the verified tenant, never from a tool "
            "argument — a model-chosen filter would be no isolation at all.",
        )
    )

    print("\n8. The backend API — an unsigned caller never reaches the handler")
    status, detail = unsigned_backend_status()
    results.append(
        report(
            "the mock TMC refuses a request that carries no SigV4 signature",
            status == 403,
            detail,
        )
    )

    # Checks, not layers: there are eight sections, and section 5 contributes two results — one of
    # them a policy-document assertion rather than a refused probe. Counting results while calling
    # them layers is the same overstatement this suite exists to catch.
    print(f"\n{sum(results)}/{len(results)} checks passed across 8 independent layers")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
