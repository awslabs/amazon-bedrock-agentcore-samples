#!/usr/bin/env python3
"""
Verify S3 Tables and Lake Formation Setup

This script checks the current state of S3 Tables and Lake Formation integration.
"""

import boto3
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from utils.aws_session_utils import get_aws_session


def main():
    session, region, account_id = get_aws_session()
    
    s3tables = boto3.client('s3tables', region_name=region)
    glue = boto3.client('glue', region_name=region)
    lakeformation = boto3.client('lakeformation', region_name=region)
    ssm = boto3.client('ssm', region_name=region)
    
    print(f"\n🔍 S3 Tables and Lake Formation Verification")
    print(f"   Region: {region}")
    print(f"   Account: {account_id}\n")
    
    # Check SSM parameters
    print("📋 SSM Parameters:")
    params = [
        'table-bucket-name',
        'table-bucket-arn',
        'namespace',
        'catalog-name',
        's3tables-catalog-name',
        'lakeformation-role-arn'
    ]
    
    ssm_values = {}
    for param in params:
        try:
            response = ssm.get_parameter(Name=f'/app/lakehouse-agent/{param}')
            value = response['Parameter']['Value']
            ssm_values[param] = value
            print(f"   ✅ {param}: {value}")
        except ssm.exceptions.ParameterNotFound:
            print(f"   ❌ {param}: NOT FOUND")
    
    # Check S3 Tables bucket
    print(f"\n📦 S3 Tables Buckets:")
    try:
        response = s3tables.list_table_buckets()
        if response['tableBuckets']:
            for bucket in response['tableBuckets']:
                print(f"   ✅ {bucket['name']}")
                print(f"      ARN: {bucket['arn']}")
        else:
            print(f"   ❌ No S3 Tables buckets found")
    except Exception as e:
        print(f"   ❌ Error listing buckets: {e}")
    
    # Check namespaces
    if 'table-bucket-arn' in ssm_values:
        print(f"\n📁 Namespaces:")
        try:
            response = s3tables.list_namespaces(
                tableBucketARN=ssm_values['table-bucket-arn']
            )
            if response['namespaces']:
                for ns in response['namespaces']:
                    print(f"   ✅ {ns['namespace'][0]}")
            else:
                print(f"   ❌ No namespaces found")
        except Exception as e:
            print(f"   ❌ Error listing namespaces: {e}")
    
    # Check tables
    if 'table-bucket-arn' in ssm_values and 'namespace' in ssm_values:
        print(f"\n📊 Tables:")
        try:
            response = s3tables.list_tables(
                tableBucketARN=ssm_values['table-bucket-arn'],
                namespace=ssm_values['namespace']
            )
            if response['tables']:
                for table in response['tables']:
                    print(f"   ✅ {table['name']}")
            else:
                print(f"   ❌ No tables found")
        except Exception as e:
            print(f"   ❌ Error listing tables: {e}")
    
    # Check Glue catalogs
    print(f"\n📚 Glue Catalogs:")
    try:
        # Get the specific catalog we created
        catalog_name = 's3tablescatalog'
        try:
            response = glue.get_catalog(CatalogId=catalog_name)
            print(f"   ✅ {catalog_name}")
            catalog_info = response['Catalog']
            if 'FederatedCatalog' in catalog_info:
                fed = catalog_info['FederatedCatalog']
                print(f"      Type: Federated")
                print(f"      Identifier: {fed.get('Identifier', 'N/A')}")
                print(f"      Connection: {fed.get('ConnectionName', 'N/A')}")
        except glue.exceptions.EntityNotFoundException:
            print(f"   ❌ Catalog '{catalog_name}' not found")
            print(f"      This is the catalog that makes S3 Tables visible in Athena!")
            print(f"      Run: python integrate_s3tables_lakeformation.py")
        except Exception as e:
            print(f"   ⚠️  Error getting catalog '{catalog_name}': {e}")
            print(f"      Trying alternative method...")
            
            # Try listing databases in the catalog as a test
            try:
                response = glue.get_databases(CatalogId=catalog_name)
                print(f"   ✅ {catalog_name} (verified via database listing)")
                if response['DatabaseList']:
                    print(f"      Databases found: {len(response['DatabaseList'])}")
                    for db in response['DatabaseList'][:3]:  # Show first 3
                        print(f"         • {db['Name']}")
            except Exception as e2:
                print(f"   ❌ Catalog does not exist: {e2}")
    except Exception as e:
        print(f"   ❌ Error checking catalogs: {e}")
    
    # Check Lake Formation registration
    print(f"\n🔐 Lake Formation Resources:")
    try:
        response = lakeformation.list_resources()
        if response['ResourceInfoList']:
            for resource in response['ResourceInfoList']:
                arn = resource['ResourceArn']
                if 's3tables' in arn:
                    print(f"   ✅ {arn}")
                    print(f"      Role: {resource.get('RoleArn', 'N/A')}")
        else:
            print(f"   ⚠️  No resources registered")
    except Exception as e:
        print(f"   ❌ Error listing resources: {e}")
    
    # Summary and recommendations
    print(f"\n📋 Summary:")
    
    has_bucket = 'table-bucket-name' in ssm_values
    has_catalog = 's3tables-catalog-name' in ssm_values
    has_lf_role = 'lakeformation-role-arn' in ssm_values
    
    if not has_lf_role or not has_catalog:
        print(f"   ❌ Lake Formation integration NOT complete")
        print(f"\n📋 Next Steps:")
        print(f"   1. Ensure you have Lake Formation admin permissions")
        print(f"   2. Run: python integrate_s3tables_lakeformation.py")
        if has_bucket:
            print(f"   3. Tables already created, run: python load_sample_data.py")
            print(f"   4. Run: python setup_lakeformation_permissions.py")
    elif not has_bucket:
        print(f"   ⚠️  Lake Formation integrated but no S3 Tables bucket")
        print(f"\n📋 Next Steps:")
        print(f"   1. Run: python setup_s3tables.py")
        print(f"   2. Run: python load_sample_data.py")
        print(f"   3. Run: python setup_lakeformation_permissions.py")
    else:
        print(f"   ✅ Setup appears complete!")
        print(f"\n💡 To view in Athena:")
        print(f"   1. Open Athena console")
        print(f"   2. Select catalog: s3tablescatalog")
        print(f"   3. Select database: {ssm_values.get('namespace', 'lakehouse_data')}")
        print(f"   4. You should see tables: claims, users")


if __name__ == '__main__':
    main()
