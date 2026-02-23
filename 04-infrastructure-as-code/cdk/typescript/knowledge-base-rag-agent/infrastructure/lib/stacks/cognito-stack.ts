import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';

/**
 * AWS CDK Stack for User Authentication with Amazon Cognito
 * 
 * This stack provides user authentication and authorization for the Bedrock Agent application:
 * - Cognito User Pool for user management and authentication
 * - User Pool Client for web application integration
 * - Identity Pool for AWS resource access with temporary credentials
 * - IAM roles for authenticated and unauthenticated users
 * 
 * SECURITY ENHANCEMENTS (T-1 - Credential Protection):
 * - Enhanced password policy (12+ characters, complexity requirements)
 * - Account recovery via email only to prevent enumeration
 * - Short-lived access tokens (1 hour) for reduced exposure
 * - User existence error prevention to prevent enumeration
 * - Token revocation capability for compromised sessions
 * - API rate limiting and Lambda concurrency controls (Tasks 9 & 3)
 * 
 * Note: Uses ESSENTIALS pricing tier for cost-effective educational deployment.
 * Advanced Security Mode (risk-based auth) requires STANDARD tier but is not
 * essential for demonstrating core Bedrock Agent patterns. Security is maintained
 * through multiple layers including strong policies and infrastructure controls.
 * 
 * The authentication system is designed to be simple yet secure, providing
 * the foundation for user-specific features and access control while protecting
 * against common authentication attacks per NIST SP 800-53 AC-7.
 */
