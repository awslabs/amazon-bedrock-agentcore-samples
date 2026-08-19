import * as cdk from 'aws-cdk-lib/core'

export interface BaseStackProps extends cdk.StackProps {
    appName: string
}