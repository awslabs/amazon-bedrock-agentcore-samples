"""Kinesis Video Streams client for fetching clips."""

import logging
from datetime import datetime
from typing import Optional
from .session_manager import get_cross_account_session

logger = logging.getLogger(__name__)


class KVSClient:
    def __init__(self, region: str = "eu-west-1"):
        self.region = region

    def get_clip(
        self, stream_name: str, start_time: datetime, end_time: datetime
    ) -> bytes:
        """Generate a video clip from a KVS stream for a specific time range."""
        try:
            session = get_cross_account_session()
            kvs_client = session.client("kinesisvideo", region_name=self.region)

            # Get data endpoint for the stream
            endpoint_response = kvs_client.get_data_endpoint(
                StreamName=stream_name, APIName="GET_CLIP"
            )
            endpoint = endpoint_response["DataEndpoint"]

            # Create media client with the endpoint
            media_client = session.client(
                "kinesis-video-archived-media",
                endpoint_url=endpoint,
                region_name=self.region,
            )

            logger.info(
                f"Generating clip from stream: {stream_name} "
                f"({start_time.isoformat()} to {end_time.isoformat()})"
            )

            clip_response = media_client.get_clip(
                StreamName=stream_name,
                ClipFragmentSelector={
                    "FragmentSelectorType": "SERVER_TIMESTAMP",
                    "TimestampRange": {
                        "StartTimestamp": start_time,
                        "EndTimestamp": end_time,
                    },
                },
            )

            # Read the streaming payload
            video_data = clip_response["Payload"].read()
            logger.info(f"Successfully generated clip from stream: {stream_name}")
            return video_data

        except Exception as e:
            logger.error(
                f"Error generating clip from KVS stream '{stream_name}': {str(e)}"
            )
            raise


_kvs_client: Optional[KVSClient] = None


def initialize_kvs_client(region: str = "eu-west-1"):
    """
    Initialize the global KVS client.

    Args:
        region: AWS region for KVS resources
    """
    global _kvs_client
    _kvs_client = KVSClient(region=region)
    logger.info(f"KVS client initialized for region '{region}'")


def get_clip(stream_name: str, start_time: datetime, end_time: datetime) -> bytes:
    """
    Get a video clip from a KVS stream.

    Args:
        stream_name: Name of the KVS stream
        start_time: Start time for the clip
        end_time: End time for the clip

    Returns:
        MP4 video data

    Raises:
        RuntimeError: If KVS client not initialized
    """
    if _kvs_client is None:
        raise RuntimeError(
            "KVS client not initialized. Call initialize_kvs_client() first."
        )
    return _kvs_client.get_clip(stream_name, start_time, end_time)
