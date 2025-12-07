import feedparser
import hashlib
import time
import threading
import json
import os
from datetime import datetime
from typing import Dict
from models import RSSItem
from transmission_client import TransmissionClient


STORAGE_PATH = "storage.json"
LOG_DIR = "logs"


class RSSManager:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.load_storage()
        self.tasks = {}  # timer thread

    # ---------------------
    # Storage
    # ---------------------
    def load_storage(self):
        if not os.path.exists(STORAGE_PATH):
            self.storage = {"rss": {}, "settings": {}}
            self.save_storage()
        else:
            with open(STORAGE_PATH, "r") as f:
                self.storage = json.load(f)

    def save_storage(self):
        with open(STORAGE_PATH, "w") as f:
            json.dump(self.storage, f, indent=4)

    # ---------------------
    # RSS CRUD
    # ---------------------
    def add_rss(self, item: RSSItem):
        self.storage["rss"][item.id] = item.dict()
        self.save_storage()
        self.start_task(item.id)

    def delete_rss(self, rss_id: str):
        if rss_id in self.tasks:
            self.tasks[rss_id].cancel()
        self.storage["rss"].pop(rss_id, None)
        self.save_storage()

    def list_rss(self):
        return self.storage["rss"]

    # ---------------------
    # Log helper
    # ---------------------
    def log(self, rss_id: str, text: str):
        ts = datetime.utcnow().isoformat()
        with open(f"{LOG_DIR}/{rss_id}.log", "a") as f:
            f.write(f"[{ts}] {text}\n")

    def get_logs(self, rss_id: str) -> str:
        path = f"{LOG_DIR}/{rss_id}.log"
        if not os.path.exists(path):
            return ""
        with open(path, "r") as f:
            return f.read()

    # ---------------------
    # Hash helper
    # ---------------------
    def compute_feed_hash(self, feed) -> str:
        combined = "".join([entry.title + entry.link for entry in feed.entries])
        return hashlib.md5(combined.encode("utf-8")).hexdigest()

    # ---------------------
    # Main RSS check logic
    # ---------------------
    def check_rss(self, rss_id: str):
        item = RSSItem(**self.storage["rss"][rss_id])

        self.log(rss_id, "Fetching RSS...")
        feed = feedparser.parse(item.url)

        # fetch failed
        if feed.bozo:
            self.log(rss_id, f"Fetch failed: {feed.bozo_exception}")
            return

        new_hash = self.compute_feed_hash(feed)

        if item.last_hash != new_hash:
            # RSS updated
            self.log(rss_id, "New content detected")
            torrent_url = feed.entries[0].link

            settings = self.storage.get("settings", {})
            tc = TransmissionClient(
                settings.get("transmission_url"),
                settings.get("username", ""),
                settings.get("password", "")
            )

            ok = tc.add_torrent(torrent_url)
            if ok:
                self.log(rss_id, f"Sent job to Transmission: {torrent_url}")
            else:
                self.log(rss_id, f"Transmission failed: {torrent_url}")

            # update hash
            item.last_hash = new_hash

        item.last_fetch = datetime.utcnow().isoformat()
        self.storage["rss"][rss_id] = item.dict()
        self.save_storage()

    # ---------------------
    # Scheduled polling
    # ---------------------
    def schedule(self, rss_id: str):
        self.check_rss(rss_id)
        interval = self.storage["rss"][rss_id]["interval"]
        self.tasks[rss_id] = threading.Timer(interval * 60, self.schedule, args=[rss_id])
        self.tasks[rss_id].start()

    def start_task(self, rss_id: str):
        if rss_id in self.tasks:
            self.tasks[rss_id].cancel()
        self.schedule(rss_id)

    def start_all(self):
        for rss_id in self.storage["rss"].keys():
            self.start_task(rss_id)
