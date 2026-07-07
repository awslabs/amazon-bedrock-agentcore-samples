# Agent Runtime

This directory contains the Strands agent and FastAPI service used by the `pay-for-x402-secure-data` sample.

## What It Does

- Accepts AgentCore Runtime-style `/invocations` requests.
- Extracts `payment_context` from the payload or request headers.
- Pays t54 x402-secure for endpoint trust scoring before target x402 service payments.
- Calls registered paid x402 service endpoints only after the trust guardrail passes.
- Delegates HTTP 402 payment retry to `AgentCorePaymentsPlugin`.
- Retries paid requests with the returned x402 payment header (`X-PAYMENT` for v1, `PAYMENT-SIGNATURE` for v2).

The runtime does not hold wallet private keys. Paid calls made through `/invocations` require:

```json
{
  "input": {
    "prompt": "Check trust for heurist_yahoo_finance, then fetch a quote snapshot for AAPL.",
    "payment_context": {
      "user_id": "user-123",
      "payment_session_id": "<session-id>",
      "payment_instrument_id": "<instrument-id>"
    }
  }
}
```

## Files

```text
agent/
├── main.py                  # stable runtime import and uvicorn entrypoint
├── http_app.py              # FastAPI /ping and /invocations app
├── runtime_context.py       # request parsing, telemetry, and payment context helpers
├── agent.py                 # Strands agent tools and prompt
├── payments.py              # AgentCore payment context and plugin config helpers
├── x402_secure.py           # plugin-compatible t54 x402-secure direct API client
├── x402_services.py         # public compatibility exports for x402 service helpers
├── x402_gateway.py          # trust-gated registered service gateway
├── x402_service_client.py   # registered target x402 HTTP client
├── x402_service_registry.py # supported service catalog and operation validation
└── x402_trust_state.py      # request-scoped trust state
```

## Local Run

From the sample root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r agent/requirements.txt
PYTHONPATH="$PWD/agent" uvicorn main:app --host 0.0.0.0 --port 8080
```

Then:

```bash
curl http://localhost:8080/ping
```

## Container Build

Build from the sample root so the Dockerfile can copy `agent/` paths:

```bash
docker build -f agent/Dockerfile -t pay-for-x402-secure-data:local .
```
