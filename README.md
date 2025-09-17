# Project Integrity Validator

A comprehensive validation tool for browser tool directories that checks file completeness, working links, valid notebooks, and proper requirements.txt files. This tool is specifically designed to validate AgentCore browser tool directories and ensure all documentation and dependencies are correct.

## 🚨 Python 3.12+ Required

**This tool requires Python 3.12 or higher.** The validator enforces this requirement at startup and will not run on older Python versions.

### Why Python 3.12+?

- Enhanced error handling and debugging capabilities
- Improved performance for file system operations
- Better type hints and static analysis support
- Modern async/await patterns for HTTP validation
- Latest security updates and bug fixes

## 📋 Features

- **File Validation**: Checks file existence, readability, and accessibility
- **Link Validation**: Validates both relative links and HTTP/HTTPS URLs
- **Notebook Validation**: Ensures Jupyter notebooks have valid JSON structure
- **Requirements Validation**: Verifies Python package dependencies and versions
- **Parallel Processing**: Multi-threaded validation for improved performance
- **Comprehensive Reporting**: Detailed reports in console or JSON format
- **Configuration Support**: YAML-based configuration for customization
- **Error Recovery**: Robust error handling with retry mechanisms

## 🎯 Default Target Directories

The validator is pre-configured to check these browser tool directories:

- `01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/01-browser-with-NovaAct`
- `01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/02-browser-with-browserUse`
- `01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands`
- `01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/04-browser-with-LlamaIndex`
- `03-integrations/01-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands`
- `03-integrations/01-AgentCore-tools/02-Agent-Core-browser-tool/04-browser-with-LlamaIndex`

## 🚀 Quick Start

### Installation

1. **Ensure Python 3.12+ is installed:**
   ```bash
   python --version  # Should show 3.12.0 or higher
   ```

2. **Install the validator:**
   ```bash
   # From the project root directory
   pip install -e .
   ```

3. **Run validation on default directories:**
   ```bash
   python -m project_integrity_validator
   ```

### Basic Usage

```bash
# Validate default browser tool directories
python -m project_integrity_validator

# Validate specific directories
python -m project_integrity_validator path/to/dir1 path/to/dir2

# Generate JSON report
python -m project_integrity_validator --json --output report.json

# Run with verbose output
python -m project_integrity_validator --verbose

# Skip HTTP link validation for faster execution
python -m project_integrity_validator --skip-http-links
```

## 📖 Installation Guide

### Prerequisites

1. **Python 3.12 or Higher**
   
   **On macOS (using Homebrew):**
   ```bash
   brew install python@3.12
   python3.12 --version
   ```
   
   **On Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install python3.12 python3.12-pip python3.12-venv
   python3.12 --version
   ```
   
   **On Windows:**
   - Download Python 3.12+ from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
   - Verify: `python --version`

2. **Create Virtual Environment (Recommended):**
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   ```

### Installation Methods

#### Method 1: Development Installation
```bash
# Clone or navigate to the project directory
cd project-integrity-validator

# Install in development mode
pip install -e .

# Verify installation
python -m project_integrity_validator --version
```

#### Method 2: Direct Installation
```bash
# Install required dependencies
pip install requests pyyaml

# Run directly from source
python -m project_integrity_validator
```

#### Method 3: Package Installation
```bash
# If distributed as a package
pip install project-integrity-validator
project-integrity-validator --help
```

## 🔧 Configuration

### Configuration File

Create a `validator_config.yaml` file to customize validation behavior:

```yaml
# Target directories to validate
target_paths:
  - "01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/01-browser-with-NovaAct"
  - "01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/02-browser-with-browserUse"
  - "custom/path/to/validate"

# Validation settings
validation:
  check_http_links: true
  http_timeout: 10
  skip_file_patterns:
    - "*.pyc"
    - "__pycache__"
    - "*.log"
  max_workers: 4

# Reporting settings
reporting:
  format: "console"  # console or json
  show_success: false
  output_file: null
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `target_paths` | List[str] | Default browser tool paths | Directories to validate |
| `check_http_links` | bool | true | Enable HTTP/HTTPS link validation |
| `http_timeout` | int | 10 | Timeout for HTTP requests (seconds) |
| `skip_file_patterns` | List[str] | ["*.pyc", "__pycache__"] | File patterns to ignore |
| `max_workers` | int | 4 | Number of parallel worker threads |
| `format` | str | "console" | Report format (console/json) |
| `show_success` | bool | false | Show successful validations |
| `output_file` | str | null | Save report to file |

### Creating Configuration Files

```bash
# Create a default configuration file
python -m project_integrity_validator --create-config validator_config.yaml

# Use custom configuration
python -m project_integrity_validator --config my_config.yaml
```

## 💻 Command Line Interface

### Basic Commands

```bash
# Show help
python -m project_integrity_validator --help

# Show version
python -m project_integrity_validator --version

# List default target directories
python -m project_integrity_validator --list-defaults

# Create default configuration
python -m project_integrity_validator --create-config config.yaml
```

### Validation Options

```bash
# Skip HTTP link validation (faster)
python -m project_integrity_validator --skip-http-links

# Set HTTP timeout
python -m project_integrity_validator --timeout 30

# Use more worker threads
python -m project_integrity_validator --workers 8

# Validate specific directories
python -m project_integrity_validator dir1 dir2 dir3
```

### Output Options

```bash
# JSON output
python -m project_integrity_validator --json

# Save to file
python -m project_integrity_validator --output report.txt

# JSON output to file
python -m project_integrity_validator --json --output report.json

# Verbose logging
python -m project_integrity_validator --verbose

