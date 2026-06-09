import httpx
import json
import subprocess

def get_twitter_token(tweet_id):
    try:
        cmd = ["node", "-e", f"console.log(((Number('{tweet_id}') / 1e15) * Math.PI).toString(36).replace(/(0+|\\.)/g, ''))"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return None

def test_twitter_syndication_with_features(tweet_id):
    print(f"\n==========================================")
    print(f"Testing Twitter Syndication WITH features: {tweet_id}")
    print(f"==========================================")
    
    token = get_twitter_token(tweet_id)
    features = (
        "tfw_timeline_list:;"
        "tfw_follower_count_sunset:true;"
        "tfw_tweet_edit_backend:on;"
        "tfw_refsrc_session:on;"
        "tfw_fosnr_soft_interventions_enabled:on;"
        "tfw_show_birdwatch_pivots_enabled:on;"
        "tfw_show_business_verified_badge:on;"
        "tfw_duplicate_scribes_to_settings:on;"
        "tfw_use_profile_image_shape_enabled:on;"
        "tfw_show_blue_verified_badge:on;"
        "tfw_legacy_timeline_sunset:true;"
        "tfw_show_gov_verified_badge:on;"
        "tfw_show_business_affiliate_badge:on;"
        "tfw_tweet_edit_frontend:on"
    )
    
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en&features={features}&token={token}"
    print(f"URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://platform.twitter.com",
    }
    
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS! Retrieved tweet JSON!")
            print(f"Text: {data.get('text')}")
            media = data.get('mediaDetails', [])
            print(f"Media details count: {len(media)}")
            for idx, m in enumerate(media):
                print(f"  Media {idx}: type={m.get('type')}, media_url={m.get('media_url_https')}")
                if 'video_info' in m:
                    print(f"    Has video_info!")
            
            with open("scratch/twitter_synd_success.json", "w") as f:
                json.dump(data, f, indent=2)
        else:
            print(f"Failed: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test NASA Webb Telescope first image tweet
    test_twitter_syndication_with_features("1546593466504245248")
    # Test SpaceX Starship Flight 4 Images tweet
    test_twitter_syndication_with_features("1802097368564179374")
