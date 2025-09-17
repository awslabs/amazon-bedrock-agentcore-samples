# Browser Tool with Strands Framework

## Overview

This directory contains tutorials and examples for using Amazon Bedrock AgentCore Browser Tool with the Strands agentic framework. Strands provides a powerful orchestration layer for building complex AI agents that can coordinate multiple tools and services.

## What is Strands?

Strands is an enterprise-grade agentic framework that excels at:

- **Agent Orchestration**: Coordinating multiple AI agents and tools in complex workflows
- **Service Integration**: Seamlessly connecting with various AWS services and external APIs
- **Workflow Management**: Building sophisticated multi-step automation processes
- **Error Handling**: Robust error recovery and retry mechanisms
- **State Management**: Maintaining context across complex agent interactions

## Integration with AgentCore Browser Tool

The combination of Strands and AgentCore Browser Tool provides:

- **Secure Browser Automation**: Enterprise-grade browser sessions with VM-level isolation
- **Intelligent Orchestration**: Strands agents that can make decisions about browser interactions
- **Scalable Architecture**: Automatic scaling of browser sessions based on demand
- **Comprehensive Monitoring**: Built-in observability for both agent logic and browser actions
- **Multi-Modal Processing**: Combining browser interactions with AI analysis

## Tutorials Available

### 🤖 CAPTCHA Handling
**Location**: `captcha-handling/`

Learn how to build Strands agents that can intelligently detect and solve various types of CAPTCHAs using AgentCore Browser Tool's secure browser sessions.

**Key Features**:
- Multi-strategy CAPTCHA detection (reCAPTCHA, hCaptcha, generic)
- AI-powered CAPTCHA analysis using Bedrock vision models
- Strands workflow orchestration for complex CAPTCHA scenarios
- Enterprise security and compliance patterns

**Prerequisites**: 
- [Strands Production Integration](../../../03-integrations/01-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands/README.md)
- [Strands Agents with Bedrock Models](../../../01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/README.md)
- [AgentCore Browser Tool Basics](../README.md)

### 🔐 Handling Sensitive Information
**Location**: `handling-sensitive-information/`

Discover how to safely handle sensitive data in browser automation scenarios using Strands agents with AgentCore Browser Tool's security features.

**Key Features**:
- Secure form filling with sensitive data protection
- Enterprise authentication workflows
- Data masking and privacy preservation
- Audit trails and compliance logging

**Prerequisites**:
- [Strands Production Integration](../../../03-integrations/01-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands/README.md)
- [AgentCore Identity](../../../03-AgentCore-identity/README.md)
- [Strands Agents with Bedrock Models](../../../01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/README.md)

## Getting Started

### Prerequisites

Before starting with Strands and AgentCore Browser Tool integration, ensure you have:

1. **AWS Account Setup**:
   - Access to Amazon Bedrock with appropriate model permissions
   - AgentCore Browser Tool service access
   - Proper IAM roles and policies configured

2. **Development Environment**:
   - Python 3.9+ with virtual environment capabilities
   - AWS CLI configured with appropriate permissions
   - Jupyter Notebook for interactive tutorials

3. **Framework Knowledge**:
   - Basic understanding of Strands framework concepts
   - Familiarity with AgentCore Browser Tool basics
   - Experience with AWS Bedrock models

### Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS Credentials**:
   ```bash
   aws configure
   # or set environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

3. **Verify Setup**:
   ```bash
   python -c "import strands; import agentcore_browser_tool; print('Setup complete!')"
   ```

## Architecture Overview

The Strands + AgentCore Browser Tool integration follows a three-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Strands Agent Layer                     │
│  (Decision Making, Workflow Orchestration, Error Handling) │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                AgentCore Browser Tool Layer                 │
│     (Secure Browser Sessions, VM Isolation, Scaling)       │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Bedrock AI Layer                        │
│        (Vision Models, Text Analysis, Decision Support)     │
└─────────────────────────────────────────────────────────────┘
```

## Key Benefits

### Enterprise Security
- **VM-Level Isolation**: Each browser session runs in its own secure virtual machine
- **Data Protection**: Sensitive information is handled with enterprise-grade security
- **Audit Trails**: Comprehensive logging for compliance and debugging
- **Access Control**: Fine-grained permissions and authentication

### Intelligent Automation
- **AI-Powered Decisions**: Strands agents make intelligent choices about browser interactions
- **Adaptive Workflows**: Dynamic adjustment based on page content and conditions
- **Multi-Modal Processing**: Combining text, images, and browser state for decision making
- **Context Awareness**: Maintaining state across complex multi-step processes

### Production Ready
- **Automatic Scaling**: Browser sessions scale based on demand
- **Error Recovery**: Robust error handling and retry mechanisms
- **Monitoring**: Built-in observability and performance metrics
- **Cost Optimization**: Pay-per-use pricing model for browser sessions

## Learning Path

### Beginner Path
1. Start with [AgentCore Browser Tool Basics](../README.md)
2. Complete [Strands with Bedrock Models](../../../01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/README.md)
3. Try the basic examples in `captcha-handling/` or `handling-sensitive-information/`

### Intermediate Path
1. Explore advanced CAPTCHA handling scenarios
2. Implement custom Strands tools for browser automation
3. Build multi-step workflows with error recovery

### Advanced Path
1. Create production-ready agents with comprehensive monitoring
2. Implement custom security and compliance patterns
3. Build scalable architectures for enterprise deployment

## Integration with AgentCore Ecosystem

This framework integrates seamlessly with other AgentCore components:

- **[AgentCore Runtime](../../../01-AgentCore-runtime/README.md)**: Deploy Strands agents to production
- **[AgentCore Memory](../../../04-AgentCore-memory/README.md)**: Persistent learning and context
- **[AgentCore Identity](../../../03-AgentCore-identity/README.md)**: Secure authentication
- **[AgentCore Observability](../../../06-AgentCore-observability/README.md)**: Monitoring and debugging
- **[AgentCore Gateway](../../../02-AgentCore-gateway/README.md)**: API integration and management

## Support and Resources

- **Strands Documentation**: [Link to Strands framework docs]
- **AgentCore Browser Tool**: [Link to AgentCore Browser Tool documentation]
- **AWS Bedrock**: [Link to Bedrock documentation]
- **Community Support**: [Link to community forums]

## Next Steps

1. **Choose Your Learning Path**: Select tutorials based on your experience level
2. **Set Up Environment**: Follow the installation and configuration steps
3. **Start with Basics**: Begin with either CAPTCHA handling or sensitive information tutorials
4. **Explore Advanced Features**: Progress to complex workflows and production patterns
5. **Join the Community**: Connect with other developers and share your experiences

---

**Note**: This directory focuses on Strands-specific implementation patterns. For framework comparisons and alternative approaches, explore the other browser tool tutorials in the parent directory.