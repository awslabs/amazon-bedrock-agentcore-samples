#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# cleanup-retained-resources.sh — Remove resources left behind after `cdk destroy`.
#
# Several resources use RETAIN removal policy to prevent accidental data loss.
# After `cdk destroy`, these resources remain and will cause "already exists"
# errors on the next `cdk deploy`. This script removes them.
#
# Also cleans up security groups and subnets that fail to delete during
# `cdk destroy` because AgentCore-managed ENIs haven't been released yet.
#
# Usage:
#   export AWS_PROFILE=my-profile   # optional
#   export AWS_REGION=us-east-1
#   ./scripts/cleanup-retained-resources.sh
#
# Prerequisites: AWS CLI v2, jq

set -euo pipefail

REGION="${AWS_REGION:?Set AWS_REGION before running this script}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text --region "$REGION")

echo "=== Cleaning up retained OpenCode resources in $REGION ($ACCOUNT) ==="
echo ""

# -----------------------------------------------------------------------
# 1. DynamoDB table
# -----------------------------------------------------------------------
echo "--- DynamoDB ---"
if aws dynamodb describe-table --table-name opencode-jobs --region "$REGION" &>/dev/null; then
    echo "  Deleting table: opencode-jobs"
    aws dynamodb delete-table --table-name opencode-jobs --region "$REGION" --output text --query 'TableDescription.TableStatus'
else
    echo "  Table opencode-jobs not found (OK)"
fi

# -----------------------------------------------------------------------
# 2. ECR repository
# -----------------------------------------------------------------------
echo ""
echo "--- ECR ---"
if aws ecr describe-repositories --repository-names opencode-agentcore --region "$REGION" &>/dev/null; then
    echo "  Deleting repository: opencode-agentcore"
    aws ecr delete-repository --repository-name opencode-agentcore --region "$REGION" --force --output text --query 'repository.repositoryName'
else
    echo "  Repository opencode-agentcore not found (OK)"
fi

# -----------------------------------------------------------------------
# 3. CloudWatch log groups
# -----------------------------------------------------------------------
echo ""
echo "--- CloudWatch Log Groups ---"
for LG in /opencode/system /opencode/container; do
    if aws logs describe-log-groups --log-group-name-prefix "$LG" --region "$REGION" \
        --query "logGroups[?logGroupName=='$LG'].logGroupName" --output text | grep -q "$LG"; then
        echo "  Deleting log group: $LG"
        aws logs delete-log-group --log-group-name "$LG" --region "$REGION"
    else
        echo "  Log group $LG not found (OK)"
    fi
done

# -----------------------------------------------------------------------
# 4. Security groups (AgentCore ENIs may hold these after destroy)
# -----------------------------------------------------------------------
echo ""
echo "--- Security Groups (OpenCode tagged) ---"
SG_IDS=$(aws ec2 describe-security-groups --region "$REGION" \
    --filters Name=tag:Project,Values=OpenCode \
    --query 'SecurityGroups[*].GroupId' --output text 2>/dev/null || true)
if [ -n "$SG_IDS" ]; then
    for SG in $SG_IDS; do
        echo "  Deleting security group: $SG"
        # Detach any ENIs first
        ENI_IDS=$(aws ec2 describe-network-interfaces --region "$REGION" \
            --filters Name=group-id,Values="$SG" \
            --query 'NetworkInterfaces[*].NetworkInterfaceId' --output text 2>/dev/null || true)
        for ENI in $ENI_IDS; do
            ATTACH=$(aws ec2 describe-network-interfaces --region "$REGION" \
                --network-interface-ids "$ENI" \
                --query 'NetworkInterfaces[0].Attachment.AttachmentId' --output text 2>/dev/null || true)
            if [ -n "$ATTACH" ] && [ "$ATTACH" != "None" ]; then
                echo "    Detaching ENI $ENI (attachment $ATTACH)"
                aws ec2 detach-network-interface --attachment-id "$ATTACH" --region "$REGION" --force 2>/dev/null || true
                sleep 5
            fi
            echo "    Deleting ENI $ENI"
            aws ec2 delete-network-interface --network-interface-id "$ENI" --region "$REGION" 2>/dev/null || true
        done
        aws ec2 delete-security-group --group-id "$SG" --region "$REGION" 2>/dev/null \
            && echo "    Deleted $SG" \
            || echo "    Could not delete $SG (ENIs may still be releasing — retry in a few minutes)"
    done
else
    echo "  No OpenCode security groups found (OK)"
fi

# -----------------------------------------------------------------------
# 5. Orphaned VPCs (retained subnets prevent VPC deletion during destroy)
# -----------------------------------------------------------------------
echo ""
echo "--- VPCs (OpenCode tagged) ---"
VPC_IDS=$(aws ec2 describe-vpcs --region "$REGION" \
    --filters Name=tag:Project,Values=OpenCode \
    --query 'Vpcs[*].VpcId' --output text 2>/dev/null || true)
if [ -n "$VPC_IDS" ]; then
    for VPC in $VPC_IDS; do
        echo "  Cleaning up VPC: $VPC"
        # Delete subnets
        SUBNET_IDS=$(aws ec2 describe-subnets --region "$REGION" \
            --filters Name=vpc-id,Values="$VPC" \
            --query 'Subnets[*].SubnetId' --output text 2>/dev/null || true)
        for SUBNET in $SUBNET_IDS; do
            echo "    Deleting subnet $SUBNET"
            aws ec2 delete-subnet --subnet-id "$SUBNET" --region "$REGION" 2>/dev/null || true
        done
        # Delete the VPC
        aws ec2 delete-vpc --vpc-id "$VPC" --region "$REGION" 2>/dev/null \
            && echo "    Deleted VPC $VPC" \
            || echo "    Could not delete VPC $VPC (may have remaining dependencies)"
    done
else
    echo "  No OpenCode VPCs found (OK)"
fi

echo ""
echo "=== Cleanup complete ==="
