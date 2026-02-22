# Media Management

RSS-to-Transmission manager with a lightweight web UI. Configure RSS feeds, set polling intervals, and push new items to Transmission.

## Features
- Feed lifecycle management: create, edit, delete RSS feeds with name, URL, PT site, keywords, and download path.
- Polling controls: per-feed interval scheduling plus manual “check now” trigger.
- Keyword filtering for supported PT sites: filter torrent entries before sending.
- Transmission integration: configure RPC host/port/credentials and send torrents to the specified download path.
- Auto-refreshing UI: periodic refresh to show latest feed status and last check time.
- Logging per feed: timestamped log files for fetch outcomes and send attempts.

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
python app.py
```
Then open `http://localhost:8000/`.

## Docker
```bash
docker compose up --build
```
Then open `http://localhost:8000/`.

## Configuration
- Settings are stored in `storage/storage.json`.
- Logs are stored in `storage/logs/`.

## Version Tracking
- Repository version source: `VERSION`.
- Backend version output: root endpoint `GET /` and OpenAPI metadata.
- Web page version display: header badge (`v<version>`) from `/api/constants.js`.
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

## Notes
- The UI is served from `src/static/index.html`.
- If Transmission is not configured, checks still run and logs are written, but no torrents are sent.

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
