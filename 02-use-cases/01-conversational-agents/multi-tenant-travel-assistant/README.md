# Multi-tenant travel assistant on Amazon Bedrock AgentCore

## Overview

Two travellers ask the same agent the same question and get different, correct answers — because
they work for different companies. Nothing in the question says which company, and **nothing the
model can influence decides it.**

```
Priya (Globex)   "What's my hotel nightly cap?"   →  $250.00 USD, 4-star maximum
Sam (Initech)    "What's my hotel nightly cap?"   →  €150.00 per night, 3-star maximum
```

Same agent, same tool, same arguments. The difference comes from a verified JWT claim that is
injected server-side, after the model has finished choosing what to call.

This sample is about the part that is hard: **making tenant isolation a property of the
architecture rather than a promise about the prompt.** A travel assistant is the vehicle — a
domain where getting it wrong means showing one company's negotiated rates to another.

### Use case details

| Information         | Details                                                                                                                                                                                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use case type       | Conversational                                                                                                                                                                                                                                            |
| Agent type          | Single agent                                                                                                                                                                                                                                              |
| Use case components | 14 tools across 9 Lambda Gateway targets, RAG with a per-tenant knowledge base filter, short- and long-term memory, Cedar authorization, guardrails, streaming, observability with a per-turn cost ledger, evaluations behind a CI gate, human escalation |
| Use case vertical   | Travel & Hospitality (corporate / managed travel)                                                                                                                                                                                                         |
| Example complexity  | Advanced                                                                                                                                                                                                                                                  |
| SDK used            | Amazon Bedrock AgentCore SDK (native), Strands Agents, AWS CDK, boto3                                                                                                                                                                                     |

### AgentCore services used

| Service       | How this sample uses it                                                                                                                                                                                                                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime       | Strands agent, streaming responses, native JWT authorizer                                                                                                                                                                                                                                                     |
| Gateway       | 9 Lambda targets exposing 14 tools, with a request interceptor that injects verified tenant identity                                                                                                                                                                                                          |
| Identity      | Cognito with immutable custom claims and a pre-token-generation Lambda                                                                                                                                                                                                                                        |
| Policy        | Cedar policies in `ENFORCE` — a call carrying no verified tenant tag matches no permit                                                                                                                                                                                                                        |
| Memory        | Observed preferences in a tenant- and traveller-scoped namespace, distinct from the declared profile                                                                                                                                                                                                          |
| Observability | Traces plus a per-step token and spend ledger yielding cost per resolved task, attributed per tenant                                                                                                                                                                                                          |
| Evaluations   | 6 deterministic code-based evaluators behind an on-demand CI gate that reads cost _and_ quality together across 12 thresholds. 2 LLM-as-judge evaluators (`GroundedNarration`, `EscalationTiming`) are declared in `agentcore.json` and deployed, but score nothing yet and hold no gate row — see "Score it" |
| Guardrails    | PII anonymised at the model's output, as a backstop — the tool layer curates PII before it ever reaches the model                                                                                                                                                                                             |

## The thing worth reading the code for

A single sentence, and every layer below exists to make it true:

> **No tool schema in this sample has a `tenant_id` parameter.**

If the model cannot name a tenant, it cannot name the wrong one. Prompt injection has nothing to
attack, because there is no argument to poison. Tenancy is resolved from claims the model never
sees, by components the model cannot reach.

Eight layers each refuse a cross-tenant request **independently**, and
`scripts/verify_isolation.py` proves it by probing all eight — in this order, so you can read its
output against this table row for row:

| Layer                 | What it refuses                                                                                                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cognito claims        | A token for one tenant simply does not carry another's `custom:tenant_id`. Immutable attribute, so a traveller cannot edit their own tenancy. The Runtime's native JWT authorizer refuses a tampered one → 401, absent → 403                |
| Cedar at the Gateway  | Policy engine in `ENFORCE`; a call with no verified tenant tag matches no permit and is denied before the tool Lambda is invoked at all. Authorises _actions_ — the hotel caps live in tenant data, not in a rule                           |
| Gateway interceptor   | A forged `X-Tenant-Id` header is **overwritten**, not trusted. Delegation, not passthrough                                                                                                                                                  |
| Tool schemas          | No tenant field exists to supply. Identity arrives in the Lambda _client context_, unreachable from anything the model shapes                                                                                                               |
| IAM row-scoping       | `dynamodb:LeadingKeys` on a per-request role assumed with a tenant session tag. The read is impossible, not merely audited                                                                                                                  |
| The travel platform   | Another tenant's traveller is a **404** — indistinguishable from one that does not exist, so the response leaks nothing about whether the id is real elsewhere                                                                              |
| Knowledge base filter | Per-tenant metadata filter built server-side, so retrieval cannot cross tenants                                                                                                                                                             |
| The platform's API    | `AWS_IAM`-authorized, so an unsigned caller is **403 before the handler runs**. Every layer above sits between the agent and this platform rather than inside it, so while the API was open a direct call walked around all of them at once |

Two of those are worth a closer look because they are commonly done wrong. The interceptor
_overwrites_ client-supplied identity headers rather than validating them — validation invites a
bypass, overwriting has none. And IAM row-scoping was verified by **removing** the control and
watching the cross-tenant read succeed, which is the only way to know a control was doing anything.

## What the assistant actually does

A corporate travel assistant, in the sense a travel management company would recognise: search,
policy, booking, in-trip context, and a way out to a human. Nine Lambda families provide **14 tools**,
and every one of them resolves tenancy from claims rather than arguments.

