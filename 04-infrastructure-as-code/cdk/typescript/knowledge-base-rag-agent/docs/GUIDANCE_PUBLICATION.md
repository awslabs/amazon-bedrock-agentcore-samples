# AWS Guidance Publication - Bedrock AgentCore Template

## Guidance Overview

### Title
Building Conversational AI Applications with Amazon Bedrock AgentCore

### Short Description
A production-ready AWS CDK template for deploying conversational AI applications using Amazon Bedrock AgentCore with integrated Memory, Knowledge Bases, and web interface.

### Long Description
This guidance provides a comprehensive, production-ready solution for building and deploying conversational AI applications on AWS using Amazon Bedrock AgentCore. It demonstrates how to deploy containerized AI agents with the Strands SDK, implement long-term memory with built-in extraction strategies, integrate Knowledge Bases for retrieval-augmented generation (RAG), and deploy a modern web interface with secure authentication. The solution follows AWS best practices for security, scalability, and operational excellence, making it suitable for both proof-of-concept and production deployments.

## Target Audience

### Primary Audience
- Solutions Architects designing conversational AI solutions
- Developers building AI-powered applications
- DevOps engineers deploying AI infrastructure

### Secondary Audience
- Technical decision makers evaluating AI solutions
- Product managers planning AI features
- Enterprise architects designing AI platforms

## Business Value

### Problem Statement
Organizations want to build conversational AI applications that can answer questions using their proprietary data and maintain context across conversations, but face challenges with:
- Complex integration of multiple AWS AI services
- Implementing persistent memory for conversation context
- Managing vector databases for knowledge retrieval
- Deploying production-ready, auto-scaling infrastructure
- Ensuring security and compliance requirements

### Solution Benefits
- **Accelerated Time to Market**: Deploy a complete conversational AI solution in hours instead of weeks
- **Reduced Development Costs**: Pre-built infrastructure and integration patterns eliminate custom development
- **Enhanced User Experience**: Built-in memory enables personalized, context-aware conversations
- **Auto-Scaling**: AgentCore Runtime automatically scales with demand
- **Session Isolation**: Each user gets isolated sessions for security and privacy
- **Maintainability**: Infrastructure as Code enables version control and reproducible deployments

### Use Cases
1. **Enterprise Knowledge Management**: Internal chatbot with long-term memory for employee knowledge base queries
2. **Customer Support**: AI-powered customer service with conversation history and company documentation
3. **Document Analysis**: Conversational interface for searching and analyzing documents with context retention
4. **Technical Documentation**: Interactive assistant for product documentation with user preference learning
5. **Compliance and Policy**: Q&A system for regulatory and policy documents with audit trails

## Architecture

### Architecture Diagram
See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture diagrams.

### Core Components
- **Amazon Bedrock AgentCore Runtime**: Containerized AI agent with Claude Sonnet 4 (Strands SDK)
- **Amazon Bedrock AgentCore Memory**: Short-term and long-term memory with extraction strategies
- **Amazon Bedrock Knowledge Base**: Vector storage with OpenSearch Serverless for RAG
- **AWS Lambda**: Serverless compute for API handlers
- **Amazon API Gateway**: RESTful API with authentication
- **AWS Cognito**: User authentication and authorization (integrated with AgentCore)
- **Amazon S3**: Document storage and static website hosting
- **Amazon CloudFront**: Content delivery network for web interface
- **AWS KMS**: Encryption for all data stores

### Technology Stack
- **Infrastructure**: AWS CDK (TypeScript) with AgentCore Alpha constructs
- **Agent Framework**: Strands Agents SDK (Python)
- **Backend**: Node.js 20.x, AWS SDK v3
- **Frontend**: Next.js, React, TypeScript
- **AI/ML**: Amazon Bedrock (Claude Sonnet 4)
- **Vector Database**: OpenSearch Serverless
- **Memory**: AgentCore Memory with built-in strategies

### AgentCore Components

#### AgentCore Runtime
The Runtime hosts containerized AI agents that:
- Auto-scale based on demand
- Provide session isolation per user
- Support framework-agnostic agent implementations
- Integrate natively with Cognito authentication

