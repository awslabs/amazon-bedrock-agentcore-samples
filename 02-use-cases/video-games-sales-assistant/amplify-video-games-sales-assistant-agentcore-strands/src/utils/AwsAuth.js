import { AWS_REGION } from '../env';

/**
 * Creates client for a specific AWS service using the default credential provider chain
 * @param {Function} ClientConstructor - AWS SDK client constructor
 * @param {Object} options - Additional client options
 * @returns {Promise<Object>} Configured AWS service client
 */
export const createAwsClient = (ClientConstructor, options = {}) => {
  // Create client configuration using default credential provider chain
  // This will automatically use credentials from:
  // 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
  // 2. AWS credentials file (~/.aws/credentials)
  // 3. IAM roles for EC2 instances
  // 4. IAM roles for Lambda functions
  // 5. Other credential providers in the chain
  const clientConfig = {
    region: AWS_REGION,
    ...options,
  };

  return new ClientConstructor(clientConfig);
};