| Family       | Tools                                                      | What a traveller experiences                                                                             |
| ------------ | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `policy`     | `get_travel_policy`, `check_policy_eligibility`            | "What's my hotel cap?" and "is business class to Tokyo within policy _for me_?" — a verdict with reasons |
| `search`     | `search_flights`, `search_hotels`                          | Priced options, each already marked in or out of policy, in the tenant's own currency                    |
| `booking`    | `prepare_booking`, `confirm_booking`, `cancel_reservation` | A two-step hold-then-confirm write path, and cancellation by the reference on the itinerary              |
| `trips`      | `get_trips`                                                | Upcoming and in-progress itineraries, which is also what makes "which hotel am I at?" answerable         |
| `profile`    | `get_traveler_profile`                                     | Seat and chain preferences, loyalty tiers — with passport and card digits curated away                   |
| `knowledge`  | `search_policy_knowledge`                                  | Free-text questions against the tenant's own policy document, with citations                             |
| `entry`      | `check_entry_requirements`                                 | Visa and passport-validity requirements for a destination, given this traveller's passports              |
| `location`   | `find_nearby`, `get_route`                                 | "Somewhere to eat near my hotel", and how long it takes to get there                                     |
| `escalation` | `escalate_to_human`                                        | A prepared handoff package — see the limitation on delivery below                                        |

Around those: **short-term memory** carries this conversation's context across turns with no tool
call — what makes "book the first one" resolvable three turns later. Separately, and on its own
schedule rather than the turn boundary, long-term extraction reads a finished conversation and writes
what it learned into a `USER_PREFERENCE` namespace scoped by `{tenant}/{traveler}` — see "What to
watch for" below for what that looks like and why it is not a same-turn recall. Responses render as
**13 typed cards** rather than prose blobs, and a card's buttons are the same closed action registry
the chat uses, so clicking and typing end at the same tool.

## The two tenants, and the three people

The demo is deliberately not "two copies of the same company with the labels swapped". Globex and
Initech differ on nine axes, and every difference is **data in the tenant's own row** rather than a
branch in the code:

|                    | Globex Corporation                                          | Initech                 |
| ------------------ | ----------------------------------------------------------- | ----------------------- |
| Currency           | USD                                                         | EUR                     |
| Hotel nightly cap  | $250                                                        | €150                    |
| Hotel star maximum | 4-star                                                      | 3-star                  |
| Cabin rule         | Business on every 4th international trip, per calendar year | Never — economy only    |
| Advance purchase   | none                                                        | 7 days before departure |
| Refundable fares   | allowed                                                     | not allowed             |
| Booking mode       | `CONFIRM_IN_CHAT`                                           | `HANDOFF`               |
| Home country       | US                                                          | IE                      |
| Support queue      | `globex-travel-desk`                                        | `initech-travel-desk`   |

`booking_mode` is the one that changes what the interface can do rather than what the answer says, and
it is the reason a Globex traveller gets confirm/decline buttons while an Initech traveller gets a
checkout link. The frontend never branches on tenant — it renders the actions the tool returned.

### Traveller and arranger

Two roles, and the distinction is about **whose record you may act on**, not about which tools exist.

- A **traveller** acts for themselves. Their authorised scope is exactly one person.
- An **arranger** — an executive assistant, a team coordinator — may act for a defined set of
  colleagues **within their own tenant**. Five tool families (`booking`, `search`, `trips`, `profile`,
  `entry`) accept an optional `traveler_name` for exactly this reason.

Note what the arranger role is _not_: it is not elevated access to the tenant, and it does not widen
the tenant boundary by a millimetre. An arranger of one tenant cannot see another tenant at all.

Delegation is authorised in two halves, and the split is the interesting part:

- **Cedar answers the static question** — may this _role_ name another traveller at all? That depends
  only on the claim and the action, which is what a policy engine is good at.
- **The resource owner answers the dynamic question** — may _this_ arranger act for _this_ traveller,
  right now? That has a current answer, so it is asked at the moment it matters
  (`GET /v1/arrangers/{id}/can-book/{target}`) rather than read from a claim that has gone stale.

`agent/MultiTenantTravel/policies/arranger.cedar` is worth opening: it contains **no rule about
`traveler_name`**, and the comment explains that two attempts to write one were rejected by the policy
analyser — the second because the argument is optional, so Cedar cannot prove the forbid would not deny
every call. That was a real signal rather than an obstacle, and it is why argument-shape validation
lives where the argument is read.

Three seeded users, each chosen to exercise something specific. `./deploy.sh --seed` prints the
generated password.

| User     | Tenant  | Role     | Seeded so that                                                                                                                                                                                                                                                |
| -------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `priya`  | Globex  | traveler | She has **4 international trips already counted for this year** — 3 taken, plus an upcoming one — so a further international booking is her 5th, one short of Globex's every-4th-trip rule. The refusal she gets is earned from that arithmetic, not asserted |
| `adaeze` | Globex  | arranger | She may book for Priya and three Globex colleagues, which is what exercises the delegation path                                                                                                                                                               |
| `sam`    | Initech | traveler | The isolation counterpart: the same questions return stricter answers, and his data must never appear under a Globex session                                                                                                                                  |

**The best single demo in the repo is available only as an arranger.** Sign in as `adaeze` and ask:

```
Book a flight to Berlin for Sam
```

Two of the Globex colleagues she can book for are **Sam Okonjo** and **Sam Adewale**, so the request is
genuinely ambiguous and the tool asks _which_ — it does not pick one, because ambiguity is a question
and never a coin flip. And Initech's **Sam Whitfield** matches the same string, is never offered as a
candidate, and is not named in the refusal. That is one question demonstrating three properties at
once: name resolution is scoped by **authorisation rather than by string match**, ambiguity is
surfaced instead of guessed, and the tenant boundary holds even inside a name lookup.

Ask for someone she is not set up to book for and the refusal is deliberately identical to the one for
a person who does not exist — distinguishing them would confirm to an unauthorised caller that a
traveller is real.

## Architecture

