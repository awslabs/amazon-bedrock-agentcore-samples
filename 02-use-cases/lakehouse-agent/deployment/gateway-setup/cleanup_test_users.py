#!/usr/bin/env python3
"""
Cleanup Test Users in Cognito User Pool

This script deletes existing test users so they can be recreated with proper usernames.

Usage:
    python cleanup_test_users.py
"""
import boto3
import sys

def cleanup_users():
    """Delete test users from Cognito User Pool."""
    # Get region and SSM client
    session = boto3.Session()
    region = session.region_name
    
    ssm = boto3.client('ssm', region_name=region)
    cognito = boto3.client('cognito-idp', region_name=region)
    
    # Get User Pool ID from SSM
    try:
        response = ssm.get_parameter(Name='/app/lakehouse-agent/cognito-user-pool-id')
        user_pool_id = response['Parameter']['Value']
        print(f"✅ Found User Pool ID: {user_pool_id}")
    except Exception as e:
        print(f"❌ Error: Could not find User Pool ID in SSM: {e}")
        print("   Please run setup_cognito.py first")
        sys.exit(1)
    
    # Test user emails to clean up
    test_emails = [
        'user001@example.com',
        'user002@example.com',
        'adjuster001@example.com'
    ]
    
    print(f"\n🔍 Searching for test users in User Pool...")
    
    # List all users and find test users
    deleted_count = 0
    try:
        paginator = cognito.get_paginator('list_users')
        for page in paginator.paginate(UserPoolId=user_pool_id):
            for user in page.get('Users', []):
                username = user['Username']
                
                # Check if user has one of the test emails
                user_email = None
                for attr in user.get('Attributes', []):
                    if attr['Name'] == 'email':
                        user_email = attr['Value']
                        break
                
                if user_email in test_emails:
                    print(f"   Found test user: {user_email} (username: {username})")
                    
                    # Delete the user
                    try:
                        cognito.admin_delete_user(
                            UserPoolId=user_pool_id,
                            Username=username
                        )
                        print(f"   ✅ Deleted user: {username}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"   ❌ Error deleting user {username}: {e}")
        
        if deleted_count == 0:
            print("   ℹ️  No test users found to delete")
        else:
            print(f"\n✅ Deleted {deleted_count} test user(s)")
            print(f"\n📝 Next step: Run setup_cognito.py to recreate users with proper usernames")
            print(f"   cd gateway-setup")
            print(f"   python setup_cognito.py")
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 70)
    print("Cognito Test Users Cleanup")
    print("=" * 70)
    
    response = input("\n⚠️  This will delete test users. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cleanup cancelled")
        sys.exit(0)
    
    cleanup_users()
