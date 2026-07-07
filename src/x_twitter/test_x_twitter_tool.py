import json
import subprocess
import tempfile
import unittest
from unittest import mock

from shared import accounts_tool, cache_tool
from x_twitter import x_twitter_tool


def _tweet(tweet_id="1", text="hello"):
    return {
        "id_str": tweet_id,
        "user": {"name": "OpenAI"},
        "full_text": text,
        "favorite_count": 11,
        "reply_count": 2,
        "retweet_count": 3,
        "views": {"count": "44"},
        "mediaDetails": [{"media_url_https": "https://img.test/x.jpg"}],
        "created_at": "Mon Jan 01 00:00:00 +0000 2024",
    }


class XTwitterToolTest(unittest.TestCase):
    def setUp(self):
        accounts_tool._sources.clear()
        cache_tool._cache.clear()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_patch = mock.patch(
            "shared.accounts_tool.settings.CONFIG_DIR", self.tmpdir.name
        )
        self.config_patch.start()
        x_twitter_tool.register()

    def tearDown(self):
        self.config_patch.stop()
        self.tmpdir.cleanup()
        accounts_tool._sources.clear()
        cache_tool._cache.clear()

    def test_register_preserves_case(self):
        source = accounts_tool.get_source("x")

        self.assertTrue(source["preserve_case"])

    def test_find_timeline_entries_nested(self):
        entries = [{"content": {}}]
        nested = {"props": [{"deep": {"timeline": {"entries": entries}}}]}

        self.assertIs(x_twitter_tool._find_timeline_entries(nested), entries)
        self.assertIsNone(x_twitter_tool._find_timeline_entries({"no": "timeline"}))

    def test_fetch_x_posts_parses_next_data_html(self):
        data = {
            "props": {
                "pageProps": {
                    "timeline": {
                        "entries": [
                            {"content": {"tweet": _tweet("123", "  full text  ")}},
                            {"content": {"tweet": {"favorite_count": None}}},
                        ]
                    }
                }
            }
        }
        html = (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(data)
            + "</script></html>"
        )
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=html.encode(), stderr=b""
        )
        with mock.patch(
            "x_twitter.x_twitter_tool.subprocess.run", return_value=fake_result
        ) as mocked_run:
            posts, error = x_twitter_tool.fetch_x_posts("Open AI")

        call_args = mocked_run.call_args
        cmd = call_args[0][0]
        self.assertIn("Open%20AI", cmd[-1])
        self.assertIsNone(error)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["account"], "Open AI")
        self.assertEqual(posts[0]["name"], "OpenAI")
        self.assertEqual(posts[0]["text"], "full text")
        self.assertEqual(posts[0]["likes"], 11)
        self.assertEqual(posts[0]["replies"], 2)
        self.assertEqual(posts[0]["retweets"], 3)
        self.assertEqual(posts[0]["views"], 44)
        self.assertEqual(posts[0]["media"], "https://img.test/x.jpg")
        self.assertEqual(posts[0]["url"], "https://x.com/Open AI/status/123")

    def test_fetch_x_posts_tweet_result_fallback_and_exception(self):
        data = {
            "timeline": {
                "entries": [
                    {"content": {"tweetResult": {"result": _tweet("fallback")}}}
                ]
            }
        }
        html_bytes = ('<script id="__NEXT_DATA__">%s</script>' % json.dumps(data)).encode()

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=html_bytes, stderr=b""
        )
        with mock.patch(
            "x_twitter.x_twitter_tool.subprocess.run", return_value=fake_result
        ):
            posts, error = x_twitter_tool.fetch_x_posts("OpenAI")
            self.assertEqual(
                posts[0]["url"],
                "https://x.com/OpenAI/status/fallback",
            )
            self.assertIsNone(error)

        with mock.patch(
            "x_twitter.x_twitter_tool.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=15),
        ):
            posts, error = x_twitter_tool.fetch_x_posts("OpenAI")

        self.assertEqual(posts, [])
        self.assertEqual(error, {"account": "OpenAI", "kind": "timeout", "code": None})

    def test_get_x_posts_cache_key_includes_accounts_tuple(self):
        path = accounts_tool.get_source("x")["path"]
        with open(path, "w") as f:
            json.dump(["OpenAI", "GoogleDeepMind"], f)

        calls = []

        def fake_fetch(account):
            calls.append(account)
            return [{"account": account}], None

        with mock.patch(
            "x_twitter.x_twitter_tool.fetch_x_posts", side_effect=fake_fetch
        ):
            posts, accounts, fetched_at, errors, cache_ttl = x_twitter_tool.get_x_posts(False)
            posts2, accounts2, fetched_at2, errors2, cache_ttl2 = x_twitter_tool.get_x_posts(False)

        self.assertEqual(accounts, ["OpenAI", "GoogleDeepMind"])
        self.assertEqual(accounts2, accounts)
        self.assertEqual(posts, [{"account": "OpenAI"}, {"account": "GoogleDeepMind"}])
        self.assertEqual(posts2, posts)
        self.assertEqual(errors, [])
        self.assertEqual(errors2, [])
        self.assertEqual(cache_ttl, 3600)
        self.assertEqual(cache_ttl2, 3600)
        self.assertEqual(fetched_at2, fetched_at)
        self.assertEqual(calls, ["OpenAI", "GoogleDeepMind"])
        self.assertIn(("x", ("OpenAI", "GoogleDeepMind")), cache_tool._cache)

    def test_get_x_posts_negative_error_uses_short_cache_ttl(self):
        path = accounts_tool.get_source("x")["path"]
        with open(path, "w") as f:
            json.dump(["OpenAI"], f)

        def fake_fetch(account):
            return [], {"account": account, "kind": "http", "code": 429}

        with mock.patch("x_twitter.x_twitter_tool.fetch_x_posts", side_effect=fake_fetch):
            posts, accounts, fetched_at, errors, cache_ttl = x_twitter_tool.get_x_posts(False)

        self.assertEqual(posts, [])
        self.assertEqual(accounts, ["OpenAI"])
        self.assertGreater(fetched_at, 0)
        self.assertEqual(errors, [{"account": "OpenAI", "kind": "http", "code": 429}])
        self.assertEqual(cache_ttl, 120)


if __name__ == "__main__":
    unittest.main()
