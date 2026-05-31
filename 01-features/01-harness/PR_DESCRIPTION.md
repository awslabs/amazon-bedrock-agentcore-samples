# PR: Add architecture diagrams for all Harness tutorials

## Summary

Adds architecture diagrams (PNG) to each of the 8 Harness tutorial subfolders, plus a comprehensive reference document that maps every use case to its services, flow, and configuration.

## What's included

### Architecture diagrams (`architecture.png` in each folder)

| # | Tutorial | Path |
|---|---|---|
| 1 | Custom Containers | `01-advanced-examples/01-custom-containers/` |
| 2 | Gateway Integration | `01-advanced-examples/02-gateway-integration/` |
| 3 | Execution Limits | `01-advanced-examples/03-execution-limits/` |
| 4 | MCP Integration | `01-advanced-examples/04-mcp-integration/` |
| 5 | Agent Skills | `01-advanced-examples/05-agent-skills/` |
| 6 | OAuth + JWT Auth | `01-advanced-examples/07-oauth/` |
| 7 | Travel Guide Agent | `02-use-cases/01-travel-agent/` |
| 8 | Automated Visual QA | `02-use-cases/02-webapp-visual-testing/` |

### Reference document

- `ARCHITECTURE_REFERENCE.md` — comprehensive breakdown of all 8 use cases: services involved, execution flow, key configuration, component relationships, and what each diagram represents.

## Design decisions

**Visual style**: Dark theme consistent with the AgentCore Gateway Deep Dive enablement deck (the official L300 material). This keeps the diagrams visually coherent with existing AgentCore presentations and marketing material.

**Diagram scope**: Each diagram focuses on the specific feature or integration pattern demonstrated by that tutorial. They show the logical flow (not infrastructure topology) so developers can quickly understand what gets deployed and how data moves between components.

**Icons**: Using the official AgentCore sub-service icons (Harness, Gateway, Identity, Observability) from the internal icon package, plus standard AWS service icons for ECR, Lambda, CloudTrail, etc.

**Naming convention**: Every diagram is named `architecture.png` so READMEs can reference them with a consistent relative path (`![Architecture](./architecture.png)`).

**Format**: PNG rather than SVG because the diagrams include raster icons and the dark theme renders more consistently across GitHub's light/dark mode viewers as a raster image.

## How to validate

Each diagram can be cross-referenced against `ARCHITECTURE_REFERENCE.md` which documents the exact services, API calls, and execution flow for every tutorial based on the source code.
