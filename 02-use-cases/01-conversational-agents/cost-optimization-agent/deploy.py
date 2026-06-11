#!/usr/bin/env python3
"""
Complete Cost Optimization Agent Deployment Script
Handles IAM role creation, permissions, container deployment, and agent setup
"""

import argparse
import json
import logging
import boto3
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CostOptimizationAgentDeployer:
    """Complete deployer for Cost Optimization Agent"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.iam_client = boto3.client("iam", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)

        # Resource tags for consistent tagging
        self.resource_tags = [
            {"Key": "Project", "Value": "bedrock-agentcore-cost-optimization"},
            {"Key": "Agent", "Value": "cost_optimization_agent"},
            {"Key": "ManagedBy", "Value": "bedrock-agentcore-samples"},
        ]

        # Tags as dict for services that need that format
        self.resource_tags_dict = {tag["Key"]: tag["Value"] for tag in self.resource_tags}

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

        # Get account ID for specific resource ARNs
        account_id = boto3.client("sts").get_caller_identity()["Account"]

        # Comprehensive execution policy
        execution_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AmazonBedrockModelInvocation",
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
                    "Sid": "CostExplorerAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ce:GetCostAndUsage",
                        "ce:GetCostForecast",
                        "ce:GetAnomalies",
                        "ce:GetSavingsPlansCoverage",
                        "ce:GetSavingsPlansUtilization",
                        "ce:GetReservationCoverage",
                        "ce:GetReservationUtilization",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "BudgetsAccess",
                    "Effect": "Allow",
                    "Action": [
                        "budgets:DescribeBudget",
                        "budgets:DescribeBudgets",
                        "budgets:ViewBudget",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "ComputeOptimizerAccess",
                    "Effect": "Allow",
                    "Action": [
                        "compute-optimizer:GetEC2InstanceRecommendations",
                        "compute-optimizer:GetEBSVolumeRecommendations",
                        "compute-optimizer:GetLambdaFunctionRecommendations",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "EC2ReadAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ec2:DescribeInstances",
                        "ec2:DescribeVolumes",
                        "ec2:DescribeSnapshots",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatchAccess",
                    "Effect": "Allow",
                    "Action": [
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:ListMetrics",
                        "cloudwatch:PutMetricData",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "PricingAccess",
                    "Effect": "Allow",
                    "Action": [
                        "pricing:GetProducts",
                        "pricing:DescribeServices",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                    "Resource": [f"arn:aws:ecr:{self.region}:{account_id}:repository/*"],
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
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
                    "Resource": [f"arn:aws:logs:{self.region}:{account_id}:log-group:*"],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                    ],
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
                    "Resource": [f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:memory/*"],
                },
                {
                    "Sid": "BedrockAgentCoreCodeInterpreter",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetCodeInterpreterSession",
                        "bedrock-agentcore:CreateCodeInterpreterSession",
                        "bedrock-agentcore:DeleteCodeInterpreterSession",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:code-interpreter/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:PutParameter",
                        "ssm:DeleteParameter",
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:{account_id}:parameter/bedrock-agentcore/cost-optimization-agent/*",
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
                Description="Execution role for Cost Optimization Agent with comprehensive permissions",
                Tags=self.resource_tags,
            )

            # Attach the comprehensive execution policy
            logger.info(f"📋 Attaching comprehensive execution policy to role: {role_name}")
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="CostOptimizationAgentComprehensivePolicy",
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
                PolicyName="CostOptimizationAgentComprehensivePolicy",
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
            import uuid

            memory_client = MemoryClient(region_name=self.region)

            # Check if memory ARN already exists in SSM
            param_name = "/bedrock-agentcore/cost-optimization-agent/memory-arn"
            try:
                response = self.ssm_client.get_parameter(Name=param_name)
                existing_memory_arn = response["Parameter"]["Value"]
                logger.info(f"✅ Found existing memory ARN in SSM: {existing_memory_arn}")

                # Verify the memory still exists
                try:
                    memory_id = existing_memory_arn.split("/")[-1]
                    memory_info = memory_client.get_memory(memory_id)
                    if memory_info.get("status") == "ACTIVE":
                        logger.info("✅ Existing memory is active and ready to use")
                        return existing_memory_arn
                    else:
                        logger.info(
                            f"⚠️ Existing memory status: {memory_info.get('status')}, creating new one"
                        )
                except Exception as e:
                    logger.info(f"⚠️ Existing memory not accessible: {e}, creating new one")

            except self.ssm_client.exceptions.ParameterNotFound:
                logger.info("No existing memory ARN found in SSM, creating new memory...")

            # Check if memory exists by name and clean up any inactive ones
            try:
                memories = memory_client.list_memories()
                for memory in memories:
                    if memory.get("name", "").startswith(
                        "CostOptimizationAgentMultiStrategy"
                    ) or memory.get("id", "").startswith("CostOptimizationAgentMultiStrategy"):
                        memory_id = memory.get("id")
                        status = memory.get("status")
                        logger.info(f"Found existing memory: {memory_id} (status: {status})")

                        if status == "ACTIVE":
                            memory_arn = memory["arn"]
                            logger.info(f"✅ Using existing active memory: {memory_arn}")

                            # Store in SSM for future use
                            try:
                                self.ssm_client.put_parameter(
                                    Name=param_name,
                                    Value=memory_arn,
                                    Type="String",
                                    Description="Memory ARN for Cost Optimization Agent",
                                    Tags=self.resource_tags,
                                )
                                logger.info("💾 Stored existing memory ARN in SSM with tags")
                            except Exception as ssm_error:
                                logger.warning(f"⚠️ Could not store in SSM: {ssm_error}")

                            return memory_arn
                        elif status in ["FAILED", "DELETING"]:
                            logger.info(f"Cleaning up inactive memory: {memory_id}")
                            try:
                                memory_client.delete_memory(memory_id)
                                logger.info(f"✅ Cleaned up inactive memory: {memory_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Could not clean up memory {memory_id}: {e}")

            except Exception as e:
                logger.warning(f"Error checking existing memories: {e}")

            # Create new memory with unique name
            unique_suffix = str(uuid.uuid4()).replace("-", "")[:8]
            memory_name = f"CostOptimizationAgentMultiStrategy_{unique_suffix}"
            logger.info(f"🧠 Creating new AgentCore Memory: {memory_name}")

            strategies = [
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "TeamPreferences",
                        "description": "Stores team preferences, budget allocations, and notification settings",
                        "namespaces": ["cost-optimization/team/{actorId}/preferences"],
                    }
                },
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "CostBaselinesSemantic",
                        "description": "Maintains cost baselines, historical patterns, and optimization outcomes",
                        "namespaces": ["cost-optimization/baselines"],
                    }
                },
            ]

            memory = memory_client.create_memory_and_wait(
                name=memory_name,
                description="Cost Optimization Agent with multi-strategy memory for baselines and preferences",
                strategies=strategies,
                event_expiry_days=90,
                max_wait=300,
                poll_interval=10,
            )

            memory_arn = memory["arn"]
            logger.info(f"✅ Memory created successfully: {memory_arn}")

            # Store memory ARN in SSM Parameter Store
            try:
                # First try to create the parameter with tags
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=memory_arn,
                    Type="String",
                    Description="Memory ARN for Cost Optimization Agent",
                    Tags=self.resource_tags,
                )
                logger.info("💾 Memory ARN stored in SSM Parameter Store with tags")
            except self.ssm_client.exceptions.ParameterAlreadyExistsException:
                # Parameter exists, update it without tags
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=memory_arn,
                    Type="String",
                    Overwrite=True,
                    Description="Memory ARN for Cost Optimization Agent",
                )
                logger.info("💾 Memory ARN updated in SSM Parameter Store")

                # Add tags separately for existing parameter
                try:
                    self.ssm_client.add_tags_to_resource(
                        ResourceType="Parameter",
                        ResourceId=param_name,
                        Tags=self.resource_tags,
                    )
                    logger.info("🏷️ Added tags to existing SSM parameter")
                except Exception as tag_error:
                    logger.warning(f"⚠️ Could not add tags to SSM parameter: {tag_error}")
            except Exception as e:
                # If tags fail, try without tags
                logger.warning(f"⚠️ Could not create parameter with tags: {e}")
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=memory_arn,
                    Type="String",
                    Overwrite=True,
                    Description="Memory ARN for Cost Optimization Agent",
                )
                logger.info("💾 Memory ARN stored in SSM Parameter Store (without tags)")

            return memory_arn

        except Exception as e:
            logger.error(f"❌ Failed to create memory: {e}")
            raise

    def deploy_agent(
        self,
        agent_name: str,
        role_name: str = "CostOptimizationAgentRole",
        entrypoint: str = "cost_optimization_agent.py",  # Now uses LLM-powered version
    ) -> str:
        """Deploy the Cost Optimization Agent with all requirements"""

        try:
            from bedrock_agentcore_starter_toolkit import Runtime

            logger.info("🚀 Starting Cost Optimization Agent Deployment")
            logger.info(f"   📝 Agent Name: {agent_name}")
            logger.info(f"   📍 Region: {self.region}")
            logger.info(f"   🎯 Entrypoint: {entrypoint}")

            # Step 1: Create AgentCore Memory
            memory_arn = self.create_agentcore_memory()

            # Step 2: Create execution role with all permissions
            execution_role_arn = self.create_execution_role(role_name)

            # Step 3: Initialize runtime
            runtime = Runtime()

            # Step 4: Configure the runtime
            logger.info("⚙️ Configuring runtime...")

            runtime.configure(
                execution_role=execution_role_arn,
                entrypoint=entrypoint,
                requirements_file="pyproject.toml",
                region=self.region,
                agent_name=agent_name,
                auto_create_ecr=True,
            )

            logger.info("✅ Configuration completed")

            # Step 5: Launch the runtime
            logger.info("🚀 Launching runtime (this may take several minutes)...")
            logger.info("   📦 Building container image...")
            logger.info("   ⬆️ Pushing to ECR...")
            logger.info("   🏗️ Creating AgentCore Runtime...")

            runtime.launch(auto_update_on_conflict=True)

            logger.info("✅ Launch completed")

            # Step 6: Get status and extract ARN
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

                logger.info("\n🎉 Cost Optimization Agent Deployed Successfully!")
                logger.info(f"🏷️ Runtime ARN: {runtime_arn}")
                logger.info(f"🧠 Memory ARN: {memory_arn}")
                logger.info(f"📍 Region: {self.region}")
                logger.info(f"🔐 Execution Role: {execution_role_arn}")
                logger.info(f"💾 ARN saved to: {arn_file}")

                # Show CloudWatch logs info
                agent_id = runtime_arn.split("/")[-1]
                log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"
                logger.info("\n📊 Monitoring:")
                logger.info(f"   CloudWatch Logs: {log_group}")
                logger.info(f"   Tail logs: aws logs tail {log_group} --follow")

                logger.info("\n📋 Next Steps:")
                logger.info("1. Test your agent: uv run python test/test_agent.py")
                logger.info("2. Monitor logs in CloudWatch")
                logger.info("3. Use the Runtime ARN for integrations")

                return runtime_arn
            else:
                logger.error("❌ Could not extract runtime ARN")
                logger.info(f"Status: {status}")
                return None

        except ImportError:
            logger.error("❌ bedrock-agentcore-starter-toolkit not installed")
            logger.info("Install with: uv add bedrock-agentcore-starter-toolkit")
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
        "cost_optimization_agent.py",
        "tools/cost_explorer_tools.py",
        "tools/budget_tools.py",
        "tools/__init__.py",
        "pyproject.toml",
    ]

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        logger.error(f"❌ Missing required files: {missing_files}")
        return False

    logger.info("✅ All required files present")

    # Check AWS credentials
    try:
        boto3.client("sts").get_caller_identity()
        logger.info("✅ AWS credentials configured")
    except Exception as e:
        logger.error(f"❌ AWS credentials not configured: {e}")
        return False

    # Check Cost Explorer access
    try:
        ce_client = boto3.client("ce")
        # Try a simple API call
        from datetime import datetime, timedelta

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
        logger.info("✅ Cost Explorer access verified")
    except Exception as e:
        logger.warning(f"⚠️ Cost Explorer access issue: {e}")
        logger.warning("   Agent will deploy but may have limited functionality")

    logger.info("✅ All prerequisites met")
    return True


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Deploy Cost Optimization Agent to Amazon Bedrock AgentCore Runtime"
    )
    parser.add_argument(
        "--agent-name",
        default="cost_optimization_agent",
        help="Name for the agent (default: cost_optimization_agent)",
    )
    parser.add_argument(
        "--role-name",
        default="CostOptimizationAgentRole",
        help="IAM role name (default: CostOptimizationAgentRole)",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")

    args = parser.parse_args()

    # Check prerequisites
    if not args.skip_checks and not check_prerequisites():
        logger.error("❌ Prerequisites not met. Fix issues above or use --skip-checks")
        exit(1)

    # Create deployer and deploy
    deployer = CostOptimizationAgentDeployer(region=args.region)

    runtime_arn = deployer.deploy_agent(agent_name=args.agent_name, role_name=args.role_name)

    if runtime_arn:
        logger.info("\n🎯 Deployment completed successfully!")
        logger.info("Run 'uv run python test/test_agent.py' to test your deployed agent.")
    else:
        logger.error("❌ Deployment failed")
        exit(1)


if __name__ == "__main__":
    main()
