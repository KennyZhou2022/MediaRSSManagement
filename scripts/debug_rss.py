import argparse
import json
import os
import feedparser

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rss_manager import RSSManager
from src.general.general_constant import STORAGE_PATH, LOG_DIR


def pretty_print_storage_entry(e):
    print(json.dumps(e, indent=4, ensure_ascii=False))


def list_rss(mgr: RSSManager):
    rss = mgr.list_rss()
    if not rss:
        print("No RSS entries found in storage.")
        return
    for rss_id, data in rss.items():
        print(f"- {rss_id}: {data.get('title', data.get('url'))} (interval={data.get('interval')})")


def check_rss_once(mgr: RSSManager, rss_id: str):
    if rss_id not in mgr.storage.get("rss", {}):
        print(f"RSS id '{rss_id}' not found in storage.")
        return
    print(f"Running check_rss for '{rss_id}'...")
    mgr.check_rss(rss_id)
    # show updated storage entry
    entry = mgr.storage["rss"][rss_id]
    print("Updated storage entry:")
    pretty_print_storage_entry(entry)


def fetch_url(url: str, show_entries: int = 5):
    print(f"Fetching URL: {url}")
    feed = feedparser.parse(url)
    if feed.bozo:
        print(f"Fetch error: {feed.bozo_exception}")
        return
    print(f"Feed title: {getattr(feed.feed, 'title', '')}")
    print(f"Entries: {len(feed.entries)}")
    for i, entry in enumerate(feed.entries[:show_entries]):
        print(f"\nEntry #{i+1}")
        print(f" title: {getattr(entry, 'title', '')}")
        print(f" link: {getattr(entry, 'link', '')}")
        print(f" published: {getattr(entry, 'published', '')}")


def show_logs(rss_id: str):
    path = os.path.join(LOG_DIR, f"{rss_id}.log")
    if not os.path.exists(path):
        print(f"No log file: {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        print(f.read())


def show_storage():
    if not os.path.exists(STORAGE_PATH):
        print("No storage file found.")
        return
    with open(STORAGE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(data, indent=4, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Debug RSS helper for MediaManagement")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List RSS entries in storage")

    c_check = sub.add_parser("check", help="Run check_rss for an rss id from storage")
    c_check.add_argument("rss_id")

    c_fetch = sub.add_parser("fetch-url", help="Fetch arbitrary RSS/Atom URL and print top entries")
    c_fetch.add_argument("url")
    c_fetch.add_argument("--count", type=int, default=5, help="How many entries to show")

    c_logs = sub.add_parser("show-logs", help="Show log file for a given rss id")
    c_logs.add_argument("rss_id")

    sub.add_parser("show-storage", help="Print storage.json contents")

    args = p.parse_args()

    mgr = RSSManager()

    if args.cmd == "list":
        list_rss(mgr)
    elif args.cmd == "check":
        check_rss_once(mgr, args.rss_id)
    elif args.cmd == "fetch-url":
        fetch_url(args.url, args.count)
    elif args.cmd == "show-logs":
        show_logs(args.rss_id)
    elif args.cmd == "show-storage":
        show_storage()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
