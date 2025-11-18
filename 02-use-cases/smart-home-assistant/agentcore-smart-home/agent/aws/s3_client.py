"""S3 client for uploading clips and generating presigned URLs."""

import boto3
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self, clip_bucket: str, region: str = "us-east-1"):
        self.clip_bucket = clip_bucket
        self.region = region
        self.client = boto3.client("s3", region_name=region)

    def upload_clip(self, video_data: bytes, filename: str) -> str:
        """Upload a video clip to S3 and return a presigned URL."""
        s3_key = f"camera-clips/{filename}"

        try:
            logger.info(f"Uploading clip to S3: {self.clip_bucket}/{s3_key}")

            self.client.upload_fileobj(
                BytesIO(video_data),
                self.clip_bucket,
                s3_key,
                ExtraArgs={"ContentType": "video/mp4"},
            )

            logger.info(f"Successfully uploaded clip: {s3_key}")

            presigned_url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.clip_bucket, "Key": s3_key},
                ExpiresIn=3600,
            )

            logger.info("Generated presigned URL for clip")
            return presigned_url

        except Exception as e:
            logger.error(f"Error uploading clip to S3: {str(e)}")
            raise


_s3_client: S3Client = None


def initialize_s3_client(clip_bucket: str, region: str = "us-east-1"):
    """
    Initialize the global S3 client.

    Args:
        clip_bucket: S3 bucket for storing video clips
        region: AWS region
    """
    global _s3_client
    _s3_client = S3Client(clip_bucket=clip_bucket, region=region)
    logger.info(f"S3 client initialized (bucket: {clip_bucket})")


def upload_clip(video_data: bytes, filename: str) -> str:
    """
    Upload a video clip using the global S3 client.

    Args:
        video_data: MP4 video data
        filename: Filename for the clip

    Returns:
        Presigned URL for the clip

    Raises:
        RuntimeError: If S3 client not initialized
    """
    if _s3_client is None:
        raise RuntimeError(
            "S3 client not initialized. Call initialize_s3_client() first."
        )
    return _s3_client.upload_clip(video_data, filename)
