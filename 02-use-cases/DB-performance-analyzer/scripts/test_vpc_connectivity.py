#!/usr/bin/env python3
import boto3
import json
import os
import sys
import time

def test_ssm_connectivity():
    """Test connectivity to SSM service"""
    print("Testing connectivity to SSM service...")
    try:
        ssm_client = boto3.client('ssm')
        # Try to get a parameter that might not exist, but this will test connectivity
        try:
            response = ssm_client.get_parameter(Name='/AuroraOps/dev')
            print("✅ Successfully connected to SSM and retrieved parameter")
            print(f"Parameter value: {response['Parameter']['Value']}")
        except ssm_client.exceptions.ParameterNotFound:
            print("✅ Successfully connected to SSM (parameter not found, but connection works)")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to SSM: {str(e)}")
        return False

def test_secrets_manager_connectivity():
    """Test connectivity to Secrets Manager service"""
    print("\nTesting connectivity to Secrets Manager service...")
    try:
        sm_client = boto3.client('secretsmanager')
        # List secrets to test connectivity
        response = sm_client.list_secrets(MaxResults=1)
        print("✅ Successfully connected to Secrets Manager")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Secrets Manager: {str(e)}")
        return False

def test_cloudwatch_logs_connectivity():
    """Test connectivity to CloudWatch Logs service"""
    print("\nTesting connectivity to CloudWatch Logs service...")
    try:
        logs_client = boto3.client('logs')
        # List log groups to test connectivity
        response = logs_client.describe_log_groups(limit=1)
        print("✅ Successfully connected to CloudWatch Logs")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to CloudWatch Logs: {str(e)}")
        return False

def main():
    """Main function to test connectivity to AWS services"""
    print("=== Testing VPC Endpoint Connectivity ===")
    
    # Set region from environment or use default
    region = os.environ.get('AWS_REGION', 'us-west-2')
    print(f"Using AWS region: {region}")
    
    # Test connectivity to each service
    ssm_success = test_ssm_connectivity()
    sm_success = test_secrets_manager_connectivity()
    logs_success = test_cloudwatch_logs_connectivity()
    
    # Print summary
    print("\n=== Connectivity Test Summary ===")
    print(f"SSM: {'✅ Connected' if ssm_success else '❌ Failed'}")
    print(f"Secrets Manager: {'✅ Connected' if sm_success else '❌ Failed'}")
    print(f"CloudWatch Logs: {'✅ Connected' if logs_success else '❌ Failed'}")
    
    # Return exit code based on success
    if ssm_success and sm_success and logs_success:
        print("\n✅ All connectivity tests passed!")
        return 0
    else:
        print("\n❌ Some connectivity tests failed. Please check VPC endpoint configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())