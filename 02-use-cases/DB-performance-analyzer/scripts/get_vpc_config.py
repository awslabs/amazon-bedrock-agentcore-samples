#!/usr/bin/env python3
import boto3
import json
import os
import sys
import argparse

def get_vpc_config(cluster_name, region):
    """
    Get VPC configuration for a database cluster and set up security groups
    """
    print(f"Getting VPC configuration for cluster: {cluster_name}")
    
    # Initialize AWS clients
    rds = boto3.client('rds', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    
    try:
        # Get cluster information
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_name)
        
        if not response['DBClusters']:
            print(f"Error: Cluster {cluster_name} not found")
            return False
        
        cluster = response['DBClusters'][0]
        
        # Get VPC ID and subnet IDs
        vpc_id = None
        subnet_ids = []
        db_security_group_ids = []
        
        # Get VPC ID and security groups from DB subnet group
        subnet_group_name = cluster.get('DBSubnetGroup')
        if subnet_group_name:
            subnet_response = rds.describe_db_subnet_groups(DBSubnetGroupName=subnet_group_name)
            if subnet_response['DBSubnetGroups']:
                subnet_group = subnet_response['DBSubnetGroups'][0]
                vpc_id = subnet_group['VpcId']
                subnet_ids = [subnet['SubnetIdentifier'] for subnet in subnet_group['Subnets']]
        
        # Get security groups
        db_security_group_ids = cluster.get('VpcSecurityGroups', [])
        db_security_group_ids = [sg['VpcSecurityGroupId'] for sg in db_security_group_ids]
        
        if not vpc_id or not subnet_ids:
            print("Error: Could not determine VPC ID or subnet IDs")
            return False
        
        print(f"Found VPC ID: {vpc_id}")
        print(f"Found subnet IDs: {subnet_ids}")
        print(f"Found DB security group IDs: {db_security_group_ids}")
        
        # Create a security group for Lambda
        lambda_sg_name = f"lambda-{cluster_name}-sg"
        
        # Check if security group already exists
        existing_sgs = ec2.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': [lambda_sg_name]},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        
        if existing_sgs['SecurityGroups']:
            lambda_sg_id = existing_sgs['SecurityGroups'][0]['GroupId']
            print(f"Using existing Lambda security group: {lambda_sg_id}")
        else:
            # Create new security group
            lambda_sg_response = ec2.create_security_group(
                GroupName=lambda_sg_name,
                Description=f"Security group for Lambda functions accessing {cluster_name}",
                VpcId=vpc_id
            )
            lambda_sg_id = lambda_sg_response['GroupId']
            
            # Check if outbound rule already exists
            try:
                # Get existing rules
                sg_rules = ec2.describe_security_group_rules(
                    Filters=[{
                        'Name': 'group-id',
                        'Values': [lambda_sg_id]
                    }, {
                        'Name': 'egress',
                        'Values': ['true']
                    }]
                )
                
                # Check if the rule already exists
                rule_exists = False
                for rule in sg_rules.get('SecurityGroupRules', []):
                    if rule.get('IpProtocol') == '-1' and rule.get('CidrIpv4') == '0.0.0.0/0':
                        rule_exists = True
                        break
                
                # Add outbound rule if it doesn't exist
                if not rule_exists:
                    ec2.authorize_security_group_egress(
                        GroupId=lambda_sg_id,
                        IpPermissions=[{
                            'IpProtocol': '-1',
                            'FromPort': -1,
                            'ToPort': -1,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        }]
                    )
                    print(f"Added outbound rule to Lambda security group {lambda_sg_id}")
                else:
                    print(f"Outbound rule already exists in Lambda security group {lambda_sg_id}")
            except Exception as e:
                print(f"Warning: Could not add outbound rule to Lambda security group: {str(e)}")
                # Continue anyway as default outbound rules are usually permissive
            
            print(f"Created Lambda security group: {lambda_sg_id}")
        
        # Update DB security group to allow inbound from Lambda
        for db_sg_id in db_security_group_ids:
            try:
                # Check if rule already exists by describing the security group
                sg_response = ec2.describe_security_groups(
                    GroupIds=[db_sg_id]
                )
                
                # Check if the Lambda security group is already referenced in any rule
                rule_exists = False
                if sg_response['SecurityGroups']:
                    for rule in sg_response['SecurityGroups'][0].get('IpPermissions', []):
                        for group_pair in rule.get('UserIdGroupPairs', []):
                            if group_pair.get('GroupId') == lambda_sg_id and rule.get('IpProtocol') == 'tcp' and rule.get('FromPort') == 5432:
                                rule_exists = True
                                break
                
                if not rule_exists:
                    ec2.authorize_security_group_ingress(
                        GroupId=db_sg_id,
                        IpPermissions=[{
                            'IpProtocol': 'tcp',
                            'FromPort': 5432,
                            'ToPort': 5432,
                            'UserIdGroupPairs': [{'GroupId': lambda_sg_id}]
                        }]
                    )
                    print(f"Added inbound rule to DB security group {db_sg_id} allowing access from Lambda security group {lambda_sg_id}")
                else:
                    print(f"Inbound rule already exists in DB security group {db_sg_id} for Lambda security group {lambda_sg_id}")
            except Exception as e:
                print(f"Warning: Could not update DB security group {db_sg_id}: {str(e)}")
        
        # Save VPC configuration to file
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(config_dir, exist_ok=True)
        
        with open(os.path.join(config_dir, "vpc_config.env"), "w") as f:
            f.write(f"export VPC_ID={vpc_id}\n")
            f.write(f"export SUBNET_IDS={','.join(subnet_ids)}\n")
            f.write(f"export LAMBDA_SECURITY_GROUP_ID={lambda_sg_id}\n")
            f.write(f"export DB_SECURITY_GROUP_IDS={','.join(db_security_group_ids)}\n")
        
        return True
        
    except Exception as e:
        print(f"Error getting VPC configuration: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get VPC configuration for a database cluster")
    parser.add_argument("--cluster-name", required=True, help="RDS/Aurora cluster name")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    
    args = parser.parse_args()
    
    success = get_vpc_config(args.cluster_name, args.region)
    
    if not success:
        sys.exit(1)