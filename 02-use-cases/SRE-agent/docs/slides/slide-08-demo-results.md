# Demo: Real-World Investigation

## Scenario: Payment Service Crisis

### **Query**
```bash
sre-agent --prompt "Why are the payment-service pods crash looping?"
```

### **Multi-Agent Investigation Flow** (6 minutes total)

| Time | Agent | Discovery |
|------|-------|-----------|
| 0:30 | Supervisor | Routes to K8s, Logs, Metrics agents |
| 1:00 | Kubernetes | Pods restarting with OOMKilled status |
| 2:30 | Metrics | Memory spike at 14:23 UTC (8.2GB peak) |
| 4:00 | Logs | Java heap exhaustion, GC pressure |
| 5:30 | Runbooks | OOM investigation playbook retrieved |
| 6:00 | Supervisor | Unified report with remediation |

---

## Quantified Business Impact

### **Before AgentCore**
- 45 minutes average investigation time
- Manual correlation across 4+ tools
- Inconsistent findings and reports
- Knowledge lost between incidents

### **After AgentCore**  
- **6 minutes** end-to-end investigation
- **Automated** correlation and synthesis
- **Personalized** reports per user role
- **Continuous** learning and improvement

---

## Live Demo Capabilities

### **Interactive Commands**
```bash
# Single query investigation
sre-agent --prompt "Find all database connection errors"

# Personalized for different users
USER_ID=Alice sre-agent --prompt "API latency spike"
USER_ID=Carol sre-agent --prompt "API latency spike"

# Interactive mode with context
sre-agent --interactive
```

### **Demo Environment Scale**
- 47 nodes, 312 pods across 8 namespaces
- 2.3M log entries with realistic patterns
- 15 services with performance metrics
- 23 operational runbooks