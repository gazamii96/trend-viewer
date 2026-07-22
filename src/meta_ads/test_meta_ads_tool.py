import json
import subprocess
import unittest
from unittest import mock

from meta_ads import meta_ads_tool
from shared import cache_tool


def _raw_ad(ad_id="111", page_id="900", page_name="Puzzle Studio", **overrides):
    ad = {
        "ad_archive_id": ad_id,
        "collation_count": 2,
        "is_active": True,
        "page_id": page_id,
        "page_name": page_name,
        "start_date": 1750000000,
        "end_date": 1784000000,
        "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
        "snapshot": {
            "page_name": page_name,
            "page_profile_picture_url": "https://scontent.test/pic.jpg",
            "title": "Match colors",
            "body": {"text": "Try a funny matching game"},
            "cta_text": "게임하기",
            "cta_type": "PLAY_GAME",
            "caption": "play.google.com",
            "link_url": "https://play.google.com/store/apps/details?id=x",
            "display_format": "VIDEO",
            "cards": [],
            "images": [],
            "videos": [
                {
                    "video_preview_image_url": "https://scontent.test/preview.jpg",
                    "video_sd_url": "https://video.test/ad.mp4",
                    "video_hd_url": "",
                }
            ],
        },
    }
    ad.update(overrides)
    return ad


def _connection(ads, count=42, end_cursor="CURSOR1", has_next=True):
    return {
        "count": count,
        "edges": [{"node": {"collated_results": [ad]}} for ad in ads],
        "page_info": {"end_cursor": end_cursor, "has_next_page": has_next},
    }


def _search_html(ads, count=42, end_cursor="CURSOR1", has_next=True, lsd="LSDTOKEN"):
    payload = {"require": [{"__bbox": {"result": {"data": {
        "ad_library_main": {"search_results_connection":
                            _connection(ads, count, end_cursor, has_next)}}}}}]}
    return (
        '<html><script>__d("LSD",[],{"token":"' + lsd + '"},1);</script>'
        '<script type="application/json" data-sjs>' + json.dumps(payload)
        + "</script></html>"
    )


def _graphql_body(ads, end_cursor="CURSOR2", has_next=True, prefix=""):
    payload = {"data": {"ad_library_main": {"search_results_connection":
               _connection(ads, count=42, end_cursor=end_cursor, has_next=has_next)}}}
    return prefix + json.dumps(payload, ensure_ascii=False)


def _curl_result(status, body):
    out = body + "\n" + meta_ads_tool._STATUS_MARKER + str(status)
    return mock.Mock(returncode=0, stdout=out.encode())


_CHALLENGE_HTML = (
    "<html><script>fetch('/__rd_verify_abc?challenge=3', "
    "{method: 'POST'}).finally(() => window.location.reload());</script></html>"
)


