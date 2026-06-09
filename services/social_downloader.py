"""
Generic social media downloader using yt-dlp.
Handles Twitter/X, Facebook, Instagram, and other platforms that yt-dlp supports.
"""

import asyncio
import os
import json
import shutil
import zipfile
import logging
import httpx
import yt_dlp
from typing import Optional
from api.models import MediaInfo, FormatInfo, DownloadResponse
from services.base_downloader import BaseDownloader
from services.cookie_helper import get_ydl_opts_with_cookies

logger = logging.getLogger(__name__)


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
        
        has_video, has_audio = self._classify_format(f)
        
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
    
    async def _extract_images(self, url: str) -> Optional[dict]:
        """Extract image details and metadata from the post using gallery-dl."""
        gallery_dl_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "venv", "Scripts", "gallery-dl.exe"
        )
        if not os.path.exists(gallery_dl_path):
            gallery_dl_path = shutil.which("gallery-dl") or "gallery-dl"
            
        cmd = [gallery_dl_path, "-j"]
        
        from services.cookie_helper import get_cookie_opts
        cookie_opts = get_cookie_opts()
        if 'cookiefile' in cookie_opts:
            cmd.extend(["--cookies", cookie_opts['cookiefile']])
        elif 'cookiesfrombrowser' in cookie_opts:
            browser_info = cookie_opts['cookiesfrombrowser']
            if isinstance(browser_info, (list, tuple)) and len(browser_info) > 1:
                cmd.extend(["--cookies-from-browser", f"{browser_info[0]}::{browser_info[1]}"])
            else:
                cmd.extend(["--cookies-from-browser", str(browser_info[0])])
        elif os.path.exists('K:/Volia/volia-backend/cookies.txt'):
            cmd.extend(["--cookies", "K:/Volia/volia-backend/cookies.txt"])
            
        cmd.append(url)
        
        loop = asyncio.get_event_loop()
        
        def run_proc():
            import subprocess
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
                return res.stdout, res.stderr, res.returncode
            except subprocess.TimeoutExpired as e:
                return e.stdout or "", e.stderr or "", -1
            except Exception as e:
                return "", str(e), -1
                
        stdout, stderr, code = await loop.run_in_executor(None, run_proc)
        
        image_urls = []
        title = None
        uploader = None
        description = None
        
        try:
            # First try parsing the entire stdout as a single JSON array/object
            data = json.loads(stdout.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, list) and len(item) >= 2:
                    status = item[0]
                    value = item[1]
                    if status == 3 and isinstance(value, str) and value.startswith("http"):
                        ext = os.path.splitext(value.split('?')[0].lower())[1]
                        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.jfif') or 'format=jpg' in value or 'format=png' in value or 'twimg.com/media/' in value:
                            image_urls.append(value)
                    
                    # Parse metadata
                    if len(item) >= 3:
                        meta = item[2]
                        if isinstance(meta, dict):
                            if not uploader:
                                uploader = meta.get('author') or meta.get('username') or meta.get('screen_name') or meta.get('user', {}).get('name')
                            if not description:
                                description = meta.get('description') or meta.get('content') or meta.get('text') or meta.get('caption')
                            if not title:
                                title = meta.get('title')
        except Exception as json_err:
            logger.debug(f"Failed to parse gallery-dl stdout as single JSON: {json_err}. Trying line-by-line fallback.")
            # Fallback to line-by-line parsing
            lines = stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, list) and len(item) >= 2:
                        status = item[0]
                        value = item[1]
                        if status == 3 and isinstance(value, str) and value.startswith("http"):
                            ext = os.path.splitext(value.split('?')[0].lower())[1]
                            if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.jfif') or 'format=jpg' in value or 'format=png' in value or 'twimg.com/media/' in value:
                                image_urls.append(value)
                        
                        # Parse metadata
                        if len(item) >= 3:
                            meta = item[2]
                            if isinstance(meta, dict):
                                if not uploader:
                                    uploader = meta.get('author') or meta.get('username') or meta.get('screen_name') or meta.get('user', {}).get('name')
                                if not description:
                                    description = meta.get('description') or meta.get('content') or meta.get('text') or meta.get('caption')
                                if not title:
                                    title = meta.get('title')
                except Exception:
                    continue
                
        if not image_urls:
            return None
            
        return {
            "image_urls": image_urls,
            "title": title,
            "uploader": uploader,
            "description": description
        }

    async def _extract_instagram_instaloader(self, url: str) -> Optional[dict]:
        """Extract details from Instagram using instaloader (without cookies)."""
        import re
        import instaloader
        
        # Extract shortcode
        match = re.search(r'/(?:p|reel|tv|reels)/([A-Za-z0-9_-]+)', url)
        if not match:
            return None
        shortcode = match.group(1)
        
        L = instaloader.Instaloader()
        loop = asyncio.get_event_loop()
        
        def _fetch():
            try:
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                
                media_items = []
                if post.typename == 'GraphSidecar':
                    for node in post.get_sidecar_nodes():
                        media_items.append({
                            'is_video': node.is_video,
                            'url': node.video_url if node.is_video else node.display_url,
                            'width': getattr(node, 'width', None),
                            'height': getattr(node, 'height', None)
                        })
                else:
                    post_width = None
                    post_height = None
                    if post.dimensions:
                        post_width = post.dimensions.width
                        post_height = post.dimensions.height
                    media_items.append({
                        'is_video': post.is_video,
                        'url': post.video_url if post.is_video else post.url,
                        'width': post_width,
                        'height': post_height
                    })
                
                return {
                    "media_items": media_items,
                    "title": post.caption or f"Instagram Post {shortcode}",
                    "uploader": post.owner_username,
                    "description": post.caption or "",
                    "thumbnail": post.url
                }
            except Exception as e:
                logger.warning(f"Instaloader failed to extract shortcode {shortcode}: {e}")
                return None
                
        return await loop.run_in_executor(None, _fetch)

    async def extract_info(self, url: str) -> MediaInfo:
        """Extract media information from the URL."""
        # Try instaloader for Instagram
        if self.platform_name == "instagram":
            try:
                insta_data = await self._extract_instagram_instaloader(url)
                if insta_data:
                    media_items = insta_data["media_items"]
                    formats = []
                    has_any_video = False
                    image_urls = []
                    
                    for idx, item in enumerate(media_items):
                        is_video = item['is_video']
                        item_url = item['url']
                        
                        if is_video:
                            has_any_video = True
                            formats.append(FormatInfo(
                                format_id=f"video_{idx}",
                                extension="mp4",
                                url=item_url,
                                label=f"Video {idx + 1} (MP4)",
                                has_video=True,
                                has_audio=True,
                            ))
                        else:
                            image_urls.append(item_url)
                            formats.append(FormatInfo(
                                format_id=f"image_{idx}",
                                extension="jpg",
                                url=item_url,
                                label=f"Image {idx + 1} (JPG)",
                                has_video=False,
                                has_audio=False,
                            ))
                    
                    # Add ZIP options if there are multiple items
                    if len(media_items) > 1:
                        if len(image_urls) == len(media_items):
                            # All are images
                            formats.append(FormatInfo(
                                format_id="all_images",
                                extension="zip",
                                url=None,
                                label="All Images (ZIP)",
                                has_video=False,
                                has_audio=False,
                            ))
                        else:
                            # Mixed or all videos
                            formats.append(FormatInfo(
                                format_id="all_media",
                                extension="zip",
                                url=None,
                                label="All Media (ZIP)",
                                has_video=True,
                                has_audio=True,
                            ))
                    
                    title = insta_data.get("title")
                    if not title:
                        parts = url.rstrip('/').split('/')
                        title = f"Instagram Post {parts[-1].split('?')[0]}"
                        
                    uploader = insta_data.get("uploader")
                    description = insta_data.get("description")
                    if not description:
                        description = f"Contains {len(media_items)} item(s)."
                        
                    # Set is_image to True only if there are NO videos
                    is_image = not has_any_video
                    
                    return MediaInfo(
                        title=title,
                        thumbnail=insta_data.get("thumbnail") or (image_urls[0] if image_urls else None),
                        duration=None,
                        uploader=uploader,
                        description=description,
                        platform=self.platform_name,
                        url=url,
                        formats=formats,
                        is_image=is_image
                    )
            except Exception as e:
                logger.warning(f"Instagram instaloader extraction failed: {e}. Falling back to default.")

        # Try image extraction first for Twitter/Instagram (fallback)
        if self.platform_name in ("twitter", "instagram"):
            try:
                img_data = await self._extract_images(url)
                if img_data:
                    image_urls = img_data["image_urls"]
                    formats = []
                    for idx, img_url in enumerate(image_urls):
                        formats.append(FormatInfo(
                            format_id=f"image_{idx}",
                            extension="jpg",
                            url=img_url,
                            label=f"Image {idx + 1} (JPG)",
                            has_video=False,
                            has_audio=False,
                        ))
                    if len(image_urls) > 1:
                        formats.append(FormatInfo(
                            format_id="all_images",
                            extension="zip",
                            url=None,
                            label="All Images (ZIP)",
                            has_video=False,
                            has_audio=False,
                        ))
                    
                    title = img_data.get("title")
                    if not title:
                        parts = url.rstrip('/').split('/')
                        title = f"{self.platform_name.capitalize()} Post {parts[-1].split('?')[0]}"
                        
                    uploader = img_data.get("uploader")
                    description = img_data.get("description")
                    if not description:
                        description = f"Contains {len(image_urls)} image(s)."
                        
                    return MediaInfo(
                        title=title,
                        thumbnail=image_urls[0],
                        duration=None,
                        uploader=uploader,
                        description=description,
                        platform=self.platform_name,
                        url=url,
                        formats=formats,
                        is_image=True
                    )
            except Exception as e:
                logger.warning(f"Image extraction failed, falling back to yt-dlp: {e}")

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
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            # Catch known authentication block patterns for image downloads when not logged in
            if self.platform_name == "twitter" and any(pattern in error_msg_lower for pattern in ("no video could be found", "guest token", "could not query", "querying api", "rate limit")):
                raise ValueError(
                    "To extract/download media from X/Twitter, Volia requires valid browser cookies. "
                    "Please log in to X/Twitter in your web browser, then go to Settings and click "
                    "'Sync Browser Cookies' in Volia Settings."
                )
            elif self.platform_name == "instagram" and ("empty media response" in error_msg_lower or "login" in error_msg_lower):
                raise ValueError(
                    "This Instagram post requires authentication. Please log in to Instagram in your "
                    "browser, then go to Settings and click 'Sync Browser Cookies' in Volia Settings."
                )
            
            if "cookie" in error_msg_lower or "database is locked" in error_msg_lower or "could not copy" in error_msg_lower:
                # Retry without cookies
                clean_opts = ydl_opts.copy()
                clean_opts.pop('cookiesfrombrowser', None)
                clean_opts.pop('cookiefile', None)
                try:
                    info = await loop.run_in_executor(None, _extract, clean_opts)
                except Exception as retry_e:
                    retry_msg_lower = str(retry_e).lower()
                    if self.platform_name == "twitter" and any(pattern in retry_msg_lower for pattern in ("no video could be found", "guest token", "could not query", "querying api", "rate limit")):
                        raise ValueError(
                            "To extract/download media from X/Twitter, Volia requires valid browser cookies. "
                            "Please log in to X/Twitter in your web browser, then go to Settings and click "
                            "'Sync Browser Cookies' in Volia Settings."
                        )
                    elif self.platform_name == "instagram" and ("empty media response" in retry_msg_lower or "login" in retry_msg_lower):
                        raise ValueError(
                            "This Instagram post requires authentication. Please log in to Instagram in your "
                            "browser, then go to Settings and click 'Sync Browser Cookies' in Volia Settings."
                        )
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
                has_video, has_audio = self._classify_format(f)
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
                        1 if a.get('ext') in ('m4a', 'mp4', 'aac') else 0,
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
        # Check if we can download Instagram via instaloader
        if self.platform_name == "instagram" and (
            format_id.startswith("image_") or 
            format_id.startswith("video_") or 
            format_id in ("all_images", "all_media", "best")
        ):
            try:
                insta_data = await self._extract_instagram_instaloader(url)
                if not insta_data or not insta_data.get("media_items"):
                    return DownloadResponse(success=False, filename=None, message="No media found to download.")
                
                media_items = insta_data["media_items"]
                parts = url.rstrip('/').split('/')
                post_id = parts[-1].split('?')[0]
                base_name = f"instagram_{post_id}"
                
                async def download_file_bytes(item_url: str) -> bytes:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://www.instagram.com/"
                    }
                    async with httpx.AsyncClient(timeout=30) as client:
                        r = await client.get(item_url, headers=headers, follow_redirects=True)
                        r.raise_for_status()
                        return r.content

                if format_id in ("all_images", "all_media"):
                    zip_filename = f"{base_name}_media.zip" if format_id == "all_media" else f"{base_name}_images.zip"
                    zip_path = os.path.join(output_dir, zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for idx, item in enumerate(media_items):
                            is_vid = item['is_video']
                            item_url = item['url']
                            content = await download_file_bytes(item_url)
                            
                            if is_vid:
                                ext = '.mp4'
                                item_filename = f"video_{idx + 1}{ext}"
                            else:
                                ext = os.path.splitext(item_url.split('?')[0].lower())[1]
                                if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                                    ext = '.jpg'
                                item_filename = f"image_{idx + 1}{ext}"
                                
                            zip_file.writestr(item_filename, content)
                            
                    return DownloadResponse(
                        success=True,
                        filename=zip_filename,
                        message=f"Successfully downloaded {len(media_items)} items as a ZIP file!"
                    )
                else:
                    # Single item download
                    idx = 0
                    if format_id != "best":
                        try:
                            # format_id is like "image_3" or "video_1"
                            idx = int(format_id.split('_')[1])
                        except (IndexError, ValueError):
                            return DownloadResponse(success=False, filename=None, message="Invalid format index.")
                    
                    if idx >= len(media_items):
                        return DownloadResponse(success=False, filename=None, message="Media index out of range.")
                        
                    item = media_items[idx]
                    is_vid = item['is_video']
                    item_url = item['url']
                    
                    content = await download_file_bytes(item_url)
                    
                    if is_vid:
                        ext = '.mp4'
                        filename = f"{base_name}_{idx + 1}{ext}"
                    else:
                        ext = os.path.splitext(item_url.split('?')[0].lower())[1]
                        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                            ext = '.jpg'
                        filename = f"{base_name}_{idx + 1}{ext}"
                        
                    file_path = os.path.join(output_dir, filename)
                    with open(file_path, 'wb') as f:
                        f.write(content)
                        
                    return DownloadResponse(
                        success=True,
                        filename=filename,
                        message="Successfully downloaded media item!"
                    )
            except Exception as e:
                logger.error(f"Instagram instaloader download failed: {e}. Falling back to default.")

        if format_id.startswith("image_") or format_id == "all_images":
            try:
                img_data = await self._extract_images(url)
                if not img_data or not img_data.get("image_urls"):
                    return DownloadResponse(success=False, filename=None, message="No images found to download.")
                
                image_urls = img_data["image_urls"]
                
                parts = url.rstrip('/').split('/')
                post_id = parts[-1].split('?')[0]
                base_name = f"{self.platform_name}_{post_id}"
                
                async def download_file_bytes(img_url: str) -> bytes:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://twitter.com/" if "twitter" in img_url or "twimg" in img_url else "https://www.instagram.com/"
                    }
                    async with httpx.AsyncClient(timeout=30) as client:
                        r = await client.get(img_url, headers=headers, follow_redirects=True)
                        r.raise_for_status()
                        return r.content

                if format_id == "all_images":
                    zip_filename = f"{base_name}_images.zip"
                    zip_path = os.path.join(output_dir, zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for idx, img_url in enumerate(image_urls):
                            content = await download_file_bytes(img_url)
                            ext = os.path.splitext(img_url.split('?')[0].lower())[1]
                            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                                ext = '.jpg'
                            img_filename = f"image_{idx + 1}{ext}"
                            zip_file.writestr(img_filename, content)
                            
                    return DownloadResponse(
                        success=True,
                        filename=zip_filename,
                        message=f"Successfully downloaded {len(image_urls)} images as a ZIP file!"
                    )
                else:
                    try:
                        idx = int(format_id.split('_')[1])
                        img_url = image_urls[idx]
                    except (IndexError, ValueError):
                        return DownloadResponse(success=False, filename=None, message="Invalid image index.")
                        
                    content = await download_file_bytes(img_url)
                    ext = os.path.splitext(img_url.split('?')[0].lower())[1]
                    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                        ext = '.jpg'
                    img_filename = f"{base_name}_{idx + 1}{ext}"
                    img_path = os.path.join(output_dir, img_filename)
                    
                    with open(img_path, 'wb') as f:
                        f.write(content)
                        
                    return DownloadResponse(
                        success=True,
                        filename=img_filename,
                        message="Successfully downloaded image!"
                    )
            except Exception as e:
                return DownloadResponse(success=False, filename=None, message=f"Image download failed: {str(e)}")

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
