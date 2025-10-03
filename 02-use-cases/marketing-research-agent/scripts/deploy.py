#!/usr/bin/env python3
"""
Complete deployment script for Marketing Research Agent.

This script handles both infrastructure deployment and memory initialization.
"""

import argparse
import logging
import subprocess
import sys
import os
from pathlib import Path

def setup_logging(verbose: bool = False):
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def run_command(command: str, cwd: str = None) -> bool:
    """Run a shell command and return success status."""
    logger = logging.getLogger(__name__)
    logger.info(f"Running: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False

def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description="Deploy Marketing Research Agent (Infrastructure + Memory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--environment", "-e",
        default="dev",
        choices=["dev", "prod"],
        help="Deployment environment (default: dev)"
    )
    parser.add_argument(
        "--skip-infra",
        action="store_true",
        help="Skip infrastructure deployment (CDK)"
    )
    parser.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip memory initialization"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Bootstrap memory with marketing intelligence data"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting deployment for {args.environment} environment")
    
    project_root = Path(__file__).parent.parent
    success = True
    
    # Step 1: Deploy Infrastructure
    if not args.skip_infra:
        logger.info("=== Deploying Infrastructure (CDK) ===")
        
        # Set environment variables for CDK
        env = os.environ.copy()
        env['CDK_DEFAULT_REGION'] = args.region
        
        # Run CDK deployment
        infra_dir = project_root / "infra"
        cdk_command = "uv run cdk deploy"
        if not run_command(cdk_command, cwd=str(infra_dir)):
            logger.error("Infrastructure deployment failed")
            success = False
    else:
        logger.info("Skipping infrastructure deployment")
    
    # Step 2: Initialize Memory
    if success and not args.skip_memory:
        logger.info("=== Initializing Memory ===")
        
        memory_command = f"python initialize_memory.py --region {args.region}"
        if args.bootstrap:
            memory_command += " --bootstrap"
        if args.verbose:
            memory_command += " --verbose"
        
        if not run_command(memory_command, cwd=str(project_root / "scripts")):
            logger.error("Memory initialization failed")
            success = False
    else:
        logger.info("Skipping memory initialization")
    
    # Summary
    if success:
        logger.info("Deployment completed successfully!")
        logger.info("The marketing research agent system is ready to use.")
    else:
        logger.error("Deployment failed. Check logs above for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())