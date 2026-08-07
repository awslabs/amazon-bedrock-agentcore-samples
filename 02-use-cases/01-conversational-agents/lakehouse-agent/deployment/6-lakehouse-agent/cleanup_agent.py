#!/usr/bin/env python3
"""
Cleanup Lakehouse Agent Runtime

Deletes:
- AgentCore Agent Runtime
- IAM execution role (AgentCoreRuntimeRole-lakehouse-agent)
- ECR repository (bedrock-agentcore-lakehouse_agent)
- CodeBuild project and role
- Local .bedrock_agentcore.yaml config
- SSM parameters

Usage:
    python cleanup_agent.py [--keep-ssm]
"""

import argparse
import os
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.aws_session_utils import get_aws_session


class AgentCleanup:
    def __init__(self, keep_ssm=False):
        _session, self.region, self.account_id = get_aws_session()
        self.bedrock = boto3.client("bedrock-agentcore-control", region_name=self.region)
        self.iam = boto3.client("iam")
        self.ecr = boto3.client("ecr", region_name=self.region)
        self.codebuild = boto3.client("codebuild", region_name=self.region)
        self.ssm = boto3.client("ssm", region_name=self.region)
        self.keep_ssm = keep_ssm

    def _get_ssm_param(self, name, default=None):
        try:
            return self.ssm.get_parameter(Name=f"/app/lakehouse-agent/{name}")["Parameter"]["Value"]
        except Exception:
            return default

    def delete_runtime(self):
        print("\n🗑️  Deleting Agent Runtime...")
        runtime_id = self._get_ssm_param("agent-runtime-id")
        if not runtime_id:
            print("   ⏭️  No runtime ID found in SSM")
            return
        try:
            self.bedrock.delete_agent_runtime(agentRuntimeId=runtime_id)
            print(f"   ✅ Deleted runtime: {runtime_id}")
            print("   ⏳ Waiting for deletion...")
            time.sleep(10)
        except self.bedrock.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Runtime not found: {runtime_id}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    def delete_iam_role(self):
        print("\n🗑️  Deleting IAM execution role...")
        role_name = "AgentCoreRuntimeRole-lakehouse-agent"
        try:
            self.iam.get_role(RoleName=role_name)
        except self.iam.exceptions.NoSuchEntityException:
            print(f"   ⏭️  Role not found: {role_name}")
            return
        try:
            for p in self.iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
                self.iam.delete_role_policy(RoleName=role_name, PolicyName=p)
            for p in self.iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]:
                self.iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
            self.iam.delete_role(RoleName=role_name)
            print(f"   ✅ Deleted role: {role_name}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    def delete_ecr_repository(self):
        print("\n🗑️  Deleting ECR repository...")
        try:
            self.ecr.delete_repository(repositoryName="bedrock-agentcore-lakehouse_agent", force=True)
            print("   ✅ Deleted ECR repo: bedrock-agentcore-lakehouse_agent")
        except self.ecr.exceptions.RepositoryNotFoundException:
            print("   ⏭️  ECR repo not found")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    def delete_codebuild_resources(self):
        print("\n🗑️  Deleting CodeBuild resources...")
        project_name = "bedrock-agentcore-lakehouse_agent-builder"

        # Resolve this project's serviceRole BEFORE deleting the project — it is the
        # only reliable ownership signal for the toolkit-created CodeBuild role. The
        # "AmazonBedrockAgentCoreSDKCodeBuild-" prefix is shared by EVERY AgentCore
        # project in the account, so a prefix match alone can hit a role owned by an
        # unrelated project.
        service_role_name = None
        try:
            projects = self.codebuild.batch_get_projects(names=[project_name])["projects"]
            if projects:
                service_role_name = projects[0].get("serviceRole", "").split("/")[-1] or None
        except Exception as e:
            print(f"   ⚠️  Could not resolve CodeBuild service role: {e}")

        # Delete project
        try:
            self.codebuild.delete_project(name=project_name)
            print("   ✅ Deleted CodeBuild project")
        except Exception:
            print("   ⏭️  CodeBuild project not found")

        # Delete CodeBuild role (pattern from toolkit) — only the role THIS project
        # referenced. Every prefix match is examined (no early return, so sibling
        # runtimes' roles are not silently skipped), but a role is deleted only when
        # it is the one this project owned.
        if not service_role_name:
            print("   ⏭️  CodeBuild role owner could not be verified — skipping role deletion")
            return
        try:
            deleted = 0
            paginator = self.iam.get_paginator("list_roles")
            for page in paginator.paginate(PathPrefix="/"):
                for role in page["Roles"]:
                    role_name = role["RoleName"]
                    if not role_name.startswith("AmazonBedrockAgentCoreSDKCodeBuild-"):
                        continue
                    if role_name != service_role_name:
                        print(f"   ⏭️  Skipping CodeBuild role owned by another project: {role_name}")
                        continue
                    for p in self.iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
                        self.iam.delete_role_policy(RoleName=role_name, PolicyName=p)
                    for p in self.iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]:
                        self.iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
                    self.iam.delete_role(RoleName=role_name)
                    print(f"   ✅ Deleted CodeBuild role: {role_name}")
                    deleted += 1
            if deleted == 0:
                print(f"   ⏭️  CodeBuild role not found: {service_role_name}")
        except Exception as e:
            print(f"   ⚠️  Error cleaning CodeBuild role: {e}")

    def delete_local_config(self):
        print("\n🗑️  Deleting local config files...")
        config_dir = Path(__file__).parent
        for f in [
            ".bedrock_agentcore.yaml",
            ".bedrock_agentcore.yaml.bk",
            ".dockerignore",
        ]:
            path = config_dir / f
            if path.exists():
                path.unlink()
                print(f"   ✅ Deleted: {f}")

    def delete_ssm_parameters(self):
        if self.keep_ssm:
            print("\n⏭️  Keeping SSM parameters (--keep-ssm)")
            return
        print("\n🗑️  Deleting SSM parameters...")
        params = ["agent-runtime-arn", "agent-runtime-id"]
        for p in params:
            try:
                self.ssm.delete_parameter(Name=f"/app/lakehouse-agent/{p}")
                print(f"   ✅ Deleted: /app/lakehouse-agent/{p}")
            except self.ssm.exceptions.ParameterNotFound:
                pass
            except Exception as e:
                print(f"   ❌ Error: {e}")

    def run(self):
        print("\n🧹 Lakehouse Agent Cleanup")
        print(f"   Region: {self.region}")
        print(f"   Account: {self.account_id}")
        self.delete_runtime()
        self.delete_iam_role()
        self.delete_ecr_repository()
        self.delete_codebuild_resources()
        self.delete_local_config()
        self.delete_ssm_parameters()
        print("\n✨ Agent cleanup complete!")


def main():
    parser = argparse.ArgumentParser(description="Cleanup Lakehouse Agent Runtime")
    parser.add_argument("--keep-ssm", action="store_true", help="Keep SSM parameters")
    args = parser.parse_args()
    AgentCleanup(keep_ssm=args.keep_ssm).run()


if __name__ == "__main__":
    main()
