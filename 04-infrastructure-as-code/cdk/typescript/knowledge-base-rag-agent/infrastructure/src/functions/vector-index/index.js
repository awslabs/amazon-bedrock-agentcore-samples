const { OpenSearchServerlessClient, BatchGetCollectionCommand } = require('@aws-sdk/client-opensearchserverless');
const https = require('https');
const { defaultProvider } = require('@aws-sdk/credential-provider-node');
const { SignatureV4 } = require('@aws-sdk/signature-v4');
const { Sha256 } = require('@aws-crypto/sha256-js');

exports.handler = async (event) => {
  console.log('Event:', JSON.stringify(event, null, 2));
  
  const { RequestType, PhysicalResourceId } = event;
  const { CollectionId, IndexName, ResourceId } = event.ResourceProperties;
  
  // Use a consistent physical ID to prevent issues during deletion
  const resourceId = PhysicalResourceId || ResourceId || `VectorIndex-${CollectionId}-${IndexName}`;
  
  if (RequestType === 'Delete') {
    console.log('Delete request - returning the same physical ID');
    return {
      PhysicalResourceId: resourceId
    };
  }
  
  if (RequestType === 'Create' || RequestType === 'Update') {
    try {
      // Get the collection endpoint
      const aoss = new OpenSearchServerlessClient({ region: process.env.AWS_REGION });
      const response = await aoss.send(new BatchGetCollectionCommand({ names: [CollectionId] }));
      const collectionEndpoint = response.collectionDetails[0].collectionEndpoint;
      console.log(`Collection endpoint: ${collectionEndpoint}`);
      
      // Define index mapping based on working quack-the-code solution
      // Key insight: _metadata (with underscore) must be type 'text' with index:false
      // Using 1024 dimensions to match amazon.titan-embed-text-v2:0 embedding model
      const indexMapping = {
        mappings: {
          properties: {
            vector: {
              type: 'knn_vector',
              dimension: 1024,
              method: {
                name: 'hnsw',
                engine: 'faiss',
                space_type: 'l2',
                parameters: {
                  ef_construction: 128,
                  m: 16
                }
              }
            },
            text: { 
              type: 'text',
              analyzer: 'standard'
            },
            _metadata: { 
              type: 'text',
              index: false
            }
          }
        },
        settings: {
          index: {
            number_of_shards: 1,
            number_of_replicas: 0,
            knn: true,
            'knn.algo_param.ef_search': 512
          }
        }
      };
      
      // Try to create the index with retry logic
      const result = await createIndexWithRetry(collectionEndpoint, IndexName, indexMapping);
      console.log('Index creation result:', result);
      
      // Verify the index actually exists before returning success
      console.log('Verifying index exists...');
      const verifyIndex = await getIndex(collectionEndpoint, IndexName);
      if (!verifyIndex) {
        throw new Error(`Index ${IndexName} was not created successfully - verification failed`);
      }
      console.log('Index verified successfully:', JSON.stringify(verifyIndex.mappings?.properties?.vector || {}, null, 2));
      
      return {
        PhysicalResourceId: resourceId,
        Data: {
          IndexName: IndexName,
          CollectionId: CollectionId,
          Status: 'Created'
        }
      };
    } catch (error) {
      console.error('Error in handler:', error);
      throw error;
    }
  }
  
  throw new Error(`Unsupported request type: ${RequestType}`);
};

