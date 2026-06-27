"""
Volia - Universal Media Downloader
Main FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import threading
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from api.routes import router as api_router
from services.cookie_helper import auto_setup_cookies, set_cookie_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Volia API",
    description="Universal Media Downloader API",
    version="1.0.0"
)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure downloads directory exists
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Auto-setup browser cookies on startup."""
    def _setup():
        cookie_path = os.path.join(os.path.dirname(__file__), "cookies.txt")
        if os.path.exists(cookie_path):
            set_cookie_file(cookie_path)
            logger.info("✅ Using static cookies.txt file for authentication")
            return
            
        logger.info("🍪 Auto-detecting browser cookies...")
        result = auto_setup_cookies()
        if result['success']:
            logger.info(f"✅ Cookie setup: {result['message']}")
        else:
            logger.warning(f"⚠️  Cookie setup: {result['message']}")
    
    # Run in background thread so startup isn't blocked
    thread = threading.Thread(target=_setup, daemon=True)
    thread.start()


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Volia API"}
