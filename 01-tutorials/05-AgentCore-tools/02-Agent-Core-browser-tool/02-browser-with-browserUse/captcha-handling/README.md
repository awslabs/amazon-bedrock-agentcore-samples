# AgentCore Browser Tool + Browser-use CAPTCHA Integration

This tutorial demonstrates how to handle various types of CAPTCHAs using **AgentCore Browser Tool** as the primary automation framework, enhanced with **browser-use's specialized CAPTCHA detection capabilities**. Learn to build enterprise-ready automation workflows that leverage AgentCore's managed infrastructure while utilizing browser-use's proven CAPTCHA expertise.

## Overview

CAPTCHAs (Completely Automated Public Turing tests to tell Computers and Humans Apart) are security measures designed to prevent automated access to websites. This tutorial teaches you how to handle them responsibly and effectively using **AgentCore Browser Tool's enterprise-grade infrastructure** combined with **browser-use's specialized CAPTCHA detection algorithms**.

### 🏢 AgentCore vs Browser-use: Key Infrastructure Difference

**The fundamental difference:**
- **AgentCore Browser Tool**: Proprietary, fully managed cloud-based browser service by AWS
- **Browser-use Framework**: Open-source agentic framework requiring self-managed browser infrastructure

### 🏗️ Hybrid Architecture Approach

This tutorial demonstrates a **hybrid architecture** that combines the best of both:

| Component | Role | Benefit |
|-----------|------|---------|
| **AgentCore Browser Tool** | Managed browser infrastructure | Zero infrastructure management, enterprise security, auto-scaling |
| **Browser-use Logic** | CAPTCHA detection algorithms | Proven detection patterns, community-tested selectors |
| **AWS Bedrock** | AI-powered analysis | Intelligent CAPTCHA solving, vision model integration |
| **AgentCore Ecosystem** | Enterprise features | Memory, Observability, managed workflows |

**Result**: Enterprise-grade managed infrastructure with proven open-source CAPTCHA detection logic.

## What You'll Learn

### 🎯 Core Concepts
- **AgentCore Browser Tool**: Primary automation framework with enterprise features
- **Hybrid Architecture**: Combining AgentCore infrastructure with browser-use CAPTCHA expertise
- **CAPTCHA Types**: Understanding reCAPTCHA, hCaptcha, image-based, and text-based CAPTCHAs
- **Enterprise Security**: VM isolation, session management, and secure credential handling
- **AI Integration**: Using AWS Bedrock Vision models through AgentCore integration
- **Ecosystem Integration**: Memory storage, Observability metrics, and workflow orchestration

### 🛠 Technical Skills
- **AgentCore Browser Tool SDK**: Session management, security contexts, and enterprise features
- **Hybrid Integration Patterns**: Combining AgentCore and browser-use effectively
- **AWS Bedrock Integration**: AI-powered CAPTCHA analysis through AgentCore
- **Enterprise Automation**: Error handling, retry strategies, and production workflows
- **Performance Optimization**: Leveraging AgentCore's managed infrastructure

### 📋 Best Practices
- Ethical automation guidelines
- Rate limiting and compliance
- Security considerations
- Terms of service respect

## Prerequisites

This tutorial builds upon foundational AgentCore Browser Tool knowledge and Browser-use concepts. **Complete these prerequisites in order**:

### 📚 Required Background Tutorials (Complete First)
1. **[AgentCore Browser Tool Getting Started](02-browser-with-browserUse/getting_started-agentcore-browser-tool-with-browser-use.ipynb)** ⭐ **START HERE**
   - *Essential foundation*: AgentCore Browser Tool setup, session management, and basic automation
   - *Time required*: 30 minutes
   - *What you'll need*: AgentCore SDK concepts and browser session management

2. **[AgentCore Browser Tool Live View](02-browser-with-browserUse/agentcore-browser-tool-live-view-with-browser-use.ipynb)** 
   - *Advanced features*: Visual debugging, live interaction monitoring, and AgentCore session inspection
   - *Time required*: 45 minutes  
   - *Why it's important*: Visual debugging skills are crucial for CAPTCHA troubleshooting in managed sessions

