"""Camera service for generating clips from KVS streams."""

import logging
from datetime import datetime
from typing import Dict, Any
from aws import kvs_client, s3_client

logger = logging.getLogger(__name__)

# Map camera names to KVS stream names
CAMERA_STREAMS = {
    "backyard": {
        "stream_name": "hassela_camera_01",
    },
}


def generate_camera_clip(camera: str, start_timestamp: str, end_timestamp: str) -> Dict[str, Any]:
    """
    Generate a video clip from camera footage.

    Args:
        camera: Name of the camera (e.g., "backyard")
        start_timestamp: Start time (ISO8601 format)
        end_timestamp: End time (ISO8601 format)

    Returns:
        Dict with 'url' key containing presigned URL, or 'error' key on failure
    """
    try:
        # Validate camera
        if camera not in CAMERA_STREAMS:
            available = ", ".join(CAMERA_STREAMS.keys())
            return {"error": f"Invalid camera. Available: {available}"}

        print('Camera is valid.')
        stream_name = CAMERA_STREAMS[camera]["stream_name"]

        # Parse timestamps
        start_time = _parse_timestamp(start_timestamp)
        end_time = _parse_timestamp(end_timestamp)

        # Validate duration (max 3 minutes = 180 seconds)
        duration_seconds = (end_time - start_time).total_seconds()
        if duration_seconds > 180:
            return {
                "error": f"Clip duration ({duration_seconds:.0f} seconds) exceeds maximum of 180 seconds (3 minutes). Please request a shorter clip."
            }
        if duration_seconds < 5:
            return {
                "error": f"Clip duration ({duration_seconds:.0f} seconds) is too short. Minimum duration is 5 seconds."
            }

        logger.info(
            f"Generating clip for camera: {camera} "
            f"({start_time.isoformat()} to {end_time.isoformat()}, duration: {duration_seconds:.0f}s)"
        )

        # Generate clip from KVS
        video_data = kvs_client.get_clip(stream_name, start_time, end_time)

        # Upload to S3
        filename = f"{camera}_{start_time.strftime('%Y%m%d_%H%M%S')}.mp4"
        presigned_url = s3_client.upload_clip(video_data, filename)

        logger.info(f"Successfully generated clip for camera: {camera}")
        return {"url": presigned_url}

    except Exception as e:
        logger.error(f"Error generating clip for camera '{camera}': {str(e)}")
        return {"error": f"Failed to generate clip: {str(e)}"}


def _parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO8601 timestamp string to datetime object."""
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