![Architecture, in seven layers. Channels in: a React SPA and a CLI client. Edge: an opt-in AWS WAF, CloudFront serving the SPA bundle and the API from one origin, a private S3 bucket. Session: API Gateway streaming into the conversation API, whose session rows live in DynamoDB with the OAuth tokens sealed by KMS, and Cognito carrying tenant and traveller claims. Agent: the AgentCore Runtime running a Strands agent, with a Bedrock guardrail on the model call, AgentCore Memory keyed on tenant and traveller, and Claude Sonnet 4.5 invoked through an application inference profile that carries the cost tags. Capability: the AgentCore Gateway with its own JWT authorizer, then a request interceptor that verifies the JWT and injects the tenant, then a Cedar policy engine in ENFORCE, then nine tool Lambda families providing fourteen tools. Data and knowledge: a knowledge base on S3 Vectors with a tenant filter, Amazon Location, and the mock travel platform reached over SigV4-signed HTTPS, which assumes a tenant-scoped IAM role per request whose LeadingKeys condition pins DynamoDB to that tenant. Cross-cutting: CloudTrail, CloudWatch Logs with PII masking and EMF metrics, Parameter Store, and opt-in VPC interface endpoints. Handoff out is drawn dashed because it is not deployed: escalate_to_human assembles the context package and logs it, and the transport to Connect, Genesys, ServiceNow or a queue is the extension point.](docs/architecture-layered.png)

**Only `agent/` is containerised.** Tools are separate Lambdas reached over MCP, so a tool fix is a
Lambda deploy and an agent fix is an image rebuild — different blast radius, deliberately.

**`backend/` is the folder you delete.** It stands in for the travel platform a travel management
company already runs. Nothing in `agent/`, `tools/` or `frontend/` imports from it; the tool Lambdas
call it over HTTP exactly as they would call yours.

## Repository layout

| Path                                | What it is                                                                                                                                                     |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent/MultiTenantTravel/`          | The Strands agent, its prompts, memory wiring and ledger. `agentcore.json` is the schema-first source of truth; the CLI generates its own CDK app from it      |
| `agent/MultiTenantTravel/policies/` | Cedar rules, one file per concern, with the reasoning inline                                                                                                   |
| `tools/`                            | Nine tool families → nine Lambdas → 14 tools. `tools/common/` holds the identity and authorisation helpers every family shares                                 |
| `shared/`                           | Contracts that cross the Python↔TypeScript boundary. `cards.py` is authoritative; `generated/cards.ts` is codegen and never hand-edited                        |
| `backend/`                          | The mock TMC. Pydantic models, deterministic option generation, seed fixtures for two tenants                                                                  |
| `conversation-api/`                 | The BFF: cookie sessions, streaming relay, the closed action registry, citation presigning                                                                     |
| `frontend/`                         | React SPA. One component per `card_type`, with an exhaustive switch — deleting a case is a compile error                                                       |
| `infra/`                            | Everything the AgentCore CLI does not own: DynamoDB, Cognito, both API Gateways, the interceptor, the knowledge base, CloudTrail, and the optional VPC and WAF |
| `scripts/`                          | Deploy wiring and seven verification suites                                                                                                                    |

## Prerequisites

|               |                                                                            |
| ------------- | -------------------------------------------------------------------------- |
| Node.js       | 20+ (`npm` included)                                                       |
| Python        | 3.13+, via [`uv`](https://docs.astral.sh/uv/getting-started/installation/) |
| Docker        | installed **and running** — CDK bundles the Python Lambdas in a container  |
| AWS CLI       | configured with credentials for the target account                         |
| AgentCore CLI | `npm install -g @aws/agentcore` — **pin `0.24.0`**, see the note below     |
| CDK bootstrap | once per account and region: `cd infra && npx cdk bootstrap`               |

`./deploy.sh` checks all of these before it touches AWS, because each one otherwise fails late and
confusingly. A missing `uv` in particular surfaces as
`uv install failed on platform aarch64-manylinux2014`, which reads like a platform problem. An
unbootstrapped account is the worst of them: CDK bundles all eleven Python Lambdas in Docker first,
warns eight times that it "could not be used to assume" a role that does not exist yet — which reads
like a permissions problem and is not — and only then stops on a missing
`/cdk-bootstrap/hnb659fds/version` parameter. Seven minutes, measured, to reach a one-line
prerequisite. The preflight now checks for it and prints the command.

Bootstrapping is left to you rather than done for you: it creates a staging bucket, an ECR repository
and five roles that are shared with every other CDK app in the account, so `cleanup.sh` does not
remove them.

**Bedrock model access.** The agent invokes
`global.anthropic.claude-sonnet-4-5-20250929-v1:0`. Access to foundation models is enabled by
default now — the console's old "Model access" page is retired — so there is usually nothing to do.
Two things still deny it, and both are worth checking before blaming the deploy: the calling
identity needs the AWS Marketplace permissions that let it subscribe on first use, and in an
organisation-managed account an SCP may block `bedrock:PutFoundationModelEntitlement`. Either
surfaces as `AccessDenied` or _"Operation not allowed"_ on the first turn rather than at deploy
time.

Confirm in one call before deploying:

```bash
aws bedrock-runtime converse --region us-east-1 \
  --model-id global.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --messages '[{"role":"user","content":[{"text":"hi"}]}]' \
  --inference-config maxTokens=5
```

**Two version pins that matter.** `aws-cdk-lib` is pinned to `2.260.0` because it must match the
cloud-assembly schema the AgentCore CLI's _embedded_ toolkit supports — the CLI never uses your
local `cdk` binary, so a mismatch produces an error telling you to upgrade a CLI that is already
current. Skip AgentCore CLI `0.25.0`; its npm dependency resolver crashes. If a global install
fails, `npm uninstall -g @aws/agentcore` first.

## Deploy

```bash
git clone https://github.com/awslabs/agentcore-samples.git
cd agentcore-samples/02-use-cases/01-conversational-agents/multi-tenant-travel-assistant

