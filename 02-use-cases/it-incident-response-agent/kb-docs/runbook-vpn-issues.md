# Runbook: VPN connection failures

## Symptoms
- VPN client fails to connect after laptop sleep / wake.
- DNS resolution intermittently fails after a successful connection.
- Repeated disconnects on macOS 14.4 with split-tunnel enabled.

## Diagnosis
1. Confirm the user's `corp-vpn` client version. Versions older than 8.4 are
   end-of-life and must be upgraded.
2. Check whether the user is on macOS 14.4 with split-tunnel enabled — this
   is a known incompatibility.
3. Review the user's recent incident history. If the user has filed two or
   more VPN tickets in 30 days, escalate to NetworkOps.

## Resolution steps
1. Ask the user to fully quit the VPN client (not just disconnect) and
   relaunch it. Sleep/wake leaves stale tunnels that block reconnection.
2. If the issue persists, instruct the user to disable split-tunnel in the
   VPN client preferences and reconnect.
3. If neither works, file a change request via the IT change system to
   schedule a profile reinstall, and notify the user with a tracking ID.

## Escalation
- Recurring incidents (>= 2 in 30 days) should be assigned to NetworkOps.
- Outage signals (e.g., the `corp-vpn` `current_status` is not
  `operational`) require a P1 page to NetworkOps oncall.
