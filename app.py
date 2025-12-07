from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid

from models import RSSItem, Settings
from rss_manager import RSSManager

app = FastAPI()
rss = RSSManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    rss.start_all()

# -------------------------------
# RSS API
# -------------------------------
@app.get("/api/rss")
def list_rss():
    return rss.list_rss()

@app.post("/api/rss")
def add_rss(item: RSSItem):
    if not item.id:
        item.id = str(uuid.uuid4())
    rss.add_rss(item)
    return {"ok": True, "id": item.id}

@app.delete("/api/rss/{rss_id}")
def delete_rss(rss_id: str):
    rss.delete_rss(rss_id)
    return {"ok": True}

@app.post("/api/rss/{rss_id}/check")
def manual_check(rss_id: str):
    rss.check_rss(rss_id)
    return {"ok": True}

@app.get("/api/rss/{rss_id}/logs")
def get_logs(rss_id: str):
    return rss.get_logs(rss_id)

# -------------------------------
# Settings API
# -------------------------------
@app.get("/api/settings")
def get_settings():
    return rss.storage.get("settings", {})

@app.post("/api/settings")
def set_settings(s: Settings):
    rss.storage["settings"] = s.dict()
    rss.save_storage()
    return {"ok": True}

