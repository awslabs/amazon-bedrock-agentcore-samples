#!/usr/bin/env python3
"""
Policy Generator Script using boto3

Generates Cedar policies from natural language input using boto3 APIs.

"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================
REGION = "us-east-1"
SERVICE_NAME = "bedrock-agentcore-control"
API_VERSION = "2025-05-01"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('policy_generator.log')
    ]
)
logger = logging.getLogger(__name__)


class PolicyGenerator:
    """Policy generator using boto3 APIs"""

    def __init__(self, aws_profile: Optional[str] = None):
        """Initialize the policy generator with AWS profile"""
        self.aws_profile = aws_profile

        logger.info("Initializing Policy Generator")
        logger.info("Region: %s", REGION)

        # Create boto3 session with profile if specified
        if aws_profile:
            logger.info("Using AWS profile: %s", aws_profile)
            session = boto3.Session(profile_name=aws_profile, region_name=REGION)
        else:
            logger.info("Using default AWS credentials")
            session = boto3.Session(region_name=REGION)

        # Create the boto3 client
        try:
            self.client = session.client(
                SERVICE_NAME,
                region_name=REGION
            )
            logger.info("Successfully created boto3 client")
        except Exception as exc:
            logger.error("Failed to create boto3 client: %s", exc)
            raise


    def list_policy_engines(self) -> List[Dict[str, Any]]:
        """List all policy engines"""
        logger.info("Listing policy engines")
        try:
            response = self.client.list_policy_engines()
            policy_engines = response.get('policyEngines', [])
            logger.info("Found %d policy engines", len(policy_engines))
            return policy_engines
        except ClientError as exc:
            logger.error("Error listing policy engines: %s", exc)
            return []

    def create_policy_engine(self, name: str) -> Optional[str]:
        """Create a new policy engine and save to gateway_config.json if available"""
        logger.info("Creating policy engine: %s", name)
        try:
            timestamp = datetime.now().isoformat()
            response = self.client.create_policy_engine(
                name=name,
                description=f'Policy engine - {timestamp}',
                clientToken=str(uuid.uuid4())
            )
            policy_engine_id = response['policyEngineId']
            policy_engine_arn = response.get('policyEngineArn')
            logger.info("Created policy engine: %s", policy_engine_id)

            # Save to gateway_config.json if it exists
            if policy_engine_arn:
                self._save_policy_engine_to_config(policy_engine_id, policy_engine_arn)

            return policy_engine_id
        except ClientError as exc:
            logger.error("Error creating policy engine: %s", exc)
            return None

    def get_policy_engine(self, policy_engine_id: str) -> Optional[Dict[str, Any]]:
        """Get policy engine details"""
        logger.debug("Getting policy engine: %s", policy_engine_id)
        try:
            response = self.client.get_policy_engine(
                policyEngineId=policy_engine_id
            )
            return response
        except ClientError as exc:
            logger.error("Error getting policy engine: %s", exc)
            return None

    def wait_for_policy_engine_active(
        self,
        policy_engine_id: str,
        timeout: int = 300
    ) -> bool:
        """Wait for policy engine to reach ACTIVE state"""
        logger.info(
            "Waiting for policy engine %s to become ACTIVE (timeout: %ds)",
            policy_engine_id, timeout
        )
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < timeout:
            poll_count += 1
            engine = self.get_policy_engine(policy_engine_id)

            if not engine:
                logger.warning("Failed to get policy engine status (poll #%d)", poll_count)
                time.sleep(5)
                continue

            status = engine.get('status')
            logger.info("Poll #%d: Policy engine status = %s", poll_count, status)

            if status == 'ACTIVE':
                logger.info("Policy engine is ACTIVE")
                return True

            if status in ['CREATE_FAILED', 'UPDATE_FAILED', 'DELETE_FAILED']:
                logger.error("Policy engine reached failed state: %s", status)
                status_reason = engine.get('statusReason', 'No reason provided')
                logger.error("Failure reason: %s", status_reason)
                return False

            time.sleep(5)

        logger.warning(
            "Policy engine did not become ACTIVE within %ds (%d polls)",
            timeout, poll_count
        )
        return False

    @staticmethod
    def _save_policy_engine_to_config(policy_engine_id: str, policy_engine_arn: str) -> None:
        """Save policy engine details to gateway_config.json if it exists"""
        try:
            # Look for gateway_config.json in current directory
            config_path = Path.cwd() / 'gateway_config.json'

            if not config_path.exists():
                logger.debug("gateway_config.json not found, skipping save")
                return

            # Read existing config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Update with policy engine details
            updates_made = []
            if 'policy_engine_id' not in config or config.get('policy_engine_id') != policy_engine_id:
                config['policy_engine_id'] = policy_engine_id
                updates_made.append(f"policy_engine_id: {policy_engine_id}")

            if 'policy_engine_arn' not in config or config.get('policy_engine_arn') != policy_engine_arn:
                config['policy_engine_arn'] = policy_engine_arn
                updates_made.append(f"policy_engine_arn: {policy_engine_arn}")

            if updates_made:
                # Save updated config
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)

                logger.info("Updated gateway_config.json with:")
                for update in updates_made:
                    logger.info("  - %s", update)
            else:
                logger.debug("gateway_config.json already has policy engine details")

        except Exception as exc:
            logger.warning("Could not save to gateway_config.json: %s", exc)


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(log_level)
