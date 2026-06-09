import asyncio
import sys
import os

# Add parent dir to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.social_downloader import SocialDownloader

async def test():
    print("Testing SocialDownloader Image Extraction...")
    
    # 1. Test Instagram Post
    print("\n--- Testing Instagram Extraction ---")
    downloader = SocialDownloader("instagram")
    try:
        info = await downloader.extract_info("https://www.instagram.com/p/C7Wb4XqORz5/")
        print("Success!")
        print(f"Title: {info.title}")
        print(f"Is Image: {getattr(info, 'is_image', False)}")
        print(f"Formats Count: {len(info.formats)}")
        for f in info.formats:
            print(f"  Format: id={f.format_id}, label={f.label}, url={f.url[:60] if f.url else None}")
    except Exception as e:
        print(f"Instagram Extraction failed: {e}")

    # 2. Test Twitter Video (should fall back to yt-dlp video format)
    print("\n--- Testing Twitter Video (Fallback) ---")
    downloader_tw = SocialDownloader("twitter")
    try:
        info_tw = await downloader_tw.extract_info("https://x.com/Eminem/status/943590594491772928")
        print("Success!")
        print(f"Title: {info_tw.title}")
        print(f"Is Image: {getattr(info_tw, 'is_image', False)}")
        print(f"Formats Count: {len(info_tw.formats)}")
        if info_tw.formats:
            print(f"  Best Format: {info_tw.formats[0].label}")
    except Exception as e:
        print(f"Twitter Extraction failed: {e}")

    # 3. Test Twitter Image Post (should raise ValueError telling us to log in/sync)
    print("\n--- Testing Twitter Image Extraction ---")
    downloader_img = SocialDownloader("twitter")
    try:
        info_img = await downloader_img.extract_info("https://x.com/SpaceX/status/1802097368564179374")
        print("Success!")
        print(f"Title: {info_img.title}")
        print(f"Is Image: {getattr(info_img, 'is_image', False)}")
        print(f"Formats Count: {len(info_img.formats)}")
    except Exception as e:
        print(f"Twitter Image Extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
