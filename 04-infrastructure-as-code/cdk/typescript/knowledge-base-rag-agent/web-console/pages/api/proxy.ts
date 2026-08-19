import type { NextApiRequest, NextApiResponse } from 'next';

/**
 * @deprecated This proxy is no longer needed as we're using CloudFront to handle CORS.
 * All API requests should go through the CloudFront distribution which properly handles CORS headers.
 */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // Return a deprecation notice
  res.status(410).json({
    error: 'API Proxy Deprecated',
    message:
      'This proxy endpoint is deprecated. API requests should now be made directly to the /api path which is handled by CloudFront.',
    code: 'DEPRECATED_PROXY',
  });
}
