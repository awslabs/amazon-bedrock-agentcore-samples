/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for AWS Amplify UI React components
  transpilePackages: ['@aws-amplify/ui-react', '@aws-amplify/ui'],
};

export default nextConfig;
