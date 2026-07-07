"""X/Twitter helpers ported from the upstream stdlib server."""

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from shared import accounts_tool, cache_tool

NEGATIVE_CACHE_TTL = 120


DEFAULT_X_ACCOUNTS = [
    "OpenAI",
    "runwayml",
    "Kling_ai",
    "GoogleDeepMind",
    "midjourney",
    "LumaLabsAI",
    "pika_labs",
    "heygen_com",
    "elevenlabsio",
    "AIatMeta",
]


def register():
    accounts_tool.register_source(
        "x", "x_accounts.json", DEFAULT_X_ACCOUNTS, preserve_case=True
    )


def _find_timeline_entries(node):
    """Find the timeline entries list in syndication __NEXT_DATA__."""
    if isinstance(node, dict):
        timeline = node.get("timeline")
        if isinstance(timeline, dict) and isinstance(timeline.get("entries"), list):
            return timeline["entries"]
        for value in node.values():
            result = _find_timeline_entries(value)
            if result:
                return result
    elif isinstance(node, list):
        for value in node:
            result = _find_timeline_entries(value)
            if result:
                return result
    return None


def fetch_x_posts(username: str):
    url = (
        "https://syndication.twitter.com/srv/timeline-profile/screen-name/"
        + quote(username)
    )
    try:
        # Use curl subprocess to avoid urllib TLS fingerprint being blocked
        # by Cloudflare (syndication endpoint returns 429 for Python urllib
        # but 200 for curl's SecureTransport stack).
        proc = subprocess.run(
            ["curl", "-s", "-H", "Accept: text/html", url],
            capture_output=True, timeout=15,
        )
        if proc.returncode != 0:
            return [], {"account": username, "kind": "http", "code": None}
        html = proc.stdout.decode("utf-8", "ignore")
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not match:
            return [], {"account": username, "kind": "parse", "code": None}
        data = json.loads(match.group(1))
    except subprocess.TimeoutExpired:
        return [], {"account": username, "kind": "timeout", "code": None}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], {"account": username, "kind": "parse", "code": None}
    except OSError:
        return [], {"account": username, "kind": "http", "code": None}

    posts = []
    for entry in _find_timeline_entries(data) or []:
        content = entry.get("content", {}) if isinstance(entry, dict) else {}
        tweet = content.get("tweet")
        if not isinstance(tweet, dict):
            tweet_result = content.get("tweetResult") or {}
            tweet = tweet_result.get("result") if isinstance(tweet_result, dict) else None
        if not isinstance(tweet, dict) or tweet.get("favorite_count") is None:
            continue

        user = tweet.get("user", {}) if isinstance(tweet.get("user"), dict) else {}
        media = ""
        for item in tweet.get("mediaDetails") or []:
            if isinstance(item, dict) and item.get("media_url_https"):
                media = item["media_url_https"]
                break

        views = tweet.get("views")
        posts.append(
            {
                "account": username,
                "name": user.get("name", username),
                "text": (tweet.get("full_text") or tweet.get("text") or "").strip(),
                "likes": tweet.get("favorite_count") or 0,
                "replies": tweet.get("reply_count") or 0,
                "retweets": tweet.get("retweet_count") or 0,
                "views": int(views.get("count", 0)) if isinstance(views, dict) else 0,
                "media": media,
                "url": "https://x.com/%s/status/%s"
                % (username, tweet.get("id_str", "")),
                "createdAt": tweet.get("created_at", ""),
            }
        )
    return posts, None


def get_x_posts(force: bool):
    source = accounts_tool.get_source("x")
    accounts = accounts_tool.load_accounts(source["path"], source["defaults"])
    cache_key = ("x", tuple(accounts))

    def fetch():
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = pool.map(fetch_x_posts, accounts)
        posts = []
        errors = []
        for items, error in results:
            posts.extend(items)
            if error:
                errors.append(error)
        return posts, errors

    def ttl_for_outcome(outcome):
        posts, errors = outcome
        return NEGATIVE_CACHE_TTL if not posts and errors else None

    (posts, errors), fetched_at = cache_tool.cached(cache_key, force, fetch, ttl=ttl_for_outcome)
    return posts, accounts, fetched_at, errors, cache_tool.ttl_for(cache_key)
