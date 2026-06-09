import httpx
import re
import json
from http.cookiejar import MozillaCookieJar

def test_x_with_cookies(url):
    print(f"\n==========================================")
    print(f"Testing X.com GET WITH cookies for URL: {url}")
    print(f"==========================================")
    
    cookie_file = "K:/Volia/volia-backend/cookies.txt"
    jar = MozillaCookieJar(cookie_file)
    try:
        # load ignoring discard and keep expires
        jar.load(ignore_discard=True, ignore_expires=True)
        print("Successfully loaded cookies jar!")
    except Exception as e:
        print(f"Error loading cookies jar: {e}")
        return
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    try:
        # Use httpx Client with cookies jar
        with httpx.Client(cookies=jar) as client:
            r = client.get(url, headers=headers, follow_redirects=True, timeout=15)
            print(f"Status Code: {r.status_code}")
            print(f"Final URL: {r.url}")
            
            html = r.text
            print(f"HTML Length: {len(html)}")
            
            # Find INITIAL_STATE
            match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html)
            if match:
                json_str = match.group(1)
                state = json.loads(json_str)
                tweets = state.get('entities', {}).get('tweets', {}).get('entities', {})
                print(f"Number of tweets found: {len(tweets)}")
                
                # Check for images in the tweet entities
                for tid, t in tweets.items():
                    print(f"  Tweet {tid}: text={t.get('text')[:100]}...")
                    # Search for media in initial state
                    # Let's write the JSON to a file to inspect
                    with open("scratch/initial_state_cookies.json", "w") as out_f:
                        json.dump(state, out_f, indent=2)
                    print("Saved state to scratch/initial_state_cookies.json")
            else:
                print("Could not find window.__INITIAL_STATE__!")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_x_with_cookies("https://x.com/SpaceX/status/1802097368564179374")
