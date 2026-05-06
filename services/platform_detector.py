"""
Platform detection service.
Auto-detects the media platform from a URL.
"""

import re
from typing import Optional


PLATFORM_PATTERNS = {
    "youtube": [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/",
        r"(?:https?://)?youtu\.be/",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/",
        r"(?:https?://)?(?:www\.)?youtube\.com/v/",
        r"(?:https?://)?(?:music\.)?youtube\.com/",
    ],
    "twitter": [
        r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/.+/status/",
        r"(?:https?://)?(?:www\.)?x\.com/.+/status/",
    ],
    "facebook": [
        r"(?:https?://)?(?:www\.)?facebook\.com/.+/videos/",
        r"(?:https?://)?(?:www\.)?facebook\.com/watch",
        r"(?:https?://)?(?:www\.)?facebook\.com/.+/posts/",
        r"(?:https?://)?(?:www\.)?fb\.watch/",
        r"(?:https?://)?(?:www\.)?facebook\.com/reel/",
    ],
    "instagram": [
        r"(?:https?://)?(?:www\.)?instagram\.com/p/",
        r"(?:https?://)?(?:www\.)?instagram\.com/reel/",
        r"(?:https?://)?(?:www\.)?instagram\.com/tv/",
        r"(?:https?://)?(?:www\.)?instagram\.com/stories/",
    ],
}

SUPPORTED_PLATFORMS = list(PLATFORM_PATTERNS.keys())


def detect_platform(url: str) -> Optional[str]:
    """
    Auto-detect the platform from a URL.
    Returns the platform name or None if unrecognized.
    """
    url = url.strip()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return None


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    return url_pattern.match(url) is not None


def is_platform_supported(platform: str) -> bool:
    """Check if a platform is supported."""
    return platform.lower() in SUPPORTED_PLATFORMS
