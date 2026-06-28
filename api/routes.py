"""
API Routes for Volia.
Handles extraction, download, history, and file serving.
"""

import os
import json
import subprocess
import sys
import asyncio
import threading
import traceback
import glob
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from api.models import ExtractRequest, DownloadRequest, MediaInfo, DownloadResponse, ErrorResponse
from services.download_manager import download_manager
from services.platform_detector import detect_platform, SUPPORTED_PLATFORMS
from services.cookie_helper import (
    set_preferred_browser, get_preferred_browser, get_cookie_file,
    auto_setup_cookies, export_cookies_from_browser, SUPPORTED_BROWSERS,
    get_cookie_opts, save_user_cookies, clear_user_cookies, analyze_cookie_file
)

router = APIRouter()


@router.get("/platforms")
async def get_platforms():
    """Get list of supported platforms."""
    platform_info = {
        "youtube": {
            "name": "YouTube",
            "icon": "youtube",
            "color": "#FF0000",
            "description": "Download videos/image, shorts, and audio from YouTube"
        },
        "twitter": {
            "name": "X (Twitter)",
            "icon": "twitter",
            "color": "#000000",
            "description": "Download videos/image from X/Twitter"
        },
        "facebook": {
            "name": "Facebook",
            "icon": "facebook",
            "color": "#1877F2",
            "description": "Download videos/image and reels from Facebook"
        },
        "instagram": {
            "name": "Instagram",
            "icon": "instagram",
            "color": "#E4405F",
            "description": "Download posts, reels, and stories from Instagram"
        },
        "spotify": {
            "name": "Spotify",
            "icon": "spotify",
            "color": "#1DB954",
            "description": "Download playlist, album, and track audio from Spotify"
        },
    }
    return {"platforms": platform_info}


@router.post("/detect")
async def detect_platform_endpoint(request: ExtractRequest):
    """Auto-detect platform from URL."""
    platform = detect_platform(request.url)
    return {
        "platform": platform,
        "supported": platform is not None,
        "url": request.url
    }


@router.post("/extract", response_model=MediaInfo)
async def extract_media_info(request: ExtractRequest):
    """
    Extract media information and available formats from a URL.
    Auto-detects platform if not specified.
    """
    try:
        has_cookies = request.cookies is not None and len(request.cookies.strip()) > 0
        cookie_len = len(request.cookies) if request.cookies else 0
        logger.info(f"[EXTRACT] url={request.url}, platform={request.platform}, has_cookies={has_cookies}, cookie_text_len={cookie_len}")
        info = await download_manager.extract_info(request.url, request.platform, request.cookies)
        return info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/download", response_model=DownloadResponse)
async def download_media(request: DownloadRequest):
    """
    Download media in the specified format.
    """
    try:
        result = await download_manager.download(
            request.url, 
            request.format_id,
            request.platform,
            request.cookies
        )
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


import logging

logger = logging.getLogger(__name__)

async def run_yt_dlp_stream(cmd: list):
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    def run_in_thread():
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            for line in process.stdout:
                line = line.strip()
                print(f"[DEBUG] stdout: {line}")
                if '|' in line:
                    parts = line.split('|')
                    data = {
                        'percent': parts[0].strip(),
                        'speed': parts[1].strip() if len(parts) > 1 else '',
                        'eta': parts[2].strip() if len(parts) > 2 else '',
                        'status': 'downloading'
                    }
                    loop.call_soon_threadsafe(queue.put_nowait, 
                        f"data: {json.dumps(data)}\n\n")

            process.wait()
            stderr_output = process.stderr.read()
            print(f"[DEBUG] stderr: {stderr_output}")
            print(f"[DEBUG] exit code: {process.returncode}")

            if process.returncode != 0:
                loop.call_soon_threadsafe(queue.put_nowait,
                    f"data: {json.dumps({'status': 'error', 'message': stderr_output})}\n\n")
            else:
                # Find the downloaded file
                downloads_dir = download_manager.downloads_dir
                files = glob.glob(os.path.join(downloads_dir, '*'))
                # Exclude history.json or other non-media files if necessary, 
                # but following user request for latest file.
                latest_file = max(files, key=os.path.getctime) if files else None
                filename = os.path.basename(latest_file) if latest_file else None
                
                loop.call_soon_threadsafe(queue.put_nowait,
                    f"data: {json.dumps({'status': 'complete', 'percent': '100%', 'filename': filename})}\n\n")

        except Exception as e:
            import traceback
            loop.call_soon_threadsafe(queue.put_nowait,
                f"data: {json.dumps({'status': 'error', 'message': traceback.format_exc()})}\n\n")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item




