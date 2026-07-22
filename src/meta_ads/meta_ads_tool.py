"""Meta Ad Library search helpers (unauthenticated, curl subprocess).

Two data paths:

1. First page — fetches the public Ad Library search page and parses the
   server-rendered JSON payload embedded in the HTML (up to ~30 ads plus the
   first pagination cursor). Facebook serves Python urllib a 403 "Client
   challenge", so we call system curl with browser-like headers (same
   workaround as x_twitter_tool). The challenge is a POST-then-retry flow; the
   issued cookie is kept in a jar file under config/ so later requests skip it.

2. "더 보기" pagination — replays the AdLibrarySearchPaginationQuery GraphQL
   call the browser fires on scroll. The pagination cursor is bound to the
   cookie-jar session that produced it, so we keep the shared jar and reuse the
   LSD token captured on the first page (stored per search in memory). The
   GraphQL doc_id rotates every few weeks; user-provided ids in
   config/meta_ads_doc_ids.json take priority over the built-in default.
"""

import json
import os
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import settings
from shared import cache_tool

NEGATIVE_CACHE_TTL = 120
AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"
GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
PAGINATION_FRIENDLY_NAME = "AdLibrarySearchPaginationQuery"
COUNTRIES = ("KR", "US", "JP", "TW", "ALL")
ACTIVE_STATUSES = ("active", "inactive", "all")
MEDIA_TYPES = ("all", "video", "image")
SEARCH_TYPES = ("keyword", "page")
PAGE_SIZE = 30

LONG_RUN_DAYS = 30  # an ad running this long is treated as a proven winner
_WATCHLIST_CONFIG = os.path.join(settings.CONFIG_DIR, "meta_ads_watchlist.json")
_WATCHLIST_MAX_WORKERS = 4
_ASSET_ALLOW = (".fbcdn.net",)
_COOKIE_JAR = os.path.join(settings.CONFIG_DIR, "meta_ads_cookies.txt")
# Built-in fallback doc_id (may go stale). config/meta_ads_doc_ids.json wins
# and can be refreshed from the browser network tab when Meta rotates it.
_DEFAULT_DOC_IDS = ["24922295957467452"]
_DOC_ID_CONFIG = os.path.join(settings.CONFIG_DIR, "meta_ads_doc_ids.json")
_DOC_ID_EXPIRED_FLAG = os.path.join(settings.CONFIG_DIR, ".meta_ads_docid_expired")

_CHALLENGE_RE = re.compile(r"fetch\('(/__rd_verify_[^']+)'")
_JSON_SCRIPT_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)
_LSD_RE = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"')
_STATUS_MARKER = "__HTTP_STATUS__:"
_MAX_CHALLENGE_TRIES = 3

# Per-search session context (lsd + sessionID) so 더보기 can reuse the token
# that the shared cookie jar produced. Keyed by the search cache key.
_context = {}
_context_lock = threading.Lock()

