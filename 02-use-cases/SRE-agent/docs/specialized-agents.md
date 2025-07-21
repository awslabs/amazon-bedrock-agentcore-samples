# Specialized Agents

## Kubernetes Infrastructure Agent

Handles container orchestration and cluster operations. This agent investigates issues across pods, deployments, services, and nodes by examining cluster state, analyzing pod health, resource utilization, and recent events.

**Capabilities:**
- Check pod status across namespaces
- Examine deployment configurations and rollout history
- Investigate cluster events for anomalies
- Analyze resource usage patterns
- Monitor node health and capacity

## Application Logs Agent

Processes log data to find relevant information. This agent understands log patterns, identifies anomalies, and correlates events across multiple services.

**Capabilities:**
- Full-text search with regex support
- Error log aggregation and categorization
- Pattern detection for recurring issues
- Time-based correlation of events
- Statistical analysis of log volumes

## Performance Metrics Agent

Monitors system metrics and identifies performance issues. This agent understands relationships between different metrics and provides both real-time analysis and historical trending.

**Capabilities:**
- Application performance metrics (response times, throughput)
- Error rate analysis with thresholding
- Resource utilization metrics (CPU, memory, disk)
- Availability and uptime monitoring
- Trend analysis for capacity planning

## Operational Runbooks Agent

Provides access to documented procedures, troubleshooting guides, and best practices. This agent helps standardize incident response by retrieving relevant procedures based on the current situation.

**Capabilities:**
- Incident-specific playbooks for common scenarios
- Detailed troubleshooting guides with step-by-step instructions
- Escalation procedures with contact information
- Common resolution patterns for known issues
- Best practices for system operations