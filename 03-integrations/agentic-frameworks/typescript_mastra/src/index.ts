import express, { type Request, type Response } from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 8080;

// Middleware
app.use(express.json());

/**
 * POST /invocations - Main agent interaction endpoint
 *
 * Required Headers:
 * - X-Amzn-Bedrock-AgentCore-Runtime-SessionId: Session ID (required)
 *
 * Optional Headers:
 * - X-Amzn-Bedrock-AgentCore-Runtime-RequestId: Request ID
 * - x-amzn-bedrock-agentcore-runtime-workload-accesstoken: Access token
 */
app.post('/invocations', (req: Request, res: Response) => {
  try {
    const sessionId = req.headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] as string;
    const requestId = req.headers['X-Amzn-Bedrock-AgentCore-Runtime-Request-Id'] as string;
    const accessToken = req.headers['x-amzn-bedrock-agentcore-runtime-workload-accesstoken'] as string;

    console.log('Received request - Session ID:', sessionId);
    if (requestId) console.log('Request ID:', requestId);
    if (accessToken) console.log('Access Token: [REDACTED]');

    // Validate required header
    if (!sessionId) {
      return res.status(400).json({
        error: 'Missing required header: X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'
      });
    }

    // Validate request body
    const { prompt } = req.body;
    if (!prompt) {
      return res.status(400).json({
        error: 'Missing required field: prompt'
      });
    }

    console.log('Prompt:', prompt);

    // Simple placeholder response (we'll add Mastra.ai later)
    const agentResponse = {
      message: `Placeholder response for prompt: "${prompt}" (Session: ${sessionId})`,
      timestamp: new Date().toISOString()
    };

    console.log('Agent response:', agentResponse.message);

    res.json(agentResponse);
  } catch (error) {
    console.error('Error processing request:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /ping - Health check endpoint
 *
 * Returns:
 * - status: "healthy" or "healthyBusy"
 * - timeOfLastUpdate: Unix timestamp in seconds
 */
app.get('/ping', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    timeOfLastUpdate: Math.floor(Date.now() / 1000)
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 AgentCore Runtime server listening on port ${PORT}`);
  console.log(`📍 Endpoints:`);
  console.log(`   POST http://0.0.0.0:${PORT}/invocations`);
  console.log(`   GET  http://0.0.0.0:${PORT}/ping`);
});
