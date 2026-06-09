import httpx

def test_fxtwitter_variants(user, tweet_id):
    urls = [
        f"https://api.fxtwitter.com/status/{tweet_id}",
        f"https://api.fxtwitter.com/{user}/status/{tweet_id}",
        f"https://api.fxtwitter.com/i/status/{tweet_id}",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"\nTesting Tweet ID: {tweet_id} (Expected User: {user})")
    for url in urls:
        try:
            r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
            print(f"URL: {url} -> status={r.status_code}")
            if r.status_code == 200:
                data = r.json()
                tweet = data.get('tweet', {})
                print(f"  Success! Author: @{tweet.get('author', {}).get('screen_name')}")
                media = tweet.get('media', {})
                print(f"  Photos: {len(media.get('photos', []))}, Videos: {len(media.get('videos', []))}")
            else:
                print(f"  Response: {r.text[:150]}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    # Test SpaceX tweet which previously returned 404
    test_fxtwitter_variants("SpaceX", "1802097368564179374")
    # Test Eminem tweet which previously worked
    test_fxtwitter_variants("Eminem", "943590594491772928")