def get_format_for_url(url: str, quality: str = None) -> str:
    twitter_domains = ['x.com', 'twitter.com', 't.co']
    instagram_domains = ['instagram.com', 'instagr.am']
    facebook_domains = ['facebook.com', 'fb.com', 'fb.watch']
    
    is_twitter = any(d in url for d in twitter_domains)
    is_instagram = any(d in url for d in instagram_domains)
    is_facebook = any(d in url for d in facebook_domains)
    
    # These platforms only have merged formats, no separate video+audio
    if is_twitter or is_instagram or is_facebook:
        return 'best[ext=mp4]/best'
    
    # YouTube - use quality-based format
    quality_map = {
        '4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
        '2k': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]/best',
        '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best',
        '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best',
        'max': 'bestvideo+bestaudio/best',
    }
    
    # Fallback/Default for YouTube
    return quality_map.get(quality, 'bestvideo[height<=1080]+bestaudio/best')


def build_yt_dlp_command(url: str, mode: str, quality: str, format: str) -> list:
    base_cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--newline',
        '--progress',
        '--progress-template', 
        '%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(progress.filename)s',
        '--restrict-filenames',
        '--no-playlist',
        '-o', os.path.join(download_manager.downloads_dir, "%(title)s.%(ext)s"),
    ]

    # Add cookies if available
    cookie_opts = get_cookie_opts()
    if 'cookiefile' in cookie_opts:
        base_cmd.extend(["--cookies", cookie_opts['cookiefile']])
    elif 'cookiesfrombrowser' in cookie_opts:
        browser_info = cookie_opts['cookiesfrombrowser']
        if isinstance(browser_info, (list, tuple)) and len(browser_info) > 1:
            base_cmd.extend(["--cookies-from-browser", f"{browser_info[0]}::{browser_info[1]}"])
        else:
            base_cmd.extend(["--cookies-from-browser", str(browser_info[0])])
    elif os.path.exists('K:/Volia/volia-backend/cookies.txt'):
        base_cmd += ['--cookies', 'K:/Volia/volia-backend/cookies.txt']

    # Anti-bot extractor args (must match get_ydl_opts_with_cookies)
    base_cmd.extend(['--extractor-args', 'youtube:player-client=default,-android_sdkless'])

    if mode == 'audio':
        base_cmd += [
            '--extract-audio',          # extract audio only
            '--audio-format', format or 'mp3',   # convert to mp3/m4a/wav etc
            '--audio-quality', '0',     # best quality
            '-f', 'bestaudio/best',
        ]
    elif mode == 'video':
        # video only no audio
        base_cmd += ['-f', f'{format}/bestvideo/best' if format else 'bestvideo/best']
    else:
        # video + audio (default)
        auto_format = get_format_for_url(url, quality)
        base_cmd += ['-f', f'{format}/{auto_format}' if format else auto_format]

    base_cmd.append(url)
    return base_cmd


