"""
YouTube downloader service using yt-dlp.
Handles extraction and downloading of YouTube content.
"""

import asyncio
import logging
import os
import yt_dlp
from typing import Optional

logger = logging.getLogger(__name__)
from api.models import MediaInfo, FormatInfo, DownloadResponse
from services.base_downloader import BaseDownloader
from services.cookie_helper import get_ydl_opts_with_cookies, temp_cookies_file


class YouTubeDownloader(BaseDownloader):
    """YouTube downloader using yt-dlp."""
    
    platform_name = "youtube"
    
    def _get_format_label(self, f: dict) -> str:
        """Generate a human-readable format label."""
        parts = []
        
        has_video = f.get('vcodec', 'none') != 'none'
        has_audio = f.get('acodec', 'none') != 'none'
        
        if has_video:
            height = f.get('height')
            if height:
                parts.append(f"{height}p")
            fps = f.get('fps')
            if fps and fps > 30:
                parts.append(f"{int(fps)}fps")
        
        ext = f.get('ext', 'unknown')
        parts.append(ext.upper())
        
        if has_video and has_audio:
            parts.append("(Video+Audio)")
        elif has_video:
            parts.append("(Video Only)")
        elif has_audio:
            abr = f.get('abr')
            if abr:
                parts.insert(0, f"{int(abr)}kbps")
            parts.append("(Audio Only)")
        
        filesize = f.get('filesize') or f.get('filesize_approx')
        if filesize:
            size_str = self._format_filesize(filesize)
            if size_str:
                parts.append(f"~{size_str}")
        
        return " ".join(parts)
    
    async def extract_info(self, url: str, cookies: Optional[str] = None) -> MediaInfo:
        """Extract video information and available formats."""
        with temp_cookies_file(cookies) as temp_path:
            ydl_opts = get_ydl_opts_with_cookies({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'no_color': True,
                'socket_timeout': 30,
                'skip_download': True,
                # Avoid loading any local yt-dlp config files
                'ignoreconfig': True,
                # Explicitly set a highly permissive format selector to prevent
                # yt-dlp from defaulting to bestvideo*+bestaudio/best, which
                # fails with "Requested format is not available" if cipher
                # decryption is unavailable.
                'format': 'best/bestvideo/bestaudio',
            }, custom_cookies_file=temp_path)
            
            loop = asyncio.get_event_loop()
            
            def _extract(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            try:
                info = await loop.run_in_executor(None, _extract, ydl_opts)
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"[EXTRACT] First extraction attempt failed: {e}")
                if "cookie" in error_msg or "database is locked" in error_msg or "could not copy" in error_msg:
                    logger.info("[EXTRACT] Retrying extraction without cookies fallback...")
                    clean_opts = ydl_opts.copy()
                    clean_opts.pop('cookiesfrombrowser', None)
                    clean_opts.pop('cookiefile', None)
                    try:
                        info = await loop.run_in_executor(None, _extract, clean_opts)
                        logger.info("[EXTRACT] Extraction retry without cookies succeeded!")
                    except Exception as retry_e:
                        logger.error(f"[EXTRACT] Extraction retry also failed: {retry_e}")
                        # Raise the original error if it was a bot check / cookie error,
                        # as it is much more informative than the retry error.
                        raise ValueError(f"Cookie authentication failed: {e} (Fallback retry failed: {retry_e})")
                else:
                    raise
        
        if not info:
            raise ValueError("Could not extract video information")
        
        formats = []
        seen_labels = set()
        
        raw_formats = info.get('formats', [])
        
        # --- Separate video-only, audio-only, and combined streams ---
        video_only = []
        audio_only = []
        combined = []
        
        for f in raw_formats:
            ext = f.get('ext', 'unknown')
            has_video = f.get('vcodec', 'none') != 'none'
            has_audio = f.get('acodec', 'none') != 'none'
            url = f.get('url')
            
            if not url or ext in ('mhtml',):
                continue
            
            if has_video and has_audio:
                combined.append(f)
            elif has_video and not has_audio:
                video_only.append(f)
            elif has_audio and not has_video:
                audio_only.append(f)
        
        # --- Find the best audio stream for merging ---
        best_audio = None
        if audio_only:
            best_audio = max(
                audio_only,
                key=lambda a: (
                    1 if a.get('ext') in ('m4a', 'mp4') else 0,
                    a.get('abr') or a.get('tbr') or 0,
                )
            )

        # --- Create merged "Video+Audio" entries for video-only streams (Requires Backend) ---
        if best_audio:
            seen_heights = set()
            for vf in sorted(video_only, key=lambda x: (
                -(x.get('height') or 0),
                -(x.get('tbr') or 0),
            )):
                height = vf.get('height')
                if not height or height in seen_heights:
                    continue
                seen_heights.add(height)
                
                merged_id = f"{vf.get('format_id')}+{best_audio.get('format_id')}"
                ext = 'mp4'
                
                v_size = vf.get('filesize') or vf.get('filesize_approx') or 0
                a_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0
                total_size = (v_size + a_size) if (v_size and a_size) else None
                
                fps = vf.get('fps')
                parts = [f"{height}p"]
                if fps and fps > 30:
                    parts.append(f"{int(fps)}fps")
                parts.append("MP4")
                parts.append("(Backend Merge)")
                if total_size:
                    parts.append(f"~{self._format_filesize(total_size)}")
                
                label = " ".join(parts)
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                
                formats.append(FormatInfo(
                    format_id=merged_id,
                    extension=ext,
                    resolution=f"{vf.get('width', '?')}x{height}",
                    url=None,  # Must be downloaded via backend
                    filesize=total_size,
                    filesize_approx=total_size,
                    vcodec=vf.get('vcodec'),
                    acodec=best_audio.get('acodec'),
                    fps=fps,
                    tbr=(vf.get('tbr') or 0) + (best_audio.get('tbr') or 0) or None,
                    label=label,
                    has_video=True,
                    has_audio=True,
                ))
        
        # --- Add native combined (progressive) formats (Client Downloadable) ---
        for f in combined:
            label = self._get_format_label(f)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            height = f.get('height')
            formats.append(FormatInfo(
                format_id=f.get('format_id', ''),
                extension=f.get('ext', 'unknown'),
                resolution=f"{f.get('width', '?')}x{height}" if height else None,
                url=f.get('url'),
                filesize=f.get('filesize'),
                filesize_approx=f.get('filesize_approx'),
                vcodec=f.get('vcodec'),
                acodec=f.get('acodec'),
                fps=f.get('fps'),
                tbr=f.get('tbr'),
                label=label,
                has_video=True,
                has_audio=True,
            ))
        
        # --- Add audio-only formats ---
        for f in audio_only:
            label = self._get_format_label(f)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            formats.append(FormatInfo(
                format_id=f.get('format_id', ''),
                extension=f.get('ext', 'unknown'),
                resolution=None,
                url=f.get('url'),
                filesize=f.get('filesize'),
                filesize_approx=f.get('filesize_approx'),
                vcodec=f.get('vcodec'),
                acodec=f.get('acodec'),
                fps=None,
                tbr=f.get('tbr'),
                label=label,
                has_video=False,
                has_audio=True,
            ))
        
        # Sort: video+audio first (highest res on top), then audio-only
        formats.sort(key=lambda x: (
            not (x.has_video and x.has_audio),
            not x.has_video,
            -(int(x.resolution.split('x')[1]) if x.resolution and 'x' in x.resolution else 0),
        ))
        
        return MediaInfo(
            title=info.get('title', 'Unknown Title'),
            thumbnail=info.get('thumbnail'),
            duration=info.get('duration'),
            uploader=info.get('uploader'),
            description=info.get('description', '')[:500] if info.get('description') else None,
            platform="youtube",
            url=url,
            formats=formats,
        )
    
    async def download(self, url: str, format_id: str, output_dir: str, cookies: Optional[str] = None) -> DownloadResponse:
        """Download video in the specified format."""
        output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
        
        with temp_cookies_file(cookies) as temp_path:
            ydl_opts = get_ydl_opts_with_cookies({
                'format': format_id,
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'no_color': True,
                'merge_output_format': 'mp4',
            }, custom_cookies_file=temp_path)
            
            loop = asyncio.get_event_loop()
            
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(filename)
                    mp4_file = base + '.mp4'
                    if os.path.exists(mp4_file):
                        return os.path.basename(mp4_file)
                    return os.path.basename(filename)
            
            try:
                filename = await loop.run_in_executor(None, _download)
                return DownloadResponse(
                    success=True,
                    filename=filename,
                    message="Download completed successfully!"
                )
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"[DOWNLOAD] First download attempt failed: {e}")
                if "cookie" in error_msg or "database is locked" in error_msg or "could not copy" in error_msg:
                    logger.info("[DOWNLOAD] Retrying download without cookies fallback...")
                    clean_opts = ydl_opts.copy()
                    clean_opts.pop('cookiesfrombrowser', None)
                    clean_opts.pop('cookiefile', None)
                    def _download_no_cookies():
                        with yt_dlp.YoutubeDL(clean_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            filename = ydl.prepare_filename(info)
                            base, _ = os.path.splitext(filename)
                            mp4_file = base + '.mp4'
                            if os.path.exists(mp4_file):
                                return os.path.basename(mp4_file)
                            return os.path.basename(filename)
                    try:
                        filename = await loop.run_in_executor(None, _download_no_cookies)
                        logger.info("[DOWNLOAD] Download retry without cookies succeeded!")
                        return DownloadResponse(
                            success=True,
                            filename=filename,
                            message="Download completed successfully!"
                        )
                    except Exception as retry_e:
                        logger.error(f"[DOWNLOAD] Download retry also failed: {retry_e}")
                        return DownloadResponse(
                            success=False,
                            filename=None,
                            message=f"Download failed: Cookie authentication failed: {str(e)} (Fallback retry failed: {str(retry_e)})"
                        )
                return DownloadResponse(
                    success=False,
                    filename=None,
                    message=f"Download failed: {str(e)}"
                )
