# Multi-Agent System: Specialized Intelligence at Work

## Supervisor Agent - The Orchestrator
**Analyzes queries** → **Creates investigation plans** → **Routes to specialists** → **Aggregates results**

---

## Four Specialist Agents

### **☸️ Kubernetes Infrastructure Agent**
- Pod status and deployment analysis
- Cluster events and resource utilization
- Node health and capacity monitoring
- *"Discovers pods are crash-looping with OOM kills"*

### **📊 Application Logs Agent**  
- Full-text search with regex patterns
- Error aggregation and anomaly detection
- Time-based event correlation
- *"Finds memory leak in payment processor logs"*

### **📈 Performance Metrics Agent**
- Response time and throughput analysis
- Error rate monitoring with thresholds
- Resource utilization tracking
- *"Confirms memory spike at 14:23 UTC"*

### **📖 Operational Runbooks Agent**
- Incident-specific playbooks
- Troubleshooting guides
- Escalation procedures
- *"Retrieves OOM investigation procedures"*

---

## Collaboration Example: Payment Service Crisis

**6-minute investigation** vs **45-minute manual process**

1. **Query**: "Why are payment-service pods crash looping?"
2. **Supervisor**: Routes to K8s + Logs + Metrics agents
3. **Result**: Unified report with root cause, impact, and remediation