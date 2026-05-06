"""
Volia - Universal Media Downloader
Main FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
import threading

from api.routes import router as api_router
from services.cookie_helper import auto_setup_cookies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Volia API",
    description="Universal Media Downloader API",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
