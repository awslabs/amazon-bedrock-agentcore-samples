#!/usr/bin/env python3
"""
Deployment script for Claude Code on Amazon Bedrock AgentCore.
This script handles the manual deployment process to preserve our custom Dockerfile.
"""

import os
import sys
import json
import boto3
import subprocess
from typing import Optional, Union, List

# Configuration
AGENT_NAME = "claude-code-agent"
REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
ECR_REPO_NAME = f"bedrock-agentcore-{AGENT_NAME}"
IMAGE_TAG = "latest"
ROLE_NAME = "claude-code-agentcore-role"

# Clients
ecr_client = boto3.client("ecr", region_name=REGION)
agentcore_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
iam_client = boto3.client("iam", region_name=REGION)


def run_command(command: Union[str, List[str]], check: bool = True, use_shell: bool = False) -> subprocess.CompletedProcess:
    """Run a command and return the result.
    
    Args:
        command: Command to run (as list for shell=False, or string for shell=True)
        check: Whether to check return code and exit on failure
        use_shell: Whether to use shell (only for commands with pipes)
    """
    if isinstance(command, str):
        if use_shell:
            # Only use shell=True when explicitly needed (for pipes)
            print(f"Running: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
        else:
            # Convert string to list for shell=False
            cmd_list = command.split()
            print(f"Running: {' '.join(cmd_list)}")
            result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True)
    else:
        # Use list directly
        print(f"Running: {' '.join(command)}")
        result = subprocess.run(command, shell=False, capture_output=True, text=True)
    
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def create_ecr_repository() -> str:
    """Create ECR repository if it doesn't exist."""
    try:
        response = ecr_client.create_repository(
            repositoryName=ECR_REPO_NAME,
            imageScanningConfiguration={"scanOnPush": True},
            imageTagMutability="MUTABLE",
        )
        print(f"✅ Created ECR repository: {ECR_REPO_NAME}")
    except ecr_client.exceptions.RepositoryAlreadyExistsException:
        print(f"ℹ️  ECR repository already exists: {ECR_REPO_NAME}")
    
    # Get repository URI
    response = ecr_client.describe_repositories(repositoryNames=[ECR_REPO_NAME])
    repo_uri = response["repositories"][0]["repositoryUri"]
    return repo_uri


def setup_docker_buildx():
    """Set up Docker buildx for multi-platform builds."""
    print("\n🔧 Setting up Docker buildx...")
    
    # Check if buildx builder exists - this needs shell for pipe
    result = run_command("docker buildx ls | grep claude-code-builder", check=False, use_shell=True)
    if result.returncode != 0:
        # Create new builder
        run_command(["docker", "buildx", "create", "--name", "claude-code-builder", "--use"])
    else:
        # Use existing builder
        run_command(["docker", "buildx", "use", "claude-code-builder"])
    
    # Start the builder
    run_command(["docker", "buildx", "inspect", "--bootstrap"])
    print("✅ Docker buildx ready")


def build_and_push_image(repo_uri: str) -> str:
    """Build and push Docker image to ECR."""
    print(f"\n🐳 Building Docker image...")
    
    # Login to ECR - needs to use shell for pipe
    print("Logging in to ECR...")
    ecr_password = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", REGION],
        capture_output=True,
        text=True
    )
    if ecr_password.returncode != 0:
        print(f"Error getting ECR password: {ecr_password.stderr}")
        sys.exit(1)
    
    docker_login = subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", 
         f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com"],
        input=ecr_password.stdout,
        capture_output=True,
        text=True
    )
    if docker_login.returncode != 0:
        print(f"Error logging in to Docker: {docker_login.stderr}")
        sys.exit(1)
    print("✅ Logged in to ECR")
    
    # Build and push image for ARM64 (Graviton)
    image_uri = f"{repo_uri}:{IMAGE_TAG}"
    print(f"Building and pushing image: {image_uri}")
    
    build_command = [
        "docker", "buildx", "build",
        "--platform", "linux/arm64",
        "-t", image_uri,
        "--push",
        "."
    ]
    
    run_command(build_command)
    print(f"✅ Image pushed to ECR: {image_uri}")
    
    # Verify image was pushed
    response = ecr_client.describe_images(
        repositoryName=ECR_REPO_NAME,
        imageIds=[{"imageTag": IMAGE_TAG}]
    )
    
    if response["imageDetails"]:
        print(f"✅ Image verified in ECR")
    else:
        print("❌ Image not found in ECR")
        sys.exit(1)
    
    return image_uri


