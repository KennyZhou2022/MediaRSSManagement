import feedparser
import hashlib
import threading
import json
import os
from datetime import datetime
from typing import Dict
from transmission_rpc import Client

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.general.general_class import RSSItem
from src.rss_manager import RSSManager
from src.general.general_constant import STORAGE_DIR, STORAGE_PATH, LOG_DIR

def test_rss_fetch(rss_id: str):
    # RSS_test = RSSManager()
    # RSS_test.load_storage()

    # item = RSSItem(**RSS_test.storage["rss"][rss_id])
    # feed = feedparser.parse(item.url)
    # print(feed)

    c = Client(host="192.168.2.104", port=9091, username="admin", password="zzhhyy&045138Aa")

    torrents_links = ['https://hhanclub.top/download.php?id=191099&passkey=19dd35bc3756f00d945c36efc728c3fe']
    for torrent_url in torrents_links:
        c.add_torrent(torrent_url)
    print("ok")

if __name__ == "__main__":
    rss_id = 'bc3fad55-ca12-4942-a9ad-43e052b76bde'
    test_rss_fetch(rss_id)