@router.get("/download-progress")
async def download_progress(
    url: str = Query(...),
    mode: Optional[str] = Query('both'),
    quality: Optional[str] = Query(None),
    format: Optional[str] = Query(None)
):
    """
    Stream download progress using Server-Sent Events (SSE).
    """
    print(f"[DEBUG] Received request for URL: {url}")
    print(f"[DEBUG] Mode: {mode}, Quality: {quality}, Format: {format}")

    # Check if the post is an image post
    try:
        info = await download_manager.extract_info(url)
        if info.platform == "spotify":
            format_id = format or ("all_songs" if any(f.format_id == "all_songs" for f in info.formats) else "mp3")
            spotify_downloader = download_manager._get_downloader("spotify")
            return StreamingResponse(
                spotify_downloader.download_stream(url, format_id, download_manager.downloads_dir),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        elif getattr(info, 'is_image', False):
            # Stream image download progress
            # Downloader formats contain either all_images or individual images
            format_id = format or ("all_images" if any(f.format_id == "all_images" for f in info.formats) else "image_0")
            
            async def run_image_stream():
                try:
                    # Starting state
                    yield f"data: {json.dumps({'percent': '10%', 'speed': 'N/A', 'eta': 'N/A', 'status': 'downloading'})}\n\n"
                    await asyncio.sleep(0.5)
                    
                    yield f"data: {json.dumps({'percent': '60%', 'speed': 'N/A', 'eta': 'N/A', 'status': 'downloading'})}\n\n"
                    
                    # Run download
                    result = await download_manager.download(url, format_id)
                    
                    if result.success:
                        yield f"data: {json.dumps({'status': 'complete', 'percent': '100%', 'filename': result.filename})}\n\n"
                    else:
                        yield f"data: {json.dumps({'status': 'error', 'message': result.message})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            
            return StreamingResponse(
                run_image_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
    except Exception as e:
        print(f"[DEBUG] Image detection failed/skipped: {e}")

    # Build the yt-dlp command using the new helper (fallback for video/other posts)
    cmd = build_yt_dlp_command(url, mode, quality, format)
    print(f"[DEBUG] Running command: {' '.join(cmd)}")

    return StreamingResponse(
        run_yt_dlp_stream(cmd),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/download-file/{filename}")
async def download_file(filename: str, background_tasks: BackgroundTasks):
    """Serve a downloaded file and delete it after transfer."""
    import urllib.parse
    
    safe_filename = urllib.parse.unquote(filename)
    file_path = os.path.join(download_manager.downloads_dir, safe_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Add background task to remove file after serving to save disk space
    background_tasks.add_task(os.remove, file_path)
    
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type='application/octet-stream',
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
    )


@router.get("/history")
async def get_history():
    """Get download history."""
    history = download_manager.get_history()
    return {"history": history}


@router.delete("/history")
async def clear_history():
    """Clear download history."""
    download_manager.clear_history()
    return {"success": True, "message": "History cleared"}


# ─── Cookie / Browser Settings ────────────────────────────────────────

class BrowserSettingRequest(BaseModel):
    browser: str


@router.get("/settings/cookies")
async def get_cookie_settings():
    """Get current cookie/browser settings."""
    cookie_path = get_cookie_file()
    analysis = None
    if cookie_path:
        analysis = analyze_cookie_file(cookie_path)
    return {
        "preferred_browser": get_preferred_browser(),
        "cookie_file": cookie_path,
        "supported_browsers": SUPPORTED_BROWSERS,
        "cookie_analysis": analysis,
    }


@router.post("/settings/cookies")
async def set_cookie_browser(request: BrowserSettingRequest):
    """Set the preferred browser for cookie extraction."""
    try:
        set_preferred_browser(request.browser)
        return {
            "success": True,
            "browser": request.browser,
            "message": f"Browser set to {request.browser}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/cookies/setup")
async def setup_cookies():
    """
    Auto-detect and set up the best available browser cookies.
    Tries each browser in order and exports cookies to a file.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, auto_setup_cookies)
    return result


@router.post("/settings/cookies/export")
async def export_cookies(request: BrowserSettingRequest):
    """Export cookies from a specific browser to a file."""
    loop = asyncio.get_event_loop()
    
    def _export():
        return export_cookies_from_browser(request.browser)
    
    cookie_file = await loop.run_in_executor(None, _export)
    
    if cookie_file:
        return {
            "success": True,
            "browser": request.browser,
            "cookie_file": cookie_file,
            "message": f"Cookies exported from {request.browser}",
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to export cookies from {request.browser}. "
                   f"Make sure {request.browser} is installed and you are logged into the sites you want to download from."
        )


class CookieUploadRequest(BaseModel):
    cookies_text: str


@router.post("/settings/cookies/upload")
async def upload_user_cookies(request: CookieUploadRequest):
    """Upload custom cookies.txt content."""
    try:
        path = save_user_cookies(request.cookies_text)
        analysis = analyze_cookie_file(path)
        return {
            "success": True,
            "cookie_file": path,
            "cookie_analysis": analysis,
            "message": f"Cookies uploaded and applied successfully! {analysis.get('message', '')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save cookies: {str(e)}")


@router.delete("/settings/cookies/upload")
async def delete_user_cookies():
    """Delete uploaded custom cookies."""
    clear_user_cookies()
    return {
        "success": True,
        "cookie_file": None,
        "cookie_analysis": None,
        "message": "Custom cookies cleared successfully!"
    }


@router.get("/debug")
async def debug_info():
    """Diagnostic endpoint to inspect the deployed environment."""
    import traceback
    try:
        import shutil
        import sys
        import yt_dlp
        
        # Check JS runtime
        js_runtimes = ["node", "deno", "bun"]
        found_runtime = None
        for rt in js_runtimes:
            if shutil.which(rt):
                found_runtime = rt
                break
                
        # Check cookie files
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        user_cookies_path = os.path.join(backend_dir, "user_cookies.txt")
        static_cookies_path = os.path.join(backend_dir, "cookies.txt")
        
        user_cookies_exists = os.path.exists(user_cookies_path)
        static_cookies_exists = os.path.exists(static_cookies_path)
        
        # Safe version retrieval
        yt_version = "unknown"
        try:
            yt_version = yt_dlp.__version__
        except Exception:
            try:
                from yt_dlp.version import __version__ as v
                yt_version = v
            except Exception:
                pass
        
        return {
            "status": "success",
            "python_version": sys.version,
            "yt_dlp_version": yt_version,
            "js_runtime_found": found_runtime,
            "user_cookies_exists": user_cookies_exists,
            "static_cookies_exists": static_cookies_exists,
            "current_directory": os.getcwd(),
            "env_path": os.environ.get("PATH", ""),
            "code_version": "v1.2-safe-debug"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


