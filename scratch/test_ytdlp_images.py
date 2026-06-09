"""Test if yt-dlp can extract image URLs from Twitter when we allow no-format errors."""
import yt_dlp
import json

def test_tweet_images(url):
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print(f"{'='*60}")
    
    opts = {
        'quiet': True,
        'no_warnings': True,
        'ignore_no_formats_error': True,  # KEY: don't crash on image-only tweets
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            print("No info returned")
            return
            
        print(f"Title: {info.get('title')}")
        print(f"Uploader: {info.get('uploader')}")
        print(f"Thumbnail: {info.get('thumbnail')}")
        print(f"Formats count: {len(info.get('formats', []))}")
        
        # Check for thumbnails list (yt-dlp often puts images here)
        thumbnails = info.get('thumbnails', [])
        print(f"Thumbnails count: {len(thumbnails)}")
        for i, t in enumerate(thumbnails):
            print(f"  Thumb {i}: {t.get('url', '')[:100]}")
        
        # Check description for image clues
        desc = info.get('description', '')
        print(f"Description: {desc[:200] if desc else 'None'}")
        
        # Dump the full info keys to see what's available
        print(f"Info keys: {sorted(info.keys())}")
        
        # Save full info for inspection
        safe_info = {}
        for k, v in info.items():
            if k in ('formats', 'thumbnails', 'subtitles', 'requested_formats'):
                safe_info[k] = v
            elif isinstance(v, (str, int, float, bool, type(None))):
                safe_info[k] = v
            elif isinstance(v, (list, dict)):
                safe_info[k] = v
        
        with open(f"scratch/ytdlp_info_{url.split('/')[-1]}.json", "w") as f:
            json.dump(safe_info, f, indent=2, default=str)
        print(f"Saved full info to scratch/ytdlp_info_{url.split('/')[-1]}.json")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Image-only tweet (SpaceX)
    test_tweet_images("https://x.com/SpaceX/status/1802097368564179374")
    # Video tweet (should still work normally)
    test_tweet_images("https://x.com/Eminem/status/943590594491772928")
