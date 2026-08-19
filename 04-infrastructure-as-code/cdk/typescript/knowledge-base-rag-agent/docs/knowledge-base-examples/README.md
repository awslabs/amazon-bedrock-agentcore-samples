# Knowledge Base Example Documents

This folder contains example documents that you can upload to your Bedrock AgentCore knowledge base for testing and demonstration purposes.

## What's Included

- **bedrock-agentcore-guide.md** - Guide to Amazon Bedrock AgentCore and its components
- **getting-started.md** - User guide for interacting with the AI assistant
- **test-kb-document.md** - Test document with specific facts to verify knowledge base retrieval

## Quick Upload

Use the upload script for the easiest experience:

```bash
# Upload examples and wait for sync to complete
./scripts/upload-documents.sh --examples --wait
```

## Manual Upload

If you prefer to upload manually:

```bash
# Get the bucket name from CloudFormation outputs
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text)

# Upload the example documents
aws s3 cp docs/knowledge-base-examples/ s3://$BUCKET_NAME/ --recursive --exclude "README.md"

# Get IDs for syncing
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text)

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`DataSourceId`].OutputValue' \
  --output text)

# Trigger sync
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID
```

## Verify Sync Status

Check if the ingestion job completed:

```bash
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID \
  --max-results 5
```

Wait for the status to show `COMPLETE` before testing (usually 1-2 minutes).

## Testing

Once synced, test the knowledge base by asking questions like:

- "What is Amazon Bedrock?" (from bedrock-agent-guide.md)
- "What is the Phoenix Rising project?" (from test-kb-document.md)
- "What embedding model does this system use?" (from test-kb-document.md)
- "How do I use the AI assistant?" (from getting-started.md)

## Technical Details

The knowledge base uses:
- **Vector Database**: OpenSearch Serverless
- **Embedding Model**: Amazon Titan Embed Text v2 (1024 dimensions)
- **Chunking**: Fixed size, 512 tokens with 20% overlap
- **Search**: Semantic vector search with k-NN

## Adding Your Own Documents

You can add your own documents to the knowledge base:

1. Upload PDF, TXT, MD, HTML, DOC, or DOCX files to the S3 bucket
2. Trigger sync with `./scripts/upload-documents.sh --sync-only`
3. Wait for ingestion to complete
4. Test by asking questions about your content

The agent will use semantic search to find relevant information from all uploaded documents.
