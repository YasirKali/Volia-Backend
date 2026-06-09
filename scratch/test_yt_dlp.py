import yt_dlp
import json
import sys

url = "https://x.com/Eminem/status/943590594491772928"
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
}

print(f"Extracting {url}...")
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print("Success!")
        print("Title:", info.get('title'))
        formats = info.get('formats', [])
        print(f"Number of formats: {len(formats)}")
        for i, f in enumerate(formats):
            print(f"Format {i}: id={f.get('format_id')}, ext={f.get('ext')}, resolution={f.get('resolution') or f.get('width')}x{f.get('height')}, vcodec={f.get('vcodec')}, acodec={f.get('acodec')}, url_present={bool(f.get('url'))}")
except Exception as e:
    print("Error:", str(e))
    sys.exit(1)