#### AgentCore Memory
The Memory service provides:
- **Short-term Memory (STM)**: Conversation context within sessions
- **Long-term Memory (LTM)**: Persistent facts, preferences, and summaries
- **Built-in Extraction Strategies**:
  - Semantic: Extracts facts and concepts
  - User Preference: Learns user preferences
  - Summarization: Compresses conversation history

## Prerequisites

### AWS Account Requirements
- AWS Account with Bedrock access enabled
- Bedrock model access for Claude Sonnet 4
- AgentCore service access (may require allowlisting)
- Service quotas sufficient for deployment (see [DEPLOYMENT.md](./DEPLOYMENT.md))

### Technical Prerequisites
- Node.js 24.8.0 or later
- npm 10.0.0 or later
- Python 3.12 or later (for agent development)
- Docker installed and running (for building the AgentCore Runtime container)
- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed (`npm install -g aws-cdk`)

### Knowledge Requirements
- Basic understanding of AWS services
- Familiarity with Infrastructure as Code concepts
- Basic knowledge of TypeScript/JavaScript
- Basic knowledge of Python (for agent customization)
- Understanding of REST APIs

## Deployment

### Deployment Time
- **Initial Setup**: 15-20 minutes
- **Infrastructure Deployment**: 45-60 minutes (includes container build)
- **Total Time**: 60-80 minutes

### Deployment Steps
See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

**Quick Start:**
```bash
# 1. Clone repository
git clone <repository-url>
cd knowledge-base-rag-agent

# 2. Install dependencies
npm install

# 3. Build web console
npm run build --workspace=web-console

# 4. Deploy infrastructure
./scripts/deploy.sh

# 5. Access web interface
# URL provided in deployment outputs
```

### Deployment Validation
- Health check endpoint returns 200 OK
- Cognito user pool created with admin user
- CloudFront distribution serving web interface
- AgentCore Runtime deployed and healthy
- AgentCore Memory configured with extraction strategies
- Knowledge Base deployed with OpenSearch Serverless
- API Gateway endpoints accessible

## Cost Estimation

### Monthly Cost Breakdown (Development/Demo)
- **AgentCore Runtime**: $20-80 (usage-based, auto-scaling)
- **AgentCore Memory**: $5-20 (storage and extraction)
- **Amazon Bedrock**: $10-50 (usage-based, ~1000 requests)
- **OpenSearch Serverless**: $50-150 (2 OCUs minimum)
- **AWS Lambda**: $1-5 (1M requests free tier)
- **API Gateway**: $1-10 (1M requests free tier)
- **Amazon S3**: $1-5 (storage and requests)
- **Amazon CloudFront**: $1-10 (data transfer)
- **AWS Cognito**: Free tier (up to 50,000 MAUs)
- **AWS KMS**: $1-5 (key usage)

**Estimated Total**: $88-320/month for development/demo usage

### Production Cost Considerations
- AgentCore Runtime scales automatically with usage
- Memory costs scale with conversation volume and retention
- Bedrock costs scale with usage (per 1K input/output tokens)
- OpenSearch Serverless scales with data volume and query load
- Consider Reserved Capacity for predictable workloads
- Implement caching strategies to reduce API calls
- Monitor and optimize using AWS Cost Explorer

### Cost Optimization Strategies
- Configure appropriate memory expiration (default 90 days)
- Use CloudFront caching to reduce origin requests
- Implement API response caching in API Gateway
- Set appropriate TTLs for Knowledge Base queries
- Use S3 Intelligent-Tiering for document storage
- Monitor and right-size OpenSearch Serverless capacity

## Security

### Security Features
- **Authentication**: AWS Cognito with native AgentCore integration
- **Session Isolation**: Each user gets isolated agent sessions
- **Authorization**: IAM roles with least privilege
- **Encryption at Rest**: All data stores encrypted with AWS KMS
- **Encryption in Transit**: TLS 1.2+ for all communications
- **Memory Encryption**: AgentCore Memory encrypted with customer-managed KMS key
- **Network Security**: VPC isolation for sensitive resources
- **Audit Logging**: CloudWatch Logs and CloudTrail

