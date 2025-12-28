import feedparser
import threading
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from src.general.general_class import RSSItem
from transmission_rpc import Client
from src.general.general_constant import STORAGE_DIR, STORAGE_PATH, LOG_DIR, DEFAULT_TRANSMISSION_PORT, DATETIME_FORMAT, TIME_ZONE


class RSSManager:
    def __init__(self):
        # make sure storage dirs exist
        os.makedirs(STORAGE_DIR, exist_ok=True)
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
            with open(STORAGE_PATH, "r", encoding="utf-8") as f:
                self.storage = json.load(f)

    def save_storage(self):
        with open(STORAGE_PATH, "w", encoding="utf-8") as f:
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
        ts = datetime.now(ZoneInfo(TIME_ZONE)).strftime(DATETIME_FORMAT)
        log_path = os.path.join(LOG_DIR, f"{rss_id}.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    def get_logs(self, rss_id: str) -> str:
        log_path = os.path.join(LOG_DIR, f"{rss_id}.log")
        if not os.path.exists(log_path):
            return ""
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()

    # ---------------------
    # Main RSS check logic
    # ---------------------
    def check_rss(self, rss_id: str):

        def save_torrent_list():

            torrent_dict = load_torrent_list()

            for entry in feed.entries:
                torrent_dict[entry.title] = entry.links[1]['href']
            with open(os.path.join(STORAGE_DIR, f"{rss_id}_torrents_list.json"), "w", encoding="utf-8") as f:
                json.dump(torrent_dict, f, indent=4, ensure_ascii=False)
            self.log(rss_id, f"Saved {len(torrent_dict)} torrent links to {rss_id}_torrents_list.json")

            def load_torrent_list():
                torrent_list_path = os.path.join(STORAGE_DIR, f"{rss_id}_torrents_list.json")
                if not os.path.exists(torrent_list_path):
                    self.log(rss_id, f"No torrent list file found: {torrent_list_path}")
                    return {}
                with open(torrent_list_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        def parse_and_download():
            
            new_title = feed.entries[0].title

            if item.last_title != new_title:
                # RSS updated
                self.log(rss_id, "New content detected")

                number_of_new = 0
                torrents_links = []

                for entry in feed.entries:
                    if entry.title != item.last_title:
                        torrents_links.append(entry.links[1]['href'])
                        number_of_new += 1

                self.log(rss_id, f"{number_of_new} new torrents found")

                # If Transmission settings are not configured, skip sending torrents
                tx_url = settings.get("transmission_url")
                tx_port = settings.get("transmission_port", DEFAULT_TRANSMISSION_PORT)
                if not tx_url:
                    self.log(rss_id, f"Transmission not configured, skipping sending {number_of_new} torrents")
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
                        for torrent_url in torrents_links:
                            try:
                                c.add_torrent(torrent_url, download_dir=item.path)
                                self.log(rss_id, f"Sent job to {item.path}: {torrent_url}")
                                # update last_title
                                item.last_title = new_title
                            except Exception as e:
                                self.log(rss_id, f"Failed to send torrent {torrent_url}: {e}")
        def search_and_download():
            pass

        item = RSSItem(**self.storage["rss"][rss_id])
        settings = self.storage.get("settings", {})

        self.log(rss_id, "Fetching RSS...")
        feed = feedparser.parse(item.url)

        # fetch failed
        if feed.bozo:
            self.log(rss_id, f"Fetch failed: {feed.bozo_exception}")
            item.last_fetch = datetime.now(ZoneInfo(TIME_ZONE)).strftime(DATETIME_FORMAT)
            self.storage["rss"][rss_id] = item.dict()
            self.save_storage()
            return

        # Check if feed has entries
        if not feed.entries or len(feed.entries) == 0:
            self.log(rss_id, "RSS feed has no entries")
            item.last_fetch = datetime.now(ZoneInfo(TIME_ZONE)).strftime(DATETIME_FORMAT)
            self.storage["rss"][rss_id] = item.dict()
            self.save_storage()
            return

        if item.pt_site == 'Audience':
            save_torrent_list()

        if item.key_words == '' or item.key_words == None:
            parse_and_download()
        else:
            search_and_download()

        item.last_fetch = datetime.now(ZoneInfo(TIME_ZONE)).strftime(DATETIME_FORMAT)
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

