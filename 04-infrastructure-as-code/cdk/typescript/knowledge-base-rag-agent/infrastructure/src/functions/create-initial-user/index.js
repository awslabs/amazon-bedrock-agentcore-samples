const { CognitoIdentityProviderClient, AdminCreateUserCommand, AdminSetUserPasswordCommand } = require('@aws-sdk/client-cognito-identity-provider');
const { SecretsManagerClient, GetSecretValueCommand } = require('@aws-sdk/client-secrets-manager');

exports.handler = async (event) => {
  // Log event but exclude sensitive data
  const sanitizedEvent = {
    ...event,
    ResourceProperties: {
      ...event.ResourceProperties,
      PasswordSecretArn: event.ResourceProperties.PasswordSecretArn ? '[REDACTED]' : undefined,
    }
  };
  console.log('Event:', JSON.stringify(sanitizedEvent, null, 2));
  
  const { RequestType, PhysicalResourceId } = event;
  const { UserPoolId, Username, Email, PasswordSecretArn } = event.ResourceProperties;
  
  const resourceId = PhysicalResourceId || `InitialUser-${Username}`;
  
  if (RequestType === 'Delete') {
    console.log('Delete request - no action needed for user creation');
    return { PhysicalResourceId: resourceId };
  }
  
  if (RequestType === 'Create' || RequestType === 'Update') {
    try {
      const cognito = new CognitoIdentityProviderClient({ region: process.env.AWS_REGION });
      const secretsManager = new SecretsManagerClient({ region: process.env.AWS_REGION });
      
      // Retrieve password from Secrets Manager
      let temporaryPassword;
      try {
        const secretResponse = await secretsManager.send(new GetSecretValueCommand({
          SecretId: PasswordSecretArn,
        }));
        
        const secretData = JSON.parse(secretResponse.SecretString);
        temporaryPassword = secretData.password;
        console.log('Successfully retrieved password from Secrets Manager');
      } catch (error) {
        console.error('Error retrieving password from Secrets Manager:', error);
        throw new Error('Failed to retrieve password from Secrets Manager');
      }
      
      // Create the user
      const createUserParams = {
        UserPoolId: UserPoolId,
        Username: Username,
        UserAttributes: [
          {
            Name: 'email',
            Value: Email,
          },
          {
            Name: 'email_verified',
            Value: 'true',
          },
        ],
        TemporaryPassword: temporaryPassword,
        MessageAction: 'SUPPRESS', // Don't send welcome email
      };
      
      try {
        await cognito.send(new AdminCreateUserCommand(createUserParams));
        console.log(`User ${Username} created successfully`);
      } catch (error) {
        if (error.name === 'UsernameExistsException') {
          console.log(`User ${Username} already exists, skipping creation`);
        } else {
          throw error;
        }
      }
      
      // Set permanent password
      const setPasswordParams = {
        UserPoolId: UserPoolId,
        Username: Username,
        Password: temporaryPassword,
        Permanent: true,
      };
      
      await cognito.send(new AdminSetUserPasswordCommand(setPasswordParams));
      console.log(`Password set for user ${Username}`);
      
      return {
        PhysicalResourceId: resourceId,
        Data: {
          Username: Username,
          Email: Email,
          // Never return the password in the response data
        },
      };
    } catch (error) {
      console.error('Error creating user:', error);
      throw error;
    }
  }
  
  throw new Error(`Unsupported request type: ${RequestType}`);
};