3. **[AgentCore Runtime Basics](01-AgentCore-runtime/README.md)** (Recommended)
   - *Enterprise context*: Understanding AgentCore's managed infrastructure and ecosystem
   - *Time required*: 30 minutes
   - *Benefit*: Broader context for enterprise automation patterns and AgentCore benefits

### ✅ Required Knowledge
- **Python Programming**: Intermediate level (async/await, classes, error handling)
- **AgentCore Browser Tool**: Session management, SDK usage, and enterprise features
- **Web Technologies**: HTML, CSS selectors, DOM manipulation
- **Browser Automation**: Completed the prerequisite AgentCore tutorials above
- **AWS Basics**: Understanding of AWS services, IAM permissions, and Bedrock access

### 🔧 Technical Setup
- **Python 3.9+** with pip package manager
- **AWS Account** with Bedrock access and proper IAM permissions
- **AWS CLI** configured with credentials (`aws configure`)
- **AgentCore Browser Tool SDK** installed and configured (`bedrock-agentcore>=1.0.0`)
- **Browser-use Framework** for CAPTCHA detection logic (`browser-use>=1.0.0`)
- **Development Environment**: Jupyter Notebook/Lab or VS Code with Python extension

### 🏢 AgentCore-Specific Prerequisites
- **AgentCore SDK Access**: Ensure you have access to the AgentCore Browser Tool SDK
- **Enterprise Permissions**: VM isolation and managed browser session access
- **AgentCore Memory**: Optional but recommended for pattern storage and optimization
- **AgentCore Observability**: Optional but recommended for monitoring and metrics

### 🎯 Skills Assessment
Before starting, you should be comfortable with:
- ✅ Creating and managing AgentCore Browser Tool sessions
- ✅ Using AgentCore SDK methods (interact, parse, discover)
- ✅ Navigating web pages through AgentCore managed browsers
- ✅ Taking and analyzing screenshots via AgentCore capabilities
- ✅ Handling web elements and interactions in enterprise contexts
- ✅ Understanding async/await Python patterns and AgentCore session lifecycle

**Not sure if you're ready?** Complete the prerequisite AgentCore tutorials first - they provide the essential foundation for this advanced hybrid integration tutorial.

### 🔑 AWS Permissions
Your AWS credentials need access to:
- **Amazon Bedrock** (Claude Vision models for AI-powered CAPTCHA solving)
- **AgentCore Browser Tool** (Managed browser sessions and VM isolation)
- **AgentCore Memory** (Optional: For CAPTCHA pattern storage and optimization)
- **AgentCore Observability** (Optional: For metrics collection and monitoring)
- **CloudWatch Logs** (For debugging and audit trails)

## Installation

### 🚀 Quick Start with AgentCore Integration

1. **Clone or navigate to the tutorial directory**:
   ```bash
   cd 01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/02-browser-with-browserUse/captcha-handling/
   ```

2. **Install AgentCore and dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   **Key dependencies installed**:
   - `bedrock-agentcore>=0.1.2` - AgentCore Browser Tool SDK
   - `browser-use>=0.1.0` - CAPTCHA detection capabilities
   - `boto3>=1.40.0` - AWS Bedrock integration
   - `pillow>=10.0.0` - Image processing for CAPTCHA analysis

3. **Configure AWS credentials** (if not already done):
   ```bash
   aws configure
   ```
   
   **Verify AgentCore access**:
   ```bash
   python -c "from bedrock_agentcore.tools import BrowserClient; print('AgentCore SDK ready!')"
   ```

4. **Create AgentCore Browser Tool in AWS Console**:
   - Navigate to AWS Management Console → Amazon Bedrock → Built-in Tools
   - Create Browser Tool with a unique name (e.g., "captcha-handler-browser")
   - Configure network settings and session timeout (default: 3600 seconds)
   - Note the Tool ARN for SDK calls

5. **Install browser binaries**:
   ```bash
   playwright install
   ```

6. **Start the AgentCore-integrated tutorial**:
   ```bash
   jupyter notebook browser-use-captcha.ipynb
   ```

### 🔧 Advanced Setup Options

**Environment Variables** (Optional):
```bash
export AWS_REGION=us-east-1
export AGENTCORE_SESSION_TIMEOUT=1800
export CAPTCHA_SCREENSHOT_DIR=./captcha_screenshots
```

