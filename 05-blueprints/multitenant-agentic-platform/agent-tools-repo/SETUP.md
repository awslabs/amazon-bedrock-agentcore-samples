# Setup Instructions

## Push to GitHub

This repository is ready to be pushed to GitHub. Follow these steps:

### 1. Create a new repository on GitHub

Go to https://github.com/new and create a new repository (e.g., `agent-tools`)

**Important:** Do NOT initialize with README, .gitignore, or license (we already have these)

### 2. Push this repository

```bash
cd agent-tools-repo

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/agent-tools.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### 3. Verify the upload

Visit your repository on GitHub and verify all files are present:
- ✅ catalog.json
- ✅ README.md
- ✅ templates/main.py
- ✅ tools/web-search/
- ✅ tools/calculator/
- ✅ tools/database-query/
- ✅ tools/email-sender/

### 4. Use in your agent deployment

Once pushed to GitHub, you can use this repository in your agent deployment:

1. Open the agent deployment UI
2. Check "Use Custom Template from GitHub"
3. Enter repository: `YOUR_USERNAME/agent-tools`
4. Enter template path: `templates/base-agent.py`
5. Enter branch: `main`
6. Click "Load Available Tools"
7. Select desired tools
8. Deploy your agent!

## Repository Structure

```
agent-tools-repo/
├── catalog.json              # Tool catalog (required)
├── README.md                 # Documentation
├── .gitignore               # Git ignore rules
├── templates/
│   └── base-agent.py        # Base agent template
└── tools/
    ├── web-search/          # 🔍 Web search tool
    │   ├── tool.py
    │   └── config.json
    ├── calculator/          # 🧮 Calculator tool
    │   ├── tool.py
    │   └── config.json
    ├── database-query/      # 🗄️ Database query tool
    │   ├── tool.py
    │   └── config.json
    └── email-sender/        # 📧 Email sender tool
        ├── tool.py
        └── config.json
```

## Available Tools

### 🔍 Web Search
- Search the web using DuckDuckGo
- No API key required
- Dependencies: requests, beautifulsoup4

### 🧮 Calculator
- Perform mathematical calculations
- Supports common math functions (sqrt, sin, cos, etc.)
- No dependencies

### 🗄️ Database Query
- Query databases using SQL
- Uses AWS RDS Data API
- Dependencies: boto3
- **Note:** Update resource ARN and secret ARN in tool.py before use

### 📧 Email Sender
- Send emails using AWS SES
- Dependencies: boto3
- **Note:** Sender email must be verified in AWS SES

## Adding More Tools

To add a new tool:

1. Create directory: `tools/your-tool-name/`
2. Add `tool.py` with your implementation
3. Add `config.json` with metadata
4. Update `catalog.json` to include your tool
5. Commit and push changes

## Testing

Test individual tools before adding to catalog:

```python
from tools.calculator.tool import calculator

result = calculator("2 + 2")
print(result)  # Should print: Result: 4
```

## Support

For issues or questions, refer to the main documentation or create an issue in the repository.
