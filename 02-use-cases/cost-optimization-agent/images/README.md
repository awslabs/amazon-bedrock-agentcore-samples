# Architecture Diagram

## Generating the Diagram

To generate the professional architecture diagram:

1. Install dependencies:
   ```bash
   pip install diagrams pillow
   ```

2. Run the generation script:
   ```bash
   cd ../scripts
   python create_architecture_diagram.py
   ```

3. The diagram will be created as `cost-optimization-architecture.png` in this directory.

## Alternative Views

If you cannot generate the visual diagram:

1. **Text-based architecture**: See [../ARCHITECTURE.md](../ARCHITECTURE.md) for a detailed ASCII diagram
2. **Mermaid diagram**: See [../architecture.mmd](../architecture.mmd) for a Mermaid flowchart (renders on GitHub)

## Diagram Standards

The generated diagram follows Amazon Bedrock AgentCore standards:
- ✅ Uses official AWS service icons
- ✅ Clear component grouping with clusters  
- ✅ Color-coded connections by function
- ✅ Professional layout matching other AgentCore samples
- ✅ Shows all major components and data flows

## Components Shown

The architecture diagram illustrates a **single-agent design**:

1. **User Layer**: FinOps Teams & Developers
2. **AgentCore Runtime**: HTTP server with streaming support
3. **Single Strands Agent**: 
   - One intelligent agent (not multi-agent)
   - Uses Claude 3.5 Sonnet for reasoning
   - Has 5 tool functions (not separate agents)
4. **Tool Functions**: 
   - analyze_cost_anomalies
   - get_budget_information
   - forecast_future_costs
   - get_service_cost_breakdown
   - get_current_month_costs
5. **AWS Cost Management APIs**: Cost Explorer, Budgets, CloudWatch

## Data Flows

The diagram shows:
- User queries to single agent
- LLM-powered tool selection
- Tool function execution
- AWS API calls
- Streaming responses back to user
