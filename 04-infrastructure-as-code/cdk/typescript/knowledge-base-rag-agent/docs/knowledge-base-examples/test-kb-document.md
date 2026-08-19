# Test Knowledge Base Document

## Project Code Name: Phoenix Rising

This is a test document to verify knowledge base ingestion for the Bedrock AgentCore Template.

### Key Information

- **Project Name**: Phoenix Rising
- **Project ID**: PR-2026-001
- **Status**: Active Testing Phase
- **Lead Engineer**: Kiro AI Assistant
- **Deployment Date**: January 29, 2026

### Project Description

Phoenix Rising is a revolutionary AI-powered system designed to demonstrate the capabilities of Amazon Bedrock AgentCore's knowledge base integration. This project showcases how documents uploaded to S3 are automatically indexed and made searchable through vector embeddings using OpenSearch Serverless.

### Technical Specifications

- **Vector Database**: OpenSearch Serverless
- **Embedding Model**: Amazon Titan Embed Text v2 (1024 dimensions)
- **Foundation Model**: Claude Sonnet 4
- **Agent Framework**: Strands Agents SDK
- **Storage**: Amazon S3
- **Memory**: AgentCore Memory (STM + LTM)

### Test Verification

If you can read this document, the knowledge base ingestion is working correctly. The agent should be able to answer questions about:
- The project code name (Phoenix Rising)
- The project ID (PR-2026-001)
- The lead engineer (Kiro AI Assistant)
- The deployment date (January 29, 2026)
- The embedding model (Titan Embed Text v2 with 1024 dimensions)

This document serves as proof that the knowledge base sync and retrieval system is functioning as expected.

### AgentCore Features

The Bedrock AgentCore Template includes:
- **AgentCore Runtime**: Containerized agent deployment with auto-scaling
- **AgentCore Memory**: Short-term and long-term memory with semantic extraction
- **Knowledge Base**: RAG using OpenSearch Serverless for vector search
- **Session Isolation**: Each user gets isolated agent sessions
- **Cognito Integration**: Native authentication with AWS Cognito
