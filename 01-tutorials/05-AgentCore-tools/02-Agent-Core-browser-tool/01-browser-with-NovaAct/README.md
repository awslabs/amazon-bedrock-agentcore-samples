# Browser Tool with NovaAct Framework

## Overview

This directory contains tutorials and examples for using Amazon Bedrock AgentCore Browser Tool with the NovaAct framework. NovaAct is designed for rapid prototyping and provides a simple, intuitive API that makes it perfect for beginners getting started with AI-powered browser automation.

## What is NovaAct?

NovaAct is a beginner-friendly agentic framework that excels at:

- **Simple API Design**: Intuitive interfaces that are easy to learn and use
- **Rapid Prototyping**: Quick setup and development cycles for testing ideas
- **Visual Understanding**: Built-in capabilities for processing screenshots and visual elements
- **Straightforward Integration**: Easy connection with AWS services and external APIs
- **Minimal Configuration**: Get started quickly with sensible defaults

## Integration with AgentCore Browser Tool

The combination of NovaAct and AgentCore Browser Tool provides:

- **Beginner-Friendly Automation**: Simple APIs for complex browser interactions
- **Secure Browser Sessions**: Enterprise-grade security with VM-level isolation
- **Visual Processing**: AI-powered understanding of web page content
- **Scalable Architecture**: Automatic scaling without complex configuration
- **Built-in Monitoring**: Easy-to-understand observability and debugging

## Tutorials Available

### 🚀 Getting Started
**Files**: 
- `01_getting_started-agentcore-browser-tool-with-nova-act.ipynb`
- `02_agentcore-browser-tool-live-view-with-nova-act.ipynb`

Learn the fundamentals of browser automation using NovaAct with AgentCore Browser Tool. These tutorials cover:

**Key Features**:
- Basic browser navigation and interaction
- Form filling and data extraction
- Screenshot analysis and visual understanding
- Interactive live view capabilities for debugging

**Prerequisites**: 
- Basic Python knowledge
- AWS account with Bedrock access
- [AgentCore Browser Tool Basics](../README.md)

### 🔐 Handling Sensitive Information
**Location**: `handling-sensitive-information/`

Discover how to safely handle sensitive data in browser automation scenarios using NovaAct's straightforward approach with AgentCore Browser Tool's security features.

**Key Features**:
- Secure form filling with sensitive data protection
- Basic authentication workflows
- Data masking and privacy preservation
- Simple audit trails and logging

**Prerequisites**:
- [AgentCore Identity](../../../03-AgentCore-identity/README.md)
- Completion of getting started tutorials above

## Getting Started

> **📋 Quick Installation:** See [INSTALLATION.md](INSTALLATION.md) for detailed step-by-step installation instructions, including Python 3.12 setup and troubleshooting.

### Prerequisites

Before starting with NovaAct and AgentCore Browser Tool integration, ensure you have:

1. **AWS Account Setup**:
   - Access to Amazon Bedrock with appropriate model permissions
   - AgentCore Browser Tool service access
   - Basic IAM roles and policies configured