**Verify Installation**:
```python
# Test AgentCore Browser Tool + browser-use integration
from bedrock_agentcore.tools import BrowserClient
from browser_use import Browser

# Both should import successfully for hybrid approach
print("✅ AgentCore Browser Tool SDK ready")
print("✅ Browser-use CAPTCHA detection ready")
```

## Tutorial Structure

### 📚 Section 1: AgentCore Environment Setup
- **AgentCore Browser Tool SDK** installation and verification
- **Hybrid Architecture** configuration (AgentCore + browser-use)
- **AWS Bedrock** client configuration through AgentCore
- **Enterprise Security** setup and session management
- Testing the integrated setup

### 🔍 Section 2: AgentCore CAPTCHA Detection
- **AgentCore Session Management**: Creating and managing browser sessions
- **Hybrid Detection**: Using browser-use algorithms within AgentCore sessions
- **Enterprise Features**: VM isolation, security contexts, and session lifecycle
- **CAPTCHA Types**: Identifying reCAPTCHA, hCaptcha, image, and text CAPTCHAs
- Building the AgentCoreCaptchaHandler class

### 🤖 Section 3: AI-Powered Analysis with AgentCore
- **Bedrock Integration**: AI model access through AgentCore infrastructure
- **Image Processing**: Screenshot capture via AgentCore capabilities
- **Prompt Engineering**: Context-aware CAPTCHA solving strategies
- **Confidence Scoring**: Validation and quality assessment
- **Performance Optimization**: Leveraging AgentCore's managed infrastructure

### 🔄 Section 4: AgentCore Ecosystem Integration
- **Memory Integration**: Storing CAPTCHA patterns in AgentCore Memory
- **Observability**: Metrics collection and performance monitoring
- **Session Orchestration**: Managing complex workflows across sessions
- **Enterprise Workflows**: Production-ready automation patterns
- **Hybrid Architecture Benefits**: Demonstrating combined capabilities

### ⚠️ Section 5: Enterprise Error Handling
- **Session Recovery**: AgentCore session failure handling and recovery
- **Fallback Strategies**: Graceful degradation and error handling
- **Production Monitoring**: Logging, metrics, and alerting

## 🚀 Quick Start

Run the hybrid integration example:

```bash
python hybrid_integration_example.py
```

## 🔧 Troubleshooting

### Common Issues

**bedrock-agentcore not found**: Contact AWS support for access to the AgentCore SDK

**browser-use installation fails**: Install from GitHub:
```bash
pip install git+https://github.com/browser-use/browser-use.git
```

**Playwright browsers missing**: Install browser binaries:
```bash
playwright install
```

**AWS credentials**: Configure with `aws configure` or set environment variables

### Validation

Run the environment validation script:
```bash
python validate_production_environment.py
```

### Diagnostic Checklist

If CAPTCHA detection isn't working:

- ✅ AgentCore Browser Tool created in AWS Console
- ✅ AWS credentials have proper permissions  
- ✅ Both bedrock-agentcore and browser-use installed
- ✅ Playwright browsers installed (`playwright install`)
- ✅ AgentCore session active and not expired
- ✅ Page fully loaded before CAPTCHA detection
- ✅ CAPTCHA elements not blocked by security policies

## 🧪 Testing

### Run Tests

```bash
# Validate environment
python validate_production_environment.py

# Run hybrid integration example
python hybrid_integration_example.py

# Validate complete setup
python final_production_validation.py
```

### Test Coverage

The tutorial includes tests for:
- AgentCore Browser Tool integration
- browser-use CAPTCHA detection
- Hybrid architecture validation
- AWS Bedrock AI analysis
- Error handling and recovery
- **Timeout Management**: Enterprise-grade timeout and retry strategies
- **Security Monitoring**: Audit logging and compliance tracking
- **Debugging Techniques**: AgentCore-specific troubleshooting methods

### 🎯 Section 6: Production Best Practices
- **Enterprise Security**: VM isolation, credential management, and data protection
- **Performance Optimization**: Leveraging AgentCore's infrastructure benefits
- **Compliance**: Ethical automation within enterprise contexts
- **Monitoring**: Production observability and alerting
- **Deployment Patterns**: Scaling CAPTCHA handling in enterprise environments

