# Bidirectional Streaming

## Overview

AgentCore runtime supports persistent WebSocket connections for real-time bidirectional streaming. This enables interactive applications like voice agents, collaborative editing, and live data processing where both client and server need to send data continuously.

## Why This Example Doesn't Include Deploy Scripts

Bidirectional streaming agents are fundamentally different from the other examples in this section. They require:

- **WebSocket server implementations** (not simple HTTP request/response)
- **Docker containers** (WebSocket servers can't use the zip-to-S3 code deployment)
- **Browser-based clients** (HTML/JS for audio capture and playback)
- **Additional AWS services** (Amazon Transcribe, Amazon Polly, Kinesis Video Streams)

This makes them significantly more complex than a `deploy.py` + `invoke.py` pattern.

## Where to Find Complete Examples

The old `01-AgentCore-runtime/06-bi-directional-streaming/` folder contains four complete, working examples:

| Sample | Architecture | Framework | Key Feature |
|:-------|:-------------|:----------|:------------|
| **01-bedrock-sonic-ws** | Native Speech-to-Speech | Raw Bedrock SDK | Full protocol control over Nova Sonic |
| **02-strands-ws** | Native S2S (multi-model) | Strands BidiAgent | MCP Gateways, Nova Sonic / Gemini / OpenAI |
| **03-langchain-transcribe-polly-ws** | STT → LLM → TTS | LangChain + Transcribe + Polly | Text LLM with voice I/O pipeline |
| **04-pipecat-sonic-ws** | Native S2S | Pipecat pipeline | Open-source framework, RTVI/Protobuf |

Each includes server code, Dockerfile, browser client, and deployment scripts.

## Architecture Patterns

### Native Speech-to-Speech (S2S)
Audio flows directly into a model that understands speech and responds with speech (Nova Sonic, Gemini, OpenAI Realtime). Lower latency, simpler pipeline, built-in VAD and barge-in.

### Sandwich (STT → LLM → TTS)
Audio is transcribed to text (Amazon Transcribe), processed by a text LLM (any model), then synthesized back to speech (Amazon Polly). More flexible — any text LLM works — but higher latency.

## Key AgentCore Features for Streaming

- **WebSocket proxy with SigV4 authentication** — clients connect through AgentCore's authenticated endpoint
- **Container deployment via ECR** — package your WebSocket server as a Docker container
- **IAM role management** — AgentCore provisions execution roles with model access
- **Auto-scaling and lifecycle management** — AgentCore handles scaling and health checks