# Header set matters: without sec-ch-ua/Sec-Fetch-* Facebook answers the
# challenged request with a generic 400 error page instead of the ad data.
_BROWSER_HEADERS = [
    "-A", settings.UA,
    "-H", "Accept-Language: ko-KR,ko;q=0.9,en;q=0.8",
    "-H", ("Accept: text/html,application/xhtml+xml,application/xml;"
           "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
    "-H", 'sec-ch-ua: "Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "-H", "sec-ch-ua-mobile: ?0",
    "-H", 'sec-ch-ua-platform: "macOS"',
    "-H", "Sec-Fetch-Dest: document",
    "-H", "Sec-Fetch-Mode: navigate",
    "-H", "Sec-Fetch-Site: none",
    "-H", "Sec-Fetch-User: ?1",
    "-H", "Upgrade-Insecure-Requests: 1",
]


def _load_doc_ids():
    """Load doc_ids from config file, falling back to built-in defaults."""
    try:
        with open(_DOC_ID_CONFIG) as f:
            ids = json.load(f)
            if isinstance(ids, list) and ids:
                return [str(i) for i in ids]
    except (OSError, json.JSONDecodeError):
        pass
    return list(_DEFAULT_DOC_IDS)


def _flag_doc_id_expired():
    """Write a flag file when every doc_id fails, so the user knows to refresh
    config/meta_ads_doc_ids.json from the browser network tab."""
    if os.path.exists(_DOC_ID_EXPIRED_FLAG):
        return
    try:
        os.makedirs(os.path.dirname(_DOC_ID_EXPIRED_FLAG), exist_ok=True)
        with open(_DOC_ID_EXPIRED_FLAG, "w") as f:
            f.write("expired")
    except OSError:
        pass


def _clear_doc_id_expired():
    try:
        os.remove(_DOC_ID_EXPIRED_FLAG)
    except OSError:
        pass


def _curl(url, method="GET", data=None, extra_headers=None):
    """Run system curl; returns (http_status, body_text)."""
    os.makedirs(settings.CONFIG_DIR, exist_ok=True)
    cmd = ["curl", "-s", "--compressed", "-b", _COOKIE_JAR, "-c", _COOKIE_JAR]
    cmd += _BROWSER_HEADERS
    if method == "POST":
        cmd += ["-X", "POST"]
        if data is not None:
            cmd += ["--data-raw", data]
        else:
            cmd += ["-H", "Content-Length: 0"]
    cmd += extra_headers or []
    cmd += ["-w", "\n" + _STATUS_MARKER + "%{http_code}", url]
    proc = subprocess.run(cmd, capture_output=True, timeout=45)
    out = proc.stdout.decode("utf-8", "ignore")
    match = re.search(re.escape(_STATUS_MARKER) + r"(\d+)\s*$", out)
    if proc.returncode != 0 or not match:
        return 0, out
    return int(match.group(1)), out[: match.start()]


def _fetch_html(url):
    """GET the URL, transparently solving the __rd_verify challenge."""
    status, html = _curl(url)
    tries = 0
    while status == 403 and "__rd_verify" in html and tries < _MAX_CHALLENGE_TRIES:
        challenge = _CHALLENGE_RE.search(html)
        if not challenge:
            break
        _curl("https://www.facebook.com" + challenge.group(1), method="POST")
        status, html = _curl(url)
        tries += 1
    return status, html


def _build_url(query, country, search_type, active_status, media_type):
    params = {
        "active_status": active_status,
        "ad_type": "all",
        "country": country,
        "is_targeted_country": "false",
        "media_type": media_type,
    }
    if search_type == "page":
        params["search_type"] = "page"
        params["view_all_page_id"] = query
    else:
        params["q"] = query
        params["search_type"] = "keyword_unordered"
    return AD_LIBRARY_URL + "?" + urlencode(params)


def _text_of(value):
    if isinstance(value, dict):
        return value.get("text") or ""
    if isinstance(value, str):
        return value
    return ""


def _first_media(snapshot):
    for video in snapshot.get("videos") or []:
        if isinstance(video, dict):
            thumb = video.get("video_preview_image_url") or ""
            url = video.get("video_sd_url") or video.get("video_hd_url") or ""
            if thumb or url:
                return thumb, url
    for image in snapshot.get("images") or []:
        if isinstance(image, dict):
            thumb = image.get("resized_image_url") or image.get("original_image_url") or ""
            if thumb:
                return thumb, ""
    for card in snapshot.get("cards") or []:
        if isinstance(card, dict):
            thumb = (card.get("video_preview_image_url")
                     or card.get("resized_image_url")
                     or card.get("original_image_url") or "")
            url = card.get("video_sd_url") or card.get("video_hd_url") or ""
            if thumb or url:
                return thumb, url
    return "", ""


def _parse_ad(raw):
    snapshot = raw.get("snapshot") or {}
    cards = [c for c in (snapshot.get("cards") or []) if isinstance(c, dict)]
    first_card = cards[0] if cards else {}
    thumbnail, video_url = _first_media(snapshot)
    ad_id = str(raw.get("ad_archive_id") or "")
    return {
        "id": ad_id,
        "pageId": str(raw.get("page_id") or ""),
        "pageName": raw.get("page_name") or snapshot.get("page_name") or "",
        "pagePic": snapshot.get("page_profile_picture_url") or "",
        "isActive": bool(raw.get("is_active")),
        "startDate": raw.get("start_date") or 0,
        "endDate": raw.get("end_date") or 0,
        "platforms": raw.get("publisher_platform") or [],
        "title": snapshot.get("title") or first_card.get("title") or "",
        "body": _text_of(snapshot.get("body")) or _text_of(first_card.get("body")),
        "ctaText": snapshot.get("cta_text") or first_card.get("cta_text") or "",
        "linkUrl": snapshot.get("link_url") or first_card.get("link_url") or "",
        "caption": snapshot.get("caption") or "",
        "displayFormat": snapshot.get("display_format") or "",
        "thumbnail": thumbnail,
        "videoUrl": video_url,
        "collationCount": raw.get("collation_count") or 1,
        "url": AD_LIBRARY_URL + "?" + urlencode({"id": ad_id}),
    }


def _walk_ads(value, ads, seen, total, page_info):
    """Recursively collect ads, result count, and page_info from a JSON tree.

    Shared by the embedded HTML payload and the GraphQL pagination response."""
    if isinstance(value, dict):
        if "ad_archive_id" in value and "snapshot" in value:
            ad_id = str(value.get("ad_archive_id"))
            if ad_id not in seen:
                seen.add(ad_id)
                ads.append(_parse_ad(value))
        conn = value.get("search_results_connection")
        if isinstance(conn, dict):
            if isinstance(conn.get("count"), int):
                total[0] = conn["count"]
            info = conn.get("page_info")
            if isinstance(info, dict):
                page_info.update(info)
        if isinstance(value.get("page_info"), dict):
            page_info.update(value["page_info"])
        for nested in value.values():
            _walk_ads(nested, ads, seen, total, page_info)
    elif isinstance(value, list):
        for nested in value:
            _walk_ads(nested, ads, seen, total, page_info)


def _parse_html(html):
    """Extract ads, total count, and the first pagination cursor from the
    embedded JSON blocks."""
    ads, seen, total, page_info = [], set(), [0], {}
    for block in _JSON_SCRIPT_RE.findall(html):
        if "ad_archive_id" not in block:
            continue
        try:
            _walk_ads(json.loads(block), ads, seen, total, page_info)
        except json.JSONDecodeError:
            continue
    return ads, total[0], page_info.get("end_cursor") or "", \
        bool(page_info.get("has_next_page"))


def _parse_graphql(body):
    """Parse a GraphQL pagination response (optionally 'for (;;);'-prefixed)."""
    text = body.strip()
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]
    text = text.split("\n", 1)[0]
    data = json.loads(text)
    if data.get("errors") or data.get("error"):
        raise ValueError("graphql error")
    ads, seen, total, page_info = [], set(), [0], {}
    _walk_ads(data, ads, seen, total, page_info)
    return ads, page_info.get("end_cursor") or "", bool(page_info.get("has_next_page"))


