# 🚀 Quick Start: LlamaIndex + AgentCore Browser Tool

## 5-Minute Integration Setup

This guide shows you how to get LlamaIndex agents working with AWS Bedrock AgentCore Browser Tool in 5 minutes.

## 📋 What's Included in This Integration

### ✅ **Complete Production Integration**
- **Real LlamaIndex Tools**: `NavigationTool`, `TextExtractionTool`, `ScreenshotTool`, `ElementClickTool`
- **Advanced CAPTCHA Handling**: AI-powered CAPTCHA detection and solving using Bedrock vision models
- **Document Processing**: Convert web content to LlamaIndex documents with metadata
- **Incremental Processing**: Track content changes over time for efficient updates
- **Security & Privacy**: Enterprise-grade PII scrubbing and audit logging
- **Error Handling**: Robust retry mechanisms and graceful degradation
- **Monitoring**: Built-in observability and performance metrics

### 🏗️ **Architecture Components**
- **25+ Python modules** working together seamlessly
- **Configuration management** with YAML/JSON support
- **Hybrid browser client** (AgentCore + local fallback)
- **Workflow orchestration** for complex multi-step operations
- **Vision model integration** for AI-powered web analysis

## 🛠️ **Prerequisites**

### Required Services
- **AWS Account** with Bedrock access
- **AgentCore Browser Tool** service access
- **Python 3.12+** environment

### Required Permissions
- AWS Bedrock model invocation (Claude models)
- AgentCore Browser Tool API access
- AWS Secrets Manager (for credential storage)

## ⚡ **Quick Setup**

### Step 1: Install Dependencies (2 minutes)

```bash
# Navigate to the integration directory
cd 03-integrations/01-AgentCore-tools/02-Agent-Core-browser-tool/04-browser-with-LlamaIndex

# Install Python dependencies
pip install -r requirements.txt

# Verify Python version (3.12+ required)
python --version
```

### Step 2: Configure AWS Credentials (1 minute)

```bash
# Method 1: AWS CLI (recommended)
aws configure

# Method 2: Environment variables
export AWS_ACCESS_KEY_ID=your_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_here
export AWS_REGION=us-east-1

# Method 3: Use AWS profile
export AWS_PROFILE=your-profile-name
```

### Step 3: Create Configuration File (1 minute)

```bash
# Copy the example configuration
cp config.example.yaml config.yaml

# Edit with your specific settings
nano config.yaml  # or your preferred editor
```

**Minimum required configuration:**
```yaml
aws_credentials:
  region: us-east-1
  profile: default  # or your AWS profile

agentcore_endpoints:
  base_url: https://your-agentcore-endpoint.amazonaws.com
  # Get this from your AgentCore deployment

llm_model: anthropic.claude-3-sonnet-20240229-v1:0
vision_model: anthropic.claude-3-sonnet-20240229-v1:0
```

### Step 4: Test the Integration (1 minute)

```bash
# Test basic functionality
python test_integration.py

# Expected output (with real endpoints):
# ✅ Full integration test completed successfully!
# All document processing features are working with AgentCore browser tool.
```

### Step 5: Create Your First Agent (30 seconds)

Create `my_first_llamaindex_agent.py`:

```python
from integration import LlamaIndexAgentCoreIntegration
from llama_index.core.agent import ReActAgent

# Initialize the integration
integration = LlamaIndexAgentCoreIntegration(config_path="config.yaml")

# Get LlamaIndex tools
tools = integration.get_llamaindex_tools()

# Create an intelligent browsing agent
agent = ReActAgent.from_tools(
    tools=tools,
    llm=integration.get_llm(),
    verbose=True
)

# Use the agent to browse and analyze websites
response = agent.chat("Browse https://example.com and summarize the main content")
print(f"Agent Response: {response}")
```

Run it:
```bash
python my_first_llamaindex_agent.py
```

## 🎯 **What Just Happened?**

You've successfully created a complete integration where:

1. **LlamaIndex Agent** receives your natural language request
2. **LlamaIndex Tools** translate the request into browser operations
3. **AgentCore Browser Client** launches a secure AWS-hosted browser
4. **Browser automation** navigates to websites and extracts content
5. **Document processing** converts web content to LlamaIndex documents
6. **AI analysis** provides intelligent responses using Bedrock models

## 🔄 **Complete Data Flow**

```mermaid
graph LR
    A[Your Query] --> B[LlamaIndex Agent]
    B --> C[LlamaIndex Tools]
    C --> D[AgentCore Browser Client]
    D --> E[AWS Browser Instance]
    E --> F[Website Content]
    F --> G[Document Processing]
    G --> H[LlamaIndex Documents]
    H --> I[AI Analysis]
    I --> J[Intelligent Response]
```

## 🚀 **Advanced Usage Examples**

### CAPTCHA Handling
```python
from captcha_tools import create_captcha_tools

# Add CAPTCHA solving capabilities
captcha_tools = create_captcha_tools(integration.browser_client)
all_tools = integration.get_llamaindex_tools() + captcha_tools

agent = ReActAgent.from_tools(tools=all_tools, llm=integration.get_llm())
response = agent.chat("Navigate to a site with CAPTCHA and solve it")
```

