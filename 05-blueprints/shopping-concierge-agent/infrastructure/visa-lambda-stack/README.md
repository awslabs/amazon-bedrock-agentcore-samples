# Visa Lambda Stack

AWS Lambda proxy for Visa Payment API integration.

## Overview

This stack deploys a Lambda function that proxies all Visa Payment API calls from the frontend. It replaces the need to run the local Flask server (`local-visa-server`) during development and production.

## Architecture

```
Frontend → API Gateway → Lambda → Visa API
                          ↓
                    Secrets Manager (Visa credentials)
```

## Quick Start

### Deploy

From the project root:

```bash
npm run deploy:visa-lambda
```

### Update Frontend

After deployment, copy the API Gateway URL from the output and update `web-ui/.env.local`:

```bash
VITE_VISA_PROXY_URL=https://YOUR_API_GATEWAY_URL/
VITE_VISA_MOCK_MODE=false
```

### Test

```bash
npm run dev
```

## Stack Resources

- **Lambda Function**: Python 3.11 container with Flask + Mangum
- **API Gateway**: REST API with `/api/visa/*` proxy routes
- **IAM Role**: Secrets Manager access for Visa credentials
- **CloudWatch Logs**: Automatic logging

## Monitoring

```bash
# View Lambda logs
aws logs tail /aws/lambda/VisaProxyLambda --follow
```

## Cost

- Development: ~$4/month
- Production: ~$37/month

## Cleanup

```bash
npm run clean:visa-lambda
```

## Documentation

See full deployment guide in this README and `../../docs/VISA_LOCAL_SETUP.md`
