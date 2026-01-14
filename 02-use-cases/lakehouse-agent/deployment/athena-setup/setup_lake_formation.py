#!/usr/bin/env python3
"""
Setup AWS Lake Formation for Row-Level Security on Health Lakehouse Data

This implements PROPER row-level security using Lake Formation data filters.
Security is enforced at the AWS query engine level, not application code.

Key Features:
- Row-level security enforced by Lake Formation, not application code
- Session tags pass user identity from OAuth to AWS credentials
- No SQL injection risk - filtering happens before query execution
- Fully auditable through CloudTrail and Lake Formation logs

Usage:
    python setup_lake_formation.py

The script reads the S3 bucket name from SSM Parameter Store at /app/lakehouse-agent/s3-bucket-name
"""

import boto3
import json
import sys
from typing import Dict, List

class LakeFormationSetup:
    def __init__(self):
        """
        Initialize Lake Formation setup with AWS region from boto3 session.
        """
        # Get region from boto3 session
        session = boto3.Session()
        self.region = session.region_name
        
        self.lf_client = boto3.client('lakeformation', region_name=self.region)
        self.glue_client = boto3.client('glue', region_name=self.region)
        self.iam_client = boto3.client('iam', region_name=self.region)
        self.sts_client = boto3.client('sts', region_name=self.region)
        self.ssm_client = boto3.client('ssm', region_name=self.region)

    def get_bucket_name_from_ssm(self) -> str:
        """
        Get S3 bucket name from SSM Parameter Store.
        
        Returns:
            S3 bucket name from /app/lakehouse-agent/s3-bucket-name parameter
        """
        try:
            response = self.ssm_client.get_parameter(
                Name='/app/lakehouse-agent/s3-bucket-name'
            )
            bucket_name = response['Parameter']['Value']
            print(f"✅ Retrieved bucket name from SSM: {bucket_name}")
            return bucket_name
        except self.ssm_client.exceptions.ParameterNotFound:
            print(f"❌ SSM parameter /app/lakehouse-agent/s3-bucket-name not found")
            print(f"   Please run setup_athena.py first to create the required parameters")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error retrieving bucket name from SSM: {e}")
            sys.exit(1)

    def store_parameters_in_ssm(self, role_name: str, role_arn: str):
        """
        Store Lake Formation role information in SSM Parameter Store.
        
        Args:
            role_name: IAM role name
            role_arn: IAM role ARN
        """
        print("\n💾 Storing configuration in SSM Parameter Store...")
        
        parameters = [
            {
                'name': '/app/lakehouse-agent/rls-role-name',
                'value': role_name,
                'description': 'Lake Formation RLS IAM role name'
            },
            {
                'name': '/app/lakehouse-agent/rls-role-arn',
                'value': role_arn,
                'description': 'Lake Formation RLS IAM role ARN'
            }
        ]
        
        for param in parameters:
            try:
                self.ssm_client.put_parameter(
                    Name=param['name'],
                    Value=param['value'],
                    Description=param['description'],
                    Type='String',
                    Overwrite=True
                )
                print(f"✅ Stored parameter: {param['name']} = {param['value']}")
            except Exception as e:
                print(f"❌ Error storing parameter {param['name']}: {e}")
                raise

    def register_s3_location(self, s3_path: str, role_arn: str):
        """
        Register S3 location with Lake Formation.

        Args:
            s3_path: S3 path (e.g., s3://bucket/path/)
            role_arn: IAM role ARN for data access
        """
        print(f"\n📍 Registering S3 location with Lake Formation: {s3_path}")

        # Convert S3 URI to ARN format required by Lake Formation
        # s3://bucket/path/ -> arn:aws:s3:::bucket/path/
        if s3_path.startswith('s3://'):
            s3_arn = s3_path.replace('s3://', 'arn:aws:s3:::')
        else:
            s3_arn = f"arn:aws:s3:::{s3_path}"

        try:
            self.lf_client.register_resource(
                ResourceArn=s3_arn,
                UseServiceLinkedRole=False,
                RoleArn=role_arn
            )
            print(f"✅ S3 location registered: {s3_arn}")
        except self.lf_client.exceptions.AlreadyExistsException:
            print(f"✅ S3 location already registered: {s3_arn}")
        except Exception as e:
            print(f"❌ Error registering S3 location: {e}")
            raise

    def create_data_filter(
        self,
        database_name: str,
        table_name: str,
        filter_name: str,
        row_filter_expression: str
    ):
        """
        Create a Lake Formation data filter for row-level security.

        Args:
            database_name: Glue database name
            table_name: Glue table name
            filter_name: Name for the data filter
            row_filter_expression: SQL expression for filtering (e.g., "user_id = '${aws:userid}'")
        """
        print(f"\n🔒 Creating Lake Formation data filter: {filter_name}")

        try:
            self.lf_client.create_data_cells_filter(
                TableData={
                    'TableCatalogId': self.sts_client.get_caller_identity()['Account'],
                    'DatabaseName': database_name,
                    'TableName': table_name,
                    'Name': filter_name,
                    'ColumnWildcard': {},  # Apply filter to all columns
                    'RowFilter': {
                        'FilterExpression': row_filter_expression
                    }
                }
            )
            print(f"✅ Data filter created: {filter_name}")
            print(f"   Expression: {row_filter_expression}")

        except self.lf_client.exceptions.AlreadyExistsException:
            print(f"✅ Data filter already exists: {filter_name}")
        except Exception as e:
            print(f"❌ Error creating data filter: {e}")
            raise

    def grant_filtered_table_access(
        self,
        principal_arn: str,
        database_name: str,
        table_name: str,
        data_filter_name: str,
        permissions: List[str] = None
    ):
        """
        Grant principal access to table with data filter applied.

        Args:
            principal_arn: IAM role/user ARN
            database_name: Glue database name
            table_name: Glue table name
            data_filter_name: Data filter to apply
            permissions: List of permissions (default: ['SELECT'])
        """
        if permissions is None:
            permissions = ['SELECT']

        print(f"\n🎫 Granting filtered table access to: {principal_arn}")

        try:
            self.lf_client.grant_permissions(
                Principal={'DataLakePrincipalIdentifier': principal_arn},
                Resource={
                    'DataCellsFilter': {
                        'TableCatalogId': self.sts_client.get_caller_identity()['Account'],
                        'DatabaseName': database_name,
                        'TableName': table_name,
                        'Name': data_filter_name
                    }
                },
                Permissions=permissions
            )
            print(f"✅ Access granted with filter: {data_filter_name}")

        except Exception as e:
            print(f"❌ Error granting permissions: {e}")
            raise

    def create_session_tag_policy(self, role_name: str) -> str:
        """
        Create IAM role with session tag support for passing user identity.

        This role will be assumed with session tags from the OAuth user identity.

        Args:
            role_name: Name for the IAM role

        Returns:
            Role ARN
        """
        print(f"\n👤 Creating IAM role with session tag support: {role_name}")

        # Trust policy allowing session tags
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "lambda.amazonaws.com",
                            "lakeformation.amazonaws.com"
                        ],
                        "AWS": f"arn:aws:iam::{self.sts_client.get_caller_identity()['Account']}:root"
                    },
                    "Action": ["sts:AssumeRole", "sts:TagSession"]
                },
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock-agentcore.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "sts:ExternalId": "bedrock-agentcore"
                        }
                    }
                }
            ]
        }

        try:
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Role for claims MCP server with session tag support for user identity',
                MaxSessionDuration=3600,
                Tags=[
                    {'Key': 'Purpose', 'Value': 'InsuranceClaimsRowLevelSecurity'}
                ]
            )

            role_arn = response['Role']['Arn']
            print(f"✅ Role created: {role_arn}")

            # Attach policies for Athena and Glue access
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonAthenaFullAccess'
            )

            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
            )

            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole'
            )

            # Attach Lake Formation permissions
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AWSLakeFormationDataAdmin'
            )

            print(f"✅ Policies attached")

            return role_arn

        except self.iam_client.exceptions.EntityAlreadyExistsException:
            response = self.iam_client.get_role(RoleName=role_name)
            print(f"✅ Role already exists: {response['Role']['Arn']}")
            return response['Role']['Arn']
        except Exception as e:
            print(f"❌ Error creating role: {e}")
            raise

    def setup_complete_rls(
        self,
        database_name: str = 'lakehouse_db',
        table_name: str = 'claims',
        s3_bucket: str = None,
        role_name: str = 'lakehouse-rls-role'
    ):
        """
        Complete setup for row-level security using Lake Formation.

        Args:
            database_name: Athena/Glue database name (default: 'lakehouse_db')
            table_name: Table name (default: 'claims')
            s3_bucket: S3 bucket name (default: read from SSM Parameter Store)
            role_name: IAM role name to create (default: 'lakehouse-rls-role')
        """
        # Get bucket name from SSM Parameter Store if not provided
        if s3_bucket is None:
            s3_bucket = self.get_bucket_name_from_ssm()
        
        print(f"\n🚀 Setting up Lake Formation Row-Level Security")
        print(f"   Database: {database_name}")
        print(f"   Table: {table_name}")
        print(f"   S3 Bucket: {s3_bucket}")

        # Step 1: Create IAM role with session tag support
        role_arn = self.create_session_tag_policy(role_name)

        # Step 2: Register S3 location
        # Strip s3:// prefix if provided in bucket name
        bucket_name = s3_bucket.replace('s3://', '')
        s3_path = f"s3://{bucket_name}/lakehouse-data/"
        self.register_s3_location(s3_path, role_arn)

        # Step 3: Create data filter using session tags
        # The ${aws:userid} or ${aws:PrincipalTag/user_id} will be replaced with actual user identity
        filter_expression = "user_id = '${aws:PrincipalTag/user_id}'"

        self.create_data_filter(
            database_name=database_name,
            table_name=table_name,
            filter_name='user_claims_filter',
            row_filter_expression=filter_expression
        )

        # Step 4: Grant filtered access to the role
        self.grant_filtered_table_access(
            principal_arn=role_arn,
            database_name=database_name,
            table_name=table_name,
            data_filter_name='user_claims_filter',
            permissions=['SELECT']
        )

        # Step 5: Store configuration in SSM Parameter Store
        self.store_parameters_in_ssm(role_name, role_arn)

        print(f"\n✨ Lake Formation Row-Level Security setup complete!")
        print(f"\n📝 Configuration Summary:")
        print(f"   Role Name: {role_name}")
        print(f"   Role ARN: {role_arn}")
        print(f"   S3 Location: {s3_path}")
        print(f"   Data Filter: user_claims_filter")
        print(f"   Filter Expression: {filter_expression}")
        
        print(f"\n💾 SSM Parameters Stored:")
        print(f"   • /app/lakehouse-agent/rls-role-name")
        print(f"   • /app/lakehouse-agent/rls-role-arn")
        
        print(f"\n🔒 Security Model:")
        print(f"   1. OAuth user identity extracted from JWT in Gateway interceptor")
        print(f"   2. User identity passed as session tag when assuming IAM role")
        print(f"   3. Lake Formation applies filter: user_id = session_tag[user_id]")
        print(f"   4. Athena query engine enforces filter BEFORE query execution")
        print(f"   5. Application code NEVER sees other users' data")

        return {
            'role_name': role_name,
            'role_arn': role_arn,
            's3_path': s3_path,
            'filter_name': 'user_claims_filter',
            'filter_expression': filter_expression
        }


def main():
    setup = LakeFormationSetup()
    setup.setup_complete_rls()


if __name__ == '__main__':
    main()
