"""
Backup of Jupyter Notebook: 01_novaact_agentcore_secure_login.ipynb
Generated on: 2025-09-15 07:11:44
Original path: 01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/01-browser-with-NovaAct/handling-sensitive-information/01_novaact_agentcore_secure_login.ipynb

This file contains the extracted content from a corrupted Jupyter notebook.
The content has been organized into sections with appropriate comments.

Notebook format: 4.4
Total cells: 22
Code cells: 5
Markdown cells: 17
"""

# ======================================================================
# IMPORTS
# ======================================================================

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from bedrock_agentcore.tools.browser_client import browser_session
from nova_act import NovaAct, BOOL_SCHEMA, ActAgentError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from secure_login_with_novaact import (
from agentcore_session_helpers import (
from boto3.session import Session


# ======================================================================
# CODE CELL 1
# ======================================================================

# Install required packages
!pip install --force-reinstall -U -r requirements.txt --quiet


# ======================================================================
# CODE CELL 2
# ======================================================================

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any

# Core libraries
from bedrock_agentcore.tools.browser_client import browser_session
from nova_act import NovaAct, BOOL_SCHEMA, ActAgentError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Import our example modules for secure login automation
sys.path.append('examples')
from secure_login_with_novaact import (
    secure_login_with_novaact_agentcore,
    secure_login_session,
    batch_secure_login,
    SecureLoginError
)
from agentcore_session_helpers import (
    managed_novaact_agentcore_session,
    secure_operation_context,
    monitor_session_health,
    get_session_observability_data
)

console = Console()

# AWS session setup
from boto3.session import Session
boto_session = Session()
region = boto_session.region_name or "us-west-2"

# Configure logging for secure operations
logging.basicConfig(level=logging.INFO)

console.print(f"✅ Environment initialized with example modules")
console.print(f"🌍 AWS Region: {region}")
console.print(f"🔐 Security mode: Enhanced with production patterns")
console.print(f"📦 Imported secure login utilities from examples/")


# ======================================================================
# CODE CELL 3
# ======================================================================

# Secure Login Automation with NovaAct and AgentCore

## Overview

This notebook demonstrates secure login automation using NovaAct with Amazon Bedrock AgentCore browser tools. You'll learn how to:

- Implement secure credential management for automated logins
- Handle multi-factor authentication (MFA) scenarios
- Protect sensitive login information during automation
- Implement session security and cleanup
- Handle login failures and security challenges

## Security Focus

This tutorial emphasizes:
- **Credential Protection**: Never hardcode or expose credentials
- **Session Isolation**: Secure browser sessions with proper cleanup
- **Audit Logging**: Track all authentication attempts
- **Error Handling**: Secure failure modes and recovery


# ======================================================================
# CODE CELL 4
# ======================================================================

# Install required packages
!pip install --force-reinstall -U -r requirements.txt --quiet


# ======================================================================
# CODE CELL 5
# ======================================================================

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any

# Core libraries
from bedrock_agentcore.tools.browser_client import browser_session
from nova_act import NovaAct, BOOL_SCHEMA, ActAgentError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Import our example modules for secure login automation
sys.path.append('examples')
from secure_login_with_novaact import (
    secure_login_with_novaact_agentcore,
    secure_login_session,
    batch_secure_login,
    SecureLoginError
)
from agentcore_session_helpers import (
    managed_novaact_agentcore_session,
    secure_operation_context,
    monitor_session_health,
    get_session_observability_data
)

console = Console()

# AWS session setup
from boto3.session import Session
boto_session = Session()
region = boto_session.region_name or "us-west-2"

# Configure logging for secure operations
logging.basicConfig(level=logging.INFO)

console.print(f"✅ Environment initialized with example modules")
console.print(f"🌍 AWS Region: {region}")
console.print(f"🔐 Security mode: Enhanced with production patterns")
console.print(f"📦 Imported secure login utilities from examples/")


# ======================================================================
# MARKDOWN CELL 6
# ======================================================================
# # Secure Login Automation with NovaAct and AgentCore
# 
# ## Overview
# 
# This notebook demonstrates secure login automation using NovaAct with Amazon Bedrock AgentCore browser tools. You'll learn how to:
# 
# - Implement secure credential management for automated logins
# - Handle multi-factor authentication (MFA) scenarios
# - Protect sensitive login information during automation
# - Implement session security and cleanup
# - Handle login failures and security challenges
# 
# ## Security Focus
# 
# This tutorial emphasizes:
# - **Credential Protection**: Never hardcode or expose credentials
# - **Session Isolation**: Secure browser sessions with proper cleanup
# - **Audit Logging**: Track all authentication attempts
# - **Error Handling**: Secure failure modes and recovery


# ======================================================================
# MARKDOWN CELL 7
# ======================================================================
# ## Prerequisites
# 
# Before running this notebook, ensure you have:
# - AWS credentials configured
# - NovaAct API key set in environment variables
# - Required Python packages installed
# - Understanding of secure credential management practices


# ======================================================================
# MARKDOWN CELL 8
# ======================================================================
# ## Setup and Imports
# 
# First, let's import the necessary libraries and set up our secure environment.


# ======================================================================
# MARKDOWN CELL 9
# ======================================================================
# ## Security Utilities
# 
# Let's create our security utilities for credential management and session protection.


# ======================================================================
# MARKDOWN CELL 10
# ======================================================================
# ## Using Production-Ready Secure Login Functions
# 
# Now let's use the production-ready secure login functions from our examples/ directory. These functions demonstrate proper NovaAct-AgentCore integration patterns.


# ======================================================================
# MARKDOWN CELL 11
# ======================================================================
# ## Execute Secure Login Demo
# 
# Now let's run our secure login automation demo with a test site.


# ======================================================================
# MARKDOWN CELL 12
# ======================================================================
# ## Advanced Session Management with AgentCore
# 
# Let's demonstrate the advanced session management features from our examples/agentcore_session_helpers.py module.


# ======================================================================
# MARKDOWN CELL 13
# ======================================================================
# ## Security Best Practices Summary
# 
# Let's review the key security practices demonstrated in this notebook.


# ======================================================================
# MARKDOWN CELL 14
# ======================================================================
# ## Conclusion
# 
# This notebook demonstrated secure login automation using NovaAct with Amazon Bedrock AgentCore browser tools.
# 
# ### Key Takeaways:
# 
# 1. **Credential Security**: Never expose or log sensitive credentials
# 2. **Session Isolation**: Use secure, isolated browser sessions
# 3. **Audit Logging**: Maintain comprehensive audit trails
# 4. **MFA Handling**: Implement secure multi-factor authentication flows
# 5. **Error Handling**: Secure failure modes and recovery procedures
# 
# ### Production Implementation:
# 
# - Integrate with enterprise credential management systems
# - Implement comprehensive monitoring and alerting
# - Regular security audits and compliance checks
# - Staff training on secure automation practices
# 
# ### Next Steps:
# 
# - Review your organization's security policies
# - Implement secure credential storage
# - Set up monitoring and alerting
# - Test MFA scenarios thoroughly
# - Conduct security reviews and penetration testing
# 
# 🎉 **Congratulations!** You've learned how to implement secure login automation with comprehensive security controls and audit capabilities.


# ======================================================================
# MARKDOWN CELL 15
# ======================================================================
# # Secure Login Automation with NovaAct and AgentCore
# 
# ## Overview
# 
# This notebook demonstrates secure login automation using NovaAct with Amazon Bedrock AgentCore browser tools. You'll learn how to:
# 
# - Implement secure credential management for automated logins
# - Handle multi-factor authentication (MFA) scenarios
# - Protect sensitive login information during automation
# - Implement session security and cleanup
# - Handle login failures and security challenges
# 
# ## Security Focus
# 
# This tutorial emphasizes:
# - **Credential Protection**: Never hardcode or expose credentials
# - **Session Isolation**: Secure browser sessions with proper cleanup
# - **Audit Logging**: Track all authentication attempts
# - **Error Handling**: Secure failure modes and recovery


# ======================================================================
# MARKDOWN CELL 16
# ======================================================================
# ## Prerequisites
# 
# Before running this notebook, ensure you have:
# - AWS credentials configured
# - NovaAct API key set in environment variables
# - Required Python packages installed
# - Understanding of secure credential management practices


# ======================================================================
# MARKDOWN CELL 17
# ======================================================================
# ## Setup and Imports
# 
# First, let's import the necessary libraries and set up our secure environment.


# ======================================================================
# MARKDOWN CELL 18
# ======================================================================
# ## Security Utilities
# 
# Let's create our security utilities for credential management and session protection.


# ======================================================================
# MARKDOWN CELL 19
# ======================================================================
# ## Using Production-Ready Secure Login Functions
# 
# Now let's use the production-ready secure login functions from our examples/ directory. These functions demonstrate proper NovaAct-AgentCore integration patterns.


# ======================================================================
# MARKDOWN CELL 20
# ======================================================================
# ## Execute Secure Login Demo
# 
# Now let's run our secure login automation demo with a test site.


# ======================================================================
# MARKDOWN CELL 21
# ======================================================================
# ## Advanced Session Management with AgentCore
# 
# Let's demonstrate the advanced session management features from our examples/agentcore_session_helpers.py module.


# ======================================================================
# MARKDOWN CELL 22
# ======================================================================
# ## Security Best Practices Summary
# 
# Let's review the key security practices demonstrated in this notebook.
