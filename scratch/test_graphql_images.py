"""
Direct Twitter/X GraphQL API - using yt-dlp's exact endpoint and features.
"""
import httpx
import json
import re
import urllib.parse

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
GRAPHQL_ENDPOINT = "2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId"

def get_guest_token():
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    r = httpx.post("https://api.x.com/1.1/guest/activate.json", headers=headers)
    if r.status_code == 200:
        return r.json().get("guest_token")
    print(f"Guest token error: {r.status_code} {r.text[:200]}")
    return None

def get_tweet(tweet_id, guest_token):
    variables = {
        "tweetId": tweet_id,
        "withCommunity": False,
        "includePromotedContent": False,
        "withVoice": False,
    }
    features = {
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }
    field_toggles = {"withArticleRichContentState": False}

    params = {
        "variables": json.dumps(variables),
        "features": json.dumps(features),
        "fieldToggles": json.dumps(field_toggles),
    }

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "X-Guest-Token": guest_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    url = f"https://x.com/i/api/graphql/{GRAPHQL_ENDPOINT}?{urllib.parse.urlencode(params)}"
    r = httpx.get(url, headers=headers, follow_redirects=True)
    print(f"GraphQL status: {r.status_code}")
    if r.status_code == 200:
        return r.json()
    print(f"Error body: {r.text[:300]}")
    return None

def extract_images(data):
    images = []
    try:
        result = data["data"]["tweetResult"]["result"]
        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", result)

        legacy = result.get("legacy", {})
        media_list = legacy.get("extended_entities", {}).get("media", [])
        if not media_list:
            media_list = legacy.get("entities", {}).get("media", [])

        user = result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
        text = legacy.get("full_text", "")
        screen_name = user.get("screen_name", "Unknown")
        name = user.get("name", screen_name)

        for m in media_list:
            if m.get("type") == "photo":
                url = m.get("media_url_https", "")
                if url:
                    if "?" not in url:
                        url += "?format=jpg&name=4096x4096"
                    else:
                        url = re.sub(r"name=\w+", "name=4096x4096", url)
                    images.append({
                        "url": url,
                        "width": m.get("original_info", {}).get("width"),
                        "height": m.get("original_info", {}).get("height"),
                    })

        return {"images": images, "text": text, "author": name, "screen_name": screen_name}
    except (KeyError, TypeError) as e:
        print(f"Parse error: {e}")
        return None

if __name__ == "__main__":
    token = get_guest_token()
    if not token:
        print("FAILED to get guest token"); exit(1)
    print(f"Got guest token: {token}")

    for label, tid in [("SpaceX images", "1802097368564179374"), ("Eminem video", "943590594491772928")]:
        print(f"\n--- {label} (ID {tid}) ---")
        data = get_tweet(tid, token)
        if data:
            with open(f"scratch/gql_{tid}.json", "w") as f:
                json.dump(data, f, indent=2)
            res = extract_images(data)
            if res:
                print(f"Author: @{res['screen_name']} ({res['author']})")
                print(f"Text: {res['text'][:120]}")
                print(f"Images: {len(res['images'])}")
                for i, img in enumerate(res["images"]):
                    print(f"  [{i}] {img['url'][:90]}  ({img['width']}x{img['height']})")
            else:
                print("No result parsed")
        else:
            print("No data returned")
