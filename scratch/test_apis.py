import httpx
import json

def test_twitter_apis(tweet_id):
    apis = {
        "fxtwitter": f"https://api.fxtwitter.com/status/{tweet_id}",
        "vxtwitter": f"https://api.vxtwitter.com/status/{tweet_id}",
        "fixupx": f"https://api.fixupx.com/status/{tweet_id}",
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"\n==========================================")
    print(f"Testing X/Twitter APIs for Tweet ID: {tweet_id}")
    print(f"==========================================")
    
    for name, url in apis.items():
        try:
            r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
            print(f"{name}: status={r.status_code}")
            if r.status_code == 200:
                data = r.json()
                # print first level keys
                print(f"  Keys: {list(data.keys())}")
                tweet = data.get('tweet', data)
                media = tweet.get('media', {})
                photos = media.get('photos', [])
                videos = media.get('videos', [])
                print(f"  Photos: {len(photos)}, Videos: {len(videos)}")
                for i, p in enumerate(photos):
                    print(f"    Photo {i}: {p.get('url')}")
                for i, v in enumerate(videos):
                    print(f"    Video {i}: {v.get('url')}")
            else:
                print(f"  Error: {r.text[:200]}")
        except Exception as e:
            print(f"  Exception for {name}: {e}")

def test_instagram_embed(shortcode):
    print(f"\n==========================================")
    print(f"Testing Instagram Embed for Shortcode: {shortcode}")
    print(f"==========================================")
    
    url = f"https://www.instagram.com/p/{shortcode}/embed/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        print(f"Embed status: {r.status_code}")
        print(f"Response length: {len(r.text)}")
        
        # Save embed html to check
        with open("scratch/insta_test_embed.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Saved embed HTML to scratch/insta_test_embed.html")
        
        # Check if we were redirected to login
        if "login" in r.url.path or "accounts/login" in r.text:
            print("Redirected to login page or contains login text.")
        else:
            print("No login redirect detected in URL.")
            
        # Try to find images in the html using regex
        # Look for script tag content containing JSON or scontent urls
        import re
        urls = re.findall(r'https?://[^\s"\\]+?cdninstagram\.com[^\s"\\]+', r.text)
        print(f"Found {len(urls)} Instagram CDN URLs in raw text.")
        
        # Try a few regexes to find display_url or similar keys
        # Instagram embeds use window.__additionalDataLoaded or PolarisEmbedPostController
        # Let's inspect some occurrences of display_url or similar patterns
        display_resources = re.findall(r'"display_url":"([^"]+)"', r.text)
        print(f"Found display_url: {len(display_resources)}")
        for url_str in display_resources[:3]:
            # unescape characters
            url_clean = url_str.replace('\\u0025', '%').replace('\\/', '/')
            print(f"  URL: {url_clean[:100]}...")
            
    except Exception as e:
        print(f"Embed Exception: {e}")

if __name__ == "__main__":
    # Test a few Tweet IDs
    # 1. SpaceX tweet with images
    test_twitter_apis("1802097368564179374")
    # 2. A recent NASA post
    test_twitter_apis("1802058371301077364")
    
    # Test Instagram post
    test_instagram_embed("C7Wb4XqORz5")
    test_instagram_embed("C754W_tov_H")
