"""
Cookie helper for yt-dlp browser cookie extraction.
Handles the common issue of browser cookie databases being locked
by copying the database to a temp location before reading.
"""

import os
import sys
import shutil
import tempfile
import sqlite3
import logging
from typing import Optional, Tuple, List
from http.cookiejar import MozillaCookieJar
import time

logger = logging.getLogger(__name__)

# Browsers to try, in order of preference
SUPPORTED_BROWSERS = ['edge', 'chrome', 'firefox', 'brave', 'opera', 'chromium']

# Default browser preference (can be changed via settings)
_preferred_browser: Optional[str] = None
_cookie_file_path: Optional[str] = None


def is_server_environment() -> bool:
    """Check if running in a headless server or container environment (e.g. Railway, Docker)."""
    if sys.platform != 'win32' and not os.getenv('DISPLAY') and not os.getenv('WAYLAND_DISPLAY'):
        return True
    if os.getenv('RAILWAY_STATIC_URL') or os.getenv('PORT') or os.getenv('DOCKER_ENV'):
        return True
    return False


def set_preferred_browser(browser: str):
    """Set the preferred browser for cookie extraction."""
    global _preferred_browser
    if browser.lower() in SUPPORTED_BROWSERS:
        _preferred_browser = browser.lower()
    else:
        raise ValueError(f"Unsupported browser: {browser}. Supported: {SUPPORTED_BROWSERS}")


def set_cookie_file(path: str):
    """Set a manual cookie file path (Netscape format)."""
    global _cookie_file_path
    if os.path.exists(path):
        _cookie_file_path = path
    else:
        raise FileNotFoundError(f"Cookie file not found: {path}")


def get_preferred_browser() -> Optional[str]:
    """Get the current preferred browser."""
    return _preferred_browser


def get_cookie_file() -> Optional[str]:
    """Get the current cookie file path."""
    return _cookie_file_path


def _get_browser_order() -> List[str]:
    """Get the browser order, with preferred browser first."""
    if _preferred_browser:
        order = [_preferred_browser]
        for b in SUPPORTED_BROWSERS:
            if b != _preferred_browser:
                order.append(b)
        return order
    return SUPPORTED_BROWSERS.copy()


def get_cookie_opts() -> dict:
    """
    Get the best yt-dlp cookie options.
    
    Tries multiple strategies:
    1. If a manual cookie file is set, use that
    2. Try cookiesfrombrowser with each browser in order
    
    Returns a dict of yt-dlp options for cookies.
    """
    # Strategy 1: Manual cookie file
    if _cookie_file_path and os.path.exists(_cookie_file_path):
        logger.info(f"Using manual cookie file: {_cookie_file_path}")
        return {'cookiefile': _cookie_file_path}
    
    # In headless server environments (like Railway), browser cookies are not available.
    # Return empty options immediately to avoid failures or logs.
    if is_server_environment():
        logger.info("Running in a server environment. Skipping browser cookie check.")
        return {}
    
    # Strategy 2: Browser cookies
    browsers = _get_browser_order()
    
    for browser in browsers:
        try:
            # Test if we can access this browser's cookies
            opts = _try_browser_cookies(browser)
            if opts:
                logger.info(f"Using cookies from browser: {browser}")
                return opts
        except Exception as e:
            logger.debug(f"Failed to get cookies from {browser}: {e}")
            continue
    
    # Strategy 3: No cookies (will fail for age-restricted content)
    logger.warning("No browser cookies available. Some content may not be accessible.")
    return {}


def _try_browser_cookies(browser: str) -> Optional[dict]:
    """
    Try to get cookie options for a specific browser.
    On non-Windows (e.g. Railway/Docker Linux), no desktop browsers
    are available, so return None to skip browser cookie extraction.
    """
    if browser in ('edge', 'chrome', 'brave', 'opera', 'chromium'):
        profile_path = _copy_chromium_cookies(browser)
        if profile_path:
            # yt-dlp's cookiesfrombrowser accepts (browser, profile_path)
            return {'cookiesfrombrowser': (browser, profile_path)}
    
    # On non-Windows (headless servers), there are no desktop browsers
    # installed, so don't attempt cookiesfrombrowser at all.
    if sys.platform != 'win32':
        return None
    
    # Fallback for Firefox or local Windows dev if copy failed
    return {'cookiesfrombrowser': (browser,)}


