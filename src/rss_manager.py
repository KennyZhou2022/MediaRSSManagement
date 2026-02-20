import feedparser
import threading
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from src.general.general_class import RSSItem
import src.general.general_constant as GC

try:
    from transmission_rpc import Client
except ImportError:
    # Keep app startup working even if transmission-rpc is missing
    Client = None

class RSSManager:
    def __init__(self):
        # make sure storage dirs exist
        os.makedirs(GC.STORAGE_DIR, exist_ok=True)
        os.makedirs(GC.LOG_DIR, exist_ok=True)
        self.load_storage()
        self.tasks = {}  # timer thread

    # ---------------------
    # Storage
    # ---------------------
    @staticmethod
    def _default_storage():
        return {"rss": {}, "settings": {}}

    @staticmethod
    def _normalize_storage(raw_storage):
        if not isinstance(raw_storage, dict):
            raise ValueError("storage root must be a JSON object")
        rss = raw_storage.get("rss", {})
        settings = raw_storage.get("settings", {})
        if not isinstance(rss, dict):
            raise ValueError("storage.rss must be an object")
        if not isinstance(settings, dict):
            raise ValueError("storage.settings must be an object")
        return {"rss": rss, "settings": settings}

    @staticmethod
    def _backup_broken_storage():
        if not os.path.exists(GC.STORAGE_PATH):
            return
        backup_path = f"{GC.STORAGE_PATH}.broken-{int(time.time())}"
        try:
            os.replace(GC.STORAGE_PATH, backup_path)
            print(f"[storage] Invalid storage detected. Backed up to: {backup_path}")
        except OSError as exc:
            print(f"[storage] Failed to backup invalid storage file: {exc}")

    def load_storage(self):
        default_storage = self._default_storage()
        if not os.path.exists(GC.STORAGE_PATH):
            self.storage = default_storage
            self.save_storage()
            return

        try:
            with open(GC.STORAGE_PATH, "r", encoding="utf-8") as f:
                raw_storage = json.load(f)
            self.storage = self._normalize_storage(raw_storage)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f"[storage] Failed to load storage file, resetting to defaults: {exc}")
            self._backup_broken_storage()
            self.storage = default_storage
            self.save_storage()

    def save_storage(self):
        with open(GC.STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.storage, f, indent=4, ensure_ascii=False)

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
        # formatted timestamp using project constants
        ts = datetime.now(ZoneInfo(GC.TIME_ZONE)).strftime(GC.DATETIME_FORMAT)
        log_path = os.path.join(GC.LOG_DIR, f"{rss_id}.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    def get_logs(self, rss_id: str) -> str:
        log_path = os.path.join(GC.LOG_DIR, f"{rss_id}.log")
        if not os.path.exists(log_path):
            return ""
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()

    # ---------------------
    # Main RSS check logic
    # ---------------------
    def check_rss(self, rss_id: str):

        def save_torrent_list():

            def load_torrent_list():
                torrent_list_path = os.path.join(GC.STORAGE_DIR, f"{rss_id}_torrents_list.json")
                if not os.path.exists(torrent_list_path):
                    self.log(rss_id, f"No torrent list file found: {torrent_list_path}")
                    return {}
                with open(torrent_list_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            torrent_dict = load_torrent_list()
            new_torrent_dict = {}

            number_of_new = 0
            for entry in feed.entries:
                if entry.title not in torrent_dict:
                    torrent_dict[entry.title] = entry.links[1]['href']
                    new_torrent_dict[entry.title] = entry.links[1]['href']
                    number_of_new += 1
            with open(os.path.join(GC.STORAGE_DIR, f"{rss_id}_torrents_list.json"), "w", encoding="utf-8") as f:
                json.dump(torrent_dict, f, indent=4, ensure_ascii=False)
            self.log(rss_id, f"Saved {number_of_new} torrent links to {rss_id}_torrents_list.json")

            return new_torrent_dict


        def parse_rss():

            torrents_links = []
            number_of_new = 0

            if item.last_title != feed.entries[0].title:
                # RSS updated
                self.log(rss_id, "New torrent detected")

                for entry in feed.entries:
                    if entry.title != item.last_title:
                        torrents_links.append(entry.links[1]['href'])
                        number_of_new += 1

                self.log(rss_id, f"{number_of_new} new torrents found")
            return torrents_links


        def search_by_keywords(torrent_dict):

            torrent_links = []

            if not item.key_words:
                self.log(rss_id, "No keywords set, skipping keyword search")
                return []

            self.log(rss_id, f"Searching for keywords: {item.key_words}")

            key_words = [s.strip() for s in item.key_words.split(';') if s.strip()]

            for key_word in key_words:

                parts = key_word.split()

                for title, link in torrent_dict.items():
                    if all(part in title for part in parts):
                        torrent_links.append(link)

            self.log(rss_id, f"Found {len(torrent_links)} torrents matching keywords: {item.key_words}")
            return torrent_links


        def send_links_to_transmission(links: list, new_title: str = ""):
            # If Transmission settings are not configured, skip sending torrents
            tx_url = settings.get("transmission_url")
            tx_port = settings.get("transmission_port", GC.DEFAULT_TRANSMISSION_PORT)
            if Client is None:
                self.log(rss_id, "transmission-rpc is not installed in active Python environment; skipping send")
            elif not tx_url:
                self.log(rss_id, f"Transmission not configured, skipping sending torrents")
            else:
                try:
                    c = Client(host=tx_url,
                            port=tx_port,
                            username=settings.get("username", ""),
                            password=settings.get("password", ""))
                except Exception as e:
                    # Log the connection failure but do not crash the whole application
                    self.log(rss_id, f"Failed to connect to Transmission: {tx_url}:{tx_port} ({e})")
                    c = None

                if c:
                    for torrent_url in links:
                        try:
                            c.add_torrent(torrent_url, download_dir=item.path)
                            self.log(rss_id, f"Sent job to {item.path}: {torrent_url}")
                            # update last_title
                            item.last_title = new_title
                        except Exception as e:
                            self.log(rss_id, f"Failed to send torrent {torrent_url}: {e}")

        item = RSSItem(**self.storage["rss"][rss_id])
        settings = self.storage.get("settings", {})

        self.log(rss_id, "Fetching RSS...")
        feed = feedparser.parse(item.url)

        # fetch failed
        if feed.bozo:
            self.log(rss_id, f"Fetch failed: {feed.bozo_exception}")
            item.last_fetch = datetime.now(ZoneInfo(GC.TIME_ZONE)).strftime(GC.DATETIME_FORMAT)
            self.storage["rss"][rss_id] = item.dict()
            self.save_storage()
            return

        # Check if feed has entries
        if not feed.entries or len(feed.entries) == 0:
            self.log(rss_id, "RSS feed has no entries")
            item.last_fetch = datetime.now(ZoneInfo(GC.TIME_ZONE)).strftime(GC.DATETIME_FORMAT)
            self.storage["rss"][rss_id] = item.dict()
            self.save_storage()
            return

        if GC.PT_SITE_TYPES[item.pt_site] in [GC.FILTER]:
            new_torrent_dict = save_torrent_list()
            torrent_links = search_by_keywords(new_torrent_dict)
        else:
            torrent_links = parse_rss()

        send_links_to_transmission(torrent_links, new_title=feed.entries[0].title)

        item.last_fetch = datetime.now(ZoneInfo(GC.TIME_ZONE)).strftime(GC.DATETIME_FORMAT)
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
        try:
            self.schedule(rss_id)
        except Exception as e:
            # if scheduling fails, log the error
            self.log(rss_id, f"Failed to start task: {str(e)}")
            raise

    def start_all(self):
        for rss_id in self.storage["rss"].keys():
            self.start_task(rss_id)
