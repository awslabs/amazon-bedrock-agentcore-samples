# Tutorial 06 Diagrams

Render with https://mermaid.live/ or mmdc CLI.

AWS-inspired palette:
- Agent: #232F3E (navy), inner: #37475A
- Memory: #7B2D8E (purple), inner: #9B4DB5
- Payments: #D45B07 (orange), inner: #E87A30
- Accent: #147EBA (blue)

## 1. architecture.png

```mermaid
graph TB
    subgraph Agent["Strands Agent"]
        direction TB
        A["System Prompt"]
        T1["recall_user_context"]
        T2["http_request"]
        PL["PaymentsPlugin"]
    end

    subgraph Memory["AgentCore Memory"]
        M1["/facts (semantic)"]
    end

    subgraph Payments["AgentCore payments"]
        PM["ProcessPayment"]
    end

    subgraph Endpoint["Paid x402 Endpoint"]
        EP["HTTP 402 → proof → content"]
    end

    T1 -->|"search"| M1
    T2 --> EP
    EP -->|"402"| PL
    PL --> PM
    PM -->|"proof"| EP
    EP -->|"200 + content"| T2

    style Agent fill:#232F3E,stroke:#232F3E,color:#fff
    style Memory fill:#7B2D8E,stroke:#5A1D6B,color:#fff
    style Payments fill:#D45B07,stroke:#A34705,color:#fff
    style Endpoint fill:#1B660F,stroke:#134A0B,color:#fff
    style A fill:#37475A,stroke:#232F3E,color:#fff
    style T1 fill:#37475A,stroke:#232F3E,color:#fff
    style T2 fill:#37475A,stroke:#232F3E,color:#fff
    style PL fill:#37475A,stroke:#232F3E,color:#fff
    style M1 fill:#9B4DB5,stroke:#7B2D8E,color:#fff
    style PM fill:#E87A30,stroke:#D45B07,color:#fff
    style EP fill:#2D8F1C,stroke:#1B660F,color:#fff
```


## 2. session_flow.png

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Memory as AgentCore Memory
    participant EP as Paid Endpoint
    participant Pay as AgentCore payments

    rect rgba(123, 45, 142, 0.1)
    Note right of User: Step 1 — RECALL
    User->>Agent: Get weather data for Seattle
    Agent->>Memory: recall_user_context("weather data Seattle")
    Memory-->>Agent: past session: spent $0.05, preferred: weather-api
    end

    rect rgba(35, 47, 62, 0.15)
    Note right of Agent: Step 2 — DECIDE
    Note over Agent: Memory has old weather data. Fetch fresh.
    end

    rect rgba(212, 91, 7, 0.1)
    Note right of Agent: Step 3 — FETCH (plugin handles payment)
    Agent->>EP: http_request(paid_url)
    EP-->>Agent: 402 Payment Required
    Agent->>Pay: ProcessPayment $0.05
    Pay-->>Agent: proof
    Agent->>EP: retry with proof
    EP-->>Agent: 200 + fresh data
    end

    rect rgba(123, 45, 142, 0.1)
    Note right of Agent: Step 4 — REPORT
    Agent-->>User: Here's the data. Cost: $0.05. Recalled Seattle weather from memory (saved $0.05).
    end

    Note over Memory: Semantic strategy auto-extracts facts for next session
```

## 3. memory_workflow.png

```mermaid
graph LR
    subgraph Session1["Session 1 (cold start)"]
        S1A["Fetch data"] --> S1B["Pay $0.15"]
        S1B --> S1C["Memory extracts facts"]
    end

    subgraph Session2["Session 2 (warm)"]
        S2A["Recall memory"] --> S2B["Skip known data"]
        S2B --> S2C["Pay only $0.05"]
    end

    S1C -->|"persists"| S2A

    style Session1 fill:#37475A,stroke:#232F3E,color:#fff
    style Session2 fill:#2D8F1C,stroke:#1B660F,color:#fff
    style S1A fill:#E87A30,stroke:#D45B07,color:#fff
    style S1B fill:#E87A30,stroke:#D45B07,color:#fff
    style S1C fill:#9B4DB5,stroke:#7B2D8E,color:#fff
    style S2A fill:#9B4DB5,stroke:#7B2D8E,color:#fff
    style S2B fill:#147EBA,stroke:#0D5E94,color:#fff
    style S2C fill:#2D8F1C,stroke:#1B660F,color:#fff
```