# Quiet mode (errors only)
python -m project_integrity_validator --quiet
```

## 📊 Validation Report Format

### Console Output

```
Project Integrity Validator
==================================================
Python version: 3.12.0
Target paths: 6
Worker threads: 4
HTTP timeout: 10s

Validating 6 directories...

Validation Results:
==================

✅ PASSED: 01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/01-browser-with-NovaAct
   Files: 15, Links: 8, Requirements: 1, Notebooks: 3

❌ FAILED: 01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/02-browser-with-browserUse
   Issues found: 2
   
   File Issues:
   - Missing file: requirements.txt
   
   Link Issues:
   - Broken link in README.md: https://example.com/broken-link

Summary:
========
Files checked: 89
Issues found: 2
Status: ❌ Issues found that need attention
```

### JSON Output

```json
{
  "target_paths": [
    "01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/01-browser-with-NovaAct"
  ],
  "total_files_checked": 89,
  "total_issues": 2,
  "summary": {
    "pass": 87,
    "fail": 2,
    "warning": 0
  },
  "results": [
    {
      "file_path": "01-tutorials/.../README.md",
      "validation_type": "link",
      "status": "fail",
      "message": "HTTP link validation failed",
      "details": "Connection timeout after 10 seconds"
    }
  ],
  "validation_timestamp": "2024-01-15T10:30:00Z",
  "python_version": "3.12.0",
  "validator_version": "1.0.0"
}
```

## 🔍 Validation Types

### File Validation
- Checks file existence and readability
- Validates file permissions
- Scans directory structure recursively
- Identifies missing or corrupted files

### Link Validation
- **Relative Links**: Verifies target files exist
- **HTTP/HTTPS Links**: Checks URL accessibility
- **Markdown Links**: Extracts from `.md` files
- **Notebook Links**: Extracts from `.ipynb` cells
- Configurable timeout and retry logic

### Notebook Validation
- Validates JSON structure of `.ipynb` files
- Checks required notebook fields (cells, metadata)
- Verifies notebook format compliance
- Detects corrupted notebook files

### Requirements Validation
- Parses `requirements.txt` files
- Validates package names and versions
- Checks package availability on PyPI
- Verifies version constraint syntax

## 🛠️ Usage Examples

### Example 1: Basic Validation

```bash
# Run validation on default directories
python -m project_integrity_validator

# Expected output:
# Project Integrity Validator
# ==================================================
# Validating 6 directories...
# ✅ All validations passed!
```

### Example 2: Custom Directory Validation

```bash
# Validate specific directories
python -m project_integrity_validator \
  tutorials/browser-tools \
  integrations/agent-tools

# With verbose output
python -m project_integrity_validator \
  --verbose \
  tutorials/browser-tools
```

### Example 3: Performance Optimization

```bash
# Fast validation (skip HTTP links)
python -m project_integrity_validator --skip-http-links

# Use more workers for large projects
python -m project_integrity_validator --workers 8

# Custom timeout for slow networks
python -m project_integrity_validator --timeout 30
```

### Example 4: Report Generation

```bash
# Generate detailed text report
python -m project_integrity_validator \
  --output validation_report.txt \
  --verbose

# Generate JSON report for automation
python -m project_integrity_validator \
  --json \
  --output report.json

# Quiet mode with JSON output
python -m project_integrity_validator \
  --quiet \
  --json \
  --output results.json
```

### Example 5: Configuration-Based Validation

```bash
# Create custom configuration
cat > my_config.yaml << EOF
target_paths:
  - "my-project/docs"
  - "my-project/tutorials"
validation:
  check_http_links: false
  max_workers: 2
reporting:
  show_success: true
EOF

# Use custom configuration
python -m project_integrity_validator --config my_config.yaml
```

## 🐛 Troubleshooting

### Common Issues

#### Python Version Error
```
Error: Python 3.12 or higher is required for this tool.
Current version: 3.11.0
```
**Solution**: Upgrade to Python 3.12+ following the installation guide above.

#### Missing Dependencies
```
ModuleNotFoundError: No module named 'requests'
```
**Solution**: Install required dependencies:
```bash
pip install requests pyyaml
```

#### Permission Errors
```
PermissionError: [Errno 13] Permission denied: '/path/to/file'
```
**Solution**: Check file permissions or run with appropriate privileges.

#### Network Timeouts
```
HTTP link validation failed: Connection timeout
```
**Solution**: Increase timeout or skip HTTP validation:
```bash
python -m project_integrity_validator --timeout 30
# or
python -m project_integrity_validator --skip-http-links
```

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
python -m project_integrity_validator --verbose
```

This will show:
- Detailed validation progress
- HTTP request/response information
- File system operation details
- Error stack traces

### Performance Issues

If validation is slow:

1. **Skip HTTP links**: `--skip-http-links`
2. **Increase workers**: `--workers 8`
3. **Reduce timeout**: `--timeout 5`
4. **Use configuration file** to exclude unnecessary paths

## 🤝 Contributing

### Development Setup

1. **Clone the repository**
2. **Create virtual environment with Python 3.12+**
3. **Install in development mode**: `pip install -e .`
4. **Run tests**: `python -m pytest`

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=project_integrity_validator

# Run specific test file
python -m pytest project_integrity_validator/test_validator.py
```

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🔗 Related Documentation

- [AgentCore Documentation](https://docs.agentcore.aws.dev/)
- [Browser Tools Guide](./01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/README.md)
- [Python 3.12 Features](https://docs.python.org/3.12/whatsnew/3.12.html)

---

**Note**: This validator is specifically designed for AgentCore browser tool directories. For general project validation needs, consider adapting the configuration to your specific requirements.