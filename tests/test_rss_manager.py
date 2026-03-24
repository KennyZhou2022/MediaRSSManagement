import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.general.general_constant as GC
from src.general.general_class import RSSItem, model_to_dict
from src.rss_manager import RSSManager


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

    def test_schedule_reschedules_after_check_exception(self):
        self._add_item()

        with patch.object(self.manager, "check_rss", side_effect=RuntimeError("boom")):
            with patch.object(self.manager, "_schedule_next_run") as mock_schedule_next:
                self.manager.schedule("feed-1")

        mock_schedule_next.assert_called_once_with("feed-1")

    def test_check_rss_tolerates_missing_torrent_link(self):
        item = self._add_item()
        feed = SimpleNamespace(
            bozo=False,
            entries=[SimpleNamespace(title="Episode 1", links=[{"rel": "alternate"}])],
        )

        with patch("src.rss_manager.feedparser.parse", return_value=feed):
            self.manager.check_rss(item.id)

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

        with patch("src.rss_manager.feedparser.parse", return_value=feed):
            self.manager.check_rss(item.id)

        saved = self.manager.storage["rss"][item.id]
        self.assertEqual(saved["last_status"], "OK")
        self.assertTrue(broken_cache.exists())
        cache_data = json.loads(broken_cache.read_text(encoding="utf-8"))
        self.assertIn("Episode 1", cache_data)


if __name__ == "__main__":
    unittest.main()
