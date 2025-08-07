# SRE Agent Presentation - Based on Blog Post

## Presentation Structure (9 Slides)

This presentation is derived directly from the [blog post](../blog_post.md) and demonstrates how Amazon Bedrock AgentCore primitives simplify building complex multi-agent SRE solutions.

### Slide Sequence

1. **[Title & Introduction](slide-01-title.md)**  
   - Challenge, solution, and quantified results
   - Sets the stage with 75% MTTR reduction

2. **[Problem & Solution](slide-02-problem-solution.md)**  
   - Natural language queries vs manual correlation
   - Introduction to AgentCore primitives

3. **[Architecture Overview](slide-03-architecture.md)**  
   - Three-layer system architecture
   - Includes architecture diagram from `docs/images/sre-agent-architecture.png`

4. **[Multi-Agent System](slide-04-multi-agent.md)**  
   - Supervisor and four specialist agents
   - Real collaboration example with timing

5. **[AgentCore Gateway](slide-05-gateway.md)**  
   - API to MCP tool transformation
   - Code examples and time savings (4-6 weeks → 2 days)

6. **[AgentCore Memory](slide-06-memory.md)**  
   - Three memory strategies with namespaces
   - Alice vs Carol personalization example

7. **[AgentCore Runtime](slide-07-runtime.md)**  
   - Development to production flow
   - Containerization and deployment simplicity

8. **[Demo & Results](slide-08-demo-results.md)**  
   - Payment service crisis investigation
   - 6-minute vs 45-minute comparison

9. **[Conclusion & Next Steps](slide-09-conclusion.md)**  
   - Key takeaways and ROI metrics
   - Clear action items and resources

## Key Themes from Blog Post

### **Business Value**
- 75% reduction in incident response time
- 60% faster root cause identification  
- 3x increase in SRE productivity
- $2.3M annual savings per 100-engineer organization

### **Technical Innovation**
- **AgentCore Gateway**: Converts any API to MCP tools in days
- **AgentCore Memory**: Enables personalization with 3 lines of code
- **AgentCore Runtime**: Production deployment with single command

### **Real-World Application**
- Natural language infrastructure queries
- Personalized investigations based on user role
- Continuous learning from every incident
- Enterprise-ready with security and scaling

## Presentation Tips

### **Opening Hook**
Start with the challenge: *"SREs face increasingly complex distributed systems, manually correlating data from multiple sources during production incidents"*

### **Architecture Visual**
Use the included architecture diagram to show the three-layer system design

### **Live Demo Points**
- Show same query with different user personas (Alice vs Carol)
- Demonstrate 6-minute investigation flow
- Highlight automated correlation across data sources

### **Closing Impact**
End with the vision: *"Transform every SRE engineer into a super-powered investigator with AI that remembers, learns, and personalizes"*

## Supporting Materials

- **Blog Post**: [docs/blog_post.md](../blog_post.md) - Complete technical narrative
- **Architecture**: [docs/images/sre-agent-architecture.png](../images/sre-agent-architecture.png) - System diagram
- **Memory System**: [docs/memory-system.md](../memory-system.md) - Deep dive on personalization
- **GitHub**: [amazon-bedrock-agentcore-samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)

## Time Allocation (30-minute presentation)

- **Introduction & Problem** (3 min)
- **Architecture Overview** (3 min)
- **Multi-Agent System** (4 min)
- **AgentCore Primitives** (10 min)
  - Gateway (3 min)
  - Memory (4 min)
  - Runtime (3 min)
- **Demo & Results** (5 min)
- **Conclusion & Q&A** (5 min)