def _aggregate_pages(ads):
    pages = {}
    for ad in ads:
        page_id = ad.get("pageId")
        if not page_id:
            continue
        entry = pages.setdefault(page_id, {
            "pageId": page_id,
            "pageName": ad.get("pageName") or "",
            "pagePic": ad.get("pagePic") or "",
            "count": 0,
        })
        entry["count"] += 1
        if not entry["pagePic"] and ad.get("pagePic"):
            entry["pagePic"] = ad["pagePic"]
    return sorted(pages.values(), key=lambda p: -p["count"])


def _build_variables(query, country, search_type, active_status, media_type, cursor):
    countries = [] if country == "ALL" else [country]
    return {
        "activeStatus": active_status,
        "adType": "ALL",
        "bylines": [],
        "collationToken": None,
        "contentLanguages": [],
        "countries": countries,
        "cursor": cursor,
        "excludedIDs": None,
        "first": PAGE_SIZE,
        "isTargetedCountry": False,
        "location": None,
        "mediaType": media_type,
        "multiCountryFilterMode": None,
        "pageIDs": [],
        "potentialReachInput": None,
        "publisherPlatforms": [],
        "queryString": "" if search_type == "page" else query,
        "regions": None,
        "searchType": "page" if search_type == "page" else "keyword_unordered",
        "sessionID": None,  # filled in by caller (per-search uuid)
        "sortData": None,
        "source": None,
        "startDate": None,
        "v": "983346",
        "viewAllPageID": query if search_type == "page" else "0",
    }


def fetch_first_page(query, country, search_type, active_status, media_type):
    """Fetch page 1 via HTML scrape.

    Returns (ads, pages, total, cursor, has_more, lsd, error_or_None)."""
    url = _build_url(query, country, search_type, active_status, media_type)
    try:
        status, html = _fetch_html(url)
    except subprocess.TimeoutExpired:
        return [], [], 0, "", False, "", {"account": query, "kind": "timeout", "code": None}
    except OSError:
        return [], [], 0, "", False, "", {"account": query, "kind": "http", "code": None}
    if status != 200:
        return [], [], 0, "", False, "", {"account": query, "kind": "http", "code": status or None}
    ads, total, cursor, has_more = _parse_html(html)
    lsd_match = _LSD_RE.search(html)
    return (ads[:PAGE_SIZE], _aggregate_pages(ads), total, cursor,
            has_more, lsd_match.group(1) if lsd_match else "", None)


