import httpx
import re

def test_og_tags(url):
    print(f"\n==========================================")
    print(f"Fetching HTML from: {url}")
    print(f"==========================================")
    
    headers = {
        # Using a Discord/Telegram-like User-Agent because fxtwitter/vxtwitter custom-renders meta tags for them
        "User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)"
    }
    
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response length: {len(r.text)}")
        
        # Find all meta tags
        meta_tags = re.findall(r'<meta\s+[^>]*property=["\'](og:[a-zA-Z0-9:]+)["\']\s+content=["\']([^"\']+)["\']', r.text)
        print(f"og: meta tags found: {len(meta_tags)}")
        for prop, val in meta_tags:
            print(f"  {prop} => {val}")
            
        twitter_meta = re.findall(r'<meta\s+[^>]*name=["\'](twitter:[a-zA-Z0-9:]+)["\']\s+content=["\']([^"\']+)["\']', r.text)
        print(f"twitter: meta tags found: {len(twitter_meta)}")
        for prop, val in twitter_meta:
            print(f"  {prop} => {val}")
            
        # Let's save the HTML to see what's inside
        domain = "fxtwitter" if "fxtwitter" in url else "vxtwitter"
        with open(f"scratch/tweet_{domain}_meta.html", "w", encoding="utf-8") as f:
            f.write(r.text)
            
    except Exception as e:
        print(f"Error fetching {url}: {e}")

if __name__ == "__main__":
    # Test SpaceX tweet which contains multiple images
    test_og_tags("https://fxtwitter.com/SpaceX/status/1802097368564179374")
    test_og_tags("https://vxtwitter.com/SpaceX/status/1802097368564179374")
