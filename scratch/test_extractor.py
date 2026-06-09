import asyncio
import json
import sys
from services.social_downloader import SocialDownloader

async def main():
    downloader = SocialDownloader("twitter")
    url = "https://x.com/Eminem/status/943590594491772928"
    try:
        info = await downloader.extract_info(url)
        print("Success!")
        print("Title:", info.title)
        print("Platform:", info.platform)
        print("Number of formats:", len(info.formats))
        for i, f in enumerate(info.formats):
            print(f"FormatInfo {i}: id={f.format_id}, ext={f.extension}, res={f.resolution}, has_v={f.has_video}, has_a={f.has_audio}, label='{f.label}'")
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
