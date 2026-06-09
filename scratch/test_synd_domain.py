import httpx
import subprocess

def get_twitter_token(tweet_id):
    try:
        cmd = ["node", "-e", f"console.log(((Number('{tweet_id}') / 1e15) * Math.PI).toString(36).replace(/(0+|\\.)/g, ''))"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return None

def test_domains(tweet_id):
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
    
    hosts = [
        "https://cdn.syndication.twimg.com",
        "https://syndication.twitter.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    for host in hosts:
        url = f"{host}/tweet-result?id={tweet_id}&lang=en&features={features}&token={token}"
        print(f"\nTesting Host: {host}")
        try:
            r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                print("SUCCESS!")
                print(r.json().get('text', '')[:100])
            else:
                print(f"Failed: {r.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_domains("1546593466504245248")
