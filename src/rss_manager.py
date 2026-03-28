import feedparser
import threading
import json
import os
import time
import traceback
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from src.general.general_class import RSSItem, model_to_dict
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
        self.state_lock = threading.RLock()
        self.load_storage()
        self.tasks = {}  # timer thread
        self.feed_run_locks = {}
        self.active_runs = {}

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
        with self.state_lock:
            with open(GC.STORAGE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.storage, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _now_str():
        return datetime.now(ZoneInfo(GC.TIME_ZONE)).strftime(GC.DATETIME_FORMAT)

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        return str(exc) or exc.__class__.__name__

    @staticmethod
    def _entry_title(entry, fallback: str) -> str:
        return getattr(entry, "title", "") or fallback

    @staticmethod
    def _extract_torrent_link(entry):
        links = getattr(entry, "links", []) or []
        for link in links:
            href = link.get("href")
            rel = str(link.get("rel", "")).lower()
            link_type = str(link.get("type", "")).lower()
            if href and (rel == "enclosure" or "bittorrent" in link_type):
                return href
        for link in links:
            href = link.get("href")
            if href:
                return href
        return None

    @staticmethod
    def _format_duration(seconds: float) -> str:
        return f"{seconds:.2f}s"

    def _manager_log_path(self):
        return os.path.join(GC.LOG_DIR, "manager.log")

    def log_manager(self, text: str):
        ts = self._now_str()
        with open(self._manager_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    def _log_feed_event(self, rss_id: str, message: str, include_manager: bool = True):
        self.log(rss_id, message)
        if include_manager:
            self.log_manager(f"[{rss_id}] {message}")

    def _get_run_lock(self, rss_id: str):
        with self.state_lock:
            run_lock = self.feed_run_locks.get(rss_id)
            if run_lock is None:
                run_lock = threading.Lock()
                self.feed_run_locks[rss_id] = run_lock
            return run_lock

    def _set_active_run(self, rss_id: str, run_meta: dict):
        with self.state_lock:
            self.active_runs[rss_id] = run_meta

    def _clear_active_run(self, rss_id: str):
        with self.state_lock:
            self.active_runs.pop(rss_id, None)

    def _get_active_run(self, rss_id: str):
        with self.state_lock:
            run_meta = self.active_runs.get(rss_id)
            return dict(run_meta) if run_meta else None

    def _new_run_id(self):
        return uuid.uuid4().hex[:8]

    def _interval_seconds(self, rss_id: str) -> int:
        rss_data = self.storage["rss"].get(rss_id, {})
        interval = rss_data.get("interval", GC.DEFAULT_RSS_INTERVAL)
        try:
            return max(int(interval), 1) * 60
        except (TypeError, ValueError):
            return GC.DEFAULT_RSS_INTERVAL * 60

    def _fetch_feed(self, rss_id: str, item: RSSItem, run_id: str):
        timeout = (GC.RSS_REQUEST_CONNECT_TIMEOUT, GC.RSS_REQUEST_READ_TIMEOUT)
        started = time.monotonic()
        self._log_feed_event(
            rss_id,
            f"run={run_id} rss-fetch-start timeout_connect={GC.RSS_REQUEST_CONNECT_TIMEOUT}s timeout_read={GC.RSS_REQUEST_READ_TIMEOUT}s url={item.url}",
        )
        response = requests.get(
            item.url,
            timeout=timeout,
            headers={"User-Agent": "MediaRSSManagement/1.1"},
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        elapsed = time.monotonic() - started
        self._log_feed_event(
            rss_id,
            f"run={run_id} rss-fetch-done status_code={response.status_code} bytes={len(response.content)} entries={len(getattr(feed, 'entries', []) or [])} elapsed={self._format_duration(elapsed)}",
        )
        return feed

    def _persist_item(self, item: RSSItem):
        with self.state_lock:
            if item.id not in self.storage["rss"]:
                return
            self.storage["rss"][item.id] = model_to_dict(item)
            self.save_storage()

    def _mark_feed_result(self, item: RSSItem, status: str, error: str = ""):
        item.last_fetch = self._now_str()
        item.last_status = status
        item.last_error = error or None
        self._persist_item(item)

    # ---------------------
    # RSS CRUD
    # ---------------------
    def add_rss(self, item: RSSItem):
        with self.state_lock:
            self.storage["rss"][item.id] = model_to_dict(item)
            self.save_storage()
        self.start_task(item.id)

    def delete_rss(self, rss_id: str):
        with self.state_lock:
            timer = self.tasks.pop(rss_id, None)
            if timer:
                timer.cancel()
            self.storage["rss"].pop(rss_id, None)
            self.feed_run_locks.pop(rss_id, None)
            self.active_runs.pop(rss_id, None)
            self.save_storage()

    def list_rss(self):
        with self.state_lock:
            return dict(self.storage["rss"])

    # ---------------------
    # Log helper
    # ---------------------
    def log(self, rss_id: str, text: str):
        # formatted timestamp using project constants
        ts = self._now_str()
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
    def check_rss(self, rss_id: str, *, trigger: str = "manual", run_id: str | None = None):
        if rss_id not in self.storage["rss"]:
            raise KeyError(f"RSS feed not found: {rss_id}")
        run_id = run_id or self._new_run_id()

        def save_torrent_list():

            def load_torrent_list():
                torrent_list_path = os.path.join(GC.STORAGE_DIR, f"{rss_id}_torrents_list.json")
                if not os.path.exists(torrent_list_path):
                    self.log(rss_id, f"No torrent list file found: {torrent_list_path}")
                    return {}
                try:
                    with open(torrent_list_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data if isinstance(data, dict) else {}
                except (OSError, json.JSONDecodeError) as exc:
                    self._log_feed_event(rss_id, f"run={run_id} torrent-cache-load-failed error={self._safe_error_message(exc)}")
                    return {}

            torrent_dict = load_torrent_list()
            new_torrent_dict = {}

            number_of_new = 0
            for entry in feed.entries:
                title = self._entry_title(entry, f"entry-{len(torrent_dict) + number_of_new + 1}")
                torrent_link = self._extract_torrent_link(entry)
                if not torrent_link:
                    self._log_feed_event(rss_id, f"run={run_id} entry-skipped reason=no_usable_torrent_link title={title}")
                    continue
                if title not in torrent_dict:
                    torrent_dict[title] = torrent_link
                    new_torrent_dict[title] = torrent_link
                    number_of_new += 1
            with open(os.path.join(GC.STORAGE_DIR, f"{rss_id}_torrents_list.json"), "w", encoding="utf-8") as f:
                json.dump(torrent_dict, f, indent=4, ensure_ascii=False)
            self._log_feed_event(rss_id, f"run={run_id} torrent-cache-saved new_entries={number_of_new} file={rss_id}_torrents_list.json")

            return new_torrent_dict


        def parse_rss():

            torrents_links = []
            number_of_new = 0
            newest_title = self._entry_title(feed.entries[0], "")

            if item.last_title != newest_title:
                # RSS updated
                self._log_feed_event(rss_id, f"run={run_id} new-torrent-detected")

                for entry in feed.entries:
                    title = self._entry_title(entry, "")
                    if title != item.last_title:
                        torrent_link = self._extract_torrent_link(entry)
                        if not torrent_link:
                            self._log_feed_event(rss_id, f"run={run_id} entry-skipped reason=no_usable_torrent_link title={title or 'unknown'}")
                            continue
                        torrents_links.append(torrent_link)
                        number_of_new += 1

                self._log_feed_event(rss_id, f"run={run_id} new-torrents-found count={number_of_new}")
            return torrents_links


        def search_by_keywords(torrent_dict):

            torrent_links = []

            if not item.key_words:
                self._log_feed_event(rss_id, f"run={run_id} keyword-search-skipped reason=no_keywords")
                return []

            self._log_feed_event(rss_id, f"run={run_id} keyword-search-start keywords={item.key_words}")

            key_words = [s.strip() for s in item.key_words.split(';') if s.strip()]

            for key_word in key_words:

                parts = key_word.split()

                for title, link in torrent_dict.items():
                    if all(part in title for part in parts):
                        torrent_links.append(link)

            self._log_feed_event(rss_id, f"run={run_id} keyword-search-done matches={len(torrent_links)} keywords={item.key_words}")
            return torrent_links


        def send_links_to_transmission(links: list, new_title: str = ""):
            # If Transmission settings are not configured, skip sending torrents
            tx_url = settings.get("transmission_url")
            tx_port = settings.get("transmission_port", GC.DEFAULT_TRANSMISSION_PORT)
            if Client is None:
                self._log_feed_event(rss_id, f"run={run_id} transmission-skipped reason=client_not_installed")
            elif not tx_url:
                self._log_feed_event(rss_id, f"run={run_id} transmission-skipped reason=not_configured")
            else:
                try:
                    c = Client(host=tx_url,
                            port=tx_port,
                            username=settings.get("username", ""),
                            password=settings.get("password", ""),
                            timeout=GC.TRANSMISSION_RPC_TIMEOUT)
                except Exception as e:
                    # Log the connection failure but do not crash the whole application
                    self._log_feed_event(
                        rss_id,
                        f"run={run_id} transmission-connect-failed host={tx_url} port={tx_port} timeout={GC.TRANSMISSION_RPC_TIMEOUT}s error={self._safe_error_message(e)}",
                    )
                    c = None

                if c:
                    for torrent_url in links:
                        try:
                            c.add_torrent(torrent_url, download_dir=item.path)
                            self._log_feed_event(rss_id, f"run={run_id} transmission-send-ok download_dir={item.path or '-'} torrent={torrent_url}")
                            # update last_title
                            item.last_title = new_title
                        except Exception as e:
                            self._log_feed_event(rss_id, f"run={run_id} transmission-send-failed torrent={torrent_url} error={self._safe_error_message(e)}")

        item = RSSItem(**self.storage["rss"][rss_id])
        settings = self.storage.get("settings", {})

        try:
            started = time.monotonic()
            self._log_feed_event(rss_id, f"run={run_id} check-start trigger={trigger} interval_min={item.interval}")
            feed = self._fetch_feed(rss_id, item, run_id)

            # fetch failed
            if feed.bozo:
                message = f"Fetch failed: {feed.bozo_exception}"
                self._log_feed_event(rss_id, f"run={run_id} rss-parse-failed error={self._safe_error_message(feed.bozo_exception)}")
                self._mark_feed_result(item, "ERROR", self._safe_error_message(feed.bozo_exception))
                return

            # Check if feed has entries
            if not feed.entries or len(feed.entries) == 0:
                message = "RSS feed has no entries"
                self._log_feed_event(rss_id, f"run={run_id} rss-empty")
                self._mark_feed_result(item, "EMPTY", message)
                return

            pt_site_type = GC.PT_SITE_TYPES.get(item.pt_site, GC.DIRECT)
            if item.pt_site not in GC.PT_SITE_TYPES:
                self._log_feed_event(rss_id, f"run={run_id} pt-site-unknown pt_site={item.pt_site} fallback=direct")

            if pt_site_type == GC.FILTER:
                new_torrent_dict = save_torrent_list()
                torrent_links = search_by_keywords(new_torrent_dict)
            else:
                torrent_links = parse_rss()

            new_title = self._entry_title(feed.entries[0], item.last_title or "")
            send_links_to_transmission(torrent_links, new_title=new_title)

            item.last_status = "OK"
            item.last_error = None
            item.last_fetch = self._now_str()
            self._persist_item(item)
            self._log_feed_event(
                rss_id,
                f"run={run_id} check-finish trigger={trigger} result=OK discovered_links={len(torrent_links)} elapsed={self._format_duration(time.monotonic() - started)}",
            )
        except Exception as exc:
            error_message = self._safe_error_message(exc)
            trace = traceback.format_exc().strip().replace("\n", " | ")
            self._log_feed_event(rss_id, f"run={run_id} check-failed trigger={trigger} error={error_message} traceback={trace}")
            self._mark_feed_result(item, "ERROR", error_message)
            raise


    # ---------------------
    # Scheduled polling
    # ---------------------
    def _schedule_next_run(self, rss_id: str, delay_seconds: int | None = None, *, source: str = "schedule"):
        with self.state_lock:
            rss_data = self.storage["rss"].get(rss_id)
            if not rss_data:
                timer = self.tasks.pop(rss_id, None)
                if timer:
                    timer.cancel()
                return

            interval_seconds = delay_seconds if delay_seconds is not None else self._interval_seconds(rss_id)
            timer = threading.Timer(interval_seconds, self.schedule, args=[rss_id])
            timer.daemon = True
            self.tasks[rss_id] = timer
            timer.start()

        self._log_feed_event(
            rss_id,
            f"scheduler-armed source={source} next_run_in={interval_seconds}s next_interval_min={max(interval_seconds // 60, 1)}",
        )

    def _run_check_with_lock(self, rss_id: str, trigger: str, run_id: str, run_lock: threading.Lock):
        started = time.monotonic()
        thread_name = threading.current_thread().name
        self._set_active_run(
            rss_id,
            {
                "run_id": run_id,
                "trigger": trigger,
                "started_at": self._now_str(),
                "started_monotonic": started,
                "thread_name": thread_name,
            },
        )
        try:
            self.check_rss(rss_id, trigger=trigger, run_id=run_id)
        except Exception as exc:
            self._log_feed_event(
                rss_id,
                f"run={run_id} worker-exit result=ERROR trigger={trigger} elapsed={self._format_duration(time.monotonic() - started)} error={self._safe_error_message(exc)}",
            )
        else:
            self._log_feed_event(
                rss_id,
                f"run={run_id} worker-exit result=OK trigger={trigger} elapsed={self._format_duration(time.monotonic() - started)}",
            )
        finally:
            self._clear_active_run(rss_id)
            run_lock.release()

    def _start_check_thread(self, rss_id: str, trigger: str):
        if rss_id not in self.storage["rss"]:
            return False

        run_lock = self._get_run_lock(rss_id)
        if not run_lock.acquire(blocking=False):
            active_run = self._get_active_run(rss_id)
            if active_run:
                active_for = time.monotonic() - active_run["started_monotonic"]
                self._log_feed_event(
                    rss_id,
                    f"scheduler-skip trigger={trigger} reason=previous_run_still_active active_run={active_run['run_id']} active_for={self._format_duration(active_for)} active_trigger={active_run['trigger']}",
                )
            else:
                self._log_feed_event(rss_id, f"scheduler-skip trigger={trigger} reason=previous_run_still_active")
            return False

        run_id = self._new_run_id()
        worker = threading.Thread(
            target=self._run_check_with_lock,
            args=(rss_id, trigger, run_id, run_lock),
            daemon=True,
            name=f"rss-check-{rss_id[:8]}",
        )
        worker.start()
        self._log_feed_event(rss_id, f"run={run_id} worker-start trigger={trigger} thread={worker.name}")
        return True

    def run_check_now(self, rss_id: str, trigger: str = "manual"):
        if rss_id not in self.storage["rss"]:
            raise KeyError(f"RSS feed not found: {rss_id}")

        run_lock = self._get_run_lock(rss_id)
        if not run_lock.acquire(blocking=False):
            active_run = self._get_active_run(rss_id)
            active_message = "another check is already running"
            if active_run:
                active_for = time.monotonic() - active_run["started_monotonic"]
                active_message = (
                    f"another check is already running "
                    f"(run={active_run['run_id']}, trigger={active_run['trigger']}, active_for={self._format_duration(active_for)})"
                )
            self._log_feed_event(rss_id, f"manual-check-skipped reason={active_message}")
            raise RuntimeError(active_message)

        run_id = self._new_run_id()
        self._set_active_run(
            rss_id,
            {
                "run_id": run_id,
                "trigger": trigger,
                "started_at": self._now_str(),
                "started_monotonic": time.monotonic(),
                "thread_name": threading.current_thread().name,
            },
        )
        try:
            self.check_rss(rss_id, trigger=trigger, run_id=run_id)
        finally:
            self._clear_active_run(rss_id)
            run_lock.release()

    def schedule(self, rss_id: str):
        if rss_id not in self.storage["rss"]:
            self._log_feed_event(rss_id, "scheduler-fire ignored because feed no longer exists")
            return

        self._log_feed_event(rss_id, "scheduler-fire trigger=timer")
        self._schedule_next_run(rss_id, source="timer")
        self._start_check_thread(rss_id, "timer")

    def start_task(self, rss_id: str):
        with self.state_lock:
            existing_timer = self.tasks.pop(rss_id, None)
            if existing_timer:
                existing_timer.cancel()
        self._log_feed_event(rss_id, "scheduler-start")
        self._schedule_next_run(rss_id, source="start")
        self._start_check_thread(rss_id, "startup")

    def start_all(self):
        self.log_manager("rss-manager start_all begin")
        for rss_id in list(self.storage["rss"].keys()):
            self.start_task(rss_id)
        self.log_manager(f"rss-manager start_all done feeds={len(self.storage['rss'])}")
