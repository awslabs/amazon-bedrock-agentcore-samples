// acting on another traveller's behalf.
//
// **Cedar answers the static half; the tool answers the dynamic half.** Cedar can see claims
// and arguments, so it can enforce "only arrangers may name another traveller". It cannot
// query DynamoDB, so it cannot know whether *this* arranger may act for *this* traveller —
// that question has a current answer and is asked at the moment it matters
// (`GET /v1/arrangers/{id}/can-book/{target}`, in `tools/common/authz.py`).
//
// "Static in policy, dynamic in the resource owner" is the correct division, and an
// authorisation engine reaching into the application database on every call would be a
// latency and coupling problem. Readers will ask, so it is worth a paragraph in the post.
//
// ---
//
// **Two attempts at this rule were rejected, and the second rejection was instructive.**
//
// Attempt 1 — `action` (any) with `resource is AgentCore::Gateway`: rejected, because the
// analyser had to consider tools whose schema has no `traveler_name` at all, where the
// condition is provably false.
//
// Attempt 2 — the specific action, still rejected as *"Overly Restrictive: will deny every
// request for … profile___get_traveler_profile"*. The reason is that `traveler_name` is
// **optional**: Cedar cannot prove the argument is ever absent, so it must assume the forbid
// may always fire, and a rule that might deny every call to a tool is exactly what the
// analyser is built to stop.
//
// That is a real signal, not an obstacle to work around. The rule as written tried to make
// Cedar reason about *argument presence* — a property of a single request — when Cedar's job
// is reasoning about *who may do what*. Argument-shape validation belongs where the argument
// is read.
//
// So this file deliberately contains **no rule about `traveler_name`**. The check lives in
// `tools/common/authz.py`, which resolves a name only within the caller's authorised scope: a
// plain traveller's scope is exactly themselves, so naming someone else resolves to nobody
// and is refused. Same outcome, enforced where the information actually is.
//
// **What would belong here** is a rule about actions arrangers may perform *at all* — e.g.
// forbidding `confirm_booking` for non-arrangers outright, independent of arguments. That
// belongs with the booking tools, and it is expressible there because it depends only on the
// claim and the action.
