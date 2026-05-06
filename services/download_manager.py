"""
Download manager service.
Routes requests to the appropriate platform-specific downloader.
Manages download history and caching.
"""

import json
import os
import time
from typing import Optional, List, Dict
from api.models import MediaInfo, DownloadResponse
from services.platform_detector import detect_platform, validate_url
from services.youtube_downloader import YouTubeDownloader
from services.social_downloader import SocialDownloader
from services.base_downloader import BaseDownloader


class DownloadManager:
    """Central manager that routes to platform-specific downloaders."""
    
    def __init__(self, downloads_dir: str = None):
        self.downloads_dir = downloads_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "downloads"
        )
        os.makedirs(self.downloads_dir, exist_ok=True)
        
        # History file
        self.history_file = os.path.join(self.downloads_dir, "history.json")
        
        # Initialize downloaders
        self._downloaders: Dict[str, BaseDownloader] = {
            "youtube": YouTubeDownloader(),
            "twitter": SocialDownloader("twitter"),
            "facebook": SocialDownloader("facebook"),
            "instagram": SocialDownloader("instagram"),
        }
    
    def _get_downloader(self, platform: str) -> BaseDownloader:
        """Get the appropriate downloader for a platform."""
        downloader = self._downloaders.get(platform)
        if not downloader:
            # Fall back to generic social downloader
            return SocialDownloader(platform)
        return downloader
    
    async def extract_info(self, url: str, platform: Optional[str] = None) -> MediaInfo:
        """
        Extract media info from URL.
        Auto-detects platform if not specified.
        """
        if not validate_url(url):
            raise ValueError("Invalid URL format. Please provide a valid URL.")
        
        # Auto-detect platform
        detected = detect_platform(url)
        platform = platform or detected
        
        if not platform:
            # Try generic extraction with yt-dlp
            platform = "unknown"
        
        downloader = self._get_downloader(platform)
        
        try:
            info = await downloader.extract_info(url)
            return info
        except Exception as e:
            raise ValueError(f"Failed to extract media info: {str(e)}")
    
    async def download(self, url: str, format_id: str, platform: Optional[str] = None) -> DownloadResponse:
        """
        Download media from URL in specified format.
        """
        if not validate_url(url):
            return DownloadResponse(
                success=False,
                filename=None,
                message="Invalid URL format."
            )
        
        detected = detect_platform(url)
        platform = platform or detected or "unknown"
        
        downloader = self._get_downloader(platform)
        
        result = await downloader.download(url, format_id, self.downloads_dir)
        
        # Save to history
        if result.success:
            self._save_to_history(url, platform, result.filename, format_id)
        
        return result
    
    def _save_to_history(self, url: str, platform: str, filename: str, format_id: str):
        """Save a download entry to history."""
        history = self.get_history()
        
        entry = {
            "url": url,
            "platform": platform,
            "filename": filename,
            "format_id": format_id,
            "timestamp": time.time(),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        history.insert(0, entry)
        
        # Keep last 50 entries
        history = history[:50]
        
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass
    
    def get_history(self) -> List[dict]:
        """Get download history."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    
    def clear_history(self):
        """Clear download history."""
        try:
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
        except Exception:
            pass


# Singleton instance
download_manager = DownloadManager()
