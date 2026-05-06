"""
API Routes for Volia.
Handles extraction, download, history, and file serving.
"""

import os
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from api.models import ExtractRequest, DownloadRequest, MediaInfo, DownloadResponse, ErrorResponse
from services.download_manager import download_manager
from services.platform_detector import detect_platform, SUPPORTED_PLATFORMS
from services.cookie_helper import (
    set_preferred_browser, get_preferred_browser, get_cookie_file,
    auto_setup_cookies, export_cookies_from_browser, SUPPORTED_BROWSERS,
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
            "description": "Download videos, shorts, and audio from YouTube"
        },
        "twitter": {
            "name": "X (Twitter)",
            "icon": "twitter",
            "color": "#000000",
            "description": "Download videos and images from X/Twitter"
        },
        "facebook": {
            "name": "Facebook",
            "icon": "facebook",
            "color": "#1877F2",
            "description": "Download videos and reels from Facebook"
        },
        "instagram": {
            "name": "Instagram",
            "icon": "instagram",
            "color": "#E4405F",
            "description": "Download posts, reels, and stories from Instagram"
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
        info = await download_manager.extract_info(request.url, request.platform)
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
            request.platform
        )
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/download/file/{filename}")
async def serve_download(filename: str):
    """Serve a downloaded file to the client."""
    filepath = os.path.join(download_manager.downloads_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        filename=filename,
        media_type='application/octet-stream'
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
    return {
        "preferred_browser": get_preferred_browser(),
        "cookie_file": get_cookie_file(),
        "supported_browsers": SUPPORTED_BROWSERS,
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

