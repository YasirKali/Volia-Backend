"""Quick test of the new Spotify embed-based extraction."""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(__file__))

from services.spotify_downloader import SpotifyDownloader

async def main():
    dl = SpotifyDownloader()
    url = "https://open.spotify.com/playlist/0mU65CtbWkitIZnx0UGYXr?si=9d5738b61f134e21"
    try:
        info = await dl.extract_info(url)
        print(f"Title: {info.title}")
        print(f"Uploader: {info.uploader}")
        print(f"Platform: {info.platform}")
        print(f"Thumbnail: {info.thumbnail}")
        print(f"Duration: {info.duration}")
        print(f"Description: {info.description}")
        print(f"Formats:")
        for f in info.formats:
            print(f"  - {f.format_id}: {f.label}")
        print("\nSUCCESS!")
    except Exception as e:
        print(f"FAILED: {e}")

asyncio.run(main())
