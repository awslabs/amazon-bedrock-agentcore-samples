#!/usr/bin/env python3
import boto3
import json
import argparse
import uuid
import sys

def verify_secret(secret_name, region='us-west-2', test_connection=True):
    """
    Verify that a secret exists and contains the required fields
    """
    secretsmanager = boto3.client('secretsmanager', region_name=region)
    try:
        # Try with ARN first if the name contains special characters
        try:
            # List secrets to find the ARN if the name has special characters
            if any(c in secret_name for c in ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+']):
                print(f"Secret name contains special characters, searching for ARN...")
                list_response = secretsmanager.list_secrets(
                    Filters=[
                        {
                            'Key': 'name',
                            'Values': [secret_name]
                        },
                    ]
                )
                
                if list_response['SecretList']:
                    secret_arn = list_response['SecretList'][0]['ARN']
                    print(f"Found secret")
                    response = secretsmanager.get_secret_value(SecretId=secret_arn)
                else:
                    # Try with the name directly as a fallback
                    response = secretsmanager.get_secret_value(SecretId=secret_name)
            else:
                # No special characters, use the name directly
                response = secretsmanager.get_secret_value(SecretId=secret_name)
        except Exception as e:
            print(f"Error accessing secret by name, trying to find by partial match: {str(e)}")
            # Try to find the secret by listing all secrets and matching partially
            list_response = secretsmanager.list_secrets()
            found = False
            
            for s in list_response['SecretList']:
                if secret_name in s['Name']:
                    print(f"Found matching secret")
                    response = secretsmanager.get_secret_value(SecretId=s['ARN'])
                    found = True
                    break
            
            if not found:
                raise Exception(f"Could not find secret matching {secret_name}")
        secret_data = json.loads(response['SecretString'])
        
        # Check for required fields
        required_fields = ['host', 'dbname', 'username', 'password', 'port']
        missing_fields = [field for field in required_fields if field not in secret_data]
        
        if missing_fields:
            print(f"Warning: Secret is missing fields: {', '.join(missing_fields)}")
            return False
        
        # Verify password is not empty
        if not secret_data['password']:
            print(f"Warning: Secret has an empty password")
            return False
            
        print(f"Secret verified successfully")
        
        # Test database connection if requested
        if test_connection:
            try:
                # Import psycopg2 only if needed
                import psycopg2
                
                print(f"Testing connection to database")
                conn = psycopg2.connect(
                    host=secret_data['host'],
                    database=secret_data['dbname'],
                    user=secret_data['username'],
                    password=secret_data['password'],
                    port=secret_data['port'],
                    connect_timeout=10
                )
                
                # Execute a simple query to verify connection
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result and result[0] == 1:
                        print("Database connection successful!")
                    else:
                        print("Database connection test returned unexpected result")
                        return False
                
                conn.close()
                return True
            except ImportError:
                print("Warning: psycopg2 not installed, skipping connection test")
                return True
            except Exception as e:
                print(f"Error connecting to database: {str(e)}")
                print("The secret appears valid but the database connection failed.")
                print("Please verify your database credentials and network connectivity.")
                return False
        
        return True
    except Exception as e:
        print(f"Error verifying secret")
        return False

def setup_database_access(cluster_name, environment, username=None, password=None, existing_secret=None, region='us-west-2'):
    """
    Set up database access by:
    1. Getting the cluster endpoint from RDS
    2. Creating a secret with the required format
    3. Storing the secret name in SSM Parameter Store
    """
    print(f"Setting up database access for cluster: {cluster_name} in {environment} environment")
    
    # Initialize AWS clients
    rds = boto3.client('rds', region_name=region)
    secretsmanager = boto3.client('secretsmanager', region_name=region)
    ssm = boto3.client('ssm', region_name=region)
    
    try:
        # Get cluster information
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_name)
        
        if not response['DBClusters']:
            print(f"Error: Cluster {cluster_name} not found")
            return False
        
        cluster = response['DBClusters'][0]
        endpoint = cluster['Endpoint']
        port = cluster['Port']
        
        # Get database name (use default if available, otherwise use 'postgres')
        db_name = 'postgres'  # Default fallback
        if 'DatabaseName' in cluster:
            db_name = cluster['DatabaseName']
            
        # Determine secret name and value
        if existing_secret:
            # Use existing secret
            secret_name = existing_secret
            print(f"Using existing secret")
            
            try:
                # Get the existing secret to verify it exists
                # Try with ARN first if the name contains special characters
                try:
                    # List secrets to find the ARN if the name has special characters
                    if any(c in secret_name for c in ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+']):
                        print(f"Secret name contains special characters, searching for ARN...")
                        list_response = secretsmanager.list_secrets(
                            Filters=[
                                {
                                    'Key': 'name',
                                    'Values': [secret_name]
                                },
                            ]
                        )
                        
                        if list_response['SecretList']:
                            secret_arn = list_response['SecretList'][0]['ARN']
                            print(f"Found secret")
                            secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)
                        else:
                            # Try with the name directly as a fallback
                            secret_response = secretsmanager.get_secret_value(SecretId=secret_name)
                    else:
                        # No special characters, use the name directly
                        secret_response = secretsmanager.get_secret_value(SecretId=secret_name)
                except Exception as e:
                    print(f"Error accessing secret by name, trying to find by partial match: {str(e)}")
                    # Try to find the secret by listing all secrets and matching partially
                    list_response = secretsmanager.list_secrets()
                    found = False
                    
                    for s in list_response['SecretList']:
                        if secret_name in s['Name']:
                            secret_response = secretsmanager.get_secret_value(SecretId=s['ARN'])
                            found = True
                            break
                    
                    if not found:
                        raise Exception(f"Could not find secret matching {secret_name}")
                
                secret_data = json.loads(secret_response['SecretString'])
                
                # Extract credentials from existing secret
                if 'username' in secret_data and 'password' in secret_data:
                    username = secret_data['username']
                    password = secret_data['password']
                    print(f"Successfully retrieved credentials from existing secret for user")
                else:
                    print(f"Error: Existing secret does not contain username and password")
                    return False
                    
                # Create a new secret with the required format
                new_secret_name = f"db-performance-analyzer-{environment}-{uuid.uuid4().hex[:8]}"
                secret_value = {
                    "host": endpoint,
                    "dbname": db_name,
                    "username": username,
                    "password": password,  # Using the password from the existing secret
                    "port": port
                }
                
                # Print confirmation but mask the password                
                print(f"Creating new secret with endpoint: {endpoint}, port: {port}, database: {db_name}")
                print(f"This will not affect the original secret")
                
                # Determine whether to create a new secret or use the existing one directly
                # Check if we're running in non-interactive mode
                if '--non-interactive' in sys.argv:
                    if '--use-existing-directly' in sys.argv:
                        print(f"Non-interactive mode: Using existing secret directly")
                        new_secret_name = secret_name
                    elif '--create-new-secret' in sys.argv:
                        print(f"Non-interactive mode: Creating new secret")
                    else:
                        # Default behavior in non-interactive mode is to create a new secret
                        print(f"Non-interactive mode: Creating new secret (default)")
                else:
                    # Interactive mode - ask the user
                    choice = input("Do you want to: (1) Create a new secret with these credentials, or (2) Use the existing secret directly? (1/2): ")
                    
                    if choice == "2":
                        print(f"Using existing secret directly")
                        # No need to create a new secret, just use the existing one
                        new_secret_name = secret_name
                    elif choice == "1":
                        print(f"Creating new secret")
                    else:
                        print("Invalid choice. Operation cancelled.")
                        return False
                
                # Create the new secret if needed
                if new_secret_name != secret_name:  # Only create if we're not using the existing secret directly
                    try:
                        secret_response = secretsmanager.create_secret(
                            Name=new_secret_name,
                            Description=f"Database credentials for {cluster_name} in {environment} environment",
                            SecretString=json.dumps(secret_value)
                        )
                        print(f"Successfully created new secret")
                    except Exception as e:
                        print(f"Error creating new secret: {str(e)}")
                        return False
                
                # Update secret_name to the new one (or keep the existing one)
                secret_name = new_secret_name
                
            except secretsmanager.exceptions.ResourceNotFoundException:
                print(f"Error: Secret not found")
                return False
        else:
            # Create new secret with provided credentials
            if not username or not password:
                print("Error: Username and password are required when not using an existing secret")
                return False
                
            secret_name = f"db-performance-analyzer-{environment}-{uuid.uuid4().hex[:8]}"
            secret_value = {
                "host": endpoint,
                "dbname": db_name,
                "username": username,
                "password": password,
                "port": port
            }
            
            print(f"Creating secret with endpoint: {endpoint}, port: {port}, database: {db_name}")
            
            # Create the secret
            secret_response = secretsmanager.create_secret(
                Name=secret_name,
                Description=f"Database credentials for {cluster_name} in {environment} environment",
                SecretString=json.dumps(secret_value)
            )
        
        # Verify the secret was created correctly
        if not verify_secret(secret_name, region):
            print(f"Error: Secret verification failed")
            return False
            
        # Store secret name in SSM Parameter Store
        ssm_parameter_name = f"/AuroraOps/{environment}"
        ssm.put_parameter(
            Name=ssm_parameter_name,
            Value=secret_name,
            Type="String",
            Overwrite=True
        )
        
        print(f"Successfully set up database access:")
        print(f"- Secret created")
        print(f"- SSM Parameter created: {ssm_parameter_name}")
        
        # Save to config file
        import os
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, f"db_{environment}_config.env"), "w") as f:
            f.write(f"export DB_CLUSTER_NAME={cluster_name}\n")
            f.write(f"# DB_SECRET_NAME stored securely in SSM Parameter Store: {ssm_parameter_name}\n")
            f.write(f"export DB_SSM_PARAMETER={ssm_parameter_name}\n")
            f.write(f"export DB_ENDPOINT={endpoint}\n")
            f.write(f"export DB_PORT={port}\n")
            f.write(f"export DB_NAME={db_name}\n")
        
        return True
        
    except Exception as e:
        print(f"Error setting up database access: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up database access for DB Performance Analyzer")
    parser.add_argument("--cluster-name", required=True, help="RDS/Aurora cluster name")
    parser.add_argument("--environment", required=True, choices=["prod", "dev"], help="Environment (prod or dev)")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--existing-secret", help="Name of existing secret in AWS Secrets Manager")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--test-connection", action="store_true", help="Test database connection after setup")
    parser.add_argument("--verify-only", help="Only verify an existing secret without creating a new one")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode (no prompts)")
    parser.add_argument("--use-existing-directly", action="store_true", help="Use existing secret directly without creating a new one")
    parser.add_argument("--create-new-secret", action="store_true", help="Always create a new secret even when using an existing one as source")
    
    args = parser.parse_args()
    
    # Handle verify-only mode
    if args.verify_only:
        print(f"Verifying secret {args.verify_only}...")
        success = verify_secret(args.verify_only, args.region, args.test_connection)
        sys.exit(0 if success else 1)
    
    # Validate arguments
    if not args.existing_secret and (not args.username or not args.password):
        parser.error("Either --existing-secret or both --username and --password must be provided")
    
    success = setup_database_access(
        args.cluster_name,
        args.environment,
        args.username,
        args.password,
        args.existing_secret,
        args.region
    )
    
    # Test connection if requested
    if success and args.test_connection:
        # Get the secret name from SSM Parameter Store
        ssm = boto3.client('ssm', region_name=args.region)
        try:
            response = ssm.get_parameter(Name=f"/AuroraOps/{args.environment}")
            secret_name = response['Parameter']['Value']
            print("Testing database connection using retrieved secret.")
            verify_secret(secret_name, args.region, True)
        except Exception as e:
            print(f"Error testing connection: {str(e)}")
            success = False
    
    if not success:
        sys.exit(1)
