"""Verify the private topology is private — and, more importantly, that it still works.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/verify_network.py

**Two failure modes, opposite in shape, and a check for each.** Going private can fail by not
actually being private (the interesting resources stay reachable and nothing complains), or by being
private and broken (a missing endpoint, whose symptom is a timeout rather than an error). The first
is silent forever; the second is silent until someone talks to the agent. So the checks come in
pairs: *is the door shut* and *does the intended path still open it*.

Checks:
  A. Zero NAT gateways in the VPC. The topology's cost and security argument both rest on this, and
     a NAT is exactly the kind of thing a later convenience fix adds.
  B. The private subnets have **no route to an internet or egress gateway**. Stronger than trusting
     the `PRIVATE_ISOLATED` label, because a route added by hand would not change the label.
  C. Every service the in-VPC code calls has an endpoint, checked against the **actual wire
     hostname** rather than the boto3 client name — `geo-places` resolves to `places.geo…`, and that
     mismatch is the single easiest way to deploy a VPC that half works.
  D. The backend API refuses a public caller. This is the claim the private topology exists to make.
  E. Interface endpoints carry a policy. An endpoint defaulting to `*` on `*` is a private route to
     an entire service, which discards most of what was paid for.
  F. **A real conversation still completes**, end to end, through the private path. Everything above
     could pass on a deployment where the agent cannot answer.

Check F is the one that matters most and it is deliberately last: A–E are cheap and diagnose *why*
F failed, so running them first turns one confusing failure into a specific one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import boto3
from deployed_refs import refs

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"


def _signed(url: str) -> urllib.request.Request:
    """A GET carrying SigV4 for `execute-api`, signed with this script's own credentials.

    The backend is `AWS_IAM`-authorized, so an unsigned probe is refused for the wrong reason — see
    `public_api_refused`. Developer credentials are the right signer here: the question is whether a
    *legitimate* caller is refused because of where the request came from.
    """
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    session = boto3.Session()
    signable = AWSRequest(method="GET", url=url, headers={"Accept": "application/json"})
    SigV4Auth(session.get_credentials(), "execute-api", REGION).add_auth(signable)
    return urllib.request.Request(url, method="GET", headers=dict(signable.headers))


VPC_NAME = "multi-tenant-travel-vpc"
BACKEND_API_NAME = "multi-tenant-travel-api"

# The wire hostname each in-VPC caller actually reaches, keyed by the endpoint service name that
# covers it. **Not the boto3 client name**, because for Amazon Location those differ in a way that
# silently breaks a VPC deployment: the client is `geo-places`, `client.meta.endpoint_url` claims
# `geo-places.us-east-1.amazonaws.com` (which does not resolve at all), and the request goes to
# `places.geo.us-east-1.amazonaws.com`. Anyone building this list from client names ships a VPC
# where the location tools time out.
REQUIRED_ENDPOINTS: dict[str, str] = {
    "geo.places": "location tool → geocoding and place search",
    "geo.routes": "location tool → route calculation",
    "bedrock-agent-runtime": "knowledge tool → knowledge base retrieval",
    "execute-api": "every tool → the backend API",
    "sts": "backend → per-request tenant-scoped credentials",
    "bedrock-runtime": "agent → model inference",
    "bedrock-agentcore": "agent → memory (data plane)",
    "bedrock-agentcore-control": "agent → memory (control plane)",
    "bedrock-agentcore.gateway": "agent → tools",
    "ssm": "agent → guardrail config and inference profile ARN",
}

# Endpoints allowed to carry no policy. **Empty, and it should stay that way.**
#
# It used to hold the three AgentCore endpoints, whose resources belong to the CLI's stack and so
# cannot be named at `infra/` synth time. That was a *sequencing* constraint, not an impossibility:
# `scripts/restrict_agentcore_endpoints.py` narrows them post-deploy, the same way
# `publish_agent_refs.py` carries the runtime ARN across the same boundary.
#
# Kept as an empty set rather than deleted, because the shape of the exemption matters: if a future
# endpoint genuinely cannot be scoped, the reason belongs here beside its name, where check E will
# print it. A silent exemption is how a control stops being noticed.
UNRESTRICTED_BY_DESIGN: set[str] = set()


def report(name: str, passed: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    for line in detail.splitlines():
        if line:
            print(f"        {line}")
    return passed


def find_vpc(ec2) -> dict | None:
    found = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": [VPC_NAME]}])["Vpcs"]
    return found[0] if found else None


def check_no_nat(ec2, vpc_id: str) -> bool:
    """A NAT gateway would undo both halves of the topology's argument at once."""
    nats = [
        n
        for n in ec2.describe_nat_gateways(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])[
            "NatGateways"
        ]
        if n["State"] not in ("deleted", "deleting")
    ]
    return report(
        "A. no NAT gateway",
        not nats,
        ""
        if not nats
        else f"found {len(nats)}: {', '.join(n['NatGatewayId'] for n in nats)}\n"
        "a NAT routes AWS calls over the internet and costs $0.045/hr + $0.045/GB",
    )