def get_execution_role_arn() -> str:
    """Get the IAM execution role ARN."""
    try:
        response = iam_client.get_role(RoleName=ROLE_NAME)
        role_arn = response["Role"]["Arn"]
        print(f"✅ Found IAM role: {role_arn}")
        return role_arn
    except iam_client.exceptions.NoSuchEntityException:
        print(f"❌ IAM role not found: {ROLE_NAME}")
        print("Please run the IAM setup script first:")
        print("  cd iam && ./setup-iam-role.sh")
        sys.exit(1)


def deploy_agent_runtime(image_uri: str, role_arn: str) -> str:
    """Deploy the agent runtime to AgentCore."""
    print("\n🚀 Deploying agent runtime...")
    
    # Use underscores instead of hyphens for runtime name (AWS naming constraint)
    runtime_name = "claude_code_agent_runtime"
    
    try:
        # Check if runtime already exists
        existing_runtimes = agentcore_client.list_agent_runtimes()
        
        for runtime in existing_runtimes.get("agentRuntimes", []):
            if runtime["agentRuntimeName"] == runtime_name:
                print(f"ℹ️  Agent runtime already exists: {runtime_name}")
                # Update existing runtime - use correct parameter names
                response = agentcore_client.update_agent_runtime(
                    agentRuntimeId=runtime["agentRuntimeId"],  # Changed from agentRuntimeArn
                    agentRuntimeArtifact={
                        "containerConfiguration": {
                            "containerUri": image_uri
                        }
                    },
                    roleArn=role_arn,  # Added required parameter
                    networkConfiguration={"networkMode": "PUBLIC"}  # Added required parameter
                )
                print(f"✅ Updated agent runtime: {runtime_name}")
                return runtime["agentRuntimeArn"]
        
        # Create new runtime
        response = agentcore_client.create_agent_runtime(
            agentRuntimeName=runtime_name,
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": image_uri
                }
            },
            networkConfiguration={"networkMode": "PUBLIC"},
            roleArn=role_arn,
            description="Claude Code autonomous coding agent"
        )
        
        print(f"✅ Created agent runtime: {runtime_name}")
        return response["agentRuntimeArn"]
        
    except Exception as e:
        print(f"❌ Error deploying agent runtime: {e}")
        sys.exit(1)


def main():
    """Main deployment process."""
    print("="*60)
    print("🚀 Claude Code Deployment for Amazon Bedrock AgentCore")
    print("="*60)
    print(f"Account ID: {ACCOUNT_ID}")
    print(f"Region: {REGION}")
    print(f"Agent Name: {AGENT_NAME}")
    print("="*60)
    
    # Step 1: Create ECR repository
    repo_uri = create_ecr_repository()
    
    # Step 2: Setup Docker buildx
    setup_docker_buildx()
    
    # Step 3: Build and push Docker image
    image_uri = build_and_push_image(repo_uri)
    
    # Step 4: Get IAM role
    role_arn = get_execution_role_arn()
    
    # Step 5: Deploy agent runtime
    runtime_arn = deploy_agent_runtime(image_uri, role_arn)
    
    # Print success message
    print("\n" + "="*60)
    print("✅ DEPLOYMENT SUCCESSFUL!")
    print("="*60)
    print(f"Agent Runtime ARN: {runtime_arn}")
    print(f"Container Image: {image_uri}")
    print("\n📝 To invoke the agent, use:")
    print(f"""
aws bedrock-agentcore invoke-agent-runtime \\
    --agent-runtime-arn {runtime_arn} \\
    --region {REGION} \\
    --payload '{{"prompt": "Create a coffee shop website called Brew Haven with menu, location, and contact sections. Deploy it to S3 and CloudFront."}}' \\
    claude_code_agent_response.json
    """)
    print("\n📊 View logs in CloudWatch:")
    print(f"  /aws/bedrock-agentcore/runtimes/claude_code_agent_runtime")
    print("="*60)


if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("Dockerfile"):
        print("❌ Error: Dockerfile not found. Please run this script from the headless-mode directory.")
        sys.exit(1)
    
    main()
