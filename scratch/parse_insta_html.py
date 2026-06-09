import re
import json
from bs4 import BeautifulSoup

def parse_insta():
    with open("scratch/insta_test_embed.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    print(f"HTML Length: {len(html)}")
    
    # 1. Use BeautifulSoup to check structure
    soup = BeautifulSoup(html, "html.parser")
    print("Title:", soup.title.string if soup.title else "No title")
    
    # 2. Check if we can find any image elements
    imgs = soup.find_all("img")
    print(f"Found img tags: {len(imgs)}")
    for idx, img in enumerate(imgs):
        print(f"  Img {idx}: src={img.get('src', '')[:100]}..., class={img.get('class')}")
        
    # 3. Look for URLs containing cdninstagram
    # A typical CDN url: https://scontent-lax3-1.cdninstagram.com/v/...
    cdn_urls = re.findall(r'https?://[^\s"\\><]+?cdninstagram\.com[^\s"\\><]+', html)
    print(f"Total raw cdninstagram URLs: {len(cdn_urls)}")
    
    # Remove duplicates
    unique_urls = list(set(cdn_urls))
    print(f"Unique cdninstagram URLs: {len(unique_urls)}")
    for idx, url in enumerate(unique_urls[:10]):
        # Unescape unicode/escapes
        clean_url = url.replace('\\u0025', '%').replace('\\/', '/')
        print(f"  URL {idx}: {clean_url[:120]}...")
        
    # 4. Check for JSON in scripts
    # Often, Instagram stores the data in window.__additionalDataLoaded or PolarisEmbedPostController or similar
    scripts = soup.find_all("script")
    print(f"Total script tags: {len(scripts)}")
    for idx, s in enumerate(scripts):
        content = s.string or ""
        if "PolarisEmbedPostController" in content or "shortcode" in content or "graphql" in content:
            print(f"  Script {idx} has keywords (len={len(content)})")
            # Write this script to a temp file to inspect
            with open(f"scratch/insta_script_{idx}.js", "w", encoding="utf-8") as sf:
                sf.write(content)
            print(f"    Saved script {idx} to scratch/insta_script_{idx}.js")

if __name__ == "__main__":
    parse_insta()
