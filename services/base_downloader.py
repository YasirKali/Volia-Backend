"""
Base downloader interface.
All platform-specific downloaders inherit from this.
"""

from abc import ABC, abstractmethod
from typing import Optional
from api.models import MediaInfo, DownloadResponse


class BaseDownloader(ABC):
    """Abstract base class for all platform downloaders."""
    
    platform_name: str = "unknown"
    
    @abstractmethod
    async def extract_info(self, url: str) -> MediaInfo:
        """
        Extract media information and available formats from the URL.
        """
        pass
    
    @abstractmethod
    async def download(self, url: str, format_id: str, output_dir: str) -> DownloadResponse:
        """
        Download the media in the specified format.
        """
        pass
    
    def _format_filesize(self, size_bytes: Optional[int]) -> Optional[str]:
        """Convert bytes to human-readable format."""
        if size_bytes is None:
            return None
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
