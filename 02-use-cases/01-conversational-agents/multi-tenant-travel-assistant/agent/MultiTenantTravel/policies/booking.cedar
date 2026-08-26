// authorisation for the write path.
//
// **This is the rule `arranger.cedar` said would belong here.** That file documents why the
// "only arrangers may name another traveller" rule is *not* expressible: `traveler_name` is
// optional, so the analyser cannot prove a forbid over it ever stays quiet and rejects it as
// always-deny. The check therefore lives in `tools/common/authz.py`, where the argument is read.
//
// The booking rules are different, and the difference is precisely what makes them expressible:
// they depend only on **the claim and the action**. No optional argument, nothing the analyser has
// to reason about the presence of. "May this principal confirm a booking at all?" is a question
// about who is asking, which is exactly what Cedar is for.
//
// Constraints already learned the hard way and still in force here:
//
//   * Action names carry the **target prefix** — `booking___confirm_booking`, not
//     `confirm_booking`. No wildcards exist, so every tool is named explicitly.
//   * Naming specific actions requires a **specific gateway ARN** — written here as the
//     `{{GATEWAY_ARN}}` placeholder that `scripts/sync_policies.py` resolves, since the gateway's
//     id is generated per-deploy and a committed ARN would match nothing anywhere else.
//   * `forbid` needs a `permit` to override; the engine is deny-by-default, so a lone forbid adds
//     nothing to a request that was never permitted.
//   * A new policy is deployed **`LOG_ONLY` first**, a lesson already paid for once here: a
//     rule that cannot be evaluated denies every matching request, and in `ACTIVE` mode that is a
//     total outage for the tool rather than a validation error.

// --- Write tools require a verified tenant ------------------------------------
//
// The same fail-closed control the read tools have, extended to the write path. A token minted
// without the pre-token-generation trigger carries no `custom:tenant_id`, matches no permit, and
// is denied by default.
//
// Separate from the read permit rather than appended to it, because the write surface is the one a
// reviewer will audit line by line — and "which tools can charge money?" should be answerable by
// reading one rule.
permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"booking___prepare_booking",
    AgentCore::Action::"booking___confirm_booking",
    AgentCore::Action::"booking___cancel_reservation"
  ],
  resource == AgentCore::Gateway::"{{GATEWAY_ARN}}"
)
when {
  principal.hasTag("custom:tenant_id")
};

// Why there is no "arranger only" rule on the write path
// ------------------------------------------------------
//
// An earlier plan for this file was `forbid confirm_booking unless role == arranger`. **That would
// have been wrong, and stating why is more useful than the rule would have been.**
//
// A traveller booking their *own* trip is the primary use case — the tool catalogue's gate is
// "self / arranger", not "arranger only". A role check would have denied the commonest legitimate
// action in the product, and it would have looked principled while doing it: "only arrangers may
// transact" reads like sound governance right up until a traveller cannot book their own flight.
//
// The real constraint on the write path is **whose booking is it**, and that is not a claim
// question. Two controls already answer it, both at the right layer:
//
//   * `tools/common/authz.py` resolves any named traveller within the caller's authorised scope, so
//     a plain traveller naming someone else resolves to nobody. A traveller cannot prepare a
//     booking for a colleague because the name does not resolve, not because a role forbids it.
//   * `confirm_booking` re-derives ownership from the offer handle server-side. A handle belonging
//     to another traveller is indistinguishable from one that never existed.
//
// And the *tenant-level* gate — whether an agent may transact in chat at all — is enforced in the
// tool by reading the tenant's `booking_mode`, because it depends on a record rather than a claim.
// Cedar cannot query the tenant table, and an authorisation engine that reached into the
// application database on every call would be a latency and coupling problem.
//
// So the honest division on this path: **Cedar answers "is this a verified caller invoking a write
// tool?", the tool answers "is this their booking, and may this customer transact?"** Knowing which
// half Cedar can carry is the skill; adding a rule it cannot carry correctly is the failure mode.
