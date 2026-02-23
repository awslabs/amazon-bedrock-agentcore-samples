# Weekly Status Report Generator with Amazon Bedrock AgentCore Runtime (Asynchronous Agent)

## Overview

In this tutorial we will learn how to build and deploy an automated weekly status report generator using Amazon Bedrock AgentCore Runtime as an **asynchronous agent**. This demonstrates how to invoke agents asynchronously for tasks that don't require immediate responses. The agent collects data from multiple sources (team updates, meeting notes, metrics, bug trackers), performs analysis, generates visualizations, and uploads comprehensive reports to S3.

### Tutorial Details

| Information         | Details                                                                          |
|:--------------------|:---------------------------------------------------------------------------------|
| Tutorial type       | Data Analysis & Reporting                                                        |
| Agent type          | Single (Asynchronous)                                                            |
| Agentic Framework   | Strands Agents                                                                   |
| LLM model           | Anthropic 4.5                                                        |
| Tutorial components | Asynchronous agent invocation, multi-tool agent, data analysis, visualization, S3 integration, AgentCore Runtime|
| Tutorial vertical   | Business Operations & Reporting                                                  |
| Example complexity  | Intermediate                                                                     |
| SDK used            | Amazon BedrockAgentCore Python SDK, boto3, matplotlib, scikit-learn              |

### Tutorial Architecture

This tutorial demonstrates how to deploy a sophisticated reporting agent to AgentCore runtime and invoke it **asynchronously**. Asynchronous invocation is ideal for tasks like report generation that may take several minutes to complete, allowing you to trigger the agent and check results later without maintaining an open connection.

The agent uses multiple tools to:
- Read and analyze data from various sources (CSV, JSON, Markdown files)
- Perform sentiment analysis and risk scoring
- Generate data visualizations (charts and graphs)
- Build forecasting models using machine learning
- Upload reports and visualizations to S3

The agent orchestrates 16 different tools to create comprehensive weekly status reports automatically.

### Tutorial Key Features

* Asynchronous agent invocation
* Hosting complex multi-tool agents on Amazon Bedrock AgentCore Runtime
* Using Amazon Bedrock models (Claude Sonnet 4)
* Using Strands Agents framework
* Data analysis and cross-referencing across multiple sources
* Automated visualization generation with matplotlib
* Machine learning forecasting with scikit-learn
* S3 integration for data storage and report delivery
* Dynamic demo data generation and date management

## Prerequisites

- AWS Account with access to Amazon Bedrock AgentCore
- Python 3.12+
- AWS CLI configured with appropriate credentials
- S3 bucket for storing demo data and reports

## What the Agent Does

When invoked, the agent:

1. **Collects Data** from multiple sources:
   - Team member updates (5 team members)
   - Meeting notes (3 meetings)
   - KPI metrics (historical and current)
   - Bug tracker data
   - Project status information

2. **Analyzes Data**:
   - Validates data quality
   - Cross-references bugs mentioned in updates
   - Performs sentiment analysis on team updates
   - Calculates risk scores for projects

3. **Generates Visualizations**:
   - Bug severity pie chart
   - Metrics status bar charts
   - Project timeline chart
   - Team velocity chart
   - Metrics forecast chart (with ML predictions)

4. **Creates Report**:
   - Synthesizes all information into a comprehensive markdown report
   - Includes executive summary, team highlights, KPIs, risks, and action items

5. **Uploads to S3**:
   - Uploads the markdown report
   - Uploads all generated charts
   - Organizes by year and week: `s3://bucket/weekly_reports/2026/week_09_2026-02-23/`