class ParseTest(unittest.TestCase):
    def test_parse_html_extracts_ads_count_and_cursor(self):
        html = _search_html([_raw_ad("1"), _raw_ad("2", page_id="901")])

        ads, total, cursor, has_more = meta_ads_tool._parse_html(html)

        self.assertEqual(total, 42)
        self.assertEqual(cursor, "CURSOR1")
        self.assertTrue(has_more)
        self.assertEqual([a["id"] for a in ads], ["1", "2"])
        first = ads[0]
        self.assertEqual(first["pageName"], "Puzzle Studio")
        self.assertEqual(first["title"], "Match colors")
        self.assertEqual(first["body"], "Try a funny matching game")
        self.assertEqual(first["ctaText"], "게임하기")
        self.assertEqual(first["thumbnail"], "https://scontent.test/preview.jpg")
        self.assertEqual(first["videoUrl"], "https://video.test/ad.mp4")
        self.assertTrue(first["isActive"])
        self.assertIn("id=1", first["url"])

    def test_parse_html_dedupes_by_ad_id(self):
        ads, _, _, _ = meta_ads_tool._parse_html(_search_html([_raw_ad("1"), _raw_ad("1")]))
        self.assertEqual(len(ads), 1)

    def test_parse_html_ignores_broken_json(self):
        html = '<script type="application/json">{"ad_archive_id": broken</script>'
        ads, total, cursor, has_more = meta_ads_tool._parse_html(html)
        self.assertEqual(ads, [])
        self.assertEqual(total, 0)
        self.assertEqual(cursor, "")
        self.assertFalse(has_more)

    def test_parse_ad_image_fallback(self):
        raw = _raw_ad("3")
        raw["snapshot"]["videos"] = []
        raw["snapshot"]["images"] = [
            {"resized_image_url": "https://scontent.test/resized.jpg",
             "original_image_url": "https://scontent.test/orig.jpg"}
        ]
        ad = meta_ads_tool._parse_ad(raw)
        self.assertEqual(ad["thumbnail"], "https://scontent.test/resized.jpg")
        self.assertEqual(ad["videoUrl"], "")

    def test_parse_ad_carousel_card_fallback(self):
        raw = _raw_ad("4")
        raw["snapshot"].update({
            "title": None, "body": None, "cta_text": None, "link_url": None,
            "videos": [],
            "cards": [{
                "title": "Card title", "body": "Card body", "cta_text": "설치하기",
                "link_url": "https://example.test/app",
                "video_preview_image_url": "https://scontent.test/card.jpg",
                "video_sd_url": "https://video.test/card.mp4",
            }],
        })
        ad = meta_ads_tool._parse_ad(raw)
        self.assertEqual(ad["title"], "Card title")
        self.assertEqual(ad["body"], "Card body")
        self.assertEqual(ad["ctaText"], "설치하기")
        self.assertEqual(ad["linkUrl"], "https://example.test/app")
        self.assertEqual(ad["thumbnail"], "https://scontent.test/card.jpg")
        self.assertEqual(ad["videoUrl"], "https://video.test/card.mp4")

    def test_aggregate_pages_sorts_by_count(self):
        ads, _, _, _ = meta_ads_tool._parse_html(_search_html([
            _raw_ad("1", page_id="900", page_name="A"),
            _raw_ad("2", page_id="901", page_name="B"),
            _raw_ad("3", page_id="901", page_name="B"),
        ]))
        pages = meta_ads_tool._aggregate_pages(ads)
        self.assertEqual([p["pageId"] for p in pages], ["901", "900"])
        self.assertEqual(pages[0]["count"], 2)
        self.assertEqual(pages[0]["pageName"], "B")

    def test_parse_graphql_plain(self):
        body = _graphql_body([_raw_ad("5"), _raw_ad("6")], end_cursor="NEXT", has_next=True)
        ads, cursor, has_more = meta_ads_tool._parse_graphql(body)
        self.assertEqual([a["id"] for a in ads], ["5", "6"])
        self.assertEqual(cursor, "NEXT")
        self.assertTrue(has_more)

    def test_parse_graphql_strips_for_loop_prefix(self):
        body = _graphql_body([_raw_ad("7")], end_cursor="C", has_next=False, prefix="for (;;);")
        ads, cursor, has_more = meta_ads_tool._parse_graphql(body)
        self.assertEqual([a["id"] for a in ads], ["7"])
        self.assertFalse(has_more)

    def test_parse_graphql_raises_on_error_payload(self):
        with self.assertRaises(ValueError):
            meta_ads_tool._parse_graphql('for (;;);{"error":1357054,"errorSummary":"x"}')


class BuildTest(unittest.TestCase):
    def test_keyword_url(self):
        url = meta_ads_tool._build_url("퍼즐 게임", "KR", "keyword", "active", "all")
        self.assertIn("search_type=keyword_unordered", url)
        self.assertIn("country=KR", url)
        self.assertIn("q=%ED%8D%BC%EC%A6%90+%EA%B2%8C%EC%9E%84", url)
        self.assertNotIn("view_all_page_id", url)

    def test_page_url(self):
        url = meta_ads_tool._build_url("900", "ALL", "page", "all", "video")
        self.assertIn("search_type=page", url)
        self.assertIn("view_all_page_id=900", url)
        self.assertIn("media_type=video", url)

    def test_taiwan_is_supported_country(self):
        self.assertIn("TW", meta_ads_tool.COUNTRIES)

    def test_variables_keyword(self):
        v = meta_ads_tool._build_variables("방치형", "KR", "keyword", "active", "all", "CUR")
        self.assertEqual(v["queryString"], "방치형")
        self.assertEqual(v["countries"], ["KR"])
        self.assertEqual(v["cursor"], "CUR")
        self.assertEqual(v["searchType"], "keyword_unordered")
        self.assertEqual(v["viewAllPageID"], "0")

    def test_variables_page_and_all_country(self):
        v = meta_ads_tool._build_variables("900", "ALL", "page", "all", "all", "CUR")
        self.assertEqual(v["searchType"], "page")
        self.assertEqual(v["viewAllPageID"], "900")
        self.assertEqual(v["queryString"], "")
        self.assertEqual(v["countries"], [])