## Supplementary Resources

In addition to the main tutorial notebook, this directory includes supplementary Python modules with advanced implementations:

### 📚 Integrated Tutorial Content
All advanced content is now integrated directly into the main tutorial notebook:

- **Section 5: Error Handling & Recovery**: Comprehensive timeout management, fallback strategies, and graceful degradation
- **Section 6: Ethical Guidelines & Best Practices**: Compliance checking, rate limiting, and security measures

The tutorial notebook provides both theoretical explanations and practical, runnable code examples for:
- **Timeout Management**: Configurable timeouts for different CAPTCHA operations
- **Fallback Strategies**: Multiple recovery strategies for failed operations  
- **Ethical Compliance**: Automated guideline verification and best practices
- **Rate Limiting**: Respectful request patterns and delays
- **Security Measures**: Data protection and audit logging

### 🚀 Running the Tutorial
Open the main notebook to access all content:

```bash
jupyter notebook browser-use-captcha.ipynb
```

The notebook provides production-ready implementations with complete examples that can be adapted for real-world CAPTCHA handling scenarios.

### 📚 Additional Documentation

This tutorial includes comprehensive supporting documentation:

- **[AgentCore Learning Materials](agentcore_learning_materials.md)**: Comprehensive guide to AgentCore integration, architecture comparisons, and performance optimization
- **[Architecture Diagrams](architecture_diagrams.md)**: Visual representations of standalone vs AgentCore hybrid architectures, performance comparisons, and deployment patterns
- **[Testing Guide](TESTING.md)**: Complete testing framework with validation, integration, and performance tests
- **[Troubleshooting Guide](troubleshooting_guide.md)**: Comprehensive problem-solving guide with common issues and solutions (includes AgentCore-specific troubleshooting)
- **[Visual Examples Guide](visual_examples_guide.md)**: Visual identification patterns, screenshots, and debugging techniques
- **[Production Workflows Guide](production_workflows_guide.md)**: Architecture diagrams, workflow patterns, and production deployment strategies

## Key Features

### 🚀 Comprehensive Coverage
- Multiple CAPTCHA types and solving strategies
- Real-world examples and use cases
- Production-ready code patterns
- Performance optimization techniques

### 🔒 Security-First Approach
- Secure credential management
- Privacy-conscious implementations
- Ethical automation practices
- Compliance guidelines

### 📖 Educational Focus
- Step-by-step explanations
- Visual examples and diagrams
- Troubleshooting guides
- Progressive complexity

### 🏢 AgentCore Integration Benefits

#### 🔒 Enterprise Security & Compliance
- **VM Isolation**: Browser sessions run in isolated virtual machines for maximum security
- **Encrypted Sessions**: All session data encrypted in transit and at rest
- **Audit Trails**: Complete logging and monitoring for compliance requirements
- **Credential Management**: Secure AWS credential handling and rotation
- **Security Contexts**: Enterprise-grade security policies and access controls

#### ⚡ Performance & Infrastructure
- **Managed Infrastructure**: Automatic browser lifecycle management and resource optimization
- **Performance Gains**: 20-25% performance improvements over standalone Browser-use
- **Resource Optimization**: Intelligent session pooling and resource allocation
- **Scalability**: Enterprise-grade scaling and load distribution
- **Reliability**: Built-in failover and recovery mechanisms

#### 🔗 Ecosystem Integration
- **Memory Integration**: Persistent CAPTCHA pattern storage and cross-session optimization
- **Observability**: Real-time metrics, monitoring, and alerting capabilities
- **Workflow Orchestration**: Seamless integration with other AgentCore tools and services
- **Data Sharing**: Secure data exchange between AgentCore ecosystem components
- **Unified SDK**: Consistent API patterns across all AgentCore tools

#### 🔄 Hybrid Architecture Advantages
- **Best of Both Worlds**: AgentCore infrastructure + Browser-use CAPTCHA expertise
- **Fallback Mechanisms**: Graceful degradation to standalone Browser-use when needed
- **Incremental Migration**: Easy transition from standalone to enterprise architecture
- **Flexibility**: Choose the right tool for each specific automation task
- **Future-Proof**: Leverage ongoing improvements in both frameworks

