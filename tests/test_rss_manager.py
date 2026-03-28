import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.general.general_constant as GC
from src.general.general_class import RSSItem, model_to_dict
from src.rss_manager import RSSManager


class FakeResponse:
    def __init__(self, content: bytes = b"", status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        return None


class RSSManagerRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.storage_dir = self.base_path / "storage"
        self.logs_dir = self.storage_dir / "logs"
        self.storage_path = self.storage_dir / "storage.json"

        self.gc_patches = [
            patch.object(GC, "STORAGE_DIR", str(self.storage_dir)),
            patch.object(GC, "LOG_DIR", str(self.logs_dir)),
            patch.object(GC, "STORAGE_PATH", str(self.storage_path)),
        ]
        for gc_patch in self.gc_patches:
            gc_patch.start()

        self.manager = RSSManager()

    def tearDown(self):
        for gc_patch in reversed(self.gc_patches):
            gc_patch.stop()
        self.temp_dir.cleanup()

    def _add_item(self, **overrides):
        item = RSSItem(
            id=overrides.get("id", "feed-1"),
            name=overrides.get("name", "Feed"),
            url=overrides.get("url", "https://example.com/rss"),
            path=overrides.get("path", ""),
            interval=overrides.get("interval", 10),
            pt_site=overrides.get("pt_site", GC.DEFAULT_PT_SITE),
            key_words=overrides.get("key_words"),
            last_title=overrides.get("last_title"),
            last_fetch=overrides.get("last_fetch"),
            last_status=overrides.get("last_status"),
            last_error=overrides.get("last_error"),
        )
        self.manager.storage["rss"][item.id] = model_to_dict(item)
        self.manager.save_storage()
        return item

    def test_schedule_arms_next_run_and_dispatches_worker(self):
        self._add_item()

        with patch.object(self.manager, "_schedule_next_run") as mock_schedule_next:
            with patch.object(self.manager, "_start_check_thread") as mock_start_worker:
                self.manager.schedule("feed-1")

        mock_schedule_next.assert_called_once_with("feed-1", source="timer")
        mock_start_worker.assert_called_once_with("feed-1", "timer")

    def test_run_check_now_rejects_overlap(self):
        item = self._add_item()
        run_lock = self.manager._get_run_lock(item.id)
        run_lock.acquire()
        self.manager._set_active_run(
            item.id,
            {
                "run_id": "active123",
                "trigger": "timer",
                "started_at": "now",
                "started_monotonic": time.monotonic() - 5,
                "thread_name": "rss-check-feed-1",
            },
        )

        try:
            with self.assertRaises(RuntimeError):
                self.manager.run_check_now(item.id)
        finally:
            self.manager._clear_active_run(item.id)
            run_lock.release()

    def test_check_rss_tolerates_missing_torrent_link(self):
        item = self._add_item()
        feed = SimpleNamespace(
            bozo=False,
            entries=[SimpleNamespace(title="Episode 1", links=[{"rel": "alternate"}])],
        )

        with patch.object(self.manager, "_fetch_feed", return_value=feed):
            self.manager.check_rss(item.id, run_id="testrun")

        saved = self.manager.storage["rss"][item.id]
        self.assertEqual(saved["last_status"], "OK")
        self.assertIsNone(saved.get("last_error"))

    def test_check_rss_tolerates_invalid_filter_cache_json(self):
        item = self._add_item(pt_site=GC.AUDIENCES, key_words="Episode")
        broken_cache = self.storage_dir / f"{item.id}_torrents_list.json"
        broken_cache.write_text("{invalid json", encoding="utf-8")
        feed = SimpleNamespace(
            bozo=False,
            entries=[
                SimpleNamespace(
                    title="Episode 1",
                    links=[
                        {"rel": "alternate", "href": "https://example.com/view"},
                        {"rel": "enclosure", "type": "application/x-bittorrent", "href": "https://example.com/file.torrent"},
                    ],
                )
            ],
        )

        with patch.object(self.manager, "_fetch_feed", return_value=feed):
            self.manager.check_rss(item.id, run_id="testrun")

        saved = self.manager.storage["rss"][item.id]
        self.assertEqual(saved["last_status"], "OK")
        self.assertTrue(broken_cache.exists())
        cache_data = json.loads(broken_cache.read_text(encoding="utf-8"))
        self.assertIn("Episode 1", cache_data)

    def test_fetch_feed_uses_explicit_request_timeouts(self):
        item = self._add_item()
        response = FakeResponse(content=b"<rss><channel></channel></rss>", status_code=200)

        with patch("src.rss_manager.requests.get", return_value=response) as mock_get:
            with patch("src.rss_manager.feedparser.parse", return_value=SimpleNamespace(entries=[], bozo=False)):
                self.manager._fetch_feed(item.id, item, "testrun")

        mock_get.assert_called_once_with(
            item.url,
            timeout=(GC.RSS_REQUEST_CONNECT_TIMEOUT, GC.RSS_REQUEST_READ_TIMEOUT),
            headers={"User-Agent": "MediaRSSManagement/1.1"},
        )


if __name__ == "__main__":
    unittest.main()