### Compliance Considerations
- **GDPR**: Data residency controls, encryption, audit trails, memory expiration
- **HIPAA**: Encryption, access controls, audit logging (requires BAA)
- **SOC 2**: Comprehensive logging and monitoring
- **PCI DSS**: Encryption and access controls for sensitive data

### Security Best Practices
- Enable MFA for all user accounts
- Rotate credentials regularly
- Review IAM policies periodically
- Enable CloudTrail for audit logging
- Implement least privilege access
- Configure appropriate memory retention policies
- Regular security assessments with AWS Security Hub

See [SECURITY.md](./SECURITY.md) for detailed security implementation.

## Operations

### Monitoring and Observability
- **CloudWatch Metrics**: Lambda performance, API Gateway requests, AgentCore invocations
- **CloudWatch Logs**: Application logs, error tracking, audit trails
- **CloudWatch Alarms**: Automated alerting for critical issues
- **AWS X-Ray**: Distributed tracing for request flows
- **AgentCore Metrics**: Runtime health, session counts, memory usage

### Maintenance Requirements
- **Regular Updates**: Keep dependencies and CDK versions current
- **Security Patches**: Apply security updates promptly
- **Backup Strategy**: S3 versioning for documents, Memory retention policies
- **Disaster Recovery**: Multi-region deployment for critical workloads

### Troubleshooting
See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues and solutions.

## Testing

### Testing Strategy
- **Unit Tests**: Component-level testing
- **Integration Tests**: API endpoint testing
- **Security Tests**: Authentication and authorization validation
- **Performance Tests**: Load testing for scalability

### Test Coverage
- Authentication flows with Cognito
- API endpoints
- AgentCore Runtime invocation
- Memory persistence and retrieval
- Knowledge Base queries
- Error handling

## Customization

### Configuration Options
- **Model Selection**: Choose different Bedrock models (Claude Sonnet 4 default)
- **Memory Strategies**: Configure extraction strategies for long-term memory
- **Knowledge Base**: Configure embedding models and vector storage
- **Authentication**: Customize Cognito user pool settings
- **API**: Add custom endpoints and integrations
- **UI**: Customize web interface branding and features

### Agent Customization
The agent code is in `infrastructure/agent/` and uses the Strands SDK:
- `src/agent.py`: Main agent definition with tools
- `src/memory.py`: Memory manager for STM/LTM integration
- `src/tools/`: Custom tools for the agent

### Extension Points
- Add custom tools to the Strands agent
- Implement custom memory extraction strategies
- Integrate additional AWS services (SageMaker, Comprehend, etc.)
- Implement custom authentication providers
- Add monitoring and alerting integrations
- Extend Knowledge Base with additional data sources

## Support and Resources

### Documentation
- [README.md](../README.md) - Project overview and quick start
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed architecture
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment guide
- [API_USAGE.md](./API_USAGE.md) - API reference
- [SECURITY.md](./SECURITY.md) - Security implementation
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues

### AWS Resources
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore CDK Alpha](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock_agentcore_alpha/)
- [Strands Agents SDK](https://strandsagents.com/)
- [AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [OpenSearch Serverless Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)
- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)

### Community and Support
- GitHub Issues for bug reports and feature requests
- AWS Support for production deployments
- AWS re:Post for community discussions

## License

This project is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

## Contributing

Contributions are welcome! Please see the contributing guidelines in the repository.

## Changelog

See [CURRENT_STATUS.md](./CURRENT_STATUS.md) for deployment status and recent updates.

## Authors

AWS Professional Services

## Version

2.0.0 - AgentCore Migration

## Tags

`amazon-bedrock`, `agentcore`, `conversational-ai`, `knowledge-base`, `rag`, `aws-cdk`, `serverless`, `chatbot`, `ai-ml`, `generative-ai`, `claude`, `strands-agents`, `memory`

## Related Guidance

- AWS Well-Architected Framework
- Serverless Application Lens
- Machine Learning Lens
- Security Pillar

## Feedback

We welcome feedback on this guidance. Please submit issues or suggestions through the repository's issue tracker.
