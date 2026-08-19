import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface MonitoringStackProps extends cdk.StackProps {
  alertEmail?: string;
}

export class MonitoringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: MonitoringStackProps) {
    super(scope, id, props);

    // Set parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Import chat function and API from SSM parameters
    const chatFunctionName = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/ChatFunctionName`
    );
    const chatFunction = lambda.Function.fromFunctionName(
      this,
      'ImportedChatFunction',
      chatFunctionName
    );

    const apiId = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/ApiId`
    );
    const apiName = 'Bedrock Agent Core API'; // Known API name from ApiStack

    // Create SNS topic for alerts
    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      topicName: 'Knowledge-Base-RAG-Agent-Alerts',
      displayName: 'Knowledge Base RAG Agent Alerts',
    });

    // Add email subscription (replace with actual email or use prop)
    const alertEmail = props?.alertEmail || 'admin@example.com';
    alertTopic.addSubscription(new subscriptions.EmailSubscription(alertEmail));

    // Create dashboard
    const dashboard = new cloudwatch.Dashboard(this, 'Dashboard', {
      dashboardName: 'Knowledge-Base-RAG-Agent',
    });

    // Add API metrics to dashboard
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Requests',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Count',
            dimensionsMap: {
              ApiName: apiName,
              Stage: 'v1',
            },
            statistic: 'Sum',
            period: cdk.Duration.minutes(1),
          }),
        ],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'API Latency',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/ApiGateway',
            metricName: 'Latency',
            dimensionsMap: {
              ApiName: apiName,
              Stage: 'v1',
            },
            statistic: 'Average',
            period: cdk.Duration.minutes(1),
          }),
        ],
        width: 12,
      })
    );

    // Add Lambda function metrics to dashboard
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Chat Function Invocations',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/Lambda',
            metricName: 'Invocations',
            dimensionsMap: {
              FunctionName: chatFunction.functionName,
            },
            statistic: 'Sum',
            period: cdk.Duration.minutes(1),
          }),
        ],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'Chat Function Duration',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/Lambda',
            metricName: 'Duration',
            dimensionsMap: {
              FunctionName: chatFunction.functionName,
            },
            statistic: 'Average',
            period: cdk.Duration.minutes(1),
          }),
        ],
        width: 12,
      }),
      new cloudwatch.GraphWidget({
        title: 'Chat Function Errors',
        left: [
          new cloudwatch.Metric({
            namespace: 'AWS/Lambda',
            metricName: 'Errors',
            dimensionsMap: {
              FunctionName: chatFunction.functionName,
            },
            statistic: 'Sum',
            period: cdk.Duration.minutes(1),
          }),
        ],
        width: 12,
      })
    );

    // Create Lambda function alarms
    // Error rate alarm
    const errorAlarm = new cloudwatch.Alarm(this, 'ChatFunctionErrorAlarm', {
      alarmName: 'Chat-Function-Error-Alarm',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Lambda',
        metricName: 'Errors',
        dimensionsMap: {
          FunctionName: chatFunction.functionName,
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      datapointsToAlarm: 1,
      alarmDescription: 'Chat function is experiencing errors',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    errorAlarm.addAlarmAction(new actions.SnsAction(alertTopic));

    // Duration alarm
    const durationAlarm = new cloudwatch.Alarm(this, 'ChatFunctionDurationAlarm', {
      alarmName: 'Chat-Function-Duration-Alarm',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/Lambda',
        metricName: 'Duration',
        dimensionsMap: {
          FunctionName: chatFunction.functionName,
        },
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 240000, // 4 minutes (close to 5 minute timeout)
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      alarmDescription: 'Chat function duration is approaching timeout',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    durationAlarm.addAlarmAction(new actions.SnsAction(alertTopic));

    // API 5xx error alarm with environment-specific name
    const api5xxErrorAlarm = new cloudwatch.Alarm(this, 'Api5xxErrorAlarm', {
      alarmName: 'API-5xx-Error-Alarm',
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: '5XXError',
        dimensionsMap: {
          ApiName: apiName,
          Stage: 'v1',
        },
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 3,
      datapointsToAlarm: 2,
      alarmDescription: 'API is returning 5XX errors',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    api5xxErrorAlarm.addAlarmAction(new actions.SnsAction(alertTopic));

    // Store monitoring resources in SSM Parameter Store
    new ssm.StringParameter(this, 'DashboardNameParameter', {
      parameterName: `${paramPrefix}/Monitoring/DashboardName`,
      description: 'CloudWatch Dashboard Name',
      stringValue: dashboard.dashboardName,
    });

    new ssm.StringParameter(this, 'AlertTopicArnParameter', {
      parameterName: `${paramPrefix}/Monitoring/AlertTopicArn`,
      description: 'SNS Alert Topic ARN',
      stringValue: alertTopic.topicArn,
    });

    // Outputs
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${dashboard.dashboardName}`,
      description: 'Dashboard URL',
      exportName: `${this.stackName}-DashboardUrl`,
    });

    new cdk.CfnOutput(this, 'AlertTopicArn', {
      value: alertTopic.topicArn,
      description: 'Alert topic ARN',
      exportName: `${this.stackName}-AlertTopicArn`,
    });

    // Tag all resources
    cdk.Tags.of(this).add('Project', 'AgentCoreTemplate');
  }
}
