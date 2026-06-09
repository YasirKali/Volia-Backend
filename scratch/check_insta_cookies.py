import os

cookie_file = "K:/Volia/volia-backend/cookies.txt"

if not os.path.exists(cookie_file):
    print("Cookies file does not exist!")
else:
    print(f"Reading cookies from {cookie_file}...")
    with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7 and "instagram.com" in parts[0]:
                domain = parts[0]
                name = parts[5]
                value = parts[6]
                # print first few characters of value for security
                val_preview = value[:5] + "..." if len(value) > 5 else value
                print(f"Domain: {domain:20s} Name: {name:20s} Value preview: {val_preview}")
