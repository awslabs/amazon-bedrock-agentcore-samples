# Diagrams -- Tutorial 08 (MPP)

Source definitions for the architecture images referenced in the README.
Render these to PNG and save alongside as `strands_mpp_flow.png`.

> **Rendering note:** the committed `strands_mpp_flow.png` was rendered from the mermaid
> source below. If you have the mermaid CLI (`mmdc`), re-render for visual consistency with
> the rest of the repo:
> ```bash
> mmdc -i diagrams.md -o strands_mpp_flow.png -b white -s 2
> ```
> (Extract the ```mermaid block first, or use your repo's standard diagram toolchain.)

## strands_mpp_flow.png

```mermaid
sequenceDiagram
    participant A as Agent (Strands + http_request)
    participant P as AgentCorePaymentsPlugin
    participant M as MPP Merchant (Tempo Moderato testnet 42431)
    participant AC as AgentCore Payments (ProcessPayment)

    A->>M: POST /search (no payment)
    M-->>A: 402 + WWW-Authenticate: Payment (MPP Challenge)
    P->>P: intercept 402 MPP challenge
    P->>AC: ProcessPayment (budget check -> sign Tempo tx)
    AC-->>P: MPP Credential (PROOF_GENERATED)
    P->>M: retry POST + Authorization: Payment <credential>
    M-->>A: 200 OK + Payment-Receipt (paid content)
    A->>A: summarize results for the user
```
