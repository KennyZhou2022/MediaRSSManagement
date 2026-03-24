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

def save_torrent_list(rss_id: str):

    def load_torrent_list():
        torrent_list_path = os.path.join(STORAGE_DIR, f"{rss_id}_torrents_list.json")
        if not os.path.exists(torrent_list_path):
            return {}
        with open(torrent_list_path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    RSS_test = RSSManager()
    RSS_test.load_storage()

    item = RSSItem(**RSS_test.storage["rss"][rss_id])
    feed = feedparser.parse(item.url)
    print(feed)

    torrent_dict = load_torrent_list()

    for entry in feed.entries:
        torrent_dict[entry.title] = entry.links[1]['href']
    with open(os.path.join(STORAGE_DIR, f"{rss_id}_torrents_list.json"), "w", encoding="utf-8") as f:
        json.dump(torrent_dict, f, indent=4, ensure_ascii=False)

def split_str(s):
    ss = [sss for sss in s.split(';') if sss.strip()]
    return ss

def find_str(key_words, title):
    for key_word in key_words:

        parts = key_word.split()

        if all(part in title for part in parts):
            print('Match!')

if __name__ == "__main__":
    # rss_id = "c7a8e9fe-042e-4730-8dba-91a04bb7e8e9"
    # save_torrent_list(rss_id)
    str_test = "隐身的名字 DV;分割"
    ss = split_str(str_test)
    print(ss)
    str_test2 = "Vanished Name S01E05 2026 2160p WEB-DL H265 DV DDP5.1-ADWeb[隐身的名字 第05集 | 类型：剧情 悬疑 | 主演：倪妮 闫妮 刘雅瑟 刘敏涛 保剑锋 *云视听极光*]"
    find_str(ss, str_test2)