import httpx
import json

def test_cobalt(url):
    print(f"\n==========================================")
    print(f"Testing Cobalt for: {url}")
    print(f"==========================================")
    
    # We will try both the root endpoint and /api/json endpoint since different versions of Cobalt use different paths
    endpoints = [
        "https://api.cobalt.tools/api/json",
        "https://api.cobalt.tools/",
    ]
    
    payload = {
        "url": url,
        "vQuality": "1080",
        "isAudioOnly": False
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for ep in endpoints:
        try:
            print(f"Trying endpoint: {ep}")
            r = httpx.post(ep, json=payload, headers=headers, follow_redirects=True, timeout=15)
            print(f"Status Code: {r.status_code}")
            print(f"Response Headers Content-Type: {r.headers.get('content-type')}")
            
            if r.status_code in (200, 201):
                try:
                    data = r.json()
                    print("JSON Response:")
                    print(json.dumps(data, indent=2))
                    # If this worked, we don't need to try the next endpoint
                    break
                except Exception as je:
                    print(f"Response not JSON: {je}")
                    print(f"Text (first 500 chars): {r.text[:500]}")
            else:
                print(f"Error Body: {r.text[:500]}")
        except Exception as e:
            print(f"Exception for {ep}: {e}")

if __name__ == "__main__":
    # 1. SpaceX tweet with images
    test_cobalt("https://x.com/SpaceX/status/1802097368564179374")
    # 2. Instagram post
    test_cobalt("https://www.instagram.com/p/C7Wb4XqORz5/")
