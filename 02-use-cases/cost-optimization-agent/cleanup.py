#!/usr/bin/env python3
"""
Complete Cost Optimization Agent Cleanup Script
Removes all resources created by deploy.py including:
- AgentCore Runtime instances
- AgentCore Memory instances
- ECR repositories
- IAM roles and policies
- SSM parameters
- CodeBuild projects
- S3 artifacts
"""

import argparse
import logging
import boto3
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CostOptimizationAgentCleaner:
    """Complete cleaner for Cost Optimization Agent resources"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.agent_name = "cost_optimization_agent"
        self.role_name = "CostOptimizationAgentRole"

        # Resource tags for safe identification
        self.project_tag = "bedrock-agentcore-cost-optimization"
        self.resource_tags = {
            "Project": self.project_tag,
            "Agent": self.agent_name,
            "ManagedBy": "bedrock-agentcore-samples",
        }

        # Initialize AWS clients
        self.iam_client = boto3.client("iam", region_name=region)
        self.ecr_client = boto3.client("ecr", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)
        self.codebuild_client = boto3.client("codebuild", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)

        try:
            from bedrock_agentcore_starter_toolkit import Runtime
            from bedrock_agentcore.memory import MemoryClient

            self.runtime = Runtime()
            self.memory_client = MemoryClient(region_name=region)
            self.agentcore_available = True
        except ImportError:
            logger.warning(
                "⚠️  bedrock-agentcore-starter-toolkit not available - skipping AgentCore cleanup"
            )
            self.agentcore_available = False

    def cleanup_agentcore_runtime(self):
        """Remove AgentCore Runtime instances"""
        logger.info("🗑️  Cleaning up AgentCore Runtime instances...")

        try:
            # Check if .agent_arn file exists
            arn_file = Path(".agent_arn")
            if arn_file.exists():
                with open(arn_file, "r") as f:
                    agent_arn = f.read().strip()

                logger.info(f"   Found agent ARN: {agent_arn}")

                # Extract agent ID from ARN
                agent_id = agent_arn.split("/")[-1]
                logger.info(f"   Deleting runtime: {agent_id}")

                try:
                    # First try using the toolkit if available
                    if self.agentcore_available:
                        logger.info("   Attempting deletion via AgentCore toolkit...")
                        self.runtime.delete()
                        logger.info("   ✅ AgentCore Runtime deleted via toolkit")
                    else:
                        raise Exception("Toolkit not available, using AWS CLI")

                except Exception as toolkit_error:
                    logger.info(f"   Toolkit deletion failed: {toolkit_error}")
                    logger.info("   Attempting deletion via AWS CLI...")

                    # Use AWS CLI command for runtime deletion
                    import subprocess

                    try:
                        cmd = [
                            "aws",
                            "bedrock-agentcore-control",
                            "delete-agent-runtime",
                            "--agent-runtime-id",
                            agent_id,
                            "--region",
                            self.region,
                        ]

                        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                        logger.info("   ✅ AgentCore Runtime deleted via AWS CLI")
                        logger.info(f"   CLI output: {result.stdout.strip()}")

                    except subprocess.CalledProcessError as cli_error:
                        logger.warning(f"   ⚠️  AWS CLI deletion failed: {cli_error}")
                        logger.warning(f"   CLI stderr: {cli_error.stderr}")
                        logger.info(
                            f"   💡 Manual deletion required: aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id {agent_id} --region {self.region}"
                        )
                        return
                    except FileNotFoundError:
                        logger.warning("   ⚠️  AWS CLI not found in PATH")
                        logger.info(
                            f"   💡 Manual deletion required: aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id {agent_id} --region {self.region}"
                        )
                        return

                # Remove the ARN file after successful deletion
                arn_file.unlink()
                logger.info("   ✅ Removed .agent_arn file")

            else:
                logger.info("   📋 No .agent_arn file found")

                # Check for any remaining runtimes that might match our agent
                logger.info("   🔍 Checking for any remaining AgentCore Runtimes...")
                try:
                    import subprocess

                    # List all runtimes to find any that match our agent name
                    cmd = [
                        "aws",
                        "bedrock-agentcore-control",
                        "list-agent-runtimes",
                        "--region",
                        self.region,
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                    import json

                    runtimes_data = json.loads(result.stdout)

                    # Look for runtimes that match our agent name
                    matching_runtimes = []
                    for runtime in runtimes_data.get("agentRuntimes", []):
                        runtime_id = runtime.get("agentRuntimeId", "")
                        if self.agent_name in runtime_id:
                            matching_runtimes.append(runtime_id)

                    if matching_runtimes:
                        logger.info(
                            f"   Found {len(matching_runtimes)} matching runtime(s) to delete"
                        )

                        for runtime_id in matching_runtimes:
                            logger.info(f"   Deleting runtime: {runtime_id}")

                            delete_cmd = [
                                "aws",
                                "bedrock-agentcore-control",
                                "delete-agent-runtime",
                                "--agent-runtime-id",
                                runtime_id,
                                "--region",
                                self.region,
                            ]

                            try:
                                subprocess.run(
                                    delete_cmd, capture_output=True, text=True, check=True
                                )
                                logger.info(f"   ✅ Deleted runtime: {runtime_id}")

                            except subprocess.CalledProcessError as e:
                                logger.warning(
                                    f"   ⚠️  Could not delete runtime {runtime_id}: {e.stderr}"
                                )
                    else:
                        logger.info("   📋 No matching AgentCore Runtimes found")

                except (
                    subprocess.CalledProcessError,
                    FileNotFoundError,
                    json.JSONDecodeError,
                ) as e:
                    logger.info(f"   📋 Could not list runtimes (this is normal): {e}")

        except Exception as e:
            logger.error(f"   ❌ Error during AgentCore Runtime cleanup: {e}")

    def cleanup_agentcore_memory(self):
        """Remove AgentCore Memory instances"""
        if not self.agentcore_available:
            logger.info("🔄 Skipping AgentCore Memory cleanup (toolkit not available)")
            return

        logger.info("🗑️  Cleaning up AgentCore Memory instances...")

        try:
            memories = self.memory_client.list_memories()
            cost_memories = [
                m
                for m in memories
                if (
                    m.get("id", "").startswith("CostOptimizationAgentMultiStrategy-")
                    or m.get("id", "").startswith("CostOptimizationAgentMultiStrategy_")
                )
            ]

            if cost_memories:
                logger.info(f"   Found {len(cost_memories)} memory instances to delete")

                for memory in cost_memories:
                    memory_id = memory.get("id")
                    status = memory.get("status")

                    try:
                        logger.info(f"   Deleting memory: {memory_id} (status: {status})")
                        self.memory_client.delete_memory(memory_id)
                        logger.info(f"   ✅ Deleted memory: {memory_id}")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not delete memory {memory_id}: {e}")

                # Remove local memory ID file
                memory_id_file = Path(".memory_id")
                if memory_id_file.exists():
                    memory_id_file.unlink()
                    logger.info("   ✅ Removed .memory_id file")

            else:
                logger.info("   📋 No CostOptimizationAgent memory instances found")

        except Exception as e:
            logger.error(f"   ❌ Error during AgentCore Memory cleanup: {e}")

    def cleanup_ssm_parameters(self):
        """Remove SSM parameters"""
        logger.info("🗑️  Cleaning up SSM parameters...")

        param_name = "/bedrock-agentcore/cost-optimization-agent/memory-id"

        try:
            self.ssm_client.delete_parameter(Name=param_name)
            logger.info(f"   ✅ Deleted SSM parameter: {param_name}")
        except self.ssm_client.exceptions.ParameterNotFound:
            logger.info(f"   📋 SSM parameter not found: {param_name}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not delete SSM parameter: {e}")

    def cleanup_ecr_repository(self):
        """Remove ECR repository (only if it matches our project)"""
        logger.info("🗑️  Cleaning up ECR repository...")

        repo_name = f"bedrock-agentcore-{self.agent_name}"

        try:
            # Check if repository exists and has our project tag
            try:
                repo_info = self.ecr_client.describe_repositories(repositoryNames=[repo_name])
                repository = repo_info["repositories"][0]

                # Get repository tags to verify it's ours
                try:
                    tags_response = self.ecr_client.list_tags_for_resource(
                        resourceArn=repository["repositoryArn"]
                    )
                    tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("tags", [])}

                    # Only delete if it has our project tag
                    if tags.get("Project") != self.project_tag:
                        logger.info(
                            f"   📋 ECR repository {repo_name} doesn't have project tag - skipping"
                        )
                        return

                except Exception:
                    # If we can't get tags, be conservative and skip
                    logger.info("   📋 Cannot verify ECR repository tags - skipping for safety")
                    return

            except self.ecr_client.exceptions.RepositoryNotFoundException:
                logger.info(f"   📋 ECR repository not found: {repo_name}")
                return

            # First, delete all images in the repository
            try:
                images = self.ecr_client.list_images(repositoryName=repo_name)
                if images["imageIds"]:
                    logger.info(f"   Deleting {len(images['imageIds'])} images from repository")
                    self.ecr_client.batch_delete_image(
                        repositoryName=repo_name, imageIds=images["imageIds"]
                    )
                    logger.info("   ✅ Deleted all images from repository")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not delete images: {e}")

            # Delete the repository
            self.ecr_client.delete_repository(repositoryName=repo_name, force=True)
            logger.info(f"   ✅ Deleted ECR repository: {repo_name}")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not delete ECR repository: {e}")

    def cleanup_codebuild_project(self):
        """Remove CodeBuild project (only if it matches our project)"""
        logger.info("🗑️  Cleaning up CodeBuild project...")

        project_name = f"bedrock-agentcore-{self.agent_name}-builder"

        try:
            # Check if project exists and verify it's ours
            try:
                projects = self.codebuild_client.batch_get_projects(names=[project_name])
                if not projects["projects"]:
                    logger.info(f"   📋 CodeBuild project not found: {project_name}")
                    return

                project = projects["projects"][0]

                # Check project tags to verify it's ours
                tags = {tag["key"]: tag["value"] for tag in project.get("tags", [])}
                if tags.get("Project") != self.project_tag:
                    logger.info(
                        f"   📋 CodeBuild project {project_name} doesn't have project tag - skipping"
                    )
                    return

            except Exception as e:
                logger.info(f"   📋 Cannot verify CodeBuild project - skipping for safety: {e}")
                return

            self.codebuild_client.delete_project(name=project_name)
            logger.info(f"   ✅ Deleted CodeBuild project: {project_name}")

        except self.codebuild_client.exceptions.InvalidInputException:
            logger.info(f"   📋 CodeBuild project not found: {project_name}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not delete CodeBuild project: {e}")

    def cleanup_s3_artifacts(self):
        """Remove S3 artifacts (only our project's artifacts)"""
        logger.info("🗑️  Cleaning up S3 artifacts...")

        try:
            # List buckets and look for CodeBuild artifacts
            buckets = self.s3_client.list_buckets()

            for bucket in buckets["Buckets"]:
                bucket_name = bucket["Name"]

                # Look for CodeBuild artifact buckets
                if "codebuild" in bucket_name.lower() and self.region in bucket_name:
                    try:
                        # Check bucket tags first for safety
                        try:
                            bucket_tags = self.s3_client.get_bucket_tagging(Bucket=bucket_name)
                            tags = {
                                tag["Key"]: tag["Value"] for tag in bucket_tags.get("TagSet", [])
                            }

                            # Only clean if bucket has our project tag or if it's a standard CodeBuild bucket
                            if tags.get(
                                "Project"
                            ) != self.project_tag and not bucket_name.startswith(
                                "bedrock-agentcore-codebuild-sources-"
                            ):
                                logger.debug(f"   Skipping bucket {bucket_name} - no project tag")
                                continue

                        except self.s3_client.exceptions.NoSuchTagSet:
                            # No tags - only proceed if it's a standard CodeBuild bucket name
                            if not bucket_name.startswith("bedrock-agentcore-codebuild-sources-"):
                                logger.debug(
                                    f"   Skipping bucket {bucket_name} - no tags and not standard name"
                                )
                                continue
                        except Exception:
                            # Can't get tags - skip for safety
                            logger.debug(f"   Skipping bucket {bucket_name} - cannot verify tags")
                            continue

                        # List objects with our agent prefix
                        objects = self.s3_client.list_objects_v2(
                            Bucket=bucket_name, Prefix=self.agent_name
                        )

                        if "Contents" in objects:
                            logger.info(
                                f"   Found {len(objects['Contents'])} artifacts in bucket: {bucket_name}"
                            )

                            # Delete objects
                            delete_objects = [{"Key": obj["Key"]} for obj in objects["Contents"]]
                            if delete_objects:
                                self.s3_client.delete_objects(
                                    Bucket=bucket_name,
                                    Delete={"Objects": delete_objects},
                                )
                                logger.info(
                                    f"   ✅ Deleted {len(delete_objects)} artifacts from {bucket_name}"
                                )

                    except Exception as e:
                        logger.debug(f"   Could not clean bucket {bucket_name}: {e}")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not clean S3 artifacts: {e}")

    def cleanup_iam_resources(self):
        """Remove IAM roles and policies (only if they have our project tag)"""
        logger.info("🗑️  Cleaning up IAM resources...")

        # Clean up main execution role
        try:
            # Check if role exists and has our project tag
            try:
                role_info = self.iam_client.get_role(RoleName=self.role_name)
                role_tags = {tag["Key"]: tag["Value"] for tag in role_info["Role"].get("Tags", [])}

                if role_tags.get("Project") != self.project_tag:
                    logger.info(
                        f"   📋 IAM role {self.role_name} doesn't have project tag - skipping"
                    )
                    return

            except self.iam_client.exceptions.NoSuchEntityException:
                logger.info(f"   📋 IAM role not found: {self.role_name}")
                return

            # Delete inline policies
            try:
                policies = self.iam_client.list_role_policies(RoleName=self.role_name)
                for policy_name in policies["PolicyNames"]:
                    self.iam_client.delete_role_policy(
                        RoleName=self.role_name, PolicyName=policy_name
                    )
                    logger.info(f"   ✅ Deleted inline policy: {policy_name}")
            except Exception as e:
                logger.debug(f"   Could not delete inline policies: {e}")

            # Delete the role
            self.iam_client.delete_role(RoleName=self.role_name)
            logger.info(f"   ✅ Deleted IAM role: {self.role_name}")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not delete IAM role: {e}")

        # Clean up CodeBuild execution role (more targeted)
        codebuild_role_pattern = f"AmazonBedrockAgentCoreSDKCodeBuild-{self.region}-"

        try:
            roles = self.iam_client.list_roles()
            for role in roles["Roles"]:
                role_name = role["RoleName"]
                if role_name.startswith(codebuild_role_pattern):
                    try:
                        # Get role tags to verify it's ours
                        role_info = self.iam_client.get_role(RoleName=role_name)
                        role_tags = {
                            tag["Key"]: tag["Value"] for tag in role_info["Role"].get("Tags", [])
                        }

                        # Only delete if it has our project tag or agent tag
                        if (
                            role_tags.get("Project") != self.project_tag
                            and role_tags.get("Agent") != self.agent_name
                        ):
                            logger.info(
                                f"   📋 CodeBuild role {role_name} doesn't have project tags - skipping"
                            )
                            continue

                        # Delete inline policies
                        policies = self.iam_client.list_role_policies(RoleName=role_name)
                        for policy_name in policies["PolicyNames"]:
                            self.iam_client.delete_role_policy(
                                RoleName=role_name, PolicyName=policy_name
                            )

                        # Delete attached managed policies
                        attached_policies = self.iam_client.list_attached_role_policies(
                            RoleName=role_name
                        )
                        for policy in attached_policies["AttachedPolicies"]:
                            self.iam_client.detach_role_policy(
                                RoleName=role_name, PolicyArn=policy["PolicyArn"]
                            )

                        # Delete the role
                        self.iam_client.delete_role(RoleName=role_name)
                        logger.info(f"   ✅ Deleted CodeBuild IAM role: {role_name}")

                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not delete CodeBuild role {role_name}: {e}")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not clean CodeBuild IAM roles: {e}")

    def cleanup_local_files(self):
        """Remove local deployment files"""
        logger.info("🗑️  Cleaning up local files...")

        files_to_remove = [
            ".agent_arn",
            ".memory_id",
            "Dockerfile",
            ".dockerignore",
            ".bedrock_agentcore.yaml",
        ]

        for file_name in files_to_remove:
            file_path = Path(file_name)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"   ✅ Removed: {file_name}")
            else:
                logger.debug(f"   📋 File not found: {file_name}")

    def cleanup_all(self, skip_iam: bool = False):
        """Clean up all resources (with tag-based safety checks)"""
        logger.info("🧹 Starting complete Cost Optimization Agent cleanup...")
        logger.info(f"   📍 Region: {self.region}")
        logger.info(f"   🎯 Agent: {self.agent_name}")
        logger.info(f"   🏷️  Project Tag: {self.project_tag}")
        logger.info("   🛡️  Safety: Only resources with matching project tags will be deleted")

        # Clean up in reverse order of creation
        self.cleanup_agentcore_runtime()
        self.cleanup_agentcore_memory()
        self.cleanup_ssm_parameters()
        self.cleanup_codebuild_project()
        self.cleanup_s3_artifacts()
        self.cleanup_ecr_repository()

        if not skip_iam:
            self.cleanup_iam_resources()
        else:
            logger.info("🔄 Skipping IAM cleanup (--skip-iam flag)")

        self.cleanup_local_files()

        logger.info("✅ Cleanup completed!")
        logger.info("🛡️  Only resources with project tag were deleted for safety")
        logger.info("💡 If any resources couldn't be deleted, check the AWS Console manually")


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description="Clean up all Cost Optimization Agent resources")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument(
        "--skip-iam",
        action="store_true",
        help="Skip IAM role cleanup (useful if roles are shared)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No resources will be deleted")
        logger.info("   This would clean up (with tag-based safety checks):")
        logger.info("   - AgentCore Runtime instances")
        logger.info("   - AgentCore Memory instances")
        logger.info("   - ECR repositories (with project tag)")
        logger.info("   - CodeBuild projects (with project tag)")
        logger.info("   - S3 artifacts (in tagged buckets or with agent prefix)")
        logger.info("   - SSM parameters")
        if not args.skip_iam:
            logger.info("   - IAM roles and policies (with project tag)")
        logger.info("   - Local deployment files")
        logger.info(
            "   🛡️  Safety: Only resources with project tag 'bedrock-agentcore-cost-optimization' would be deleted"
        )
        return

    # Confirm deletion
    print("⚠️  WARNING: This will delete Cost Optimization Agent resources!")
    print(f"   Region: {args.region}")
    print(
        "   🛡️  Safety: Only resources with project tag 'bedrock-agentcore-cost-optimization' will be deleted"
    )
    if args.skip_iam:
        print("   IAM resources will be PRESERVED")
    else:
        print("   IAM resources will be DELETED (if they have the project tag)")

    confirm = input("\nAre you sure you want to continue? (type 'yes' to confirm): ")
    if confirm.lower() != "yes":
        print("❌ Cleanup cancelled")
        return

    # Create cleaner and run cleanup
    cleaner = CostOptimizationAgentCleaner(region=args.region)
    cleaner.cleanup_all(skip_iam=args.skip_iam)


if __name__ == "__main__":
    main()
