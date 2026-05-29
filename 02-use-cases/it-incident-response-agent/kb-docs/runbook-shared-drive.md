# Runbook: Shared drive slow / inaccessible

## Symptoms
- File listings on the shared drive take more than 10 seconds.
- Saving large files times out or returns "network path not found".
- Issue is most common when users are on `corp-vpn` from US-WEST.

## Diagnosis
1. Confirm the user is on `corp-vpn`. The shared drive is unreachable
   without VPN by design.
2. Confirm the user is in the US-WEST region. There is a known routing
   issue from US-WEST when VPN is enabled.
3. Check whether the SMB gateway override is configured in the user's
   network profile.

## Resolution steps
1. Apply the SMB gateway override from the IT self-service portal. This
   reroutes shared-drive traffic via the gateway and bypasses the slow
   path.
2. Ask the user to remap the network drive after the override is applied.
3. Record the change via `create_change_request` with action
   `apply_smb_gateway_override`.

## Escalation
- If the SMB gateway is itself slow or unavailable, escalate to the
  Storage team.
