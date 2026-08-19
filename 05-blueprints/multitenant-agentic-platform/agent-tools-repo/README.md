# Agent Tools Repository

This repository contains modular tools for composing AI agents with various capabilities.

## Structure

```
agent-tools-repo/
├── catalog.json              # Tool catalog
├── templates/
│   └── main.py        # Base agent template
└── tools/
    ├── web-search/          # Web search tool
    ├── calculator/          # Calculator tool
    ├── database-query/      # Database query tool
    └── email-sender/        # Email sender tool
```

## Available Tools

### 🔍 Web Search
Search the web using DuckDuckGo to retrieve information.

### 🧮 Calculator
Perform mathematical calculations and evaluations.

### 🗄️ Database Query
Query databases using SQL with AWS RDS Data API.

### 📧 Email Sender
Send emails using AWS SES.

## Usage

1. Reference this repository in your agent deployment UI
2. Load the tool catalog
3. Select desired tools
4. Deploy your agent with the selected tools

## Adding New Tools

1. Create a new directory under `tools/`
2. Add `tool.py` with your tool implementation
3. Add `config.json` with tool metadata
4. Update `catalog.json` to include your new tool

## Tool Implementation

Tools use the `@tool` decorator from the strands library:

```python
from strands import tool

@tool
def my_tool(param: str) -> str:
    """Tool description"""
    # Implementation
    return result
```

See individual tool directories for examples.
