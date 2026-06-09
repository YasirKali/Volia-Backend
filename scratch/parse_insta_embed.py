import re

with open("scratch/instagram_embed.html", "r", encoding="utf-8") as f:
    html = f.read()

print(f"File size: {len(html)}")

# Print first 500 characters
print("--- FIRST 500 CHARACTERS ---")
print(html[:500])

# Print last 500 characters
print("--- LAST 500 CHARACTERS ---")
print(html[-500:])

# Search for common strings
for word in ["login", "login_page", "redirect", "shortcode", "graphql", "scontent", "cdninstagram"]:
    count = len(re.findall(re.escape(word), html, re.IGNORECASE))
    print(f"Occurrences of '{word}': {count}")

# Print script tags
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"Number of script tags: {len(scripts)}")
for idx, s in enumerate(scripts):
    if len(s.strip()) > 100:
        print(f"  Script {idx} (len {len(s)}): {s.strip()[:150]}...")
