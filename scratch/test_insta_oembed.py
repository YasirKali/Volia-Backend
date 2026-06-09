import httpx

def test_instagram_oembed(url):
    print(f"\n==========================================")
    print(f"Testing Instagram oEmbed for: {url}")
    print(f"==========================================")
    
    oembed_url = f"https://api.instagram.com/oembed?url={url}"
    try:
        r = httpx.get(oembed_url, follow_redirects=True, timeout=10)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print("Keys:", list(data.keys()))
            print(f"Title: {data.get('title')}")
            print(f"Thumbnail URL: {data.get('thumbnail_url')}")
            print(f"HTML (first 100 chars): {data.get('html', '')[:100]}...")
            
            # Save response
            import json
            with open("scratch/insta_oembed_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print("Saved response to scratch/insta_oembed_response.json")
        else:
            print(f"Error: {r.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test public Instagram post
    test_instagram_oembed("https://www.instagram.com/p/C7Wb4XqORz5/")