### Document Processing Pipeline
```python
from document_processor import DocumentPipeline

async def process_multiple_sites():
    async with DocumentPipeline(config_path="config.yaml") as pipeline:
        urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
        results = await pipeline.process_multiple_urls(urls)
        documents = pipeline.get_successful_documents(results)
        return documents

# Use in your application
documents = asyncio.run(process_multiple_sites())
```

### Incremental Content Monitoring
```python
from incremental_processor import IncrementalProcessor

processor = IncrementalProcessor(config_path="config.yaml")

# Monitor a site for changes
result = await processor.process_url_incremental("https://news-site.com")
if result.change_detection.changes_detected:
    print(f"Changes detected: {result.change_detection.change_summary}")
```

## 🛠️ **Configuration Options**

### Test Mode (for development)
```yaml
test_mode: true  # Enables simulation mode without real AWS services
```

### Security Settings
```yaml
enable_input_sanitization: true
enable_pii_scrubbing: true
audit_logging: true
```

### Browser Configuration
```yaml
browser_config:
  headless: true
  viewport_width: 1920
  viewport_height: 1080
  timeout_seconds: 30
  enable_javascript: true
```

### Retry Configuration
```yaml
retry_config:
  max_attempts: 3
  base_delay: 1.0
  max_delay: 60.0
  exponential_base: 2.0
```

## 🆘 **Troubleshooting**

### Common Issues and Solutions

#### 1. **AWS Authentication Error**
```
Error: AWS authentication failed
```
**Solution**: 
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

#### 2. **AgentCore Endpoint Error**
```
Error: Cannot connect to AgentCore endpoint
```
**Solution**: 
- Verify your AgentCore deployment is active
- Check the `base_url` in your configuration
- Ensure you have proper IAM permissions

#### 3. **LlamaIndex Import Error**
```
ModuleNotFoundError: No module named 'llama_index'
```
**Solution**:
```bash
pip install llama-index llama-index-core llama-index-llms-bedrock
```

#### 4. **Configuration Validation Error**
```
ConfigurationError: AgentCore browser tool endpoint required
```
**Solution**: Add `test_mode: true` to your config for development, or provide real endpoints

#### 5. **Python Version Error**
```
Error: Python 3.12+ required
```
**Solution**:
```bash
# Install Python 3.12
# On macOS with Homebrew:
brew install python@3.12

# Create virtual environment
python3.12 -m venv venv312
source venv312/bin/activate
```

## 📊 **Validation Commands**

### Test Integration Structure
```bash
# Test all imports and basic functionality
python -c "
from integration import LlamaIndexAgentCoreIntegration
from tools import NavigationTool, TextExtractionTool
from captcha_tools import AdvancedCaptchaDetectionTool
print('✅ All imports successful')
"
```

### Test Configuration
```bash
# Validate configuration file
python -c "
from config import ConfigurationManager
config = ConfigurationManager('config.yaml')
print('✅ Configuration valid')
"
```

### Test AWS Connectivity
```bash
# Test AWS Bedrock access
python -c "
import boto3
bedrock = boto3.client('bedrock', region_name='us-east-1')
models = bedrock.list_foundation_models()
claude_models = [m for m in models['modelSummaries'] if 'claude' in m['modelId'].lower()]
print(f'✅ {len(claude_models)} Claude models available')
"
```

## 🎯 **Next Steps**

### 1. **Explore Advanced Features**
- Check out `examples/` directory for more complex scenarios
- Review `ARCHITECTURE_FLOW.md` for detailed component interactions
- Experiment with different LlamaIndex agent types

### 2. **Production Deployment**
- Set up proper AWS IAM roles and policies
- Configure monitoring and logging
- Implement error alerting and recovery

### 3. **Customization**
- Create custom LlamaIndex tools for your specific use cases
- Extend the document processing pipeline
- Add custom security and compliance policies

### 4. **Integration with Other Services**
- Connect to your existing LlamaIndex applications
- Integrate with vector databases for RAG applications
- Add custom workflow orchestration

## 📚 **Additional Resources**

- **[Architecture Flow](./ARCHITECTURE_FLOW.md)**: Detailed component interactions
- **[Tutorial Materials](../../../../01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/04-browser-with-LlamaIndex/README.md)**: Step-by-step learning materials
- **[AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-browser-tool.html)**: Official AWS documentation
- **[LlamaIndex Documentation](https://docs.llamaindex.ai/)**: LlamaIndex framework documentation

## 🎉 **Success!**

You now have a fully functional LlamaIndex + AgentCore Browser Tool integration! Your agents can intelligently browse websites, handle CAPTCHAs, process documents, and provide AI-powered analysis - all running on secure AWS infrastructure.

---

**Total Setup Time**: ~5 minutes  
**Result**: Production-ready AI agents with enterprise-grade browser automation capabilities  
**Next**: Build amazing applications with intelligent web browsing! 🚀