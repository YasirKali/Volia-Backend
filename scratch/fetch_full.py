import httpx

url = "https://raw.githubusercontent.com/vercel/react-tweet/main/packages/react-tweet/src/api/fetch-tweet.ts"

try:
    response = httpx.get(url)
    if response.status_code == 200:
        code = response.text
        print("Successfully fetched full code!")
        with open("scratch/fetch_tweet_full.ts", "w", encoding="utf-8") as f:
            f.write(code)
        print("Saved code to scratch/fetch_tweet_full.ts")
        
        # print lines 50 to 90
        lines = code.split("\n")
        print("\n=== Lines 50 to 90 ===")
        for idx, line in enumerate(lines[50:100]):
            print(f"{idx+50}: {line}")
            
    else:
        print(f"Failed to fetch: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