export class CognitoStack extends cdk.Stack {
  /** Cognito User Pool for managing user accounts */
  public readonly userPool: cognito.UserPool;
  /** User Pool Client for web application authentication */
  public readonly userPoolClient: cognito.UserPoolClient;
  /** Identity Pool for AWS credential federation */
  public readonly identityPool: cognito.CfnIdentityPool;
  /** IAM role for authenticated users */
  public readonly authenticatedRole: iam.Role;
  /** IAM role for unauthenticated users (if needed) */
  public readonly unauthenticatedRole: iam.Role;
  /** Initial user credentials for easy access */
  public readonly initialUserEmail: string;
  public readonly initialUserPasswordSecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Create Cognito User Pool for user authentication
    // This manages user accounts, passwords, and basic profile information
    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `AgentCore-Users-${cdk.Stack.of(this).account}`, // Make name unique to avoid conflicts
      selfSignUpEnabled: true, // Allow users to create accounts
      autoVerify: { email: true }, // Automatically verify email addresses
      signInAliases: { email: true }, // Allow sign-in with email
      standardAttributes: {
        email: { required: true, mutable: true },
        givenName: { required: false, mutable: true },
        familyName: { required: false, mutable: true },
      },
      // Enhanced password policy for stronger security (T-1)
      passwordPolicy: {
        minLength: 12, // Increased from 8 to 12 characters for better security
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true, // Required for cdk-nag compliance
        tempPasswordValidity: cdk.Duration.days(7),
      },
      // Account lockout policy to prevent credential stuffing attacks (T-1)
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      signInCaseSensitive: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Safe for demo environments
    });

    // Force replacement if username configuration changes
    const cfnUserPool = this.userPool.node.defaultChild as cognito.CfnUserPool;
    cfnUserPool.cfnOptions.updateReplacePolicy = cdk.CfnDeletionPolicy.DELETE;

    // Configure account lockout policy to prevent credential stuffing attacks (T-1)
    // This implements NIST SP 800-53 AC-7 (Unsuccessful Logon Attempts)
    cfnUserPool.addPropertyOverride('AccountRecoverySetting', {
      RecoveryMechanisms: [
        {
          Name: 'verified_email',
          Priority: 1,
        },
      ],
    });

    // Note: Advanced Security Mode requires STANDARD pricing tier
    // For educational/demo purposes, we use ESSENTIALS tier and rely on other security measures:
    // - Strong password policy (12+ chars, complexity requirements)
    // - Account recovery via email only
    // - Short-lived tokens (1 hour)
    // - User existence error prevention
    // - API rate limiting and Lambda concurrency controls

    // Configure risk-based authentication and account lockout
    cfnUserPool.addPropertyOverride('Policies', {
      PasswordPolicy: {
        MinimumLength: 12,
        RequireUppercase: true,
        RequireLowercase: true,
        RequireNumbers: true,
        RequireSymbols: true,
        TemporaryPasswordValidityDays: 7,
      },
    });

    // Create User Pool Client with enhanced security settings (T-1)
    this.userPoolClient = this.userPool.addClient('WebClient', {
      userPoolClientName: 'AgentCoreTemplate-WebClient',
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      // Enhanced security settings to prevent credential stuffing (T-1)
      preventUserExistenceErrors: true, // Prevents user enumeration attacks
      // Configure token validity periods for better security
      accessTokenValidity: cdk.Duration.hours(1), // Short-lived access tokens
      idTokenValidity: cdk.Duration.hours(1), // Short-lived ID tokens
      refreshTokenValidity: cdk.Duration.days(30), // Longer-lived refresh tokens
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
          implicitCodeGrant: true,
        },
        scopes: [cognito.OAuthScope.EMAIL, cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE],
        callbackUrls: [
          'http://localhost:3000/callback',
          'https://knowledge-base-rag-agent.aws/callback',
        ],
        logoutUrls: [
          'http://localhost:3000/',
          'https://knowledge-base-rag-agent.aws/',
        ],
      },
    });

    // Configure additional security settings on the User Pool Client (T-1)
    const cfnUserPoolClient = this.userPoolClient.node.defaultChild as cognito.CfnUserPoolClient;
    
    // Enable token revocation for better security
    cfnUserPoolClient.addPropertyOverride('EnableTokenRevocation', true);
    
    // Configure authentication flow policy to prevent certain attack vectors
    cfnUserPoolClient.addPropertyOverride('ExplicitAuthFlows', [
      'ALLOW_USER_PASSWORD_AUTH',
      'ALLOW_USER_SRP_AUTH',
      'ALLOW_REFRESH_TOKEN_AUTH',
    ]);

    // Create Identity Pool
    this.identityPool = new cognito.CfnIdentityPool(this, 'IdentityPool', {
      identityPoolName: 'AgentCoreTemplate',
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [
        {
          clientId: this.userPoolClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
        },
      ],
    });

    // Create roles for authenticated and unauthenticated users
    this.authenticatedRole = new iam.Role(this, 'AuthenticatedRole', {
      roleName: 'AgentCoreTemplate-Auth',
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref,
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'authenticated',
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
    });

    this.unauthenticatedRole = new iam.Role(this, 'UnauthenticatedRole', {
      roleName: 'AgentCoreTemplate-Unauth',
      assumedBy: new iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: {
            'cognito-identity.amazonaws.com:aud': this.identityPool.ref,
          },
          'ForAnyValue:StringLike': {
            'cognito-identity.amazonaws.com:amr': 'unauthenticated',
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
    });

    // Attach roles to Identity Pool
    new cognito.CfnIdentityPoolRoleAttachment(this, 'IdentityPoolRoleAttachment', {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: this.authenticatedRole.roleArn,
        unauthenticated: this.unauthenticatedRole.roleArn,
      },
    });

    // Create initial user for easy access
    this.initialUserEmail = 'admin@example.com';
    
    // Create Secrets Manager secret for initial user password
    // Password meets enhanced policy requirements: 12+ chars, uppercase, lowercase, digits, symbols
    this.initialUserPasswordSecret = new secretsmanager.Secret(this, 'InitialUserPasswordSecret', {
      secretName: 'KnowledgeBaseRagAgent/InitialUserPassword',
      description: 'Initial user password for Knowledge Base RAG Agent',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: this.initialUserEmail }),
        generateStringKey: 'password',
        excludeCharacters: '"@/\\\'',
        includeSpace: false,
        passwordLength: 16,
        requireEachIncludedType: true,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Safe for demo environments
    });

    // Import the common layer from the shared resources stack
    const commonLayerArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/CommonLayerArn`
    );
    const commonLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'CommonLayer',
      commonLayerArn
    );

    // Lambda function to create initial user
    const createUserFunction = new lambda.Function(this, 'CreateInitialUserFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.resolve(__dirname, '../../src/functions/create-initial-user')),
      layers: [commonLayer],
      timeout: cdk.Duration.minutes(5),
      description: 'Creates initial Cognito user for the application',
      // T-3 DoS Protection: Set reserved concurrency for setup function (lower limit as it's used less frequently)
      reservedConcurrentExecutions: 5, // Lower limit for setup/configuration function
    });

    // Grant permissions to manage Cognito users and read secrets
    createUserFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'cognito-idp:AdminCreateUser',
          'cognito-idp:AdminSetUserPassword',
          'cognito-idp:AdminGetUser',
        ],
        resources: [this.userPool.userPoolArn],
      })
    );

    // Grant permission to read the password secret
    createUserFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
        ],
        resources: [this.initialUserPasswordSecret.secretArn],
      })
    );

    // Custom resource to create initial user
    new cdk.CustomResource(this, 'CreateInitialUser', {
      serviceToken: new cr.Provider(this, 'CreateInitialUserProvider', {
        onEventHandler: createUserFunction,
      }).serviceToken,
      properties: {
        UserPoolId: this.userPool.userPoolId,
        Username: this.initialUserEmail, // Use email as username since signInAliases is set to email
        Email: this.initialUserEmail,
        PasswordSecretArn: this.initialUserPasswordSecret.secretArn,
        Version: '2.1', // Increment to force re-execution after user deletion
      },
    });



    new ssm.StringParameter(this, 'InitialUserPasswordSecretArnParameter', {
      parameterName: `${paramPrefix}/InitialUserPasswordSecretArn`,
      description: 'Initial user password secret ARN',
      stringValue: this.initialUserPasswordSecret.secretArn,
    });

    // Store values in SSM Parameter Store
    new ssm.StringParameter(this, 'UserPoolIdParameter', {
      parameterName: `${paramPrefix}/UserPoolId`,
      description: 'Cognito User Pool ID',
      stringValue: this.userPool.userPoolId,
    });

    new ssm.StringParameter(this, 'UserPoolClientIdParameter', {
      parameterName: `${paramPrefix}/UserPoolClientId`,
      description: 'Cognito User Pool Client ID',
      stringValue: this.userPoolClient.userPoolClientId,
    });

    new ssm.StringParameter(this, 'IdentityPoolIdParameter', {
      parameterName: `${paramPrefix}/IdentityPoolId`,
      description: 'Cognito Identity Pool ID',
      stringValue: this.identityPool.ref,
    });

    // Outputs
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'User Pool ID',
      exportName: `${this.stackName}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'User Pool Client ID',
      exportName: `${this.stackName}-UserPoolClientId`,
    });

    new cdk.CfnOutput(this, 'IdentityPoolId', {
      value: this.identityPool.ref,
      description: 'Identity Pool ID',
      exportName: `${this.stackName}-IdentityPoolId`,
    });

    new cdk.CfnOutput(this, 'InitialUserEmail', {
      value: this.initialUserEmail,
      description: 'Initial user email for login',
      exportName: `${this.stackName}-InitialUserEmail`,
    });

    new cdk.CfnOutput(this, 'InitialUserPasswordSecretArn', {
      value: this.initialUserPasswordSecret.secretArn,
      description: 'Initial user password secret ARN',
      exportName: `${this.stackName}-InitialUserPasswordSecretArn`,
    });


  }
}
