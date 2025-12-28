from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os
import sys
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.general.general_constant import DATETIME_FORMAT, TIME_ZONE

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.rss_manager import RSSManager
from src.api.routes import router, set_rss_manager
from src.api.constants import router as constants_router

app = FastAPI()
rss = RSSManager()
# Set the RSSManager instance for API routes
set_rss_manager(rss)

#region agent log
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        log_path = r"c:\Users\Kenny\Documents\GitHub\MediaManagement\.cursor\debug.log"
        # helper to produce epoch ms and formatted ts
        def _log_times():
            try:
                tz = ZoneInfo(TIME_ZONE)
                now = datetime.now(tz)
                return int(now.timestamp() * 1000), now.strftime(DATETIME_FORMAT)
            except Exception:
                now = datetime.now()
                return int(now.timestamp() * 1000), now.isoformat()
        try:
            ts_ms, ts_str = _log_times()
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run3",
                "hypothesisId": "A",
                "location": "app.py:RequestLoggingMiddleware",
                "message": "Incoming request",
                "data": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "query": str(request.url.query)
                },
                "timestamp": ts_ms,
                "ts": ts_str
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            pass
        response = await call_next(request)
        #endregion agent log
        #region agent log
        try:
            ts_ms, ts_str = _log_times()
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run3",
                "hypothesisId": "A",
                "location": "app.py:RequestLoggingMiddleware",
                "message": "Response sent",
                "data": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", "")
                },
                "timestamp": ts_ms,
                "ts": ts_str
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            pass
        # #endregion agent log
        return response

app.add_middleware(RequestLoggingMiddleware)
# Mount static files
static_dir = os.path.join("src", "static")
#region agent log
log_path = r"c:\Users\Kenny\Documents\GitHub\MediaManagement\.cursor\debug.log"
try:
    def _log_times():
        try:
            tz = ZoneInfo(TIME_ZONE)
            now = datetime.now(tz)
            return int(now.timestamp() * 1000), now.strftime(DATETIME_FORMAT)
        except Exception:
            now = datetime.now()
            return int(now.timestamp() * 1000), now.isoformat()

    ts_ms, ts_str = _log_times()

    log_entry = {
        "sessionId": "debug-session",
        "runId": "run3",
        "hypothesisId": "B",
        "location": "app.py:static_dir_setup",
        "message": "Static directory check",
        "data": {
            "static_dir": static_dir,
            "exists": os.path.exists(static_dir),
            "index_html_exists": os.path.exists(os.path.join(static_dir, "index.html"))
        },
        "timestamp": ts_ms,
        "ts": ts_str
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
except Exception as e:
    pass
#endregion agent log
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["api"])
app.include_router(constants_router, prefix="/api", tags=["constants"])

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.on_event("startup")
def startup_event():
    rss.start_all()

# -------------------------------
# Root endpoint
# -------------------------------
@app.get("/")
def root():
    # #region agent log
    log_path = r"c:\Users\Kenny\Documents\GitHub\MediaManagement\.cursor\debug.log"
    try:
        ts_ms, ts_str = _log_times()
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run3",
            "hypothesisId": "C",
            "location": "app.py:root",
            "message": "Root endpoint called",
            "data": {
                "static_dir": static_dir,
                "index_path": os.path.join(static_dir, "index.html"),
                "index_exists": os.path.exists(os.path.join(static_dir, "index.html"))
            },
            "timestamp": ts_ms,
            "ts": ts_str
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        pass
    # #endregion agent log
    # Serve HTML file if it exists, otherwise return API info
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {
        "message": "RSS to Transmission Manager API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "rss": "/api/rss",
            "feeds": "/api/feeds",
            "settings": "/api/settings"
        }
    }