def _get_chromium_paths(browser: str) -> Tuple[Optional[str], Optional[str]]:
    """Get the cookie database and Local State paths for a Chromium-based browser."""
    if sys.platform != 'win32':
        return None, None
    
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    app_data = os.environ.get('APPDATA', '')
    
    # Base paths for User Data
    user_data_paths = {
        'edge': os.path.join(local_app_data, 'Microsoft', 'Edge', 'User Data'),
        'chrome': os.path.join(local_app_data, 'Google', 'Chrome', 'User Data'),
        'brave': os.path.join(local_app_data, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'opera': os.path.join(app_data, 'Opera Software', 'Opera Stable'),
        'chromium': os.path.join(local_app_data, 'Chromium', 'User Data'),
    }
    
    base_path = user_data_paths.get(browser)
    if not base_path or not os.path.exists(base_path):
        return None, None
    
    local_state = os.path.join(base_path, 'Local State')
    
    # Try common profile names
    for profile in ['Default', 'Profile 1', 'Profile 2']:
        # Modern path: Network/Cookies
        cookie_path = os.path.join(base_path, profile, 'Network', 'Cookies')
        if os.path.exists(cookie_path):
            return cookie_path, local_state
        
        # Older path: Cookies
        cookie_path = os.path.join(base_path, profile, 'Cookies')
        if os.path.exists(cookie_path):
            return cookie_path, local_state
            
    # If it's Opera, it might be directly in the base path
    if browser == 'opera':
        cookie_path = os.path.join(base_path, 'Network', 'Cookies')
        if os.path.exists(cookie_path):
            return cookie_path, local_state
        cookie_path = os.path.join(base_path, 'Cookies')
        if os.path.exists(cookie_path):
            return cookie_path, local_state

    return None, None


def _copy_chromium_cookies(browser: str) -> Optional[str]:
    """
    Copy a Chromium browser's cookie database and Local State to a temp dir.
    Uses SQLite backup API to handle locked databases (browser is running).
    Returns the path to the temp profile directory.
    """
    cookie_db_path, local_state_path = _get_chromium_paths(browser)
    if not cookie_db_path:
        return None
    
    try:
        temp_dir = os.path.join(tempfile.gettempdir(), 'volia_profiles', browser)
        # Create profile structure
        # yt-dlp looks for Cookies in the root or in Network/
        network_dir = os.path.join(temp_dir, 'Default', 'Network')
        os.makedirs(network_dir, exist_ok=True)
        
        temp_cookies = os.path.join(network_dir, 'Cookies')
        
        # Strategy 1: Use SQLite backup API (handles locked databases)
        copied = False
        try:
            source_conn = sqlite3.connect(f'file:{cookie_db_path}?mode=ro&nolock=1', uri=True)
            dest_conn = sqlite3.connect(temp_cookies)
            source_conn.backup(dest_conn)
            dest_conn.close()
            source_conn.close()
            copied = True
            logger.info(f"Copied {browser} cookies via SQLite backup API")
        except Exception as e1:
            logger.debug(f"SQLite backup failed for {browser}: {e1}")
        
        # Strategy 2: Try raw file copy (works if browser is closed)
        if not copied:
            try:
                shutil.copy2(cookie_db_path, temp_cookies)
                copied = True
                logger.info(f"Copied {browser} cookies via file copy")
            except Exception as e2:
                logger.debug(f"File copy failed for {browser}: {e2}")
        
        # Strategy 3: On Windows, try using robocopy (can read locked files)
        if not copied and sys.platform == 'win32':
            try:
                import subprocess
                src_dir = os.path.dirname(cookie_db_path)
                src_file = os.path.basename(cookie_db_path)
                dest_dir = os.path.dirname(temp_cookies)
                result = subprocess.run(
                    ['robocopy', src_dir, dest_dir, src_file, '/NFL', '/NDL', '/NJH', '/NJS', '/nc', '/ns', '/np'],
                    capture_output=True, timeout=10
                )
                # robocopy returns 0 or 1 on success
                if result.returncode <= 1 and os.path.exists(temp_cookies):
                    copied = True
                    logger.info(f"Copied {browser} cookies via robocopy")
            except Exception as e3:
                logger.debug(f"Robocopy failed for {browser}: {e3}")
        
        if not copied:
            logger.warning(f"All copy strategies failed for {browser}")
            return None
        
        # Copy Local State (needed for decryption) — this file is usually not locked
        if local_state_path and os.path.exists(local_state_path):
            temp_local_state = os.path.join(temp_dir, 'Local State')
            try:
                shutil.copy2(local_state_path, temp_local_state)
            except Exception:
                # Try read/write as fallback
                try:
                    with open(local_state_path, 'rb') as fsrc:
                        with open(temp_local_state, 'wb') as fdst:
                            fdst.write(fsrc.read())
                except Exception as e:
                    logger.debug(f"Failed to copy Local State for {browser}: {e}")
                    return None
        
        logger.info(f"Successfully created temp profile for {browser}")
        return temp_dir
        
    except Exception as e:
        logger.debug(f"Error creating temp profile for {browser}: {e}")
        return None


def _copy_firefox_cookies() -> Optional[str]:
    """Try to find and copy Firefox cookies."""
    if sys.platform != 'win32':
        return None
    
    app_data = os.environ.get('APPDATA', '')
    profiles_dir = os.path.join(app_data, 'Mozilla', 'Firefox', 'Profiles')
    
    if not os.path.exists(profiles_dir):
        return None
    
    # Find the default profile
    for entry in os.listdir(profiles_dir):
        cookie_db = os.path.join(profiles_dir, entry, 'cookies.sqlite')
        if os.path.exists(cookie_db):
            logger.debug(f"Found Firefox cookies at: {cookie_db}")
            return None  # Let yt-dlp handle Firefox cookies
    
    return None


def get_ydl_opts_with_cookies(base_opts: dict = None) -> dict:
    """
    Get yt-dlp options with the best available cookie configuration.
    Merges cookie options into any base options provided.
    
    Usage:
        opts = get_ydl_opts_with_cookies({
            'quiet': True,
            'no_warnings': True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            ...
    """
    opts = base_opts.copy() if base_opts else {}
    
    # Remove any existing cookie settings
    opts.pop('cookiesfrombrowser', None)
    opts.pop('cookiefile', None)
    
    # Add the best cookie options
    cookie_opts = get_cookie_opts()
    opts.update(cookie_opts)
    
    return opts


def export_cookies_from_browser(browser: str = None, output_path: str = None) -> str:
    """
    Export cookies from a browser to a Netscape-format cookie file.
    
    Uses multiple strategies:
    1. First copies the cookie DB using our SQLite backup approach
    2. Then uses yt-dlp with the copied profile to export
    3. Falls back to direct SQLite read if yt-dlp fails
    
    Returns the path to the exported cookie file.
    """
    import subprocess
    
    if not browser:
        browser = _preferred_browser or 'edge'
    
    if not output_path:
        temp_dir = os.path.join(tempfile.gettempdir(), 'volia_cookies')
        os.makedirs(temp_dir, exist_ok=True)
        output_path = os.path.join(temp_dir, f'{browser}_cookies.txt')
    
    # Strategy 1: Copy profile then use yt-dlp with the copied profile
    if browser in ('edge', 'chrome', 'brave', 'opera', 'chromium'):
        profile_path = _copy_chromium_cookies(browser)
        if profile_path:
            try:
                result = subprocess.run(
                    [
                        sys.executable, '-m', 'yt_dlp',
                        '--cookies-from-browser', f'{browser}::{profile_path}',
                        '--cookies', output_path,
                        '--skip-download',
                        '--no-warnings',
                        '-q',
                        'https://www.youtube.com',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Exported cookies from {browser} via copied profile")
                    return output_path
            except Exception as e:
                logger.debug(f"yt-dlp export with copied profile failed for {browser}: {e}")
    
    # Strategy 2: Try yt-dlp directly (works if browser is closed)
    try:
        result = subprocess.run(
            [
                sys.executable, '-m', 'yt_dlp',
                '--cookies-from-browser', browser,
                '--cookies', output_path,
                '--skip-download',
                '--no-warnings',
                '-q',
                'https://www.youtube.com',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Exported cookies from {browser} via direct yt-dlp")
            return output_path
    except subprocess.TimeoutExpired:
        logger.debug(f"Direct yt-dlp cookie export timed out for {browser}")
    except Exception as e:
        logger.debug(f"Direct yt-dlp cookie export failed for {browser}: {e}")
    
    # Strategy 3: Directly read the SQLite cookie DB and write Netscape format
    if browser in ('edge', 'chrome', 'brave', 'opera', 'chromium'):
        try:
            cookie_db_path, _ = _get_chromium_paths(browser)
            if cookie_db_path:
                temp_db = os.path.join(tempfile.gettempdir(), 'volia_cookies', f'{browser}_temp.db')
                os.makedirs(os.path.dirname(temp_db), exist_ok=True)
                
                # Copy the DB using SQLite backup
                source_conn = sqlite3.connect(f'file:{cookie_db_path}?mode=ro&nolock=1', uri=True)
                dest_conn = sqlite3.connect(temp_db)
                source_conn.backup(dest_conn)
                dest_conn.close()
                source_conn.close()
                
                # Read cookies and write Netscape format
                conn = sqlite3.connect(temp_db)
                cursor = conn.execute(
                    "SELECT host_key, path, is_secure, expires_utc, name, value "
                    "FROM cookies"
                )
                
                with open(output_path, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.se/docs/http-cookies.html\n")
                    f.write("# This file was generated by Volia\n\n")
                    
                    for row in cursor:
                        host, path, secure, expires, name, value = row
                        secure_str = "TRUE" if secure else "FALSE"
                        domain_flag = "TRUE" if host.startswith('.') else "FALSE"
                        # Chrome stores expiry as microseconds since 1601-01-01
                        # Convert to Unix epoch (seconds since 1970-01-01)
                        if expires > 0:
                            expires_unix = int((expires / 1000000) - 11644473600)
                        else:
                            expires_unix = 0
                        f.write(f"{host}\t{domain_flag}\t{path}\t{secure_str}\t{expires_unix}\t{name}\t{value}\n")
                
                conn.close()
                
                # Clean up temp db
                try:
                    os.remove(temp_db)
                except Exception:
                    pass
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                    logger.info(f"Exported cookies from {browser} via direct SQLite read")
                    return output_path
        except Exception as e:
            logger.debug(f"Direct SQLite cookie export failed for {browser}: {e}")
    
    logger.warning(f"All cookie export strategies failed for {browser}")
    return None


def auto_setup_cookies() -> dict:
    """
    Automatically detect and set up the best cookie source.
    Tries exporting from each available browser.
    
    Returns a status dict with info about what was set up.
    """
    global _cookie_file_path
    
    # Check if running in a server environment where no browsers are available
    if is_server_environment():
        # Look for static cookies.txt in the backend folder as a fallback
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        cookie_path = os.path.join(backend_dir, "cookies.txt")
        if os.path.exists(cookie_path):
            _cookie_file_path = cookie_path
            logger.info("✅ Server environment: using static cookies.txt fallback")
            return {
                'success': True,
                'browser': None,
                'cookie_file': cookie_path,
                'message': 'Using static cookies.txt fallback in server environment'
            }
        
        logger.info("☁️ Server environment: skipped browser cookie export")
        return {
            'success': False,
            'browser': None,
            'cookie_file': None,
            'message': 'Skipped browser cookie setup on headless server environment'
        }
    
    browsers = _get_browser_order()
    
    for browser in browsers:
        logger.info(f"Trying to export cookies from {browser}...")
        cookie_file = export_cookies_from_browser(browser)
        
        if cookie_file:
            _cookie_file_path = cookie_file
            return {
                'success': True,
                'browser': browser,
                'cookie_file': cookie_file,
                'message': f'Successfully exported cookies from {browser}'
            }
    
    # If export failed for all browsers, try the temporary profile approach
    for browser in browsers:
        try:
            opts = _try_browser_cookies(browser)
            if opts:
                # Test if these options actually work
                import yt_dlp
                test_opts = opts.copy()
                test_opts.update({'quiet': True, 'no_warnings': True})
                
                with yt_dlp.YoutubeDL(test_opts) as ydl:
                    # We don't need to actually extract anything, just check if it initializes
                    # without immediately failing (though some errors only show on extraction)
                    pass
                
                set_preferred_browser(browser)
                return {
                    'success': True,
                    'browser': browser,
                    'cookie_file': None,
                    'message': f'Using temporary profile for {browser}'
                }
        except Exception as e:
            logger.debug(f"Failed to setup temporary profile for {browser}: {e}")
            continue
    
    return {
        'success': False,
        'browser': None,
        'cookie_file': None,
        'message': 'Could not access cookies from any browser. Try closing your browser and retrying, or export cookies manually.'
    }
