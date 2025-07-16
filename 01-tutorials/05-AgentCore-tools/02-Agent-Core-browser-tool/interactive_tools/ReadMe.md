# Amazon Bedrock Agentcore SDK Tools Examples

This folder contains examples demonstrating the use of Genesis SDK tools:

## Browser Tools

* `browser_viewer.py` - Amazon Bedrock Agentcore Browser Live Viewer with proper display sizing support.
* `run_live_viewer.py` - Standalone script to run the Bedrock Agentcore Browser Live Viewer.

## Code Interpreter Tools

* `research_agent_code_interpreter.py` - LangGraph-powered research agent with dynamic code generation

## Prerequisites

### Python Dependencies
```bash
uv pip install -r requirements.txt
```

Required packages: fastapi, uvicorn, rich, boto3, genesis

### AWS Credentials (For S3 Storage)
For S3 recording storage, ensure AWS credentials are configured:
```bash
aws configure
```

## Browser Live Viewer

Real-time browser viewing capability using Amazon DCV technology.

### Features

**Display Size Control**
- 1280×720 (HD)
- 1600×900 (HD+) - Default
- 1920×1080 (Full HD)
- 2560×1440 (2K)

**Session Control**
- Take Control: Disable automation and interact manually
- Release Control: Return control to automation

### Configuration
- Custom ports: `BrowserViewerServer(browser_client, port=8080)`

## Browser Session Recording and Replay

Record and replay browser sessions for debugging, testing, and demonstration purposes.

### Important Limitations
This tool records DOM events using rrweb, not video streams:
- The actual browser content (DCV canvas) may appear as a black box
- For pixel-perfect video recording, use screen recording software


## Troubleshooting

### DCV SDK Not Found
Ensure the DCV SDK files are placed in `interactive_tools/static/dcvjs/`

### Browser Session Not Visible
- Check browser console (F12) for errors
- Ensure AWS credentials have proper permissions

### Recording Not Found During Replay
- Check the exact path shown when recording was saved
- For S3 recordings, use the full S3 URL
- Ensure the file exists using `aws s3 ls` or `ls` commands

### S3 Access Errors
- Verify AWS credentials are configured
- Check IAM permissions for S3 operations
- Ensure bucket name is globally unique

## Performance Considerations
- Recording adds overhead to browser performance
- File sizes typically 1-10MB per minute
- S3 uploads happen after recording stops
- Replay requires downloading entire file first

## Architecture Notes
- Live viewer uses FastAPI to serve presigned DCV URLs
- Recording captures DOM events via rrweb library
- Replay uses rrweb-player for playback
- All components share the same BrowserClient instance
- Modular design allows independent usage of each component
