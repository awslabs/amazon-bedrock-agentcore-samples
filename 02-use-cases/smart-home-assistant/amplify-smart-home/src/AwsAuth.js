import { ACCESS_KEY_ID, SECRET_ACCESS_KEY, AWS_REGION } from '../env';

/**
 * Creates client for a specific AWS service with authenticated credentials
 * @param {Function} ClientConstructor - AWS SDK client constructor
 * @param {Object} options - Additional client options
 * @returns {Promise<Object>} Configured AWS service client
 */
export const createAwsClient = (ClientConstructor, options = {}) => {
  // Create client configuration
  const clientConfig = {
    region: AWS_REGION,
    credentials: {
      accessKeyId: ACCESS_KEY_ID,
      secretAccessKey: SECRET_ACCESS_KEY
    },
    ...options,
  };

  return new ClientConstructor(clientConfig);
};