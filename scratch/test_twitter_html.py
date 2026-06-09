import httpx
import re

def test_x_html(url):
    print(f"\n==========================================")
    print(f"Testing direct X.com GET for URL: {url}")
    print(f"==========================================")
    
    # We will try a few user agents
    user_agents = {
        "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    for name, ua in user_agents.items():
        print(f"\nTrying User-Agent: {name}")
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        try:
            r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
            print(f"Status Code: {r.status_code}")
            print(f"Final URL: {r.url}")
            
            html = r.text
            print(f"HTML Length: {len(html)}")
            
            # Save HTML to file for inspection
            filename = f"scratch/x_{name.lower()}_page.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Saved page source to {filename}")
            
            # Search for og:image or twitter:image
            og_images = re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            print(f"Found property og:image: {og_images}")
            
            twitter_images = re.findall(r'<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"', html)
            print(f"Found name twitter:image: {twitter_images}")
            
            # Search for any other twimg urls
            twimg_urls = re.findall(r'https://pbs\.twimg\.com/media/[^"\s\\>]+', html)
            unique_twimgs = list(set(twimg_urls))
            print(f"Found {len(unique_twimgs)} pbs.twimg.com/media URLs:")
            for idx, u in enumerate(unique_twimgs[:10]):
                clean_url = u.replace('\\/', '/').replace('&amp;', '&')
                print(f"  Image URL {idx}: {clean_url}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    # SpaceX Starship Flight 4 Images tweet (multiple images)
    test_x_html("https://x.com/SpaceX/status/1802097368564179374")
