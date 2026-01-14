#!/usr/bin/env python3
"""
AWS Session Utility for SSO-aware boto3 Session Creation

This module provides a centralized way to create and validate AWS sessions,
with special handling for AWS SSO authentication. It addresses common issues
with SSO token expiration and profile detection.

Usage:
    from aws_session_utils import get_aws_session

    # Auto-detect profile from environment
    session, region, account_id = get_aws_session()

    # Use specific profile
    session, region, account_id = get_aws_session(profile_name='myprofile')

    # Specify region
    session, region, account_id = get_aws_session(region_name='us-west-2')
"""

import boto3
import os
import sys
from typing import Tuple, Optional
from botocore.exceptions import (
    NoCredentialsError,
    ProfileNotFound,
    ClientError,
    TokenRetrievalError,
    SSOTokenLoadError
)


def get_aws_session(
    profile_name: Optional[str] = None,
    region_name: Optional[str] = None,
    verbose: bool = True
) -> Tuple[boto3.Session, str, str]:
    """
    Create and validate AWS session with SSO support.

    This function:
    1. Detects AWS profile from environment variables or parameters
    2. Creates boto3 session with correct profile
    3. Validates credentials are available and not expired
    4. Provides clear error messages with remediation steps

    Args:
        profile_name: Optional AWS profile name to use. If not provided,
                     will check AWS_PROFILE and AWS_DEFAULT_PROFILE env vars.
        region_name: Optional AWS region. If not provided, will auto-detect
                    from session, environment, or use us-east-1 default.
        verbose: If True, print status messages. Default True.

    Returns:
        Tuple of (boto3.Session, region_name: str, account_id: str)

    Raises:
        ValueError: If credentials are not configured or invalid
        SystemExit: On unrecoverable authentication errors

    Examples:
        >>> session, region, account = get_aws_session()
        >>> s3_client = session.client('s3', region_name=region)

        >>> session, region, account = get_aws_session(profile_name='prod')
    """

    # Check if running in container/Lambda environment
    # In these environments, IAM roles provide credentials automatically
    is_container = any([
        os.environ.get('AWS_EXECUTION_ENV'),  # Lambda, ECS, etc.
        os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'),  # ECS
        os.environ.get('AWS_CONTAINER_CREDENTIALS_FULL_URI'),  # ECS
        os.environ.get('ECS_CONTAINER_METADATA_URI'),  # ECS
        os.environ.get('K8S_AWS_ROLE_ARN'),  # Kubernetes
    ])

    if is_container and not profile_name:
        # In container environment, use simple session with IAM role credentials
        if verbose:
            print("🔍 Container environment detected - using IAM role credentials")

        region = _detect_region_simple(region_name)
        session = boto3.Session(region_name=region)

        try:
            sts_client = session.client('sts', region_name=region)
            account_id = sts_client.get_caller_identity()['Account']

            if verbose:
                print(f"✅ Container credentials validated")
                print(f"   Region: {region}")
                print(f"   Account ID: {account_id}")

            return session, region, account_id
        except Exception as e:
            print(f"❌ Failed to validate container credentials: {e}")
            # In container, let the error propagate rather than SystemExit
            raise ValueError(f"Container credential validation failed: {e}") from e

    # Determine which profile to use (for local development)
    detected_profile = _detect_profile(profile_name, verbose)

    # Create session with detected profile
    try:
        if detected_profile:
            session = boto3.Session(profile_name=detected_profile)
        else:
            session = boto3.Session()
    except ProfileNotFound as e:
        _print_profile_not_found_error(detected_profile)
        raise SystemExit(1) from e

    # Detect region
    region = _detect_region(session, region_name, verbose)

    # Recreate session with explicit region if needed
    if region and not session.region_name:
        if detected_profile:
            session = boto3.Session(profile_name=detected_profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)

    # Validate credentials
    try:
        credentials = session.get_credentials()
        if not credentials:
            _print_no_credentials_error(detected_profile)
            raise SystemExit(1)

        # Test credentials by getting account ID
        sts_client = session.client('sts', region_name=region)
        account_id = sts_client.get_caller_identity()['Account']

    except (TokenRetrievalError, SSOTokenLoadError) as e:
        _print_sso_token_expired_error(detected_profile, region, str(e))
        raise SystemExit(1) from e
    except NoCredentialsError as e:
        _print_no_credentials_error(detected_profile)
        raise SystemExit(1) from e
    except ClientError as e:
        if 'ExpiredToken' in str(e) or 'InvalidToken' in str(e):
            _print_sso_token_expired_error(detected_profile, region, str(e))
            raise SystemExit(1) from e
        else:
            print(f"\n❌ AWS API Error: {e}")
            raise SystemExit(1) from e
    except Exception as e:
        print(f"\n❌ Unexpected error validating AWS credentials: {e}")
        print(f"   Error type: {type(e).__name__}")
        raise SystemExit(1) from e

    # Print success message
    if verbose:
        _print_success_message(detected_profile, region, account_id, credentials)

    return session, region, account_id


def _detect_profile(profile_name: Optional[str], verbose: bool) -> Optional[str]:
    """Detect which AWS profile to use."""
    if profile_name:
        if verbose:
            print(f"🔍 Using specified profile: {profile_name}")
        return profile_name

    # Check environment variables in order of precedence
    env_profile = os.environ.get('AWS_PROFILE') or os.environ.get('AWS_DEFAULT_PROFILE')

    if env_profile:
        if verbose:
            env_var = 'AWS_PROFILE' if os.environ.get('AWS_PROFILE') else 'AWS_DEFAULT_PROFILE'
            print(f"🔍 Using profile from {env_var}: {env_profile}")
        return env_profile

    if verbose:
        print("🔍 Using default AWS credentials (no profile specified)")
    return None


