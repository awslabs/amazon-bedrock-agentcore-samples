# AgentCore Memory: From Stateless to Intelligent

## Three Memory Strategies for Persistent Intelligence

### **1. User Preferences Strategy**  
`/sre/users/{user_id}/preferences`
- Investigation style and communication channels
- Escalation procedures and report formatting
- Personalized for each user's role

### **2. Infrastructure Knowledge Strategy**
`/sre/infrastructure/{user_id}/{session_id}`
- Domain expertise from past discoveries
- Pattern recognition across investigations
- Accumulated organizational knowledge

### **3. Investigation Memory Strategy**
`/sre/investigations/{user_id}/{session_id}`
- Historical incident patterns
- Proven remediation approaches
- Lessons learned from failures

---

## Personalization in Action: Same Incident, Different Views

### **Alice (Technical SRE) Investigation**
```markdown
## Technical Investigation Summary
**Root Cause**: Payment processor memory leak causing OOM kills
**Analysis**:
- Pod restart frequency increased 300% at 14:23 UTC
- Memory utilization peaked at 8.2GB (80% limit)
- JVM garbage collection latency spiked to 2.3s
**Next Steps**:
1. Implement heap dump analysis
2. Review recent code deployments
3. Increase memory limits
```

### **Carol (Executive) Investigation**  
```markdown
## Business Impact Assessment
**Status**: CRITICAL - Payment processing degraded
**Impact**: 23% transaction failure rate, $47K at risk
**Timeline**: Detected 14:23 UTC, ETA 45 minutes
**Actions**: Customer communication initiated,
           VP Engineering escalation if not resolved by 15:15
```

---

## Implementation Simplicity

```python
# Initialize memory with 3 lines of code
memory_client = SREMemoryClient("sre_agent_memory")
memory_client.store_user_preference("Alice", preferences)
context = memory_client.retrieve_investigation_history(query)
```

**Result**: Intelligent, learning system that improves with every incident