def check_no_egress_routes(ec2, vpc_id: str) -> bool:
    """No route to an internet or NAT gateway from any subnet in this VPC.

    Checked on the **route tables** rather than by trusting the subnet type: `PRIVATE_ISOLATED` is a
    CDK-side label, and a route added later by hand would leave it intact while making the subnet
    routable. The route table is where the truth lives.
    """
    tables = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])[
        "RouteTables"
    ]
    offenders = []
    for table in tables:
        for route in table.get("Routes", []):
            target = (
                route.get("GatewayId", "")
                or route.get("NatGatewayId", "")
                or route.get("TransitGatewayId", "")
            )
            # `local` is the VPC's own CIDR and always present. A `vpce-` gateway id is an S3 or
            # DynamoDB gateway endpoint, which is a route to AWS rather than to the internet.
            if target and not target.startswith(("local", "vpce-")):
                offenders.append(f"{table['RouteTableId']} → {target}")
    return report(
        "B. no route to an internet or NAT gateway",
        not offenders,
        "\n".join(offenders),
    )


def check_endpoints(ec2, vpc_id: str) -> tuple[bool, list[dict]]:
    """Every service the in-VPC code calls has an endpoint, and nothing extra is being paid for."""
    endpoints = ec2.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])[
        "VpcEndpoints"
    ]
    present = {e["ServiceName"].replace(f"com.amazonaws.{REGION}.", ""): e for e in endpoints}

    missing = [
        f"{service:28} needed by {why}"
        for service, why in REQUIRED_ENDPOINTS.items()
        if service not in present
    ]
    interface = [e for e in endpoints if e["VpcEndpointType"] == "Interface"]
    gateway = [e for e in endpoints if e["VpcEndpointType"] == "Gateway"]

    # Surplus is a cost finding rather than a correctness one, so it is reported but does not fail:
    # an endpoint someone added for a reason not yet in this list should prompt a conversation, not
    # a red build.
    surplus = [
        name
        for name, e in present.items()
        if e["VpcEndpointType"] == "Interface" and name not in REQUIRED_ENDPOINTS
    ]

    detail = (
        f"{len(interface)} interface + {len(gateway)} gateway endpoints\n"
        f"idle cost: {len(interface)} × 2 AZ × $0.01 × 730h = "
        f"${len(interface) * 2 * 0.01 * 730:.2f}/month"
    )
    if surplus:
        detail += f"\nnot in the required list (costing $14.60/mo each): {', '.join(surplus)}"
    if missing:
        detail += "\nMISSING:\n" + "\n".join(missing)

    return report("C. every called service has an endpoint", not missing, detail), interface


def check_backend_is_private(api_id: str) -> bool:
    """A public caller must be refused.

    A private REST API keeps its public hostname — only the resource policy and endpoint type change
    — so this URL still resolves. That is what makes the check meaningful: a `403` here is the
    policy working, not DNS failing. A `200` would mean the API is still open.

    **The request is signed, and it has to be now, or this check proves the wrong thing.** The API
    is `AWS_IAM`-authorized, so an *unsigned* call is refused with 403 in every topology — public or
    private, resource policy correct or broken. Left unsigned, this would pass on the strength of
    missing credentials and report the VPC boundary as working without testing it. Signed, a 403
    means a properly authenticated caller was refused for *where it came from*, which is what the
    private topology provides. The unsigned case is worth asserting too, in the default topology,
    so it lives in `verify_isolation.py` as layer 8.

    `/v1/health` and **not** `/v1/v1/health`: most routes here do carry the stage prefix twice
    (stage `v1` plus a router prefix `/v1`), but `health` is mounted on the app rather than on a
    router, so it has only one. Confirmed against the live API before relying on it — the wrong path
    returns 404, and a 404 is *not* a refusal, so this check would have silently proven nothing.
    """
    url = f"https://{api_id}.execute-api.{REGION}.amazonaws.com/v1/health"
    request = _signed(url)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return report(
                "D. backend API refuses a public caller",
                False,
                f"{url}\nreturned {response.status} — the API is still publicly reachable",
            )
    except urllib.error.HTTPError as error:
        # 403 is the private API refusing a caller that arrived from outside the VPC. A 404 is
        # called out separately because it is the failure mode of this *check* rather than of the
        # topology: a mistyped path proves nothing while looking like a pass.
        if error.code == 404:
            return report(
                "D. backend API refuses a public caller",
                False,
                f"{url}\nHTTP 404 — wrong path, so this proves nothing either way",
            )
        return report(
            "D. backend API refuses a public caller",
            error.code == 403,
            f"{url}\nHTTP {error.code}"
            + ("" if error.code == 403 else " — expected 403 from the resource policy"),
        )
    except (urllib.error.URLError, TimeoutError) as error:
        # No route at all also means not publicly reachable, but it is a *different* fact and worth
        # distinguishing: 403 proves the policy is doing the work.
        return report(
            "D. backend API refuses a public caller",
            True,
            f"{url}\nunreachable ({type(error).__name__}) — private, though via no route rather "
            "than an explicit refusal",
        )


