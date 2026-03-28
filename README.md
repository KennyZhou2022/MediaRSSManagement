# Media RSS Management

RSS-to-Transmission manager with a lightweight web UI. Configure RSS feeds, set polling intervals, and push new items to Transmission.

## Features
- Feed lifecycle management: create, edit, delete RSS feeds with name, URL, PT site, keywords, and download path.
- Polling controls: per-feed interval scheduling plus manual “check now” trigger.
- Resilient scheduler: periodic timers and feed execution are decoupled, so a single failed run no longer stops future polling.
- Overlap protection: scheduled and manual checks for the same feed do not run concurrently.
- Keyword filtering for supported PT sites: filter torrent entries before sending.
- Transmission integration: configure RPC host/port/credentials and send torrents to the specified download path, with explicit RPC timeout protection.
- Auto-refreshing UI: periodic refresh to show latest feed status and last check time.
- Logging and diagnostics: per-feed logs plus a manager log to trace scheduler activity, skipped runs, start/finish events, and failures.

## Requirements
- Python 3.10+
- Transmission RPC endpoint (optional, for sending torrents)

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (Local)
```bash
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
Then open `http://127.0.0.1:8000/`.

## Docker
```bash
docker compose up --build
```
Then open `http://localhost:8000/`.

## Configuration
- Settings are stored in `storage/storage.json`.
- Logs are stored in `storage/logs/`.
- Runtime timeouts are defined in `src/general/general_constant.py`:
  - `RSS_REQUEST_CONNECT_TIMEOUT`
  - `RSS_REQUEST_READ_TIMEOUT`
  - `TRANSMISSION_RPC_TIMEOUT`

## Version Tracking
- Repository version source: `VERSION`.
- Backend version output: root endpoint `GET /` and OpenAPI metadata.
- Web page version display: header badge (`v<version>`) from `/api/version` (with constants fallback).
- Release process: bump the value in `VERSION` before tagging/releasing.

## API (Core)
- `GET /api/feeds`
- `POST /api/feeds`
- `PUT /api/feeds/{id}`
- `DELETE /api/feeds/{id}`
- `POST /api/feeds/{id}/check`
- `GET /api/feeds/{id}/logs`
- `GET /api/settings`
- `POST /api/settings`
- `GET /api/version`

## Notes
- The UI is served from `src/static/index.html`.
- If Transmission is not configured, checks still run and logs are written, but no torrents are sent.
- If `storage/storage.json` is missing or invalid JSON, the app auto-recovers with defaults and backs up invalid files.
- Feed parsing and filter-cache loading now tolerate malformed RSS data and broken local cache files more gracefully.
- Scheduler diagnostics are written to `storage/logs/manager.log`.
- Per-feed diagnostics are written to `storage/logs/<rss_id>.log`, including scheduler arm/fire/skip events and run-level errors.
- If a manual check is requested while the same feed is already running, the API rejects it instead of starting an overlapping run.

## Software Structure
- `app.py`: FastAPI app bootstrap, middleware, routing, and static UI mount.
- `src/api/`: API routes and frontend constants endpoint.
- `src/general/`: Shared constants and Pydantic models.
- `src/rss_manager.py`: Core RSS polling, storage, and Transmission integration.
- `src/static/`: Single-page UI and static assets.
- `storage/`: Persistent JSON storage and per-feed logs.
- `scripts/`: Debug helpers.

## Environment Variables
None are required.

If you deploy with a process manager or container platform, set the bind host/port using your platform defaults (the app itself does not read environment variables).
