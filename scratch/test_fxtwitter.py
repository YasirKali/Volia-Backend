"""Test fxtwitter.com API for extracting tweet images."""
import httpx
import json

def test_fxtwitter(tweet_url):
    """Use fxtwitter API to get tweet data including images."""
    # Extract tweet ID from URL
    parts = tweet_url.rstrip('/').split('/')
    tweet_id = parts[-1]
    
    # fxtwitter API endpoint
    api_url = f"https://api.fxtwitter.com/status/{tweet_id}"
    
    print(f"\n{'='*50}")
    print(f"Testing fxtwitter API for tweet: {tweet_id}")
    print(f"API URL: {api_url}")
    print(f"{'='*50}")
    
    headers = {
        "User-Agent": "Volia/1.0",
    }
    
    try:
        r = httpx.get(api_url, headers=headers, follow_redirects=True, timeout=15)
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            tweet = data.get('tweet', {})
            
            print(f"Author: @{tweet.get('author', {}).get('screen_name')}")
            print(f"Text: {tweet.get('text', '')[:100]}...")
            
            media = tweet.get('media', {})
            photos = media.get('photos', [])
            videos = media.get('videos', [])
            
            print(f"\nPhotos: {len(photos)}")
            for i, photo in enumerate(photos):
                print(f"  Photo {i}: url={photo.get('url')}")
                print(f"    width={photo.get('width')}, height={photo.get('height')}")
            
            print(f"\nVideos: {len(videos)}")
            for i, video in enumerate(videos):
                print(f"  Video {i}: url={video.get('url')}")
            
            # Save full response
            with open("scratch/fxtwitter_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print("\nSaved full response to scratch/fxtwitter_response.json")
        else:
            print(f"Error: {r.text[:300]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test with SpaceX multi-image tweet  
    test_fxtwitter("https://x.com/SpaceX/status/1802097368564179374")
    
    # Test with a known video tweet (Eminem)
    test_fxtwitter("https://x.com/Eminem/status/943590594491772928")
