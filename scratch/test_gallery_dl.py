import subprocess
import json
import sys

def test_gallery_dl(url, use_cookies=False):
    print(f"\n==========================================")
    print(f"Testing gallery-dl for URL: {url}")
    print(f"==========================================")
    
    cmd = [
        "sys.executable", "-m", "gallery_dl", 
        "-j", # dump json
        url
    ]
    # Replace sys.executable reference with the virtualenv's gallery-dl command or python executable
    cmd = [
        "venv\\Scripts\\gallery-dl.exe",
        "-j",
    ]
    
    if use_cookies:
        cmd.extend(["--cookies", "K:/Volia/volia-backend/cookies.txt"])
        
    cmd.append(url)
    
    print(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print(f"Return Code: {result.returncode}")
        print(f"Stdout (first 500 chars):\n{result.stdout[:500]}")
        print(f"Stderr:\n{result.stderr}")
        
        # Try to parse stdout lines. gallery-dl -j typically prints JSON arrays or lines of JSON
        lines = result.stdout.strip().split('\n')
        print(f"Number of stdout lines: {len(lines)}")
        
        parsed_items = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                parsed_items.append(item)
            except Exception as pe:
                pass
                
        print(f"Successfully parsed {len(parsed_items)} JSON objects")
        if parsed_items:
            print("First parsed item type/structure:")
            first = parsed_items[0]
            if isinstance(first, list):
                print(f"List of length {len(first)}")
                print(f"First item in list: {first[0] if first else 'empty'}")
            elif isinstance(first, dict):
                print(f"Keys: {list(first.keys())}")
                if 'category' in first:
                    print(f"Category: {first['category']}")
                # print some details depending on the structure
                
            # Save the parsed results
            out_fn = f"scratch/gallery_dl_{url.split('/')[-2] if '/' in url else 'out'}.json"
            with open(out_fn, 'w', encoding='utf-8') as out_f:
                json.dump(parsed_items, out_f, indent=2)
            print(f"Saved parsed objects to {out_fn}")
            
    except Exception as e:
        print(f"Error executing gallery-dl: {e}")

if __name__ == "__main__":
    # Test Twitter
    test_gallery_dl("https://x.com/SpaceX/status/1802097368564179374", use_cookies=True)
    # Test Instagram
    test_gallery_dl("https://www.instagram.com/p/C7Wb4XqORz5/", use_cookies=True)
