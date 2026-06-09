import asyncio
import sys
from services.social_downloader import SocialDownloader
import yt_dlp
from services.cookie_helper import get_ydl_opts_with_cookies

async def main():
    url = "https://x.com/Eminem/status/943590594491772928"
    ydl_opts = get_ydl_opts_with_cookies({
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'no_color': True,
        'socket_timeout': 30,
    })
    
    def _extract(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
            
    try:
        info = _extract(ydl_opts)
    except Exception as e:
        print("First attempt failed, retrying without cookies...")
        clean_opts = ydl_opts.copy()
        clean_opts.pop('cookiesfrombrowser', None)
        clean_opts.pop('cookiefile', None)
        info = _extract(clean_opts)
    
    raw_formats = info.get('formats', [])
    print(f"Total raw formats from yt-dlp: {len(raw_formats)}")
    
    video_only = []
    audio_only = []
    combined = []
    
    for idx, f in enumerate(raw_formats):
        ext = f.get('ext', 'unknown')
        has_video = f.get('vcodec', 'none') != 'none'
        has_audio = f.get('acodec', 'none') != 'none'
        url_val = f.get('url')
        print(f"Raw format {idx}: id={f.get('format_id')}, ext={ext}, has_video={has_video} (vcodec={f.get('vcodec')}), has_audio={has_audio} (acodec={f.get('acodec')}), url_present={bool(url_val)}")
        
        if not url_val or ext in ('mhtml',):
            print(f"  Skipped: url_val={bool(url_val)}, ext={ext}")
            continue
        
        if has_video and has_audio:
            combined.append(f)
            print("  -> combined")
        elif has_video and not has_audio:
            video_only.append(f)
            print("  -> video_only")
        elif has_audio and not has_video:
            audio_only.append(f)
            print("  -> audio_only")
        else:
            print("  -> none!")

    print(f"combined count: {len(combined)}")
    print(f"video_only count: {len(video_only)}")
    print(f"audio_only count: {len(audio_only)}")

if __name__ == "__main__":
    asyncio.run(main())
