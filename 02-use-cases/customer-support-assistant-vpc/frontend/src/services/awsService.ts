import AWS from 'aws-sdk'

// Initialize AWS SDK with credentials from environment or default provider chain
const configureAWS = () => {
  // AWS SDK will use credentials from the browser's environment
  // In production, you might want to use AWS Amplify or Cognito Identity Pool
  AWS.config.region = process.env.VITE_AWS_REGION || 'us-west-2'
}

/**
 * Get SSM Parameter value
 */
export async function getSSMParameter(name: string, withDecryption: boolean = true): Promise<string> {
  configureAWS()

  const ssm = new AWS.SSM()

  try {
    const response = await ssm.getParameter({
      Name: name,
      WithDecryption: withDecryption,
    }).promise()

    return response.Parameter?.Value || ''
  } catch (error) {
    console.error('Error getting SSM parameter:', error)
    throw error
  }
}

/**
 * Get nested stack name from parent stack
 */
export async function getNestedStackName(
  parentStackName: string,
  logicalResourceId: string,
  region: string
): Promise<string> {
  const cfn = new AWS.CloudFormation({ region })

  try {
    const response = await cfn.describeStackResource({
      StackName: parentStackName,
      LogicalResourceId: logicalResourceId,
    }).promise()

    const physicalResourceId = response.StackResourceDetail?.PhysicalResourceId
    if (!physicalResourceId) {
      throw new Error('Physical resource ID not found')
    }

    // Extract stack name from ARN format: arn:aws:cloudformation:region:account:stack/stack-name/guid
    const stackName = physicalResourceId.split('/').slice(-2, -1)[0]
    return stackName
  } catch (error) {
    console.error('Error getting nested stack name:', error)
    throw error
  }
}

/**
 * Get CloudFormation stack output value
 */
export async function getStackOutput(
  stackName: string,
  outputKey: string,
  region: string
): Promise<string> {
  const cfn = new AWS.CloudFormation({ region })

  try {
    const response = await cfn.describeStacks({
      StackName: stackName,
    }).promise()

    if (!response.Stacks || response.Stacks.length === 0) {
      throw new Error(`Stack '${stackName}' not found`)
    }

    const stack = response.Stacks[0]
    const outputs = stack.Outputs || []

    const output = outputs.find((o) => o.OutputKey === outputKey)
    if (!output || !output.OutputValue) {
      throw new Error(`Output '${outputKey}' not found in stack '${stackName}'`)
    }

    return output.OutputValue
  } catch (error) {
    console.error('Error getting stack output:', error)
    throw error
  }
}

/**
 * Get AWS region from SDK configuration
 */
export function getAWSRegion(): string {
  return AWS.config.region || 'us-west-2'
}

/**
 * Get AWS account ID
 */
export async function getAccountId(): Promise<string> {
  const sts = new AWS.STS()

  try {
    const response = await sts.getCallerIdentity().promise()
    return response.Account || ''
  } catch (error) {
    console.error('Error getting account ID:', error)
    throw error
  }
}

/**
 * Get agent ARN from CloudFormation stack
 */
export async function getAgentARNFromStack(stackName: string): Promise<{ agentArn: string; region: string }> {
  const region = getAWSRegion()

  try {
    const agentStackName = await getNestedStackName(stackName, 'AgentServerStack', region)
    const runtimeId = await getStackOutput(agentStackName, 'AgentRuntimeId', region)
    const accountId = await getAccountId()

    const agentArn = `arn:aws:bedrock-agentcore:${region}:${accountId}:runtime/${runtimeId}`

    return { agentArn, region }
  } catch (error) {
    console.error('Error getting agent ARN from stack:', error)
    throw error
  }
}
