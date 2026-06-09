import asyncio
import sys
sys.path.insert(0, 'K:/Volia/volia-backend')

import yt_dlp
from services.social_downloader import SocialDownloader

async def main():
    url = "https://x.com/Eminem/status/943590594491772928"
    
    # Extract with plain yt-dlp (no cookies to avoid cookie errors)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        raw_info = ydl.extract_info(url, download=False)
    
    raw_formats = raw_info.get('formats', [])
    print(f"=== Raw yt-dlp formats: {len(raw_formats)} ===")
    
    downloader = SocialDownloader("twitter")
    
    for idx, f in enumerate(raw_formats):
        has_video, has_audio = downloader._classify_format(f)
        print(f"  Format {idx}: id={f.get('format_id'):30s} vcodec={str(f.get('vcodec')):15s} acodec={str(f.get('acodec')):10s} => has_video={has_video}, has_audio={has_audio}")

    # Now test through the actual extract_info method
    print(f"\n=== SocialDownloader.extract_info ===")
    info = await downloader.extract_info(url)
    print(f"Title: {info.title}")
    print(f"Formats returned: {len(info.formats)}")
    for i, f in enumerate(info.formats):
        print(f"  [{i}] id={f.format_id:30s} res={str(f.resolution):15s} has_video={f.has_video} has_audio={f.has_audio} label='{f.label}'")

if __name__ == "__main__":
    asyncio.run(main())
