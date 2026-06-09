import httpx
import json

def test_fxtwitter(tweet_id):
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        print(f"ID {tweet_id} -> status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            tweet = data.get('tweet', {})
            media = tweet.get('media', {})
            photos = media.get('photos', [])
            print(f"  Success! Author: @{tweet.get('author', {}).get('screen_name')}")
            print(f"  Photos ({len(photos)}): {[p.get('url') for p in photos]}")
        else:
            print(f"  Error: {r.text[:150]}")
    except Exception as e:
        print(f"  Exception: {e}")

if __name__ == "__main__":
    # Test multiple tweets
    tweet_ids = [
        "1802058371301077364", # NASA tweet
        "1801646271974052309", # Random tweet
        "1801269986341208479", # Another tweet
        "1546593466504245248", # Webb telescope
        "1722572323067822459", # Cat image tweet
    ]
    for tid in tweet_ids:
        test_fxtwitter(tid)
