import httpx
import json
import subprocess

def get_twitter_token(tweet_id):
    try:
        cmd = ["node", "-e", f"console.log(((Number('{tweet_id}') / 1e15) * Math.PI).toString(36).replace(/(0+|\\.)/g, ''))"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return None

def test_id(tweet_id):
    print(f"\n--- Testing Tweet ID: {tweet_id} ---")
    
    # 1. Test Vercel proxy
    proxy_url = f"https://react-tweet.vercel.app/api/tweet/{tweet_id}"
    try:
        r = httpx.get(proxy_url, follow_redirects=True)
        print(f"Proxy status: {r.status_code}")
        if r.status_code == 200:
            print("Proxy success!")
            data = r.json()
            media = data.get('mediaDetails', [])
            print(f"Media count: {len(media)}")
            for m in media:
                print(f"  {m.get('type')}: {m.get('media_url_https')}")
        else:
            print(f"Proxy body: {r.text}")
    except Exception as e:
        print(f"Proxy exception: {e}")
        
    # 2. Test syndication endpoint directly with token
    token = get_twitter_token(tweet_id)
    synd_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en&token={token}"
    try:
        r = httpx.get(synd_url, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        print(f"Direct syndication status: {r.status_code}")
        if r.status_code == 200:
            print("Direct syndication success!")
            data = r.json()
            media = data.get('mediaDetails', [])
            print(f"Media count: {len(media)}")
            for m in media:
                print(f"  {m.get('type')}: {m.get('media_url_https')}")
        else:
            print(f"Direct syndication body (truncated): {r.text[:200]}")
    except Exception as e:
        print(f"Direct exception: {e}")

if __name__ == "__main__":
    # Test a few different IDs
    ids = [
        "1546593466504245248",  # Webb Telescope first image (1 image)
        "1694936317767221370",  # Random public tweet with images
        "1802097368564179374"   # SpaceX tweet
    ]
    for tid in ids:
        test_id(tid)
