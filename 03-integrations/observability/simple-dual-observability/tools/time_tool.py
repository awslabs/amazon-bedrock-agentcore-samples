"""Time tool for retrieving current time in different timezones."""

import logging
from datetime import datetime
from typing import Any

import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _validate_timezone(
    timezone: str,
) -> pytz.tzinfo.BaseTzInfo:
    """Validate and return timezone object.

    Args:
        timezone: The timezone name to validate

    Returns:
        Timezone object

    Raises:
        ValueError: If timezone is invalid
    """
    try:
        tz = pytz.timezone(timezone)
        return tz
    except pytz.exceptions.UnknownTimeZoneError as e:
        logger.error(f"Unknown timezone: {timezone}")
        raise ValueError(
            f"Unknown timezone: {timezone}. "
            f"Please use a valid timezone name like 'America/New_York' or 'Europe/London'"
        ) from e


def get_time(
    timezone: str,
) -> dict[str, Any]:
    """Get current time for a timezone.

    Args:
        timezone: The timezone name (e.g., 'America/New_York', 'Europe/London')

    Returns:
        Dictionary containing current time information including timezone,
        formatted time, date, and ISO format

    Raises:
        ValueError: If timezone is empty or invalid
    """
    if not timezone or not isinstance(timezone, str):
        logger.error(f"Invalid timezone parameter: {timezone}")
        raise ValueError("Timezone must be a non-empty string")

    timezone_normalized = timezone.strip()

    if not timezone_normalized:
        logger.error("Empty timezone after normalization")
        raise ValueError("Timezone cannot be empty")

    logger.info(f"Getting time for timezone: {timezone_normalized}")

    # Validate and get timezone
    tz = _validate_timezone(timezone_normalized)

    # Get current time in timezone
    current_time = datetime.now(tz)

    result = {
        "timezone": timezone_normalized,
        "time": current_time.strftime("%I:%M:%S %p"),
        "date": current_time.strftime("%Y-%m-%d"),
        "day_of_week": current_time.strftime("%A"),
        "iso_format": current_time.isoformat(),
    }

    logger.info(f"Time in {timezone_normalized}: {result['date']} {result['time']}")

    return result
