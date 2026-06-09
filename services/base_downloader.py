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
    
    @staticmethod
    def _classify_format(f: dict) -> tuple:
        """Classify a format's video/audio presence, handling None vs 'none' codecs.
        
        Twitter/X and some platforms report vcodec/acodec as None (absent) rather
        than 'none' for progressive HTTP streams. This method handles both cases
        by inferring from resolution/height/width when codec info is missing.
        """
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        
        # Determine has_video
        if vcodec == 'none':
            has_video = False
        elif vcodec is not None:
            has_video = True
        else:
            # vcodec missing — infer from resolution/height/width
            height = f.get('height')
            width = f.get('width')
            resolution = f.get('resolution', '')
            has_video = bool(
                height or width
                or (resolution and resolution != 'audio only')
            )
        
        # Determine has_audio
        if acodec == 'none':
            has_audio = False
        elif acodec is not None:
            has_audio = True
        else:
            # acodec missing — infer from context
            resolution = f.get('resolution', '')
            abr = f.get('abr')
            if resolution == 'audio only' or abr is not None:
                has_audio = True
            elif has_video:
                # Progressive streams with video but unknown audio — assume combined
                has_audio = True
            else:
                has_audio = False
        
        return has_video, has_audio
    
    def _format_filesize(self, size_bytes: Optional[int]) -> Optional[str]:
        """Convert bytes to human-readable format."""
        if size_bytes is None:
            return None
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