> **Learn More**: See the [AgentCore Learning Materials](agentcore_learning_materials.md) for detailed architecture comparisons, performance benchmarks, and migration guides.

## Usage Examples

### AgentCore-Integrated CAPTCHA Detection
```python
from bedrock_agentcore.browser import AgentCoreBrowser
from agentcore_captcha_integration import AgentCoreCaptchaHandler

async def detect_captcha_with_agentcore():
    # Create AgentCore managed session
    handler = AgentCoreCaptchaHandler()
    session_info = await handler.create_managed_session("captcha-session")
    
    try:
        # Navigate and detect using AgentCore infrastructure
        result = await handler.detect_captcha_with_agentcore("https://example.com/login")
        
        print(f"CAPTCHA detected: {result.captcha_type}")
        print(f"Confidence: {result.confidence_score}")
        print(f"Session ID: {result.agentcore_session_id}")
        
        return result
    finally:
        # Automatic cleanup with AgentCore session management
        await handler.cleanup_session()
```

### Hybrid AI-Powered CAPTCHA Solving
```python
from agentcore_captcha_integration import AgentCoreCaptchaHandler

async def solve_captcha_hybrid_approach():
    handler = AgentCoreCaptchaHandler()
    
    # Create enterprise session with VM isolation
    session_info = await handler.create_managed_session("captcha-solver")
    
    try:
        # Detect using Browser-use algorithms in AgentCore session
        detection_result = await handler.detect_captcha_with_agentcore(
            "https://example.com/captcha-challenge"
        )
        
        # Solve using AWS Bedrock through AgentCore
        solution = await handler.solve_captcha_with_bedrock(detection_result)
        
        # Store pattern in AgentCore Memory for future optimization
        await handler.store_captcha_pattern(detection_result, solution)
        
        return solution
    finally:
        await handler.cleanup_session()
```

### Enterprise Workflow Integration
```python
from bedrock_agentcore.memory import ConversationMemory
from bedrock_agentcore.observability import Metrics

async def enterprise_captcha_workflow():
    handler = AgentCoreCaptchaHandler()
    
    # Initialize AgentCore ecosystem components
    memory = ConversationMemory()
    metrics = Metrics()
    
    session_info = await handler.create_managed_session("enterprise-captcha")
    
    try:
        # Track operation start
        await metrics.record_event("captcha_workflow_started", {
            "session_id": session_info["session_id"],
            "security_context": session_info["security_context"]
        })
        
        # Retrieve historical patterns from Memory
        patterns = await memory.retrieve_context("captcha_patterns")
        
        # Enhanced detection with historical data
        result = await handler.detect_with_memory_optimization(
            "https://example.com/login", patterns
        )
        
        # Record success metrics
        await metrics.record_event("captcha_detected", {
            "type": result.captcha_type,
            "confidence": result.confidence_score
        })
        
        return result
        
    except Exception as e:
        # Track errors for monitoring
        await metrics.record_error("captcha_workflow_failed", str(e))
        raise
    finally:
        await handler.cleanup_session()
```

## Troubleshooting

### AgentCore-Specific Issues

**AgentCore SDK Import Errors**
- Ensure `bedrock-agentcore>=1.0.0` is installed: `pip install bedrock-agentcore`
- Verify AWS credentials have AgentCore access permissions
- Check region settings (us-east-1 recommended for AgentCore services)

**Session Creation Failures**
- Verify AgentCore Browser Tool access in your AWS account
- Check IAM permissions for AgentCore session management
- Ensure VM isolation features are enabled in your region
- Try creating a session with basic configuration first

**Hybrid Integration Issues**
- Verify both AgentCore SDK and Browser-use are properly installed
- Check for version compatibility between frameworks
- Test AgentCore and Browser-use independently before integration
- Review the [AgentCore Learning Materials](agentcore_learning_materials.md) for integration patterns

### Traditional Issues (Enhanced for AgentCore)

**AWS Credentials Not Found**
- Ensure AWS CLI is configured: `aws configure`
- Check IAM permissions for Bedrock AND AgentCore access
- Verify region settings (us-east-1 recommended)
- Test AgentCore SDK access: `python -c "from bedrock_agentcore.browser import AgentCoreBrowser"`