class FirstPageTest(unittest.TestCase):
    def setUp(self):
        cache_tool._cache.clear()
        meta_ads_tool._context.clear()
        p = mock.patch("meta_ads.meta_ads_tool.os.makedirs")
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        cache_tool._cache.clear()
        meta_ads_tool._context.clear()

    def test_fetch_first_page_ok(self):
        html = _search_html([_raw_ad("1")], lsd="MYLSD")
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, html)):
            ads, pages, total, cursor, has_more, lsd, error = \
                meta_ads_tool.fetch_first_page("puzzle", "KR", "keyword", "active", "all")
        self.assertIsNone(error)
        self.assertEqual(len(ads), 1)
        self.assertEqual(total, 42)
        self.assertEqual(cursor, "CURSOR1")
        self.assertTrue(has_more)
        self.assertEqual(lsd, "MYLSD")
        self.assertEqual(pages[0]["pageId"], "900")

    def test_fetch_first_page_solves_challenge(self):
        html = _search_html([_raw_ad("1")])
        responses = [
            _curl_result(403, _CHALLENGE_HTML),
            _curl_result(200, ""),
            _curl_result(200, html),
        ]
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        side_effect=responses) as run:
            ads, *_ , error = meta_ads_tool.fetch_first_page(
                "puzzle", "KR", "keyword", "active", "all")
        self.assertIsNone(error)
        self.assertEqual(len(ads), 1)
        challenge_call = run.call_args_list[1].args[0]
        self.assertIn("https://www.facebook.com/__rd_verify_abc?challenge=3", challenge_call)
        self.assertIn("POST", challenge_call)

    def test_fetch_first_page_timeout(self):
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=45)):
            ads, _, _, _, _, _, error = meta_ads_tool.fetch_first_page(
                "puzzle", "KR", "keyword", "active", "all")
        self.assertEqual(ads, [])
        self.assertEqual(error["kind"], "timeout")

    def test_fetch_first_page_curl_failure(self):
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=mock.Mock(returncode=6, stdout=b"")):
            ads, _, _, _, _, _, error = meta_ads_tool.fetch_first_page(
                "puzzle", "KR", "keyword", "active", "all")
        self.assertEqual(ads, [])
        self.assertEqual(error, {"account": "puzzle", "kind": "http", "code": None})


class FetchMoreTest(unittest.TestCase):
    def setUp(self):
        cache_tool._cache.clear()
        p = mock.patch("meta_ads.meta_ads_tool.os.makedirs")
        p.start()
        self.addCleanup(p.stop)
        # Ensure config doc_ids fall back to the built-in default.
        lp = mock.patch("meta_ads.meta_ads_tool._load_doc_ids",
                        return_value=["24922295957467452"])
        lp.start()
        self.addCleanup(lp.stop)

    def test_fetch_more_ok_sends_docid_and_cursor(self):
        body = _graphql_body([_raw_ad("10"), _raw_ad("11")], end_cursor="C2", has_next=True)
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, body)) as run:
            ads, cursor, has_more, error = meta_ads_tool.fetch_more(
                "puzzle", "KR", "keyword", "active", "all",
                "C1", "LSD", "sess-1")
        self.assertIsNone(error)
        self.assertEqual([a["id"] for a in ads], ["10", "11"])
        self.assertEqual(cursor, "C2")
        self.assertTrue(has_more)
        # the POST carries the pagination doc_id and the incoming cursor
        cmd = run.call_args.args[0]
        joined = " ".join(cmd)
        self.assertIn("24922295957467452", joined)
        self.assertIn("C1", joined)

    def test_fetch_more_requires_cursor_and_lsd(self):
        ads, cursor, has_more, error = meta_ads_tool.fetch_more(
            "puzzle", "KR", "keyword", "active", "all", "", "", "s")
        self.assertEqual(ads, [])
        self.assertEqual(error["kind"], "parse")

    def test_fetch_more_error_payload_flags_docid_expired(self):
        body = 'for (;;);{"error":1357054,"errorSummary":"x"}'
        flagged = []
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, body)), \
             mock.patch("meta_ads.meta_ads_tool._flag_doc_id_expired",
                        side_effect=lambda: flagged.append(True)):
            ads, cursor, has_more, error = meta_ads_tool.fetch_more(
                "puzzle", "KR", "keyword", "active", "all", "C1", "LSD", "s")
        self.assertEqual(ads, [])
        self.assertEqual(error["kind"], "doc_id_expired")
        self.assertTrue(flagged)

    def test_fetch_more_http_error(self):
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(429, "")):
            ads, _, _, error = meta_ads_tool.fetch_more(
                "puzzle", "KR", "keyword", "active", "all", "C1", "LSD", "s")
        self.assertEqual(ads, [])
        self.assertEqual(error, {"account": "puzzle", "kind": "http", "code": 429})


