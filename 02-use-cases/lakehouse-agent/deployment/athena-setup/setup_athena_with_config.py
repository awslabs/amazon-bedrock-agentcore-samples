#!/usr/bin/env python3
"""
Athena Setup Script - Using Centralized Configuration

This is the updated version that reads from config.py instead of command-line arguments.
All configuration is managed through SSM Parameter Store.

Usage:
    # Setup SSM parameters first with S3_BUCKET_NAME
    python setup_athena_with_config.py

    # Or use command-line args to override
    python setup_athena_with_config.py --bucket-name override-bucket
"""

import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
import argparse

# Import the original AthenaSetup class
from setup_athena import AthenaSetup


def main():
    parser = argparse.ArgumentParser(
        description='Setup Athena with configuration from SSM Parameter Store'
    )
    # Optional overrides
    parser.add_argument(
        '--region',
        default=config.AWS_REGION,
        help=f'AWS region (default from config: {config.AWS_REGION})'
    )
    parser.add_argument(
        '--bucket-name',
        default=config.S3_BUCKET_NAME,
        help=f'S3 bucket name (default from config: {config.S3_BUCKET_NAME})'
    )

    args = parser.parse_args()

    # Validate configuration
    print("🔍 Validating configuration...")
    if not config.is_valid():
        print("\n❌ Configuration is invalid!")
        config.print_status()
        print("\n📝 Please update your SSM parameters with required values.")
        print("   See CONFIGURATION_GUIDE.md for details.")
        sys.exit(1)

    print("✅ Configuration validated\n")

    # Show configuration being used
    print(f"📋 Using configuration:")
    print(f"   Region: {args.region}")
    print(f"   Bucket: {args.bucket_name}")
    print(f"   Database: {config.ATHENA_DATABASE_NAME}")
    print()

    # Run setup
    setup = AthenaSetup(args.region, args.bucket_name)
    setup.setup()


if __name__ == '__main__':
    main()