./deploy.sh --seed          # first deploy: also loads fixtures and creates the demo users
```

That is the whole thing. It sequences derived files → CDK → seed → agent → three wiring steps →
frontend, and prints the site URL at the end.

```bash
./deploy.sh                 # subsequent deploys
./deploy.sh --private       # capability and data layers inside a VPC (see Cost)
./deploy.sh --waf           # WAF web ACL at the edge (see Cost; recommended if you share the URL)
./deploy.sh --skip-agent    # infrastructure only
```

**`--private` and `--waf` are not sticky — pass them on every deploy that should keep them.** They are
synth-time context, not stored state, so a bare `./deploy.sh` against a private deployment synthesises
the public topology and CloudFormation dutifully removes the VPC endpoints; the same bare deploy deletes
a web ACL created with `--waf`. Nothing errors, because from CDK's point of view you asked for this.
Either keep the flags in a shell alias, or set them in the environment once — `TRAVEL_PRIVATE=true` and
`TRAVEL_WAF=true` are read the same way and survive across commands.

**`us-east-1` only, and the synth refuses anything else.** Another region does not merely go
unsupported, it fails badly: the Lambda Web Adapter layer ARN is regional and pinned, and a
mismatched layer surfaces as a Lambda _init timeout_ rather than an architecture error — twenty
minutes of CloudFormation and then a message naming nothing. Refusing at synth, with both reasons in
the error, is cheaper than letting you find that out. (With `--waf` there is a second pin: a
`CLOUDFRONT`-scoped web ACL can only exist in `us-east-1`, which is an AWS constraint rather than a
choice here.)

`TRAVEL_REGION` still exists and is read **instead of** `AWS_REGION` — a shell carrying a region for
unrelated work would otherwise build a second parallel stack in it, with no error anywhere.

### Going private later is an upgrade, not a redeploy

Deploying public first and adding `--private` afterwards is the intended path, and it is in place:
the backend's REST API changes endpoint type rather than being replaced, so its API id survives and
no tool's `BACKEND_API_URL` moves. Cognito, DynamoDB and the SPA are untouched. The runtime joins the
VPC, which is one more `agentcore deploy` and a version bump.

Two things will otherwise look like failures:

- **Do not pass `--seed` again.** `seed.users` cannot re-run against an existing pool, because
  `custom:tenant_id` is immutable by design — a traveller must not be able to edit their own tenancy.
- **The first invoke or two may return `AccessDenied`, then succeed with no further change.** IAM
  needs up to a minute to propagate the new endpoint policies. This reads exactly like a fix that did
  not work; wait before changing anything.

One real consequence: the per-tool `test_local.py` scripts stop working from a laptop, because there
is no longer a route to the backend. That is the migration succeeding. Use `verify_network.py`, which
checks the topology and the endpoint policies, and the other suites, which go through the gateway.

### The first deploy runs the agent step twice, on purpose

Two values are derived from the Gateway's own id, and that id does not exist until the Gateway does:
the Cedar `resource` ARN, and the runtime's `GATEWAY_MCP_URL`. AgentCore requires a _specific_
gateway ARN in any rule that names specific actions, so there is no way to write the policy ahead of
time.

So the first pass deploys a policy naming a gateway that is not there yet — which **denies every
tool call**, the correct direction to fail — and the second pass replaces both values with the live
ones and redeploys. `deploy.sh` does this for you and stops loudly if the placeholder survives.
Steady-state deploys are a single pass.

### Nothing in this repo names an account

Every account-specific value is read back from the deployment that owns it, not committed:

- `scripts/render_agent_spec.py` fills `agentcore.json` (tool Lambda ARNs, Cognito discovery URL,
  client ids, VPC ids) from the CDK stack's own outputs and the `/multi-tenant-travel/*` parameters
  it publishes
- `scripts/sync_policies.py` substitutes the live Gateway ARN into the Cedar rules
- the runtime's IAM policy documents ship unrendered, in either of the two forms
  `render_agent_spec.py` recognises — `{{ACCOUNT}}`/`{{REGION}}`, or a literal `000000000000` and
  region. It fills both in place, and it is idempotent, so it also corrects a document left pointing at
  a previous account

This is not tidiness. A spec naming another account's Lambda ARNs **deploys perfectly**: the stack
succeeds, the Gateway reports `READY`, its targets report `READY`, and every tool call then fails at
invoke time. A cross-account reference is a runtime error, not a deploy-time one, which is exactly
the kind of failure a sample must not hand a reader.

## Try it

Sign in as `priya`, `adaeze` or `sam` — see [the two tenants and the three
people](#the-two-tenants-and-the-three-people) for who they are and why each exists.
`./deploy.sh --seed` prints the generated password.

### Sample prompts

**Start here, then repeat it as the other tenant.** It is the whole thesis in one question:

```
What's my hotel nightly cap?
```

Then the rest of the surface:

```
Find me a flight to Berlin next Tuesday
What does my company's policy say about conference travel?
Is a business-class fare to Tokyo within policy for me?
What are the entry requirements for Japan?
Find somewhere to eat near my hotel
I'm vegetarian, and I always want a late checkout
Show me my upcoming trips
I'd rather talk to a person about this
```

The dietary and checkout line is the start of a two-part demo, not a one-liner — see "What to watch
for" below for the second half and why it needs a wait rather than a second message.

And as `adaeze`, the delegation path — `Book a flight to Berlin for Sam` is the ambiguous one worth
watching, for the reasons above.

### What to watch for, rather than just read

**Ask both tenants the same eligibility question and read the _reason_, not the verdict.** Priya gets
`cabin_entitlement_not_yet_earned` with the every-fourth-trip arithmetic worked against her 4
international trips already counted this year (3 taken, one upcoming); Sam gets a flat
`cabin_above_policy`, because Initech has no entitlement to earn. Two different refusals from one
code path, both derived from tenant data.

Then watch the capability difference bite: `confirm_booking` **refuses Initech at the tool**, not by
hiding a button in the UI. The absent buttons are a consequence, not the control.

**Complete a booking both ways, because the write path takes either.** Plain language works — "book
the first one", then "yes, confirm it" — and it is the normal path. The buttons on a card do the same
thing. Both end at `prepare_booking` then `confirm_booking`, and the tool does not know or care which
one you used.

Worth doing the clicking version anyway, because it shows a boundary that prose cannot. A click sends
`{action_id, payload}` and **never text**: the server looks the action up in a closed registry
(`conversation-api/app/actions.py`) and composes the phrase the agent receives. So a click cannot
smuggle instructions, and the offer handle is relayed by the server from the card rather than retyped
by the model.

That distinction is not theoretical. Confirming in prose is the path where the model **claimed a
booking it had not made** — "your flight is confirmed, charged to your Visa", with no tool call, in 4
of 6 measured runs — and where it invented handles like `book_7a1d3e9f2b4c6a8e` when the real one was
`off_294eae67b1`. Four attempts to fix that by strengthening the prompt moved the number around and
one made it worse. What fixed it was checking the artefacts: `unclaimed.py` buffers prose that claims
a completed action and replaces it if no booking tool ran (0 in 6 after), and `_OFFER_REF` in
`tools/booking/handler.py` refuses a handle the server never issued — with a message saying the
handle was invented rather than the backend's misleading "no such offer", which the agent had been
relaying as "your hold expired" about a hold seconds old.

Either way the server re-derives ownership, expiry and price before anything is booked, so a stale
click and an over-confident sentence both fail closed.

**Open the console and try to find the credential.** With the app signed in, `sessionStorage` and
`document.cookie` both come back empty. `localStorage` is not empty — it holds one key,
`travel-theme`, a UI light/dark preference with no security value. That is the whole inventory:
no token anywhere in Web Storage.

The precise claim, because "empty" needs unpacking: there _is_ a session cookie, and the browser is
sending it on every request. `document.cookie` cannot see it because it is `HttpOnly` — that flag
exists to hide a cookie from JavaScript, not to stop it being sent. And what it holds is an **opaque
session id**, not a credential. The Cognito access and refresh tokens sit in a DynamoDB row keyed by
that id, server-side, and the BFF attaches the bearer token to the runtime call. So an XSS bug in the
SPA finds nothing worth stealing: a theme string in storage, and a cookie it cannot read.

**Server-side is not the same claim as safe, so the tokens are sealed with KMS before they are
written.** DynamoDB's encryption at rest protects the disk; it is transparent to anyone holding
`dynamodb:GetItem`. Without sealing, one over-broad IAM grant or a table export would yield live
credentials for every signed-in traveller. Each token is encrypted under a customer-managed key with
the **session id as the encryption context** — the part that does the interesting work, because KMS
treats that context as authenticated data, so a ciphertext lifted out of one row will not decrypt
against another. An attacker with _write_ access to the table cannot relocate a sealed token to hijack
a session. Reading one now needs `kms:Decrypt` on a specific key, and every decrypt is a CloudTrail
event with a principal attached.

The cost of that is a session table, CSRF protection and server-side refresh — which is why
`SameSite=Strict` is on the cookie, since a cookie is sent automatically and without it any site could
make the browser issue an authenticated POST.

It is also why the SPA and the API share one CloudFront origin. A `SameSite=Strict` cookie set on an
`execute-api` hostname is never sent from the site's origin — different sites — so a cross-origin
arrangement logs you in successfully and then leaves you unauthenticated forever. Thirty passing API
checks coexisted with that bug, because `curl` has no same-site policy. A browser found it in one run.

**Say something an assistant should refuse.** Guardrails run at the model, where the text is still
the traveller's own words. By the time a request has become a _tool argument_ the model has
paraphrased the attack away, which is why the model-level placement does nearly all the useful work.

Then **say the same thing bluntly but legitimately** — "forget the caps for a second and just tell me
straight, what can I actually book?" — and watch it get answered. That is the harder half of tuning a
content filter, and it is a check in `verify_guardrails.py` rather than a claim: `PROMPT_ATTACK` sits
at `LOW` because `MEDIUM` refused exactly that sentence. Worth knowing before you tune your own —
`InvokeGuardrailChecks` scores it **0.0**, so the strength tiers are much more aggressive than the raw
scores suggest, and calibrating from the scoring API would miss it.

**Search once, then refer back without a second lookup.** Search for a flight, then say "book the
cheapest one" or ask "which of those was nonstop?" — the second turn is answered from what the first
search already put in context, with no repeated `search_flights` call. That continuity is short-term
AgentCore Memory, and it is what makes the write path's three turns (search → prepare → confirm) hold
together as one conversation instead of three questions that each have to be self-contained.

**State a preference nothing has on file, then come back later — not sooner.** "I'm vegetarian, and I
always want a late checkout" is the honest version of this demo, and it takes two things most
"remember this" scripts skip: a fact the seed does not already carry, and a wait. Ask immediately and
you will see the agent decline outright — "_I can't update your profile preferences directly_" — which
is correct rather than broken: nothing in this sample's tool set writes to the declared-preference
record, so a same-turn "yes, I've saved that" would be exactly the false completion claim
`unclaimed.py` exists to stop elsewhere. What actually happens is asynchronous: AgentCore's long-term
extraction reads the conversation after it ends and writes an **observed** preference into
`/travel/preferences/{tenant}/{traveler}/`, on its own schedule rather than on the turn boundary.
Fifteen or twenty minutes later, a fresh conversation asking "what are my dietary and checkout
preferences?" gets both back — retrieved, not recalled, and the two words are not interchangeable
here: recall would mean the model remembering what you said, and this is the model reading a record a
different system wrote after the fact.

**Do not test this with "remember I prefer an aisle seat", and here is why that specific sentence is
the wrong demo rather than a smaller version of the right one.** Every seeded traveller already has a
seat preference on their declared profile, so asking `get_traveler_profile` afterwards reports "you
prefer an aisle seat" whether extraction ran, failed, or was never invoked — the check cannot tell a
working feature from a no-op. A convincing demo needs a fact that is not already sitting somewhere
else answering the question for the wrong reason.

## Verify it

Eight suites, each of which needs a deployment. The demo password is read from Parameter Store,
where `seed.users` stored it, so none of them takes a credential on the command line:

```bash
cd backend
uv run python ../scripts/verify_isolation.py          # 8 isolation layers
uv run python ../scripts/verify_tools.py              # all 14 tools via the Gateway
uv run python ../scripts/verify_conversation_api.py   # streaming, CSRF, a booking by clicking
uv run python ../scripts/verify_audit.py              # CloudTrail attribution
uv run python ../scripts/verify_guardrails.py    # a filter fires, and does not fire on a blunt user
uv run python ../scripts/verify_log_masking.py         # PII masked at log ingestion
uv run python ../scripts/verify_network.py            # only with --private
uv run python ../scripts/verify_booking_integrity.py  # a hold cannot be booked twice
```

Everything that needs no AWS account at all runs in seconds:

```bash
./test.sh     # 199 backend, 127 agent, 86 evaluation, 39 BFF, 31 frontend, 30 tool, 23 interceptor
```

The interceptor suite is the one to read: it covers forged, tampered, `alg:none`, expired and
spoofed-header tokens without touching AWS.

## Score it

The suites above answer "is the deployment wired correctly?". They cannot answer "is the agent still
behaving?", and the difference is not academic: every one of them passed while the knowledge base was
empty and memory was answering policy questions from a stale copy, because both produced _correct_
answers. What caught those was a fixture asserting which tool a turn must call.

```bash
./run-evals.sh                       # the whole set against the deployment
./run-evals.sh --dry-run             # what would run, and the estimated spend
./run-evals.sh --suite A --sample 2  # a subset, which never returns a merge verdict
./run-evals.sh --json run.json       # the full run record, per task
```

Fifty-seven turns across seven suites — policy answers, eligibility verdicts, search and booking,
context and location, escalation, adversarial prompts, and drift. The last of those is the one worth
reading, because non-determinism is normally what makes agent tests flaky: each drift task arms a
seeded condition in the mock backend first — a fare that rises between the hold and the confirmation,
a hold already expired, an emptied inventory, a stalled upstream, a policy cap that drops — so the
condition fires on every run instead of by luck. Conditions are armed per conversation and expire on
their own, so a run cannot leave the deployment stuck in a simulated failure.

The gate reads twelve rows and exits non-zero on any of them, so it can fail a commit.

**All six evaluators behind those quality rows are deterministic code — no model sits in the judging
loop.** So a gate run costs only the turns themselves, it returns the same verdict twice, and a failure
names a condition rather than an opinion.

**Two LLM judges are written and deployed, and they are the honest half-finished part of this.**
`agentcore.json` declares `GroundedNarration` (per trace) and `EscalationTiming` (per session), both
`llmAsAJudge` on Claude Haiku 4.5, and both are created in AWS on every deploy — the grounding one asks
exactly the question a judge is better at than code: did the prose assert only what the tools returned?
What is missing is narrow and named in `evaluation/gate.yaml`: `Evaluate` takes session spans as an
inline document, and **nothing here emits spans in OTel format**, so neither judge scores yet. They hold
no gate row, because a threshold with nothing computing it must not pass. Read them as a worked example
of the declaration and a to-do on the wiring, not as a working judge.

**A row with nothing measuring it does not pass.** Unmeasured is failure, not silence — which is why
a `--suite`/`--sample` subset returns no merge verdict at all, and why `evaluation/tests/test_gate.py`
rejects a threshold added with no evaluator behind it. A gate that goes green on a run that measured
nothing is the failure mode worth engineering against.

The last full run:

|                        |                                        |
| ---------------------- | -------------------------------------- |
| Resolved               | 57 of 57                               |
| Cost per resolved task | **$0.0203** against a ceiling of $0.30 |
| Steps                  | p50 2, p95 4, against a ceiling of 10  |
| Cache hit rate         | 0.79 against a floor of 0.70           |
| Spend for the full set | ~$1.16                                 |

Four of those rows are thresholds on _money_, which is the half of agent evaluation that usually goes
unmeasured. A trajectory is priced from the token counts on its own stream, cache reads and writes
included — measured to be additive to `inputTokens` for Anthropic on Bedrock, which is the opposite of
the convention AWS documents for OpenAI models on the same service, and asserted in a test so an SDK
change cannot silently flip it.

One task is reported as skipped rather than passed, with the reason, because a suite that quietly
drops what it cannot run shows a clean sheet for exactly the behaviour nobody has exercised.

## Cost

Almost everything is pay-per-request, so an idle deployment costs about a dollar a month.

|                         |                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Default (`./deploy.sh`) | **~$1/month** standing — one customer-managed KMS key. Everything else is pay-per-request                                  |
| With `--waf`            | **+~$10/month** standing — the WAF web ACL and its five rules                                                              |
| With `--private`        | **+~$161/month** standing — 11 interface VPC endpoints × 2 AZs at `$0.01`/endpoint-hour (`$160.60`)                        |
| Per conversation        | Model tokens dominate. Prompt caching is on, with the breakpoint placed so per-traveller context costs only its own tokens |

The AZ multiplier is the part that surprises people: `$0.01/hour` reads as free, but the same
endpoint across two AZs for a month is `2 × 0.01 × 730 = $14.60` — **per service.**

**The default row said `~$0` until someone checked the invoice.** It is a customer-managed KMS key —
`SessionKey` in `infra/lib/conversation-api.ts`, which seals the OAuth tokens in the session table so
that `dynamodb:GetItem` alone is not enough to read a traveller's credentials. KMS bills $1 per key per
month whether or not anything decrypts, and rotation is on, which adds a prorated charge for the first
two rotations — so about $1 now and up to $3 after two years. Decrypt requests are free at any volume
this demo reaches (20,000/month). A dollar is the right trade for that property, and the point of the
row is that a reader should be able to read the number rather than discover it.

That figure is list price rather than a measurement, and the reason is itself worth knowing: the
`KMS-Keys` line does **not** carry the `project` tag in Cost Explorer, so filtering the sample's own
tag returns `$0` for KMS. Key storage is billed per key rather than per request, and per-key storage is
one of the line items AWS does not tag-allocate. Tag-filtered cost views are a floor, not a total.

Both costed switches are **opt-in for exactly this reason**: a reader cloning a repo should not learn
about a standing charge from an invoice. `--waf` is **recommended before you share the demo URL
broadly**, since it adds edge rate limiting and AWS's managed rule sets. What is _not_ lost by leaving
it off is any isolation property — the web ACL was never the tenancy boundary, and API Gateway stage
throttling stays on regardless as the free abuse ceiling. The thing worth bounding is model spend
rather than request volume: every turn that reaches the agent costs tokens.

**`--waf` protects the CloudFront origin, and the API's own hostname stays reachable.** Worth stating
because it is the kind of gap that reads as covered: the web ACL is `CLOUDFRONT`-scoped, so it inspects
traffic arriving at the distribution — which is the SPA _and_ the API, since they share one origin. It
does **not** attach to the conversation API's `execute-api` hostname, and that hostname is public and
published to Parameter Store for the SPA build to read. So a caller who addresses the API directly skips
the managed rule sets and the edge rate limit.

Three reasons that is documented rather than closed. The direct path still needs a valid session cookie
and refuses cross-origin POSTs. **API Gateway stage throttling — 20 req/s, burst 40 — is on the stage
itself**, so it applies to direct callers too, and that is the control that bounds model spend, which is
the expensive axis here. And closing it properly means a _second_, regional web ACL: another ~$10/month
on a flag that exists precisely so a reader is not surprised by a standing charge. Attaching one is the
right move for a deployment serving real traffic, and `infra/lib/edge-protection.ts` is where it would
go.

**`--private` is the expensive switch, and what it buys is a real property** — no NAT, so Bedrock and
DynamoDB traffic never touches the internet. The alternatives were priced before anything was built
and rejected on the record: a single NAT gateway is cheaper at `$36.50/month`, and it would have
routed Bedrock and DynamoDB over the internet, falsifying the only claim the private topology exists
to make.

**Model spend is attributable.** The agent invokes an application inference profile rather than a
raw model id, so Bedrock usage carries a `component=agent` tag instead of collapsing into one
untagged line item.

**Tagging alone does not make the tags usable, though**, which is worth knowing before you go looking
for them in Cost Explorer. A tag key becomes a billing dimension only once it is activated under
Billing → Cost allocation tags, and AWS will not let you activate a key until it has appeared in
billing data — up to 24 hours after the first deploy. Activation is also **not retroactive**, so spend
before then is permanently unattributable. `deploy.sh` prints the reminder rather than doing it,
because it changes account-level billing settings that `cleanup.sh` cannot put back:

```bash
cd backend && uv run python ../scripts/activate_cost_tags.py   # optional, idempotent, run ~24h later
```

If you deploy with `--private`, tear it down between sessions.

## Clean up

```bash
./cleanup.sh
```

Agent first, and that order is load-bearing rather than tidy. The Runtime's JWT authorizer points at
the Cognito pool `infra/` owns, and deleting a Runtime makes CloudFormation validate that authorizer by
fetching the pool's OpenID discovery document. Destroy `infra/` first and that fetch fails, the stack
stops in `DELETE_FAILED`, and CloudFormation has no way to finish — recovery is a direct
`DeleteAgentRuntime` call, which the service accepts because it does not run the same validation. So a
failed agent teardown stops the script instead of continuing. Its Gateway targets also point at the
tool Lambdas, which is the second reason.

Then the frontend bucket, then `infra/`, then anything left under `/multi-tenant-travel/` in Parameter
Store, then the log groups. Both of those last two sweep by prefix rather than by name: they run after
the stacks are gone, so whatever still matches is by definition unowned. Log groups matter here because
the Runtime's group holds traveller prompts and survives its stack. Both stacks are
`RemovalPolicy.DESTROY`.

A customer-managed KMS key is the one thing teardown cannot finish. Deleting it starts a mandatory
7-30 day window that AWS will not let you shorten, and the key bills until it closes.

It will tell you what it is about to delete — including conversation history and the audit bucket —
and wait.

## Honest limitations

Things this sample does _not_ do, and why, because a sample that only lists its wins teaches less:

- **Row-level audit is an IAM guarantee, not a CloudTrail one.** DynamoDB item-level events are
  unsupported **on a trail** in either selector shape — the basic one returns
  `UnsupportedOperationException: The operation requested is not supported in the region`, the advanced
  one `The AWS::DynamoDB::Table data resource type is not supported`. Worth being exact, because the
  DynamoDB documentation lists `GetItem`, `Query` and `PutItem` as loggable data events and reading
  that alone suggests this entry is wrong: the capability exists, it just needs a CloudTrail Lake
  **event data store** rather than a trail, which is a separate resource with per-event ingestion
  pricing. Not added here, because a sample should not quietly commit a reader to that. So the trail
  proves which tenant, which conversation, and on whose behalf credentials were obtained, and the
  row-level guarantee is the `LeadingKeys` boundary making the read impossible rather than detecting
  it afterwards.
- **The step budget cannot be tripped from a prompt, so exercising it takes an operator.** Measured,
  not assumed: a fully specified eight-leg itinerary produced **15 tool calls in 2 steps**, because
  the model batches parallel calls into one step. So `max_steps` counts model invocations rather than
  work — it guards against _looping_, which is the one thing a traveller cannot ask for, and breadth
  is bounded by the USD cap instead. The break-out itself **is** verified end to end: with the cap
  lowered to 1, a turn stops at one step with `outcome=escalated_budget`, an escalation card, and a
  reason assembled from the ledger. Doing that needs a cap no deployment would run plus a container
  restart, so the eval suite reports that task as skipped rather than passing it.
- **The handoff to a human is prepared, not delivered.** `escalate_to_human` assembles the context
  package — reason, itinerary, what was already tried — and logs it. There is no ticket, no queue and
  no pager: delivery is one call at a marked extension point in `tools/escalation/handler.py`, left
  out because every organisation's destination is different. The card says so too, reading "Handoff
  package prepared" with a `warn` badge rather than announcing a transfer, and `status` is a value
  (`prepared`) rather than a label baked into the frontend — so wiring a real transport is two edits
  that stay in step.
- **Eval runs mutate the agent they measure.** A run writes conversation events, and long-term
  extraction turns some of them into stored preferences, so the agent's memory is not identical
  before and after. Extraction is constrained to exclude anything a tool owns — tenant policy,
  itineraries — which removes the failure that mattered, where a stored copy of a cap let the agent
  answer without calling `get_travel_policy`. A run is still not perfectly idempotent.
- **The mock travel platform still trusts `X-Tenant-Id` — `AWS_IAM` only controls who may send one.**
  Worth being exact, because it is the easiest thing here to overclaim: signing does not make the
  header trustworthy, it makes the _caller_ trustworthy. **The interceptor decides which tenant; IAM
  decides who may assert one.** A component inside this boundary that set the header from something
  a traveller supplied would defeat the whole chain, and no signature would notice.

## Further reading

The reasoning lives next to the code rather than in a documentation folder, deliberately: a comment
explaining why a control exists survives a refactor of that control, and a separate document does
not. Each of these explains a decision instead of restating the code:

|                                                                    |                                                                                                          |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `backend/README.md`                                                | Why this folder is the one you delete, and why its API returns full PII on purpose                       |
| `agent/MultiTenantTravel/README.md`                                | The agent project, and what `agentcore.json` owns                                                        |
| `agent/MultiTenantTravel/AGENTS.md`                                | Binding rules for the AgentCore project — schema-first, and why renaming a resource destroys it          |
| `agent/MultiTenantTravel/app/MultiTenantTravel/policies/README.md` | The runtime's IAM documents, and the quietest failure in the repo                                        |
| `agent/MultiTenantTravel/policies/*.cedar`                         | The authorisation rules, each with its reasoning inline — including a rule that was **rejected** and why |
| `frontend/README.md`                                               | One component per card type, and the exhaustive switch                                                   |

### Related samples in this repository

Four neighbours overlap with this one on a single axis each, and reading the pair is more useful than
reading either alone. This sample deliberately does not reimplement what they already cover.

| Sample                                                                                                                                            | What it covers                                                                                 | Where this one goes instead                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`05-blueprints/travel-concierge-agent`](../../../05-blueprints/travel-concierge-agent)                                                           | Agentic **payments** in a consumer-travel skin — web-search tools, card tokenisation           | Corporate managed travel. Payment here is a mock corporate-instrument reference and card data never enters agent context — for a real payment rail, read that blueprint                                 |
| [`05-blueprints/multitenant-agentic-platform`](../../../05-blueprints/multitenant-agentic-platform)                                               | A multi-tenant **platform** for deploying one agent per tenant, with per-tenant token metering | The opposite decomposition: **one shared agent, many tenants' data**, isolation enforced in IAM and Cedar rather than by separate deployments, and cost per _resolved outcome_ rather than tokens alone |
| [`02-use-cases/01-conversational-agents/lakehouse-agent`](../lakehouse-agent)                                                                     | Row-level security from OAuth claims, against Athena                                           | The same claims-to-enforcement idea carried across DynamoDB key conditions, knowledge-base metadata filters and tool authorisation                                                                      |
| [`02-use-cases/02-workflow-automation-agents/visa-b2b-account-payable-agent`](../../02-workflow-automation-agents/visa-b2b-account-payable-agent) | A real payment-rail integration                                                                | No payment rail. The booking write path stops at a corporate instrument reference                                                                                                                       |

It is also a worked answer to [#864](https://github.com/awslabs/agentcore-samples/issues/864), which
asked for row-level multi-tenant filtering driven by the logged-in user, with the Gateway and its
interceptor translating to the calling user.

## License

Apache-2.0, from the `LICENSE` file at the root of this repository. There is no separate license file
here on purpose — a second copy is a second thing to keep in step, and none of the neighbouring
samples carry one.

## Disclaimer

The examples provided in this repository are for experimental and educational purposes only. They
demonstrate concepts and techniques but are not intended for direct use in production environments.
Make sure to have Amazon Bedrock Guardrails in place to protect against
[prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).

The two tenants, their travellers, their negotiated rates and their policy documents are entirely
fictional, and `backend/` is a mock travel platform rather than a real one. No third-party API keys or
real traveller data are involved.
