#!/usr/bin/env python3
"""
Complete Market Trends Agent Deployment Script
Handles IAM role creation, permissions, container deployment, and agent setup
"""

import argparse
import json
import logging
import boto3
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MarketTrendsAgentDeployer:
    """Complete deployer for Market Trends Agent"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.iam_client = boto3.client("iam", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)

    def create_execution_role(self, role_name: str) -> str:
        """Create IAM execution role with all required permissions"""

        # Trust policy for Bedrock AgentCore
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        # Get account ID and region for specific resource ARNs
        account_id = boto3.client("sts").get_caller_identity()["Account"]

        # Comprehensive execution policy with least privilege permissions
        execution_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockModelInvocation",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{self.region}:{account_id}:*",
                    ],
                },
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                    "Resource": [
                        f"arn:aws:ecr:{self.region}:{account_id}:repository/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:DescribeLogGroups"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                    ],
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                    ],
                    "Resource": ["*"],
                },
                {
                    "Effect": "Allow",
                    "Resource": "*",
                    "Action": "cloudwatch:PutMetricData",
                    "Condition": {
                        "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                    },
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default/workload-identity/market-trends-agent-*",
                    ],
                },
                {
                    "Sid": "BedrockAgentCoreMemoryOperations",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:ListMemories",
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:RetrieveMemories",
                        "bedrock-agentcore:GetMemoryStrategies",
                        "bedrock-agentcore:DeleteMemory",
                        "bedrock-agentcore:GetMemory",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:memory/*"
                    ],
                },
                {
                    "Sid": "BedrockAgentCoreBrowserOperations",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetBrowserSession",
                        "bedrock-agentcore:StartBrowserSession",
                        "bedrock-agentcore:StopBrowserSession",
                        "bedrock-agentcore:CreateBrowserSession",
                        "bedrock-agentcore:DeleteBrowserSession",
                        "bedrock-agentcore:ConnectBrowserAutomationStream",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:browser-custom/*",
                        f"arn:aws:bedrock-agentcore:*:aws:browser/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:PutParameter",
                        "ssm:DeleteParameter",
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:{account_id}:parameter/bedrock-agentcore/market-trends-agent/*",
                    "Sid": "SSMParameterAccess",
                },
            ],
        }

        try:
            # Create the role
            logger.info(f"🔐 Creating IAM role: {role_name}")
            role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Execution role for Market Trends Agent with comprehensive permissions",
            )

            # Attach the comprehensive execution policy
            logger.info(
                f"📋 Attaching comprehensive execution policy to role: {role_name}"
            )
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="MarketTrendsAgentComprehensivePolicy",
                PolicyDocument=json.dumps(execution_policy),
            )

            role_arn = role_response["Role"]["Arn"]
            logger.info(f"✅ Created IAM role with ARN: {role_arn}")

            # Wait for role to propagate
            logger.info("⏳ Waiting for role to propagate...")
            time.sleep(10)

            return role_arn

        except self.iam_client.exceptions.EntityAlreadyExistsException:
            logger.info(f"📋 IAM role {role_name} already exists, using existing role")

            # Update the existing role with comprehensive permissions
            logger.info("📋 Updating existing role with comprehensive permissions...")
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="MarketTrendsAgentComprehensivePolicy",
                PolicyDocument=json.dumps(execution_policy),
            )

            role_response = self.iam_client.get_role(RoleName=role_name)
            return role_response["Role"]["Arn"]

        except Exception as e:
            logger.error(f"❌ Failed to create IAM role: {e}")
            raise

    def create_agentcore_memory(self) -> str:
        """Create AgentCore Memory and store ARN in SSM Parameter Store"""
        try:
            from bedrock_agentcore.memory import MemoryClient
            from bedrock_agentcore.memory.constants import StrategyType

            memory_name = "MarketTrendsAgentMultiStrategy"
            memory_client = MemoryClient(region_name=self.region)

            # Check if memory ARN already exists in SSM
            param_name = "/bedrock-agentcore/market-trends-agent/memory-arn"
            try:
                response = self.ssm_client.get_parameter(Name=param_name)
                existing_memory_arn = response["Parameter"]["Value"]
                logger.info(
                    f"✅ Found existing memory ARN in SSM: {existing_memory_arn}"
                )
                return existing_memory_arn
            except self.ssm_client.exceptions.ParameterNotFound:
                logger.info(
                    "No existing memory ARN found in SSM, creating new memory..."
                )

            # Check if memory exists by name
            try:
                memories = memory_client.list_memories()
                for memory in memories:
                    if (
                        memory.get("name") == memory_name
                        and memory.get("status") == "ACTIVE"
                    ):
                        memory_arn = memory["arn"]
                        logger.info(f"✅ Found existing active memory: {memory_arn}")

                        # Store in SSM for future use
                        self.ssm_client.put_parameter(
                            Name=param_name,
                            Value=memory_arn,
                            Type="String",
                            Overwrite=True,
                            Description="Memory ARN for Market Trends Agent",
                        )
                        logger.info("💾 Stored existing memory ARN in SSM")
                        return memory_arn
            except Exception as e:
                logger.warning(f"Error checking existing memories: {e}")

            # Create new memory
            logger.info("🧠 Creating new AgentCore Memory...")

            strategies = [
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "BrokerPreferences",
                        "description": "Captures broker preferences, risk tolerance, and investment styles",
                        "namespaces": ["market-trends/broker/{actorId}/preferences"],
                    }
                },
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "MarketTrendsSemantic",
                        "description": "Stores financial facts, market analysis, and investment insights",
                        "namespaces": ["market-trends/broker/{actorId}/semantic"],
                    }
                },
            ]

            memory = memory_client.create_memory_and_wait(
                name=memory_name,
                description="Market Trends Agent with multi-strategy memory for broker financial interests",
                strategies=strategies,
                event_expiry_days=90,
                max_wait=300,
                poll_interval=10,
            )

            memory_arn = memory["arn"]
            logger.info(f"✅ Memory created successfully: {memory_arn}")

            # Store memory ARN in SSM Parameter Store
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=memory_arn,
                Type="String",
                Overwrite=True,
                Description="Memory ARN for Market Trends Agent",
            )
            logger.info("💾 Memory ARN stored in SSM Parameter Store")

            return memory_arn

        except Exception as e:
            logger.error(f"❌ Failed to create memory: {e}")
            raise

    def deploy_agent(
        self,
        agent_name: str,
        role_name: str = "MarketTrendsAgentRole",
        entrypoint: str = "market_trends_agent.py",
        requirements_file: str = None,
    ) -> str:
        """Deploy the Market Trends Agent with all requirements"""

        try:
            from bedrock_agentcore_starter_toolkit import Runtime

            logger.info("🚀 Starting Market Trends Agent Deployment")
            logger.info(f"   📝 Agent Name: {agent_name}")
            logger.info(f"   📍 Region: {self.region}")
            logger.info(f"   🎯 Entrypoint: {entrypoint}")

            # Step 1: Determine dependency management approach
            if requirements_file is None:
                # Auto-detect: prefer uv if pyproject.toml exists, fallback to requirements.txt
                if Path("pyproject.toml").exists():
                    logger.info(
                        "📦 Using uv with pyproject.toml for dependency management"
                    )
                    requirements_file = "pyproject.toml"
                elif Path("requirements.txt").exists():
                    logger.info(
                        "📦 Using pip with requirements.txt for dependency management"
                    )
                    requirements_file = "requirements.txt"
                else:
                    raise FileNotFoundError(
                        "No pyproject.toml or requirements.txt found"
                    )

            logger.info(f"   📋 Dependencies: {requirements_file}")

            # Step 2: Create AgentCore Memory
            memory_arn = self.create_agentcore_memory()

            # Step 3: Create execution role with all permissions
            execution_role_arn = self.create_execution_role(role_name)

            # Step 4: Initialize runtime
            runtime = Runtime()

            # Step 5: Configure the runtime
            logger.info("⚙️ Configuring runtime...")

            runtime.configure(
                execution_role=execution_role_arn,
                entrypoint=entrypoint,
                requirements_file=requirements_file,
                region=self.region,
                agent_name=agent_name,
                auto_create_ecr=True,
            )

            logger.info("✅ Configuration completed")

            # Step 6: Launch the runtime
            logger.info("🚀 Launching runtime (this may take several minutes)...")
            logger.info("   📦 Building container image...")
            logger.info("   ⬆️ Pushing to ECR...")
            logger.info("   🏗️ Creating AgentCore Runtime...")

            runtime.launch(auto_update_on_conflict=True)

            logger.info("✅ Launch completed")

            # Step 7: Get status and extract ARN
            logger.info("📊 Getting runtime status...")
            status = runtime.status()

            # Extract runtime ARN
            runtime_arn = None
            if hasattr(status, "agent_arn"):
                runtime_arn = status.agent_arn
            elif hasattr(status, "config") and hasattr(status.config, "agent_arn"):
                runtime_arn = status.config.agent_arn

            if runtime_arn:
                # Save ARN to file
                arn_file = Path(".agent_arn")
                with open(arn_file, "w") as f:
                    f.write(runtime_arn)

                logger.info("\n🎉 Market Trends Agent Deployed Successfully!")
                logger.info(f"🏷️ Runtime ARN: {runtime_arn}")
                logger.info(f"🧠 Memory ARN: {memory_arn}")
                logger.info(f"� Regiotn: {self.region}")
                logger.info(f"� AExecution Role: {execution_role_arn}")
                logger.info(f"💾 ARN saved to: {arn_file}")

                # Show CloudWatch logs info
                agent_id = runtime_arn.split("/")[-1]
                log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"
                logger.info("\n📊 Monitoring:")
                logger.info(f"   CloudWatch Logs: {log_group}")
                logger.info(f"   Tail logs: aws logs tail {log_group} --follow")

                logger.info("\n📋 Next Steps:")
                logger.info("1. Test your agent: python test_agent.py")
                logger.info("2. Monitor logs in CloudWatch")
                logger.info("3. Use the Runtime ARN for integrations")

                return runtime_arn
            else:
                logger.error("❌ Could not extract runtime ARN")
                logger.info(f"Status: {status}")
                return None

        except ImportError:
            logger.error("❌ bedrock-agentcore-starter-toolkit not installed")
            if Path("pyproject.toml").exists():
                logger.info("Install with: uv add bedrock-agentcore-starter-toolkit")
            else:
                logger.info(
                    "Install with: pip install bedrock-agentcore-starter-toolkit"
                )
            return None
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            import traceback

            logger.error(f"Full error: {traceback.format_exc()}")
            return None


def check_prerequisites():
    """Check if all prerequisites are met"""
    logger.info("🔍 Checking prerequisites...")

    # Check if required files exist
    required_files = [
        "market_trends_agent.py",
        "tools/browser_tool.py",
        "tools/broker_card_tools.py",
        "tools/memory_tools.py",
        "tools/__init__.py",
    ]

    # Check for dependency files (either pyproject.toml or requirements.txt)
    has_pyproject = Path("pyproject.toml").exists()
    has_requirements = Path("requirements.txt").exists()

    if not has_pyproject and not has_requirements:
        logger.error("❌ No dependency file found (pyproject.toml or requirements.txt)")
        return False

    if has_pyproject:
        logger.info("✅ Found pyproject.toml - will use uv for dependency management")
    elif has_requirements:
        logger.info(
            "✅ Found requirements.txt - will use pip for dependency management"
        )

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        logger.error(f"❌ Missing required files: {missing_files}")
        return False

    # Note: Docker/Podman not required - AgentCore uses AWS CodeBuild for container building
    logger.info(
        "✅ Container building will use AWS CodeBuild (no local Docker required)"
    )

    # Check AWS credentials
    try:
        boto3.client("sts").get_caller_identity()
        logger.info("✅ AWS credentials configured")
    except Exception as e:
        logger.error(f"❌ AWS credentials not configured: {e}")
        return False

    logger.info("✅ All prerequisites met")
    return True


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Deploy Market Trends Agent to Amazon Bedrock AgentCore Runtime"
    )
    parser.add_argument(
        "--agent-name",
        default="market_trends_agent",
        help="Name for the agent (default: market_trends_agent)",
    )
    parser.add_argument(
        "--role-name",
        default="MarketTrendsAgentRole",
        help="IAM role name (default: MarketTrendsAgentRole)",
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip prerequisite checks"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not args.skip_checks and not check_prerequisites():
        logger.error("❌ Prerequisites not met. Fix issues above or use --skip-checks")
        exit(1)

    # Create deployer and deploy
    deployer = MarketTrendsAgentDeployer(region=args.region)

    runtime_arn = deployer.deploy_agent(
        agent_name=args.agent_name, role_name=args.role_name
    )

    if runtime_arn:
        logger.info("\n🎯 Deployment completed successfully!")
        logger.info("Run 'python test_agent.py' to test your deployed agent.")
    else:
        logger.error("❌ Deployment failed")
        exit(1)


if __name__ == "__main__":
    main()
