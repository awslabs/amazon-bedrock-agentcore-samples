# Browser Tool with Strands Integration

**Production-Ready Integration Package**

## Overview

This package provides a complete, production-ready integration between AWS Bedrock AgentCore's browser capabilities and the Strands agent framework, enabling AI agents to perform intelligent web browsing and content analysis in enterprise environments.

> **📚 Learning Resources**: For tutorials and step-by-step learning materials, see the [Browser Tool with Strands Tutorial](../../../../01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands/README.md) which builds upon this production integration.

## Integration Details

| **Attribute**           | **Value**                                                    |
|-------------------------|--------------------------------------------------------------|
| **Status**              | Production-Ready                                             |
| **Complexity**          | Enterprise-Grade                                             |
| **Prerequisites**       | Python 3.10+, AWS account with Bedrock access, Production environment |
| **AgentCore components**| AgentCore Browser Tool                                       |
| **Agentic Framework**   | Strands Agents                                              |
| **LLM model**           | Anthropic Claude 3.5 Sonnet v2 (via AWS Bedrock)          |
| **Integration components** | Complete browser tool integration, AI-powered web analysis, Enterprise security |
| **Use cases**           | Cross-vertical (applicable to multiple domains)            |

## What This Integration Provides

- **Complete Production Integration**: Full Strands agents integration with AWS Bedrock AgentCore browser tools
- **Enterprise-Ready Components**: Production-grade AI agents for web browsing and content analysis
- **Advanced Content Extraction**: Multiple content extraction modes (text, HTML, metadata) with enterprise security
- **Intelligent Research Workflows**: Production-ready research agents with comprehensive error handling
- **Deployment-Ready Code**: Complete implementation with monitoring, logging, and production deployment patterns

## Architecture

```
User Request → Strands Agent → Browser Tool → Bedrock AgentCore → AWS Browser Instance → Web Content
                    ↓              ↓              ↓                    ↓                ↓
              AI Analysis ← Content Extract ← Browser Automation ← JavaScript Execution ← Target Website
```

For a comprehensive architecture overview including detailed component diagrams, data flow, security architecture, and deployment patterns, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Prerequisites

### AWS Requirements
- AWS account with active subscription
- AWS Bedrock service access enabled
- IAM permissions for Bedrock model invocation
- Access to Anthropic Claude models in Bedrock

### Development Environment
- Python 3.10 or higher (required for Strands agents)
- Virtual environment capability
- Internet connectivity for package installation

### Knowledge Requirements
- Basic Python programming
- Understanding of AI agents and tools
- Familiarity with AWS services (helpful but not required)

## Setup Instructions

### Step 1: Quick Setup (Recommended)

```bash
# Run the automated setup script
chmod +x setup.sh
./setup.sh
```

### Step 1: Manual Setup (Alternative)

```bash
# Ensure Python 3.10+ is installed
python3 --version  # Should show 3.10 or higher

# Create and activate virtual environment
python3 -m venv venv_310
source venv_310/bin/activate  # On Windows: venv_310\Scripts\activate

# Install required packages
pip install -r requirements.txt

# Install Playwright browsers (required for browser automation)
playwright install
```

### Step 2: AWS Configuration

```bash
# Option 1: Use AWS CLI
aws configure

# Option 2: Set environment variables
cp .env.template .env
# Edit .env with your AWS credentials
```

### Step 3: Verify Setup

```bash
# Activate virtual environment (if not already active)
source venv_310/bin/activate

# Test basic functionality
python bedrock_strands_browser_tool.py

# Run comprehensive integration tests
python test_integration.py
```

## Implementation

### Core Integration Code

The main integration is implemented in `bedrock_strands_browser_tool.py`:

```python
from strands import tool
from bedrock_agentcore.tools.browser_client import browser_session
import requests
from bs4 import BeautifulSoup

@tool
def browse_web(url: str, extract_mode: str = "text") -> str:
    """Browse a web page and extract content using Bedrock AgentCore foundation."""
    # Implementation details in the actual file
```

### Key Features

1. **Multiple Extraction Modes**:
   - `text`: Clean text content extraction
   - `html`: Full HTML content preservation
   - `metadata`: Page metadata (title, status, etc.)

2. **Robust Error Handling**:
   - Invalid URL validation
   - Network connectivity issues
   - AWS authentication errors
   - Timeout management

