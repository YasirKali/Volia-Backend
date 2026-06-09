import re
import json

with open("scratch/x_chrome_page.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find window.__INITIAL_STATE__=
match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*window\.', html)
if not match:
    # Try another regex
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html)

if match:
    json_str = match.group(1)
    print(f"Extracted INITIAL_STATE string of length {len(json_str)}")
    try:
        state = json.loads(json_str)
        print("Successfully parsed INITIAL_STATE JSON!")
        
        # Save to file
        with open("scratch/initial_state.json", "w") as out_f:
            json.dump(state, out_f, indent=2)
        print("Saved state to scratch/initial_state.json")
        
        # Print top-level keys
        print(f"Top-level keys: {list(state.keys())}")
        
        # Search for tweets or media in entities
        entities = state.get('entities', {})
        print(f"Entities keys: {list(entities.keys())}")
        
        # Check tweets entities
        tweets = entities.get('tweets', {}).get('entities', {})
        print(f"Number of tweets: {len(tweets)}")
        for tid, t in tweets.items():
            print(f"  Tweet {tid}: text={t.get('text')[:60]}...")
            
    except Exception as e:
        print(f"Error parsing JSON: {e}")
else:
    print("Could not find window.__INITIAL_STATE__ in HTML!")