def fetch_more(query, country, search_type, active_status, media_type,
               cursor, lsd, session_id):
    """Fetch the next page via the pagination GraphQL query.

    Returns (ads, next_cursor, has_more, error_or_None)."""
    if not (cursor and lsd):
        return [], "", False, {"account": query, "kind": "parse", "code": None}
    variables = _build_variables(
        query, country, search_type, active_status, media_type, cursor
    )
    variables["sessionID"] = session_id
    extra_headers = [
        "-H", "Accept: */*",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "-H", "X-FB-LSD: " + lsd,
        "-H", "Origin: https://www.facebook.com",
        "-H", "Referer: " + _build_url(query, country, search_type, active_status, media_type),
        "-H", "Sec-Fetch-Dest: empty",
        "-H", "Sec-Fetch-Mode: cors",
        "-H", "Sec-Fetch-Site: same-origin",
        "-H", "X-FB-Friendly-Name: " + PAGINATION_FRIENDLY_NAME,
    ]
    last_error = None
    all_failed = True
    doc_ids = _load_doc_ids()
    for doc_id in doc_ids:
        payload = urlencode({
            "lsd": lsd,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": PAGINATION_FRIENDLY_NAME,
            "variables": json.dumps(variables, ensure_ascii=False),
            "server_timestamps": "true",
            "doc_id": doc_id,
            "__a": "1",
        })
        try:
            status, body = _curl(GRAPHQL_URL, method="POST", data=payload,
                                 extra_headers=extra_headers)
        except subprocess.TimeoutExpired:
            return [], "", False, {"account": query, "kind": "timeout", "code": None}
        except OSError:
            return [], "", False, {"account": query, "kind": "http", "code": None}
        if status != 200:
            last_error = {"account": query, "kind": "http", "code": status or None}
            continue
        try:
            ads, next_cursor, has_more = _parse_graphql(body)
        except (ValueError, json.JSONDecodeError):
            last_error = {"account": query, "kind": "doc_id_expired", "code": None}
            continue
        all_failed = False
        _clear_doc_id_expired()
        return ads[:PAGE_SIZE], next_cursor, has_more, None
    if all_failed and doc_ids:
        _flag_doc_id_expired()
    return [], "", False, last_error or {"account": query, "kind": "parse", "code": None}


def get_meta_ads(query, country, search_type, active_status, media_type,
                 force, cursor=None):
    """Cached search. Returns (data, fetched_at, errors, cache_ttl).

    Without `cursor`: first page (HTML scrape). With `cursor`: next page
    (GraphQL). `data` carries `cursor`/`hasMore` for the 더보기 button."""
    search_key = ("meta_ads", search_type, query, country, active_status, media_type)

    if not cursor:
        def fetch():
            (ads, pages, total, next_cursor, has_more, lsd,
             error) = fetch_first_page(
                query, country, search_type, active_status, media_type
            )
            session_id = str(uuid.uuid4())
            with _context_lock:
                _context[search_key] = {"lsd": lsd, "sessionID": session_id}
            data = {
                "ads": ads, "pages": pages, "totalCount": total,
                "cursor": next_cursor, "hasMore": has_more and bool(lsd),
            }
            return data, [error] if error else []

        def ttl_for_outcome(outcome):
            data, errors = outcome
            return NEGATIVE_CACHE_TTL if not data["ads"] and errors else None

        (data, errors), fetched_at = cache_tool.cached(
            search_key, force, fetch, ttl=ttl_for_outcome
        )
        return data, fetched_at, errors, cache_tool.ttl_for(search_key)

    # Pagination request.
    page_key = search_key + ("page", cursor)

    def fetch_page():
        with _context_lock:
            ctx = _context.get(search_key) or {}
        lsd = ctx.get("lsd") or ""
        session_id = ctx.get("sessionID") or str(uuid.uuid4())
        ads, next_cursor, has_more, error = fetch_more(
            query, country, search_type, active_status, media_type,
            cursor, lsd, session_id
        )
        data = {"ads": ads, "pages": [], "totalCount": 0,
                "cursor": next_cursor, "hasMore": has_more}
        return data, [error] if error else []

    def ttl_for_outcome(outcome):
        data, errors = outcome
        return NEGATIVE_CACHE_TTL if not data["ads"] and errors else None

    (data, errors), fetched_at = cache_tool.cached(
        page_key, force, fetch_page, ttl=ttl_for_outcome
    )
    return data, fetched_at, errors, cache_tool.ttl_for(page_key)


# ---------------------------------------------------------------------------
# Competitor watchlist
# ---------------------------------------------------------------------------