async function createIndexWithRetry(collectionEndpoint, indexName, indexMapping) {
  const maxRetries = 8;
  const initialRetryDelay = 15000; // 15 seconds - OpenSearch Serverless needs time to become active
  
  // First, check if index exists and has wrong dimensions - if so, delete it
  try {
    const existingIndex = await getIndex(collectionEndpoint, indexName);
    if (existingIndex) {
      const existingDimension = existingIndex?.mappings?.properties?.vector?.dimension;
      const targetDimension = indexMapping.mappings.properties.vector.dimension;
      console.log(`Existing index dimension: ${existingDimension}, target: ${targetDimension}`);
      
      if (existingDimension && existingDimension !== targetDimension) {
        console.log(`Dimension mismatch - deleting existing index to recreate with correct dimensions`);
        await deleteIndex(collectionEndpoint, indexName);
        // Wait for deletion to propagate
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
    }
  } catch (checkError) {
    console.log('Could not check existing index (may not exist):', checkError.message);
  }
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      console.log(`Attempt ${attempt + 1} of ${maxRetries} to create index ${indexName}...`);
      
      // Add a delay with exponential backoff
      if (attempt > 0) {
        const delayMs = initialRetryDelay * Math.pow(2, attempt - 1);
        console.log(`Waiting ${delayMs/1000} seconds before attempt ${attempt + 1}...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
      
      // Try to create the index
      const result = await createIndex(collectionEndpoint, indexName, indexMapping);
      console.log(`Index ${indexName} created successfully on attempt ${attempt + 1}`);
      return result;
    } catch (error) {
      console.error(`Attempt ${attempt + 1} failed:`, error);
      
      // Check if the error is because the index already exists
      if (error.message && (
          error.message.includes('resource_already_exists_exception') || 
          error.message.includes('index_already_exists_exception') ||
          error.message.includes('already exists')
      )) {
        
        return {
          statusCode: 200,
          body: JSON.stringify({ message: 'Index already exists' })
        };
      }
      
      // If this is the last attempt, throw the error
      if (attempt === maxRetries - 1) {
        throw error;
      }
      
      // For 403 errors, continue with retry (permissions may be propagating)
    }
  }
}

async function getIndex(collectionEndpoint, indexName) {
  const credentials = await defaultProvider()();
  const signer = new SignatureV4({
    credentials,
    region: process.env.AWS_REGION,
    service: 'aoss',
    sha256: Sha256
  });
  
  const url = new URL(collectionEndpoint);
  const request = {
    method: 'GET',
    hostname: url.hostname,
    path: `/${indexName}`,
    headers: {
      'Host': url.hostname
    }
  };
  
  const signedRequest = await signer.sign(request);
  
  return await new Promise((resolve, reject) => {
    const req = https.request({
      method: signedRequest.method,
      hostname: signedRequest.hostname,
      path: signedRequest.path,
      headers: signedRequest.headers
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode === 200) {
          const parsed = JSON.parse(data);
          resolve(parsed[indexName]);
        } else if (res.statusCode === 404) {
          resolve(null);
        } else {
          reject(new Error(`GET index failed: ${res.statusCode} ${data}`));
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

async function deleteIndex(collectionEndpoint, indexName) {
  const credentials = await defaultProvider()();
  const signer = new SignatureV4({
    credentials,
    region: process.env.AWS_REGION,
    service: 'aoss',
    sha256: Sha256
  });
  
  const url = new URL(collectionEndpoint);
  const request = {
    method: 'DELETE',
    hostname: url.hostname,
    path: `/${indexName}`,
    headers: {
      'Host': url.hostname
    }
  };
  
  const signedRequest = await signer.sign(request);
  
  return await new Promise((resolve, reject) => {
    const req = https.request({
      method: signedRequest.method,
      hostname: signedRequest.hostname,
      path: signedRequest.path,
      headers: signedRequest.headers
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log(`Delete index response: ${res.statusCode} ${data}`);
        resolve({ statusCode: res.statusCode, body: data });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

async function createIndex(collectionEndpoint, indexName, indexMapping) {
  // Get credentials from the default provider chain
  const credentials = await defaultProvider()();
    
    // Create a Signature V4 signer
    const signer = new SignatureV4({
      credentials,
      region: process.env.AWS_REGION,
      service: 'aoss',
      sha256: Sha256
    });
    
    // Parse the collection endpoint
    const url = new URL(collectionEndpoint);
    
    // Create the request
    const request = {
      method: 'PUT',
      hostname: url.hostname,
      path: `/${indexName}`,
      headers: {
        'Content-Type': 'application/json',
        'Host': url.hostname
      },
      body: JSON.stringify(indexMapping)
    };
    
    // Sign the request
    const signedRequest = await signer.sign(request);
    
    // Send the request
    return await new Promise((resolve, reject) => {
      const req = https.request({
        method: signedRequest.method,
        hostname: signedRequest.hostname,
        path: signedRequest.path,
        headers: signedRequest.headers
      }, (res) => {
        let data = '';
        res.on('data', (chunk) => {
          data += chunk;
        });
        res.on('end', () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve({
              statusCode: res.statusCode,
              body: data
            });
          } else if (data.includes('resource_already_exists_exception') || 
                    data.includes('index_already_exists_exception') ||
                    data.includes('already exists')) {
            // Index already exists - this is fine, treat as success
            
            resolve({
              statusCode: 200,
              body: JSON.stringify({ message: 'Index already exists' })
            });
          } else {
            reject(new Error(`HTTP error ${res.statusCode}: ${data}`));
          }
        });
      });
      
      req.on('error', (error) => {
        reject(error);
      });
      
      req.write(signedRequest.body);
      req.end();
    });
}