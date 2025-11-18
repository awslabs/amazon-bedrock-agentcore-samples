"""Cross-account AWS session manager with automatic credential caching."""

import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class CrossAccountSessionManager:
    def __init__(self, cross_account_role_arn: str, session_name: str = "CameraAgentSession"):
        self.cross_account_role_arn = cross_account_role_arn
        self.session_name = session_name
        self._session: Optional[boto3.Session] = None
        self._session_expiration: Optional[datetime] = None
        self._sts_client = boto3.client("sts")

    def get_session(self) -> boto3.Session:
        """Get or refresh cross-account AWS session."""
        now = datetime.utcnow()
        needs_refresh = (
            self._session is None
            or self._session_expiration is None
            or now >= self._session_expiration - timedelta(minutes=5)
        )

        if needs_refresh:
            self._refresh_session()

        return self._session

    def _refresh_session(self):
        """Assume role and create new session with temporary credentials."""
        logger.info(f"Assuming cross-account role: {self.cross_account_role_arn}")

        try:
            assumed_role = self._sts_client.assume_role(
                RoleArn=self.cross_account_role_arn,
                RoleSessionName=self.session_name,
                DurationSeconds=3600,  # 1 hour
            )

            credentials = assumed_role["Credentials"]
            self._session_expiration = credentials["Expiration"].replace(tzinfo=None)

            self._session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )

            logger.info(
                f"Cross-account session refreshed (expires at {self._session_expiration} UTC)"
            )

        except Exception as e:
            logger.error(f"Failed to assume cross-account role: {str(e)}")
            raise


_session_manager: Optional[CrossAccountSessionManager] = None


def initialize_session_manager(cross_account_role_arn: str):
    """Initialize the global cross-account session manager."""
    global _session_manager
    _session_manager = CrossAccountSessionManager(cross_account_role_arn)
    _session_manager.get_session()
    logger.info("Cross-account session manager initialized")


def get_cross_account_session() -> boto3.Session:
    """Get the current cross-account session."""
    if _session_manager is None:
        raise RuntimeError(
            "Session manager not initialized. Call initialize_session_manager() first."
        )
    return _session_manager.get_session()
