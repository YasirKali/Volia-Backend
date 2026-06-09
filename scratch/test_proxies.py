import httpx
import re

def test_url(name, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)"
    }
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        print(f"{name}: status={r.status_code}, url={r.url}")
        
        # Check og:image or twitter:image
        images = re.findall(r'<meta\s+[^>]*property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', r.text)
        if not images:
            images = re.findall(r'<meta\s+[^>]*name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']', r.text)
            
        print(f"  Images found: {len(images)}")
        for img in images[:4]:
            print(f"    {img}")
            
        # Check if it has description saying private/not found
        desc = re.findall(r'<meta\s+[^>]*property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', r.text)
        if desc:
            print(f"    Description: {desc[0][:100]}")
    except Exception as e:
        print(f"{name}: error: {e}")

if __name__ == "__main__":
    tweet_id = "1802097368564179374"  # SpaceX tweet
    
    proxies = {
        "fxtwitter.com": f"https://fxtwitter.com/SpaceX/status/{tweet_id}",
        "fixupx.com": f"https://fixupx.com/SpaceX/status/{tweet_id}",
        "fixvx.com": f"https://fixvx.com/SpaceX/status/{tweet_id}",
        "api.fxtwitter.com": f"https://api.fxtwitter.com/SpaceX/status/{tweet_id}",
    }
    
    for name, url in proxies.items():
        test_url(name, url)