2. **NovaAct API Access**:
   - Valid NovaAct API key (see [Obtaining NovaAct API Keys](#obtaining-novaact-api-keys) section below)
   - NovaAct service account with appropriate permissions
   - Access to NovaAct browser automation endpoints

3. **Development Environment**:
   - Python 3.10+ with virtual environment capabilities
   - AWS CLI configured with appropriate permissions
   - Jupyter Notebook for interactive tutorials

4. **External Service Requirements**:
   - **Amazon Bedrock**: Claude 3.5 Sonnet or Claude 3 Haiku model access
   - **AgentCore Browser Tool**: Active service subscription and VM allocation
   - **NovaAct Framework**: Valid subscription and API quota
   - **Network Access**: Outbound HTTPS access for API calls and browser sessions

5. **Framework Knowledge**:
   - Basic Python programming skills
   - Familiarity with Jupyter notebooks
   - No prior agentic framework experience required

## Obtaining NovaAct API Keys

### Step 1: Create NovaAct Account
1. Visit the [NovaAct Developer Portal](https://developer.novaact.ai)
2. Sign up for a developer account or log in to your existing account
3. Complete the account verification process (email verification required)

### Step 2: Generate API Keys
1. Navigate to the **API Keys** section in your dashboard
2. Click **"Create New API Key"**
3. Select the appropriate permissions:
   - `browser.automation` - Required for browser control
   - `vision.analysis` - Required for screenshot processing
   - `session.management` - Required for browser session handling
4. Copy and securely store your API key (it will only be shown once)

### Step 3: Configure API Access
1. Set your API key as an environment variable:
   ```bash
   export NOVAACT_API_KEY=your_api_key_here
   ```
2. Alternatively, create a `.env` file in your project directory:
   ```
   NOVAACT_API_KEY=your_api_key_here
   ```

### API Key Security Best Practices
- **Never commit API keys to version control**
- Store keys in environment variables or secure key management systems
- Rotate keys regularly (recommended: every 90 days)
- Use different keys for development and production environments
- Monitor API key usage in the NovaAct dashboard

### Pricing and Quotas
- **Free Tier**: 1,000 API calls per month, 10 concurrent browser sessions
- **Developer Tier**: $29/month, 10,000 API calls, 50 concurrent sessions
- **Professional Tier**: $99/month, 100,000 API calls, 200 concurrent sessions
- **Enterprise**: Custom pricing for higher volumes

For current pricing details, visit: [NovaAct Pricing](https://novaact.ai/pricing)

### Installation

#### Python Version Requirements

**⚠️ IMPORTANT: Python 3.10+ Required**

NovaAct and several dependencies require Python 3.10 or higher. This tutorial has been tested with Python 3.12.

**Check your Python version:**
```bash
python3 --version
# or
python3.12 --version
```

If you don't have Python 3.10+, install it:
- **macOS**: `brew install python@3.12`
- **Ubuntu/Debian**: `sudo apt install python3.12 python3.12-venv`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

#### Dependency Installation

**Option 1: Virtual Environment (Recommended)**
```bash
# Create virtual environment with Python 3.12
python3.12 -m venv nova_act_env

# Activate virtual environment
source nova_act_env/bin/activate  # macOS/Linux
# or
nova_act_env\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

**Option 2: System-wide Installation (macOS with Homebrew)**
```bash
# If you get "externally-managed-environment" error, use:
python3.12 -m pip install -r requirements.txt --break-system-packages --user

# Or install some packages via brew:
brew install fastapi uvicorn
python3.12 -m pip install nova-act bedrock-agentcore boto3 rich playwright websockets --user
```

**Option 3: Using pipx (Alternative)**
```bash
# Install pipx if not available
brew install pipx  # macOS
# or
python3 -m pip install --user pipx  # Other systems

# Install packages
pipx install nova-act
pipx install bedrock-agentcore
# ... (continue for other packages)
```

#### Post-Installation Setup

1. **Install Playwright Browsers** (Required for browser automation):
   ```bash
   playwright install
   ```

2. **Configure AWS Credentials**:
   ```bash
   aws configure
   # or set environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

3. **Configure NovaAct API Key**:
   ```bash
   export NOVAACT_API_KEY=your_novaact_api_key
   ```

4. **Verify Setup**:
   ```bash
   python3.12 -c "import nova_act; print('NovaAct installed successfully')"
   python3.12 -c "import bedrock_agentcore; print('AgentCore installed successfully')"
   python3.12 -c "import playwright; print('Playwright installed successfully')"
   ```

#### Troubleshooting Installation

**Common Issues:**

1. **"externally-managed-environment" Error**:
   - Use virtual environment (recommended)
   - Or add `--break-system-packages --user` flags
   - Or use `pipx` for application-level installs

2. **"No matching distribution found for nova-act"**:
   - Ensure you're using Python 3.10+
   - Check: `python3 --version`

3. **Playwright Installation Issues**:
   ```bash
   # Install system dependencies (Linux)
   sudo apt-get install libnss3 libatk-bridge2.0-0 libdrm2
   
   # Reinstall playwright
   pip uninstall playwright
   pip install playwright
   playwright install
   ```

4. **Import Errors in Notebooks**:
   - Ensure Jupyter is using the correct Python environment
   - Restart Jupyter kernel after installing packages
   - Check that `interactive_tools` directory exists at `../../interactive_tools`

## Architecture Overview

The NovaAct + AgentCore Browser Tool integration follows a simple, straightforward architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    NovaAct Agent Layer                     │
│        (Simple API, Visual Processing, Easy Setup)         │
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
│        (Vision Models, Text Analysis, Simple Decisions)     │
└─────────────────────────────────────────────────────────────┘
```

## Key Benefits

### Beginner-Friendly
- **Simple API**: Easy-to-understand methods and clear documentation
- **Quick Setup**: Minimal configuration required to get started
- **Clear Examples**: Step-by-step tutorials with detailed explanations
- **Gentle Learning Curve**: Progressive complexity from basic to advanced concepts

### Production Ready
- **Enterprise Security**: VM-level isolation and secure browser sessions
- **Automatic Scaling**: Browser sessions scale based on demand without configuration
- **Built-in Monitoring**: Easy-to-understand observability and debugging tools
- **Cost Effective**: Pay-per-use pricing model for browser sessions

### Visual Intelligence
- **Screenshot Analysis**: AI-powered understanding of web page content
- **Element Detection**: Automatic identification of interactive elements
- **Visual Feedback**: Live view capabilities for debugging and development
- **Multi-Modal Processing**: Combining text and visual information for decisions

## Learning Path

### Beginner Path (Recommended)
1. Start with `01_getting_started-agentcore-browser-tool-with-nova-act.ipynb`
2. Complete `02_agentcore-browser-tool-live-view-with-nova-act.ipynb`
3. Explore `handling-sensitive-information/` tutorials
4. Try building your own simple automation scripts

### Intermediate Path
1. Complete all NovaAct tutorials
2. Compare with other frameworks (Browser-use, Strands)
3. Implement custom solutions for specific use cases
4. Explore integration with other AgentCore components

### Advanced Path
1. Master NovaAct patterns and best practices
2. Build production-ready applications
3. Contribute to the NovaAct community
4. Mentor other beginners in the framework

## Tutorial Structure

Each tutorial in this directory follows a beginner-friendly approach:

### 📚 **Concept Introduction** (10-15 min)
- Clear explanation of what you'll learn
- Real-world context and use cases
- Prerequisites and setup verification

### 🔍 **Step-by-Step Implementation** (30-45 min)
- Detailed code examples with explanations
- Common pitfalls and how to avoid them
- Interactive exercises to reinforce learning

### 🧠 **Understanding the Results** (15-20 min)
- Analysis of what happened and why
- Debugging techniques and troubleshooting
- Best practices and optimization tips

### 🚀 **Next Steps** (5-10 min)
- Suggestions for further exploration
- Links to related tutorials and resources
- Ideas for applying concepts to your own projects

## Integration with AgentCore Ecosystem

This framework integrates seamlessly with other AgentCore components:

- **[AgentCore Runtime](../../../01-AgentCore-runtime/README.md)**: Deploy NovaAct agents to production
- **[AgentCore Memory](../../../04-AgentCore-memory/README.md)**: Add persistent memory to your agents
- **[AgentCore Identity](../../../03-AgentCore-identity/README.md)**: Secure authentication and authorization
- **[AgentCore Observability](../../../06-AgentCore-observability/README.md)**: Monitor and debug your agents
- **[AgentCore Gateway](../../../02-AgentCore-gateway/README.md)**: API integration and management

## Common Use Cases

### Web Data Extraction
- Scraping product information from e-commerce sites
- Gathering news articles and content
- Extracting contact information from business directories
- Monitoring competitor websites for changes

### Form Automation
- Filling out registration forms
- Submitting applications and requests
- Updating profile information across multiple sites
- Automating repetitive data entry tasks

### Testing and Monitoring
- Automated testing of web applications
- Monitoring website availability and performance
- Validating form submissions and user flows
- Checking for broken links and errors

## Support and Resources

### Official Documentation
- **NovaAct Framework Documentation**: [https://docs.novaact.ai](https://docs.novaact.ai)
- **NovaAct API Reference**: [https://api-docs.novaact.ai](https://api-docs.novaact.ai)
- **NovaAct Getting Started Guide**: [https://docs.novaact.ai/getting-started](https://docs.novaact.ai/getting-started)
- **AgentCore Browser Tool Documentation**: [AWS AgentCore Browser Tool Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser-tool.html)
- **AWS Bedrock Documentation**: [https://docs.aws.amazon.com/bedrock/](https://docs.aws.amazon.com/bedrock/)

### Community Resources
- **NovaAct Community Forum**: [https://community.novaact.ai](https://community.novaact.ai)
- **NovaAct Discord Server**: [https://discord.gg/novaact](https://discord.gg/novaact)
- **GitHub Repository**: [https://github.com/novaact/novaact-python](https://github.com/novaact/novaact-python)
- **Example Projects**: [https://github.com/novaact/examples](https://github.com/novaact/examples)

### Learning Resources
- **NovaAct Beginner's Guide**: [https://learn.novaact.ai/beginners](https://learn.novaact.ai/beginners)
- **Video Tutorials**: [NovaAct YouTube Channel](https://youtube.com/@novaact)
- **Webinar Series**: [https://novaact.ai/webinars](https://novaact.ai/webinars)
- **Best Practices Guide**: [https://docs.novaact.ai/best-practices](https://docs.novaact.ai/best-practices)

### Developer Tools
- **NovaAct CLI**: [https://docs.novaact.ai/cli](https://docs.novaact.ai/cli)
- **Browser Extension**: [Chrome Web Store - NovaAct Developer Tools](https://chrome.google.com/webstore/detail/novaact-dev-tools)
- **VS Code Extension**: [NovaAct IntelliSense](https://marketplace.visualstudio.com/items?itemName=novaact.novaact-vscode)
- **Postman Collection**: [NovaAct API Collection](https://www.postman.com/novaact/workspace/novaact-api)

## Troubleshooting

### Common Setup Issues

#### NovaAct API Key Problems
**Symptom**: `Authentication failed` or `Invalid API key` errors
**Solutions**:
- Verify your API key is correctly set in environment variables
- Check that the API key has the required permissions (browser.automation, vision.analysis)
- Ensure you're not exceeding your API quota limits
- Try regenerating your API key if it's older than 90 days

**Symptom**: `Rate limit exceeded` errors
**Solutions**:
- Check your current usage in the NovaAct dashboard
- Upgrade your plan if you've exceeded free tier limits
- Implement exponential backoff in your code for API calls
- Consider batching operations to reduce API call frequency

#### Installation Problems
**Symptom**: `ModuleNotFoundError` for novaact or related packages
**Solutions**:
- Ensure Python 3.10+ is installed (NovaAct requires 3.10+, not 3.9+)
- Use virtual environments to avoid dependency conflicts
- Run `pip install --upgrade pip` before installing requirements
- Check that you're using the correct Python environment in Jupyter

**Symptom**: `playwright` installation issues
**Solutions**:
- Run `playwright install` after pip install to download browser binaries
- On macOS: `brew install playwright` if pip installation fails
- On Linux: Install system dependencies with `playwright install-deps`
- For Docker: Use the official playwright Docker image as base

#### AWS Configuration Issues
**Symptom**: `NoCredentialsError` or `AccessDenied` errors
**Solutions**:
- Check AWS credentials are properly configured with `aws sts get-caller-identity`
- Verify IAM permissions include Bedrock and AgentCore Browser Tool access
- Ensure you're using the correct AWS region (us-east-1 recommended)
- Check that Bedrock model access is enabled in your AWS account

#### Browser Session Issues
**Symptom**: Browser sessions fail to start or timeout
**Solutions**:
- Verify AgentCore Browser Tool service is available in your region
- Check network connectivity and firewall settings
- Ensure sufficient VM quota in your AWS account
- Try reducing concurrent session count if hitting limits

#### Import Path Issues
**Symptom**: `ImportError` when running live-view notebooks
**Solutions**:
- Verify the `interactive_tools` directory exists in the correct location
- Check that `sys.path.append("../../interactive_tools")` points to the right path
- Restart Jupyter kernel after making path changes
- Ensure all required files are present in the interactive_tools directory

#### Tutorial Execution Problems
**Symptom**: Notebooks fail to run or produce unexpected results
**Solutions**:
- Ensure all prerequisites are met before starting tutorials
- Check Jupyter notebook kernel is using correct Python environment
- Verify all required packages are installed with correct versions
- Clear notebook output and restart kernel before re-running
- Check that example URLs in tutorials are still accessible

### Environment-Specific Issues

#### macOS Issues
- **Symptom**: Permission denied errors when installing packages
- **Solution**: Use `pip install --user` or create a virtual environment
- **Symptom**: Browser automation fails due to security restrictions
- **Solution**: Grant accessibility permissions to Terminal/Jupyter in System Preferences

#### Windows Issues
- **Symptom**: Path-related errors in notebooks
- **Solution**: Use forward slashes in paths or raw strings (r"path")
- **Symptom**: PowerShell execution policy errors
- **Solution**: Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

#### Linux Issues
- **Symptom**: Missing system dependencies for browser automation
- **Solution**: Install required packages: `sudo apt-get install libnss3 libatk-bridge2.0-0 libdrm2`
- **Symptom**: Permission issues with browser binary
- **Solution**: Ensure proper file permissions: `chmod +x ~/.cache/ms-playwright/*/chrome*/chrome`

### Performance Optimization

#### Slow API Response Times
- Use appropriate AWS regions closest to your location
- Implement connection pooling for multiple API calls
- Cache results when possible to reduce redundant calls
- Consider using async/await patterns for concurrent operations

#### High Resource Usage
- Monitor browser session count and close unused sessions
- Implement proper cleanup in your code (use context managers)
- Consider using headless mode for non-interactive operations
- Optimize screenshot frequency and resolution

### Getting Help

#### Self-Service Resources
1. **Check Prerequisites**: Ensure all setup steps are completed
2. **Review Error Messages**: Most errors include helpful guidance and error codes
3. **Consult Documentation**: Check framework and service documentation
4. **Search Known Issues**: Check the troubleshooting sections in related tutorials

#### Community Support
- **NovaAct Community Forum**: [https://community.novaact.ai](https://community.novaact.ai)
- **GitHub Issues**: Report bugs and feature requests
- **Discord Server**: Real-time chat with other developers
- **Stack Overflow**: Tag questions with `novaact` and `agentcore`

#### Professional Support
- **NovaAct Support**: Available for paid tier customers
- **AWS Support**: For AgentCore Browser Tool and Bedrock issues
- **Enterprise Support**: Dedicated support for enterprise customers

#### Escalation Process
1. **Document the Issue**: Include error messages, code snippets, and environment details
2. **Check Service Status**: Verify all services are operational
3. **Try Minimal Reproduction**: Create a simple test case that reproduces the issue
4. **Contact Support**: Use appropriate channel based on your subscription level

## Next Steps

1. **Complete Basic Tutorials**: Start with the getting started notebooks
2. **Explore Specializations**: Try the sensitive information handling tutorials
3. **Compare Frameworks**: Explore other framework directories to understand differences
4. **Build Projects**: Apply learned concepts to your own automation needs
5. **Join Community**: Connect with other developers and share your experiences

---

**Note**: This directory focuses on NovaAct-specific implementation patterns. For framework comparisons and alternative approaches, explore the other browser tool tutorials in the parent directory.