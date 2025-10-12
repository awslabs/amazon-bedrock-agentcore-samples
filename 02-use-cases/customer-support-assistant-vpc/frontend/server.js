import express from 'express'
import AWS from 'aws-sdk'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
const PORT = process.env.PORT || 8501

// Configure AWS SDK
AWS.config.region = process.env.AWS_REGION || 'us-west-2'

// Middleware
app.use(express.json())

/**
 * Get SSM Parameter value
 */
async function getSSMParameter(name, withDecryption = true) {
  const ssm = new AWS.SSM()

  try {
    const response = await ssm.getParameter({
      Name: name,
      WithDecryption: withDecryption,
    }).promise()

    return response.Parameter?.Value || ''
  } catch (error) {
    console.error(`Error getting SSM parameter ${name}:`, error.message)
    throw error
  }
}

/**
 * API endpoint to get Cognito configuration
 */
app.get('/api/config', async (req, res) => {
  try {
    const stackName = req.query.stack || process.env.VITE_STACK_NAME || 'customer-support-vpc-dev'

    console.log(`Fetching configuration for stack: ${stackName}`)

    const [cognitoDomain, clientId] = await Promise.all([
      getSSMParameter('/app/customersupportvpc/agentcore/cognito_domain'),
      getSSMParameter('/app/customersupportvpc/agentcore/web_client_id'),
    ])

    res.json({
      stackName,
      cognitoDomain: cognitoDomain.replace('https://', ''),
      clientId,
      region: AWS.config.region,
    })
  } catch (error) {
    console.error('Error fetching configuration:', error)
    res.status(500).json({
      error: 'Failed to load configuration',
      message: error.message
    })
  }
})

/**
 * Health check endpoint
 */
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

// Serve static files from Vite build in production
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, 'dist')))

  // Handle React Router - send all requests to index.html
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'dist', 'index.html'))
  })
}

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`)
  console.log(`AWS Region: ${AWS.config.region}`)
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`)
})