class GetMetaAdsTest(unittest.TestCase):
    def setUp(self):
        cache_tool._cache.clear()
        meta_ads_tool._context.clear()
        p = mock.patch("meta_ads.meta_ads_tool.os.makedirs")
        p.start()
        self.addCleanup(p.stop)
        lp = mock.patch("meta_ads.meta_ads_tool._load_doc_ids",
                        return_value=["24922295957467452"])
        lp.start()
        self.addCleanup(lp.stop)

    def tearDown(self):
        cache_tool._cache.clear()
        meta_ads_tool._context.clear()

    def test_first_page_negative_ttl_on_error(self):
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=mock.Mock(returncode=6, stdout=b"")):
            data, _, errors, cache_ttl = meta_ads_tool.get_meta_ads(
                "puzzle", "KR", "keyword", "active", "all", False)
        self.assertEqual(data["ads"], [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(cache_ttl, meta_ads_tool.NEGATIVE_CACHE_TTL)

    def test_first_page_success_stores_context_and_cursor(self):
        html = _search_html([_raw_ad("1")], lsd="MYLSD", has_next=True)
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, html)):
            data, _, errors, cache_ttl = meta_ads_tool.get_meta_ads(
                "puzzle", "KR", "keyword", "active", "all", False)
        self.assertEqual(len(data["ads"]), 1)
        self.assertEqual(data["cursor"], "CURSOR1")
        self.assertTrue(data["hasMore"])
        self.assertEqual(errors, [])
        self.assertGreater(cache_ttl, meta_ads_tool.NEGATIVE_CACHE_TTL)
        key = ("meta_ads", "keyword", "puzzle", "KR", "active", "all")
        self.assertEqual(meta_ads_tool._context[key]["lsd"], "MYLSD")

    def test_has_more_false_when_no_lsd(self):
        html = _search_html([_raw_ad("1")], lsd="", has_next=True).replace('__d("LSD",[],{"token":""},1);', "")
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, html)):
            data, _, _, _ = meta_ads_tool.get_meta_ads(
                "puzzle", "KR", "keyword", "active", "all", False)
        self.assertFalse(data["hasMore"])

    def test_pagination_uses_stored_lsd(self):
        html = _search_html([_raw_ad("1")], lsd="MYLSD", has_next=True)
        page2 = _graphql_body([_raw_ad("2"), _raw_ad("3")], end_cursor="CURSOR2", has_next=False)
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, html)):
            meta_ads_tool.get_meta_ads("puzzle", "KR", "keyword", "active", "all", False)
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, page2)) as run:
            data, _, errors, _ = meta_ads_tool.get_meta_ads(
                "puzzle", "KR", "keyword", "active", "all", False, cursor="CURSOR1")
        self.assertEqual(errors, [])
        self.assertEqual([a["id"] for a in data["ads"]], ["2", "3"])
        self.assertEqual(data["cursor"], "CURSOR2")
        self.assertFalse(data["hasMore"])
        joined = " ".join(run.call_args.args[0])
        self.assertIn("MYLSD", joined)

    def test_first_page_serves_cache_without_refetch(self):
        html = _search_html([_raw_ad("1")])
        with mock.patch("meta_ads.meta_ads_tool.subprocess.run",
                        return_value=_curl_result(200, html)) as run:
            meta_ads_tool.get_meta_ads("puzzle", "KR", "keyword", "active", "all", False)
            first = run.call_count
            meta_ads_tool.get_meta_ads("puzzle", "KR", "keyword", "active", "all", False)
        self.assertEqual(run.call_count, first)


if __name__ == "__main__":
    unittest.main()
