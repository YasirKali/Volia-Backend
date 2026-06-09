"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional, List


class ExtractRequest(BaseModel):
    url: str
    platform: Optional[str] = None  # auto-detect if not provided


class FormatInfo(BaseModel):
    format_id: str
    extension: str
    resolution: Optional[str] = None
    url: Optional[str] = None  # Direct download URL
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    fps: Optional[float] = None
    tbr: Optional[float] = None  # total bitrate
    label: str  # human-readable label like "1080p MP4"
    has_video: bool = True
    has_audio: bool = True


class MediaInfo(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None  # seconds
    uploader: Optional[str] = None
    description: Optional[str] = None
    platform: str
    url: str
    formats: List[FormatInfo] = []
    is_image: bool = False


class DownloadRequest(BaseModel):
    url: str
    format_id: str
    platform: Optional[str] = None


class DownloadResponse(BaseModel):
    success: bool
    filename: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