**Browser Session Errors**
- AgentCore manages browser instances - check session status in AgentCore console
- Verify network connectivity to AgentCore services
- Try creating sessions with different configurations
- Use AgentCore session debugging tools for detailed diagnostics

**CAPTCHA Detection Failures in AgentCore Sessions**
- Update Browser-use selectors for new CAPTCHA versions
- Verify AgentCore screenshot capture is working
- Check if site structure changes affect AgentCore page analysis
- Test detection in both AgentCore and standalone modes for comparison

**AI Model Errors with AgentCore Integration**
- Ensure Bedrock model access is enabled through AgentCore
- Check rate limits and quotas for both Bedrock and AgentCore
- Verify image format and size requirements for AgentCore image processing
- Test Bedrock integration independently of CAPTCHA detection

### Getting Help

For AgentCore-specific issues:
1. **Check the [Troubleshooting Guide](troubleshooting_guide.md)** for detailed AgentCore troubleshooting
2. **Review AgentCore documentation** for session management and SDK usage
3. **Test components independently** - AgentCore, Browser-use, and Bedrock separately
4. **Use AgentCore debugging tools** for session inspection and diagnostics

> **Detailed Troubleshooting**: See the comprehensive [Troubleshooting Guide](troubleshooting_guide.md) for AgentCore-specific debugging techniques and common resolution patterns.

## Tutorial Series Integration

### 📚 Prerequisites (Complete These First)
This tutorial builds upon foundational Browser-use concepts. **[View the complete integration guide](INTEGRATION_GUIDE.md)** for detailed learning pathways.

**Required Prerequisites**:
- **[Getting Started with Browser-use](02-browser-with-browserUse/getting_started-agentcore-browser-tool-with-browser-use.ipynb)** ⭐ **Essential foundation**
- **[Browser-use Live View](02-browser-with-browserUse/agentcore-browser-tool-live-view-with-browser-use.ipynb)** 🔍 **Visual debugging skills**

**Recommended Background**:
- **[AgentCore Runtime Basics](01-AgentCore-runtime/README.md)** 🏢 **Enterprise context and managed infrastructure**

### 🔗 Related AgentCore Tutorials
Continue your learning journey with these complementary tutorials:

- **[AgentCore Memory](04-AgentCore-memory/README.md)**: Persistent state management for CAPTCHA patterns
- **[AgentCore Observability](06-AgentCore-observability/README.md)**: Monitor CAPTCHA solving performance  
- **[AgentCore Runtime](01-AgentCore-runtime/README.md)**: Deploy CAPTCHA handling at enterprise scale
- **[End-to-End Labs](07-AgentCore-E2E/README.md)**: Complete system integration examples

### 🎯 Learning Path Recommendations
- **Beginners**: Complete prerequisites → CAPTCHA tutorial → Advanced AgentCore tools
- **Intermediate**: Review prerequisites → Focus on CAPTCHA sections 3-5 → Integration projects
- **Advanced**: Quick prerequisite review → CAPTCHA sections 5-7 → Production deployment

## Contributing

Found an issue or want to improve the tutorial?

1. Check existing issues and discussions
2. Follow the contribution guidelines
3. Submit pull requests with clear descriptions
4. Include tests for new examples

## Ethical Considerations

### ⚖️ Responsible Usage
This tutorial is for educational purposes and legitimate automation needs. Always:

- Respect website terms of service
- Implement appropriate rate limiting
- Use CAPTCHA solving only when legally permitted
- Consider the impact on website resources
- Maintain user privacy and data security

### 🚫 Prohibited Uses
Do not use these techniques for:
- Bypassing security measures maliciously
- Automated account creation for spam
- Circumventing rate limits inappropriately
- Any illegal or unethical activities

## License

This tutorial is part of the AWS AgentCore documentation and follows the same licensing terms. Use responsibly and in accordance with AWS terms of service.

## Support

For questions and support:
- Review the troubleshooting section
- Check AWS Bedrock documentation
- Consult Browser-use community resources
- Follow ethical automation guidelines

---

**Ready to get started?** Open the `browser-use-captcha.ipynb` notebook and begin your journey into intelligent CAPTCHA handling! 🚀