def check_endpoint_policies(interface_endpoints: list[dict]) -> bool:
    """Interface endpoints should be narrowed to the calls that legitimately cross them."""
    open_endpoints, restricted, known_gaps = [], [], []
    for endpoint in interface_endpoints:
        service = endpoint["ServiceName"].replace(f"com.amazonaws.{REGION}.", "")
        policy = json.loads(endpoint.get("PolicyDocument") or "{}")
        statements = policy.get("Statement", [])
        # The default policy is a single `*` on `*`. Anything narrower than that is a real
        # restriction; the wildcard pair is the absence of one.
        wide_open = not statements or all(
            statement.get("Action") in ("*", ["*"]) and statement.get("Resource") in ("*", ["*"])
            for statement in statements
        )
        if not wide_open:
            restricted.append(service)
        elif service in UNRESTRICTED_BY_DESIGN:
            known_gaps.append(service)
        else:
            open_endpoints.append(service)

    detail = f"restricted: {', '.join(sorted(restricted)) or 'none'}"
    if known_gaps:
        detail += (
            "\nopen by design (ARNs live in the AgentCore CLI's stack): "
            f"{', '.join(sorted(known_gaps))}"
        )
    if open_endpoints:
        detail += f"\nOPEN with no reason recorded: {', '.join(sorted(open_endpoints))}"
    return report("E. interface endpoints are narrowed", not open_endpoints, detail)


def check_conversation_still_works(password: str | None) -> bool:
    """The check everything else exists to explain a failure of.

    A–E can all pass on a deployment where the agent cannot answer a question — a missing endpoint
    surfaces as a timeout deep in a tool, not as a networking error. Reuses the existing exit suite
    rather than reimplementing a turn, because a second implementation of "have a conversation" is a
    second thing to keep correct.
    """
    if not password:
        return report(
            "F. a real conversation still completes",
            False,
            "skipped: no demo password available — seed the pool or pass --password\n"
            "A–E all passing means nothing on its own — they cannot see a tool timing out",
        )

    sys.path.insert(0, "..")
    from scripts.verify_guardrails import invoke_agent, session_id, text_of, token_for

    try:
        token = token_for("priya", password)
        # A question that exercises the longest private path in one turn: the tool Lambda reaches
        # the backend through `execute-api`, the backend assumes its role through `sts` and reads
        # DynamoDB through the gateway endpoint, and the agent reached the tool through the Gateway
        # endpoint having read its config through `ssm`. Six endpoints, one question.
        # Argument order is `(token, prompt, session)` — **not** `(token, session, prompt)`.
        # Getting it backwards sends the prompt as the session id, which is shorter than the
        # service's 33-character minimum, so the runtime 400s before the agent ever runs. The
        # symptom is "the agent returned nothing", identical to a missing VPC endpoint — which is
        # exactly the false diagnosis this check exists to avoid.
        answer = text_of(
            invoke_agent(token, "What is my hotel nightly cap?", session_id("vpc-verify"))
        )
        ok = bool(answer and answer.strip())
        return report(
            "F. a real conversation still completes",
            ok,
            (answer or "")[:200] if ok else "the agent returned nothing",
        )
    except Exception as error:  # noqa: BLE001 — any failure here is the finding
        return report(
            "F. a real conversation still completes",
            False,
            f"{type(error).__name__}: {error}\n"
            "a timeout here usually means a missing endpoint: the hostname resolves, so the SDK "
            "waits for a route that does not exist",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--password",
        help="demo password for priya, to run check F (the end-to-end turn)",
    )
    args = parser.parse_args()

    ec2 = boto3.client("ec2", region_name=REGION)
    apigw = boto3.client("apigateway", region_name=REGION)

    print("\nPrivate network verification\n")

    vpc = find_vpc(ec2)
    if not vpc:
        print(
            f"  no VPC named {VPC_NAME!r} — the stack is deployed public.\n"
            "  Deploy with TRAVEL_PRIVATE=true to create it."
        )
        return 1
    print(f"  VPC {vpc['VpcId']} ({vpc['CidrBlock']})\n")

    results = [
        check_no_nat(ec2, vpc["VpcId"]),
        check_no_egress_routes(ec2, vpc["VpcId"]),
    ]
    endpoints_ok, interface_endpoints = check_endpoints(ec2, vpc["VpcId"])
    results.append(endpoints_ok)

    api = next((a for a in apigw.get_rest_apis()["items"] if a["name"] == BACKEND_API_NAME), None)
    if api:
        types = api.get("endpointConfiguration", {}).get("types", [])
        results.append(
            report(
                "D0. backend API endpoint type is PRIVATE",
                types == ["PRIVATE"],
                f"{api['id']}: {types}",
            )
        )
        results.append(check_backend_is_private(api["id"]))
    else:
        results.append(report("D. backend API", False, f"no API named {BACKEND_API_NAME!r}"))

    results.append(check_endpoint_policies(interface_endpoints))
    # Read rather than required, so a credential need not travel through shell history.
    results.append(check_conversation_still_works(args.password or refs.demo_password))

    passed = sum(1 for r in results if r)
    print(f"\n  {passed}/{len(results)} checks passed\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