3. **AWS Integration**:
   - Bedrock AgentCore session management
   - AWS credential handling
   - Regional configuration support

## Usage Examples

### Basic Web Browsing

```python
from bedrock_strands_browser_tool import browse_web

# Extract text content
content = browse_web("https://example.com", "text")
print(content)
```

### AI Agent Integration

```python
from strands import Agent
from bedrock_strands_browser_tool import browse_web

# Create intelligent browsing agent
agent = Agent(
    tools=[browse_web],
    model="anthropic.claude-instant-v1"
)

# Use natural language to browse and analyze
result = agent("Browse https://example.com and summarize the key information")
print(result)
```

### Advanced Research Workflow

```python
# Multi-step research agent
research_agent = Agent(
    tools=[browse_web],
    model="anthropic.claude-instant-v1",
    system_prompt="You are a research analyst."
)

# Comprehensive company analysis
analysis = research_agent("""
Research Tesla by:
1. Browsing their main website
2. Analyzing recent news
3. Providing strategic insights
""")
```

## Use Cases

### 1. Competitive Intelligence
- Automated competitor website analysis
- Product and pricing information extraction
- Market positioning assessment

### 2. Market Research
- Industry trend monitoring
- News and announcement tracking
- Regulatory change detection

### 3. Content Curation
- Multi-source content aggregation
- Intelligent content summarization
- Quality assessment and filtering

### 4. Compliance Monitoring
- Regulatory website monitoring
- Policy change detection
- Compliance requirement tracking

## Testing

Run the comprehensive test suite:

```bash
# Basic functionality test
python test_integration.py

# Example usage test
python example_usage.py
```

Expected output:
```
✅ AWS Bedrock connectivity verified
✅ Browser tool integration working
✅ AI agent analysis functional
🎉 All tests passed!
```

## Troubleshooting

### Common Issues

#### AWS Credentials Error
```
Error: AWS authentication failed
```
**Solution**: Verify AWS credentials and IAM permissions for Bedrock.

#### Model Access Error
```
AccessDeniedException: You don't have access to the model
```
**Solution**: Request access to Claude models in AWS Bedrock console.

#### Import Error
```
ModuleNotFoundError: No module named 'strands'
```
**Solution**: Ensure virtual environment is activated and dependencies installed.

## Performance Considerations

- **Concurrent Requests**: Tool supports parallel browsing operations
- **Memory Usage**: Optimized for large-scale content processing
- **Rate Limiting**: Built-in protection against service limits
- **Caching**: Consider implementing caching for frequently accessed content

## Security Best Practices

- Use IAM roles instead of access keys when possible
- Implement input validation for URLs and parameters
- Monitor and log all browsing activities
- Set appropriate timeout values to prevent hanging requests

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "example_usage.py"]
```

### AWS Lambda Deployment
```python
import json
from bedrock_strands_browser_tool import browse_web

def lambda_handler(event, context):
    url = event['url']
    result = browse_web(url)
    return {'statusCode': 200, 'body': json.dumps({'result': result})}
```

## Related Resources

- **[Tutorial Materials](../../../../01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands/README.md)**: Step-by-step learning materials that build upon this integration
- **[AgentCore Browser Tool Overview](../README.md)**: General browser tool documentation and other framework integrations
- **[AgentCore Runtime](../../../../01-tutorials/01-AgentCore-runtime/README.md)**: Deploy this integration to production environments
- **[AgentCore Identity](../../../../01-tutorials/03-AgentCore-identity/README.md)**: Enhance with secure authentication capabilities

## Next Steps

1. **Deploy to Production**: Use this integration as the foundation for your production deployment
2. **Customize for Your Domain**: Extend the provided components for specific use cases
3. **Scale Your Implementation**: Leverage the built-in scaling and monitoring capabilities
4. **Integrate with AgentCore Ecosystem**: Connect with other AgentCore services and tools

## Contributing

This tutorial is part of the AWS Labs AgentCore samples. To contribute improvements:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description

## License

This sample code is made available under the MIT-0 license. See the LICENSE file.

## Support

For issues related to this tutorial:
- Check the troubleshooting section above
- Review AWS Bedrock documentation
- Submit issues to the main repository

---

**Built with AWS Bedrock AgentCore and Strands Agents**