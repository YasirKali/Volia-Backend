"""
Generic social media downloader using yt-dlp.
Handles Twitter/X, Facebook, Instagram, and other platforms that yt-dlp supports.
"""

import asyncio
import os
import yt_dlp
from typing import Optional
from api.models import MediaInfo, FormatInfo, DownloadResponse
from services.base_downloader import BaseDownloader
from services.cookie_helper import get_ydl_opts_with_cookies


class SocialDownloader(BaseDownloader):
    """
    Generic social media downloader using yt-dlp.
    yt-dlp supports many social platforms natively.
    """
    
    def __init__(self, platform: str = "social"):
        self.platform_name = platform
    
    def _get_format_label(self, f: dict) -> str:
        """Generate a human-readable format label."""
        parts = []
        
        has_video = f.get('vcodec', 'none') != 'none'
        has_audio = f.get('acodec', 'none') != 'none'
        
        if has_video:
            height = f.get('height')
            width = f.get('width')
            if height:
                parts.append(f"{height}p")
            elif width:
                parts.append(f"{width}w")
        
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
    
    async def extract_info(self, url: str) -> MediaInfo:
        """Extract media information from the URL."""
        ydl_opts = get_ydl_opts_with_cookies({
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'no_color': True,
            'socket_timeout': 30,
        })
        
        loop = asyncio.get_event_loop()
        
        def _extract(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info = await loop.run_in_executor(None, _extract, ydl_opts)
        except Exception as e:
            error_msg = str(e).lower()
            if "cookie" in error_msg or "database is locked" in error_msg or "could not copy" in error_msg:
                # Retry without cookies
                clean_opts = ydl_opts.copy()
                clean_opts.pop('cookiesfrombrowser', None)
                clean_opts.pop('cookiefile', None)
                try:
                    info = await loop.run_in_executor(None, _extract, clean_opts)
                except Exception as retry_e:
                    raise retry_e
            else:
                raise
        
        if not info:
            raise ValueError("Could not extract media information")
        
        formats = []
        seen_labels = set()
        
        raw_formats = info.get('formats', [])
        
        # If no formats list, create a default one from the info
        if not raw_formats and info.get('url'):
            default_format = FormatInfo(
                format_id="best",
                extension=info.get('ext', 'mp4'),
                resolution=f"{info.get('width', '?')}x{info.get('height', '?')}" if info.get('height') else None,
                filesize=info.get('filesize'),
                filesize_approx=info.get('filesize_approx'),
                label=f"Best Quality {info.get('ext', 'MP4').upper()}",
                has_video=True,
                has_audio=True,
            )
            formats.append(default_format)
        else:
            # --- Separate video-only, audio-only, and combined streams ---
            video_only = []
            audio_only = []
            combined = []
            
            for f in raw_formats:
                ext = f.get('ext', 'unknown')
                has_video = f.get('vcodec', 'none') != 'none'
                has_audio = f.get('acodec', 'none') != 'none'
                
                if not has_video and not has_audio:
                    continue
                if ext in ('mhtml',):
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
                        1 if a.get('ext') in ('m4a', 'mp4', 'aac') else 0,
                        a.get('abr') or a.get('tbr') or 0,
                    )
                )
            
            # --- Create merged "Video+Audio" entries for video-only streams ---
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
                    ext = 'mp4'  # merge_output_format will be mp4
                    
                    # Estimate combined filesize
                    v_size = vf.get('filesize') or vf.get('filesize_approx') or 0
                    a_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0
                    total_size = (v_size + a_size) if (v_size and a_size) else None
                    
                    fps = vf.get('fps')
                    parts = [f"{height}p"]
                    if fps and fps > 30:
                        parts.append(f"{int(fps)}fps")
                    parts.append("MP4")
                    parts.append("(Video+Audio)")
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
            
            # --- Add native combined (progressive) formats ---
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
            -(int(x.resolution.split('x')[1]) if x.resolution and 'x' in x.resolution and x.resolution.split('x')[1].isdigit() else 0),
        ))
        
        return MediaInfo(
            title=info.get('title', 'Unknown Title'),
            thumbnail=info.get('thumbnail'),
            duration=info.get('duration'),
            uploader=info.get('uploader') or info.get('uploader_id'),
            description=info.get('description', '')[:500] if info.get('description') else None,
            platform=self.platform_name,
            url=url,
            formats=formats,
        )
    
    async def download(self, url: str, format_id: str, output_dir: str) -> DownloadResponse:
        """Download media in the specified format."""
        output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
        
        # Detect merged format (e.g. "137+140") and add merge options
        is_merged = '+' in format_id and format_id != 'best'
        
        ydl_opts = get_ydl_opts_with_cookies({
            'format': format_id if format_id != 'best' else 'best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'socket_timeout': 30,
        })
        
        # Add merge_output_format for merged streams so ffmpeg combines them
        if is_merged:
            ydl_opts['merge_output_format'] = 'mp4'
        
        loop = asyncio.get_event_loop()
        
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Check for merged mp4 file
                if is_merged:
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
            if "cookie" in error_msg or "database is locked" in error_msg or "could not copy" in error_msg:
                # Retry without cookies
                clean_opts = ydl_opts.copy()
                clean_opts.pop('cookiesfrombrowser', None)
                clean_opts.pop('cookiefile', None)
                def _download_no_cookies():
                    with yt_dlp.YoutubeDL(clean_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        if is_merged:
                            base, _ = os.path.splitext(filename)
                            mp4_file = base + '.mp4'
                            if os.path.exists(mp4_file):
                                return os.path.basename(mp4_file)
                        return os.path.basename(filename)
                try:
                    filename = await loop.run_in_executor(None, _download_no_cookies)
                    return DownloadResponse(
                        success=True,
                        filename=filename,
                        message="Download completed successfully!"
                    )
                except Exception as retry_e:
                    return DownloadResponse(
                        success=False,
                        filename=None,
                        message=f"Download failed: {str(retry_e)}"
                    )
            return DownloadResponse(
                success=False,
                filename=None,
                message=f"Download failed: {str(e)}"
            )
