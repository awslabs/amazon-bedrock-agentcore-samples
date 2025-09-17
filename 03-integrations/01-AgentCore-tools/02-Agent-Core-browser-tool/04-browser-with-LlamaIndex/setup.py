"""
Setup configuration for LlamaIndex-AgentCore browser tool integration.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Read requirements
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="llamaindex-agentcore-browser-integration",
    version="0.1.0",
    author="AWS AgentCore Team",
    author_email="agentcore-team@amazon.com",
    description="LlamaIndex integration with Amazon Bedrock AgentCore Browser Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aws-samples/agentcore-samples",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.12,<3.13",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.12.0",
            "mypy>=1.8.0",
            "black>=23.12.0",
            "isort>=5.13.0",
            "flake8>=7.0.0",
        ],
        "docs": [
            "sphinx>=7.0.0",
            "sphinx-rtd-theme>=2.0.0",
            "myst-parser>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "llamaindex-agentcore=llamaindex_agentcore_integration.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.md"],
    },
    keywords=[
        "llamaindex",
        "agentcore",
        "browser-automation",
        "web-scraping",
        "captcha-solving",
        "aws",
        "bedrock",
        "ai-agents",
    ],
    project_urls={
        "Bug Reports": "https://github.com/aws-samples/agentcore-samples/issues",
        "Source": "https://github.com/aws-samples/agentcore-samples",
        "Documentation": "https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html",
    },
)