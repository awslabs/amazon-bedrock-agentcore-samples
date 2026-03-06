import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export class VisaStubStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda function for VirtualCardRequisition
    const virtualCardLambda = new lambda.Function(this, 'VirtualCardRequisition', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.virtualCardRequisition',
      code: lambda.Code.fromAsset('lambda/visa-stubs'),
      description: 'Visa B2B Virtual Card Requisition Stub API',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        RESPONSE_MODE: 'SUCCESS', // SUCCESS, FAILURE, TIMEOUT
      },
    });

    // Lambda function for ProcessPayments
    const processPaymentsLambda = new lambda.Function(this, 'ProcessPayments', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.processPayments',
      code: lambda.Code.fromAsset('lambda/visa-stubs'),
      description: 'Visa B2B Process Payments Stub API',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        RESPONSE_MODE: 'SUCCESS',
      },
    });

    // Lambda function for GetPaymentDetails
    const getPaymentDetailsLambda = new lambda.Function(this, 'GetPaymentDetails', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.getPaymentDetails',
      code: lambda.Code.fromAsset('lambda/visa-stubs'),
      description: 'Visa B2B Get Payment Details Stub API',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        RESPONSE_MODE: 'SUCCESS',
      },
    });

    // Lambda function for GetSecurityCode
    const getSecurityCodeLambda = new lambda.Function(this, 'GetSecurityCode', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.getSecurityCode',
      code: lambda.Code.fromAsset('lambda/visa-stubs'),
      description: 'Visa B2B Get Security Code (CVV2) Stub API',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        RESPONSE_MODE: 'SUCCESS',
      },
    });

    // API Gateway for Visa B2B stub endpoints
    const api = new apigateway.RestApi(this, 'VisaStubApi', {
      restApiName: 'visa-b2b-stub-api',
      description: 'Visa B2B Virtual Account Payment stub API',
      deployOptions: {
        stageName: 'v1',
        // Disable logging to avoid CloudWatch Logs role requirement
        loggingLevel: apigateway.MethodLoggingLevel.OFF,
        dataTraceEnabled: false,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    // Create resource structure: /vpa/v1/accountManagement/VirtualCardRequisition
    const vpaResource = api.root.addResource('vpa');
    const v1Resource = vpaResource.addResource('v1');
    
    // Account Management endpoints
    const accountMgmtResource = v1Resource.addResource('accountManagement');
    
    const virtualCardResource = accountMgmtResource.addResource('VirtualCardRequisition');
    virtualCardResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(virtualCardLambda, {
        proxy: true,
      })
    );

    const getSecurityCodeResource = accountMgmtResource.addResource('GetSecurityCode');
    getSecurityCodeResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(getSecurityCodeLambda, {
        proxy: true,
      })
    );

    // Payment endpoints
    const paymentResource = v1Resource.addResource('payment');
    
    const processPaymentsResource = paymentResource.addResource('ProcessPayments');
    processPaymentsResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(processPaymentsLambda, {
        proxy: true,
      })
    );

    const getPaymentDetailsResource = paymentResource.addResource('GetPaymentDetails');
    getPaymentDetailsResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(getPaymentDetailsLambda, {
        proxy: true,
      })
    );

    // Outputs
    new cdk.CfnOutput(this, 'VisaStubApiUrl', {
      value: api.url,
      description: 'Visa B2B Stub API Gateway URL',
      exportName: 'VisaStubApiUrl',
    });

    new cdk.CfnOutput(this, 'VirtualCardRequisitionEndpoint', {
      value: `${api.url}vpa/v1/accountManagement/VirtualCardRequisition`,
      description: 'Virtual Card Requisition endpoint',
    });

    new cdk.CfnOutput(this, 'ProcessPaymentsEndpoint', {
      value: `${api.url}vpa/v1/payment/ProcessPayments`,
      description: 'Process Payments endpoint',
    });

    new cdk.CfnOutput(this, 'GetPaymentDetailsEndpoint', {
      value: `${api.url}vpa/v1/payment/GetPaymentDetails`,
      description: 'Get Payment Details endpoint',
    });

    new cdk.CfnOutput(this, 'GetSecurityCodeEndpoint', {
      value: `${api.url}vpa/v1/accountManagement/GetSecurityCode`,
      description: 'Get Security Code (CVV2) endpoint',
    });
  }
}