def _detect_region_simple(region_name: Optional[str]) -> str:
    """Detect AWS region without session (for container environments)."""
    if region_name:
        return region_name

    # Try environment variables
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if region:
        return region

    # Default to us-east-1
    return 'us-east-1'


def _detect_region(
    session: boto3.Session,
    region_name: Optional[str],
    verbose: bool
) -> str:
    """Detect AWS region from multiple sources."""
    if region_name:
        if verbose:
            print(f"🌍 Using specified region: {region_name}")
        return region_name

    # Try to get from session
    region = session.region_name
    if region:
        if verbose:
            print(f"🌍 Using region from AWS config: {region}")
        return region

    # Try environment variables
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if region:
        env_var = 'AWS_REGION' if os.environ.get('AWS_REGION') else 'AWS_DEFAULT_REGION'
        if verbose:
            print(f"🌍 Using region from {env_var}: {region}")
        return region

    # Default to us-east-1
    region = 'us-east-1'
    if verbose:
        print(f"⚠️  No AWS region configured, using default: {region}")
        print("   To set your region:")
        print("   - Environment variable: export AWS_DEFAULT_REGION=your-region")
        print("   - AWS CLI: aws configure set region your-region")
    return region


def _print_success_message(
    profile: Optional[str],
    region: str,
    account_id: str,
    credentials
) -> None:
    """Print success message with credential info."""
    print("\n✅ AWS Credentials Validated")
    print(f"   Region: {region}")
    print(f"   Account ID: {account_id}")
    print(f"   Profile: {profile or 'default'}")

    # Try to detect SSO
    is_sso = False
    try:
        if hasattr(credentials, 'method'):
            method_str = str(credentials.method).lower()
            is_sso = 'sso' in method_str
    except:
        pass

    if is_sso:
        print("   Auth method: AWS SSO")
    else:
        print("   Auth method: AWS credentials (IAM/access keys)")
    print()


def _print_no_credentials_error(profile: Optional[str]) -> None:
    """Print helpful error message when no credentials are found."""
    print("\n" + "="*70)
    print("❌ AWS CREDENTIALS NOT CONFIGURED")
    print("="*70)
    print("\nNo AWS credentials were found.")

    if profile:
        print(f"\nCurrent profile: {profile}")
        print("\nThis profile may not be configured. To set it up:")
        print(f"  aws configure --profile {profile}")

    print("\nTo configure AWS credentials, use one of these methods:")
    print("\n1. AWS SSO (Recommended for organizations):")
    print("   aws configure sso")
    print("   aws sso login --profile your-profile-name")
    print("   export AWS_PROFILE=your-profile-name")

    print("\n2. AWS CLI with access keys:")
    print("   aws configure")

    print("\n3. Environment variables:")
    print("   export AWS_ACCESS_KEY_ID=your-key")
    print("   export AWS_SECRET_ACCESS_KEY=your-secret")

    print("\n4. IAM Role (if running on EC2/ECS/Lambda):")
    print("   Credentials are automatically provided")

    print("\n" + "="*70)


def _print_sso_token_expired_error(
    profile: Optional[str],
    region: str,
    error_detail: str
) -> None:
    """Print helpful error message for SSO token expiration."""
    print("\n" + "="*70)
    print("❌ AWS SSO TOKEN EXPIRED")
    print("="*70)
    print("\nYour AWS SSO session has expired and needs to be refreshed.")

    if profile:
        print(f"\nTo refresh your SSO credentials for profile '{profile}', run:")
        print(f"  aws sso login --profile {profile}")

        print("\nThen ensure your environment uses this profile:")
        print(f"  export AWS_PROFILE={profile}")
    else:
        print("\nTo refresh your SSO credentials, run:")
        print("  aws sso login")

        print("\nIf you use a specific profile, specify it:")
        print("  aws sso login --profile your-profile-name")
        print("  export AWS_PROFILE=your-profile-name")

    print("\nCurrent environment:")
    print(f"  AWS_PROFILE: {os.environ.get('AWS_PROFILE', 'not set')}")
    print(f"  AWS_DEFAULT_PROFILE: {os.environ.get('AWS_DEFAULT_PROFILE', 'not set')}")
    print(f"  AWS_REGION: {region}")

    print("\n" + "="*70)
    print(f"Error details: {error_detail}")
    print("="*70)


def _print_profile_not_found_error(profile: str) -> None:
    """Print helpful error message when profile is not found."""
    print("\n" + "="*70)
    print(f"❌ AWS PROFILE NOT FOUND: {profile}")
    print("="*70)

    print(f"\nThe AWS profile '{profile}' was not found in your AWS configuration.")

    print("\nTo list available profiles:")
    print("  aws configure list-profiles")

    print(f"\nTo create this profile:")
    print(f"  aws configure --profile {profile}")

    print("\nOr for SSO:")
    print("  aws configure sso")

    print("\n" + "="*70)


if __name__ == '__main__':
    """Test the session utility."""
    print("Testing AWS Session Utility\n")
    print("="*70)

    try:
        session, region, account_id = get_aws_session()
        print("\n✅ Test successful!")
        print(f"\nYou can now use this session to create AWS clients:")
        print(f"  s3_client = session.client('s3', region_name='{region}')")
        print(f"  dynamodb = session.resource('dynamodb', region_name='{region}')")

    except SystemExit:
        print("\n❌ Test failed - please fix the errors above and try again")
        sys.exit(1)