def load_watchlist():
    """Return the saved competitor pages: [{pageId, pageName}, ...]."""
    try:
        with open(_WATCHLIST_CONFIG, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and str(item.get("pageId") or "").isdigit():
            out.append({"pageId": str(item["pageId"]),
                        "pageName": item.get("pageName") or ""})
    return out


def _save_watchlist(items):
    os.makedirs(settings.CONFIG_DIR, exist_ok=True)
    with open(_WATCHLIST_CONFIG, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def update_watchlist(action, page_id, page_name=""):
    """Add or remove a competitor page. Returns the updated list."""
    page_id = str(page_id or "").strip()
    items = load_watchlist()
    if action == "add" and page_id.isdigit():
        if not any(i["pageId"] == page_id for i in items):
            items.append({"pageId": page_id, "pageName": page_name or ""})
            _save_watchlist(items)
    elif action == "remove":
        filtered = [i for i in items if i["pageId"] != page_id]
        if len(filtered) != len(items):
            items = filtered
            _save_watchlist(items)
    return items


def _running_days(ad, now):
    start = ad.get("startDate") or 0
    return int((now - start) / 86400) if start else 0


def _summarize_page(entry, country, now):
    """Fetch one competitor page's first result set and reduce it to a
    dashboard row. Stats are over the sampled first page (up to PAGE_SIZE),
    except totalCount which is the page's full active-ad count."""
    page_id = entry["pageId"]
    ads, _, total, _, _, _, error = fetch_first_page(
        page_id, country, "page", "active", "all"
    )
    row = {
        "pageId": page_id,
        "pageName": entry.get("pageName") or (ads[0]["pageName"] if ads else page_id),
        "pagePic": ads[0]["pagePic"] if ads else "",
        "totalCount": total,
        "sampleCount": len(ads),
        "newThisWeek": sum(1 for a in ads if 0 <= _running_days(a, now) <= 7),
        "longRun": sum(1 for a in ads if _running_days(a, now) >= LONG_RUN_DAYS),
        "longestDays": max((_running_days(a, now) for a in ads), default=0),
        "videoShare": (round(100 * sum(
            1 for a in ads if a.get("displayFormat") == "VIDEO" or a.get("videoUrl")
        ) / len(ads)) if ads else 0),
        "topAd": None,
        "error": bool(error),
    }
    if ads:
        best = max(ads, key=lambda a: _running_days(a, now))
        row["topAd"] = {
            "id": best["id"], "url": best["url"], "thumbnail": best["thumbnail"],
            "title": best["title"] or best["body"], "days": _running_days(best, now),
        }
    return row


def get_watchlist_dashboard(country, force):
    """Fetch a summary row for every watched page. Returns
    (data, fetched_at, cache_ttl). data = {rows, watchlist}."""
    watchlist = load_watchlist()
    cache_key = ("meta_ads_dashboard", country, tuple(sorted(i["pageId"] for i in watchlist)))

    def fetch():
        now = time.time()
        if not watchlist:
            return {"rows": [], "watchlist": []}
        with ThreadPoolExecutor(max_workers=_WATCHLIST_MAX_WORKERS) as pool:
            rows = list(pool.map(
                lambda e: _summarize_page(e, country, now), watchlist
            ))
        rows.sort(key=lambda r: -r["totalCount"])
        return {"rows": rows, "watchlist": watchlist}

    def ttl_for_outcome(outcome):
        return NEGATIVE_CACHE_TTL if not outcome["rows"] else None

    data, fetched_at = cache_tool.cached(cache_key, force, fetch, ttl=ttl_for_outcome)
    return data, fetched_at, cache_tool.ttl_for(cache_key)


# ---------------------------------------------------------------------------
# Creative asset download (swipe file)
# ---------------------------------------------------------------------------

def fetch_asset(url):
    """Download a creative (image/video) from an fbcdn host for the swipe
    file. Returns (status, content_type, body_bytes, filename)."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    if not url.startswith("https://") or not host.endswith(_ASSET_ALLOW):
        return 400, "application/json; charset=utf-8", \
            json.dumps({"error": "host not allowed"}).encode(), ""
    is_video = "video" in host or ".mp4" in url.split("?", 1)[0]
    ext = "mp4" if is_video else "jpg"
    ctype = "video/mp4" if is_video else "image/jpeg"
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--compressed", "-A", settings.UA, url],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0 or not proc.stdout:
            return 502, "application/json; charset=utf-8", \
                json.dumps({"error": "fetch failed"}).encode(), ""
        return 200, ctype, proc.stdout, "meta_ad_creative." + ext
    except (subprocess.TimeoutExpired, OSError):
        return 502, "application/json; charset=utf-8", \
            json.dumps({"error": "fetch failed"}).encode(), ""
