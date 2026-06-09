import re

with open("scratch/x_chrome_page.html", "r", encoding="utf-8") as f:
    html = f.read()

print(f"File size: {len(html)}")

# Check search terms
for term in ["twimg", "pbs", "media", "SpaceX", "starship", "og:image", "twitter:image", "JSON"]:
    matches = len(re.findall(re.escape(term), html, re.IGNORECASE))
    print(f"Occurrences of '{term}': {matches}")

# Let's search for any URL-like structures containing twimg or media
urls = re.findall(r'https?://[^"\s\\>]+', html)
print(f"\nTotal URLs found: {len(urls)}")

twimg_urls = [u for u in urls if "twimg" in u]
print(f"Twimg URLs found: {len(twimg_urls)}")
for idx, u in enumerate(list(set(twimg_urls))[:10]):
    print(f"  {idx}: {u[:100]}")
    
# Let's search for any JSON strings or Script tags that look promising
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"\nNumber of script tags: {len(scripts)}")
for idx, s in enumerate(scripts):
    if "twimg" in s or "SpaceX" in s:
        print(f"  Script {idx} (len {len(s)}) contains matches!")
        print(f"    Preview: {s.strip()[:200]}...")
