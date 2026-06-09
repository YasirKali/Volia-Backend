import os

cookie_file = "K:/Volia/volia-backend/cookies.txt"

if not os.path.exists(cookie_file):
    print("Cookies file does not exist!")
else:
    print(f"Cookies file size: {os.path.getsize(cookie_file)} bytes")
    domains = set()
    with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) > 0:
                domains.add(parts[0])
                
    print(f"Total domains in cookies file: {len(domains)}")
    print("Matching domains:")
    for d in sorted(domains):
        if any(term in d for term in ["twitter", "x.com", "instagram", "facebook", "youtube"]):
            print(f"  {d}")
