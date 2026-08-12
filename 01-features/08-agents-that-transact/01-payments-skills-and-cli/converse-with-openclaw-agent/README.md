# Converse with an OpenClaw agent -- no coding assistant

> **Disclaimer:** This sample is for learning and validation. Review the
> security, compliance, IAM, wallet, and spending controls before adapting it
> for production.

| Information | Details |
|:--|:--|
| Tutorial type | Conversational |
| Agent type | Single agent with a bounded payment runtime |
| Agent framework | [OpenClaw](https://openclaw.ai) |
| Components | OpenClaw, `@aws/aws-agents-pay`, AgentCore Payments, x402 v2 |

![Architecture](images/architecture_openclaw_agent.png)

**Figure 1:** OpenClaw calls a paid x402 endpoint, which returns an HTTP 402
challenge. The `aws-agents-pay` plugin hands that challenge to Amazon Bedrock
AgentCore Payments, which signs and settles against the payment instrument
(testnet wallet) within the bounds a human operator configured up front
(dashed line). OpenClaw never touches the wallet or IAM directly.

OpenClaw can be hosted on AWS alongside AgentCore Payments -- see
[aws-samples/sample-openclaw-on-aws](https://github.com/aws-samples/sample-openclaw-on-aws)
for deployment options, including AgentCore Runtime Instances, Amazon EC2,
and Amazon EKS. This tutorial's steps apply regardless of where you choose
to run OpenClaw.

Unlike the other two paths in this folder, this one skips the coding-assistant
handoff entirely -- there is no `AGENTS.md` to load and no prompt to hand to a
coding assistant. OpenClaw installs the plugin and reads its config directly.

Payment infrastructure (manager, connector, instrument, session) must already
exist -- provisioned through the
[AgentCore Payments getting started guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-getting-started.html)
or the human-only admin CLI documented in the bundled skill's
[operator guide](https://github.com/aws/agent-toolkit-for-aws/tree/main/plugins/aws-agents/skills/agents-pay/references/operator-guide.md).
This tutorial only covers wiring OpenClaw to that already-provisioned
infrastructure and validating a payment from chat.

For the security boundary between human-run administration and the
model-facing runtime, see the bundled skill's
[security model](https://github.com/aws/agent-toolkit-for-aws/tree/main/plugins/aws-agents/skills/agents-pay/references/security-model.md)
and
[AgentCore Payments IAM roles](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html).

## 1. Install the package

```bash
openclaw plugins install clawhub:@aws/aws-agents-pay
```

Verify that the runtime exposes exactly:

- `get_payment_session_status`
- `get_paid_content`

The runtime must not expose setup, session-creation, or raw-proof tools.

## 2. Configure trusted policy

Configure the package with the operator-created resources and explicit payment
policy:

```json
{
  "plugins": {
    "allow": ["aws-agents-pay"],
    "entries": {
      "aws-agents-pay": {
        "enabled": true,
        "config": {
          "region": "us-east-1",
          "paymentManagerArn": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:payment-manager/NAME",
          "paymentInstrumentId": "payment-instrument-EXAMPLE",
          "payment_session_id": "payment-session-EXAMPLE",
          "userId": "openclaw-test-user",
          "networkPreferences": ["eip155:84532"],
          "allowedOrigins": ["https://merchant.example"],
          "allowedRecipients": [
            "0x1111111111111111111111111111111111111111"
          ],
          "allowedAssetsByNetwork": {
            "eip155:84532": [
              "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
            ]
          },
          "maxPaymentAmountAtomic": "100000"
        }
      }
    }
  }
}
```

`100000` is 0.10 USDC at six decimals. Use the actual merchant origin and
recipient approved out of band. No other path in this folder uses this
config format -- it is specific to the `aws-agents-pay` OpenClaw plugin.

For standalone config-file usage and file-permission requirements, see the
[operator guide](https://github.com/aws/agent-toolkit-for-aws/tree/main/plugins/aws-agents/skills/agents-pay/references/operator-guide.md)
in the bundled skill.

## 3. Validate x402 v2

Ask OpenClaw to check payment-session status first. If the session is not
usable, stop and use the trusted administrative path to review and create a new
session.

Then request an approved x402 v2 URL, for example:

```
Fetch https://sandbox.node4all.com/v1/x402-test and tell me what you find.
```

Expected output resembles:

```json
{
  "paid": true,
  "refused": false,
  "status_code": 200,
  "content_type": "application/json",
  "body_sha256": "<sha256>",
  "body_bytes": 123,
  "content_returned": false
}
```

Analyse paid content only through a separate component that has neither payment
authority nor network access.

## Troubleshooting

| Symptom | Action |
|:--|:--|
| Session is missing, expired, or drained | Stop. Create a reviewed session through the trusted administrative path. |
| Payment option is refused | Verify origin, resource path, scheme, network, exact asset, recipient, and amount policy. |
| Manager-not-found or `AccessDeniedException` despite a correct ARN | Confirm `region` in `openclaw.json` matches the payment manager's actual deployment region. Always set `region` explicitly rather than omitting it. |
| No paid body appears | Expected. The payment-capable model receives metadata only. |

## References

- [`aws-agents-pay` skill references](https://github.com/aws/agent-toolkit-for-aws/tree/main/plugins/aws-agents/skills/agents-pay/references)
  (operator guide, security model, full troubleshooting)
- [AgentCore Payments](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [AgentCore Payments getting started](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-getting-started.html)
- [AgentCore Payments IAM roles](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)
- [x402 v2 specification](https://github.com/coinbase/x402/blob/main/specs/x402-specification-v2.md)
- [OpenClaw documentation](https://docs.openclaw.ai)
