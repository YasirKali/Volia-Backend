import os
import sys
import sqlite3
import tempfile
import json
import glob
from http.cookiejar import MozillaCookieJar

def get_chromium_cookies(browser, cookie_path, local_state_path):
    temp_cookies = os.path.join(tempfile.gettempdir(), f"volia_scan_{browser}.db")
    try:
        # SQLite backup API
        source_conn = sqlite3.connect(f'file:{cookie_path}?mode=ro&nolock=1', uri=True)
        dest_conn = sqlite3.connect(temp_cookies)
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
        
        conn = sqlite3.connect(temp_cookies)
        cursor = conn.execute("SELECT host_key, name, value FROM cookies")
        cookies = []
        for host, name, value in cursor:
            cookies.append((host, name))
        conn.close()
        os.remove(temp_cookies)
        return cookies
    except Exception as e:
        if os.path.exists(temp_cookies):
            try: os.remove(temp_cookies)
            except: pass
        return []

def get_firefox_cookies(profile_path):
    cookie_db = os.path.join(profile_path, 'cookies.sqlite')
    if not os.path.exists(cookie_db):
        return []
    temp_cookies = os.path.join(tempfile.gettempdir(), "volia_scan_firefox.db")
    try:
        source_conn = sqlite3.connect(f'file:{cookie_db}?mode=ro&nolock=1', uri=True)
        dest_conn = sqlite3.connect(temp_cookies)
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
        
        conn = sqlite3.connect(temp_cookies)
        cursor = conn.execute("SELECT host, name FROM moz_cookies")
        cookies = []
        for host, name in cursor:
            cookies.append((host, name))
        conn.close()
        os.remove(temp_cookies)
        return cookies
    except Exception as e:
        if os.path.exists(temp_cookies):
            try: os.remove(temp_cookies)
            except: pass
        return []

def scan_browsers():
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    app_data = os.environ.get('APPDATA', '')
    
    browsers = {
        'edge': os.path.join(local_app_data, 'Microsoft', 'Edge', 'User Data'),
        'chrome': os.path.join(local_app_data, 'Google', 'Chrome', 'User Data'),
        'brave': os.path.join(local_app_data, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'opera': os.path.join(app_data, 'Opera Software', 'Opera Stable'),
        'chromium': os.path.join(local_app_data, 'Chromium', 'User Data'),
    }
    
    print("==================================================")
    print("Scanning Chromium-based browsers...")
    print("==================================================")
    
    for name, base_path in browsers.items():
        if not os.path.exists(base_path):
            continue
        print(f"\nBrowser: {name} (found user data directory)")
        
        # Find profiles
        profiles = ['Default', 'Profile 1', 'Profile 2', 'Profile 3', '.']
        for p in profiles:
            cookie_paths = [
                os.path.join(base_path, p, 'Network', 'Cookies'),
                os.path.join(base_path, p, 'Cookies')
            ]
            for cp in cookie_paths:
                if os.path.exists(cp):
                    profile_name = p if p != '.' else 'Root (Opera)'
                    print(f"  Profile: {profile_name} -> Found Cookies database")
                    cookies = get_chromium_cookies(name, cp, os.path.join(base_path, 'Local State'))
                    
                    tw_auth = [c for c in cookies if ('twitter' in c[0] or 'x.com' in c[0]) and c[1] == 'auth_token']
                    ig_session = [c for c in cookies if 'instagram' in c[0] and c[1] == 'sessionid']
                    
                    print(f"    Total cookies: {len(cookies)}")
                    print(f"    Twitter auth_token: {'FOUND' if tw_auth else 'NOT FOUND'}")
                    print(f"    Instagram sessionid: {'FOUND' if ig_session else 'NOT FOUND'}")

    print("\n==================================================")
    print("Scanning Firefox profiles...")
    print("==================================================")
    ff_base = os.path.join(app_data, 'Mozilla', 'Firefox', 'Profiles')
    if os.path.exists(ff_base):
        for entry in os.listdir(ff_base):
            profile_path = os.path.join(ff_base, entry)
            if os.path.isdir(profile_path):
                cookie_db = os.path.join(profile_path, 'cookies.sqlite')
                if os.path.exists(cookie_db):
                    print(f"\nFirefox Profile: {entry}")
                    cookies = get_firefox_cookies(profile_path)
                    tw_auth = [c for c in cookies if ('twitter' in c[0] or 'x.com' in c[0]) and c[1] == 'auth_token']
                    ig_session = [c for c in cookies if 'instagram' in c[0] and c[1] == 'sessionid']
                    print(f"  Total cookies: {len(cookies)}")
                    print(f"  Twitter auth_token: {'FOUND' if tw_auth else 'NOT FOUND'}")
                    print(f"  Instagram sessionid: {'FOUND' if ig_session else 'NOT FOUND'}")

if __name__ == "__main__":
    scan_browsers()
