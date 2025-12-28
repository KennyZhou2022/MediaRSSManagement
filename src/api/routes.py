"""
API routes
"""
from fastapi import APIRouter, HTTPException, Depends
import uuid
from src.general.general_class import RSSItem, Settings
from src.general.general_constant import DEFAULT_TRANSMISSION_URL, DEFAULT_TRANSMISSION_PORT, DEFAULT_RSS_INTERVAL
from src.rss_manager import RSSManager

router = APIRouter()


# RSSManager instance dependency injection 
# Use _rss_manager to initialize
_rss_instance = None

def set_rss_manager(instance: RSSManager):
    """ Set the RSSManager instance for dependency injection """
    global _rss_instance
    _rss_instance = instance

def get_rss_manager() -> RSSManager:
    """ Dependency to get the RSSManager instance """
    if _rss_instance is None:
        raise RuntimeError("RSSManager instance not initialized")
    return _rss_instance


def _convert_rss_to_feed(rss_id: str, rss_data: dict) -> dict:
    """Convert internal RSS format to frontend feed format"""
    return {
        "id": rss_id,
        "name": rss_data.get("name", ""),
        "url": rss_data.get("url", ""),
        "path": rss_data.get("path", ""),
        "interval": rss_data.get("interval", 10),
        "enabled": True,  # Default to enabled
        "lastChecked": rss_data.get("last_fetch"),
        "lastStatus": "OK" if rss_data.get("last_fetch") else "Never"
    }


# -------------------------------
# RSS API
# -------------------------------
@router.get("/rss")
def list_rss(rss: RSSManager = Depends(get_rss_manager)):
    return rss.list_rss()


@router.post("/rss")
def add_rss(item: RSSItem, rss: RSSManager = Depends(get_rss_manager)):
    if not item.id:
        item.id = str(uuid.uuid4())
    rss.add_rss(item)
    return {"ok": True, "id": item.id}


@router.delete("/rss/{rss_id}")
def delete_rss(rss_id: str, rss: RSSManager = Depends(get_rss_manager)):
    rss.delete_rss(rss_id)
    return {"ok": True}


@router.post("/rss/{rss_id}/check")
def manual_check(rss_id: str, rss: RSSManager = Depends(get_rss_manager)):
    rss.check_rss(rss_id)
    return {"ok": True}


@router.get("/rss/{rss_id}/logs")
def get_logs(rss_id: str, rss: RSSManager = Depends(get_rss_manager)):
    return rss.get_logs(rss_id)


# -------------------------------
# Settings API
# -------------------------------
@router.get("/settings")
def get_settings(rss: RSSManager = Depends(get_rss_manager)):
    settings = rss.storage.get("settings", {})
    # 返回默认值如果设置不存在
    default_settings = {
        "transmission_url": DEFAULT_TRANSMISSION_URL,
        "transmission_port": DEFAULT_TRANSMISSION_PORT,
        "username": "",
        "password": "",
        "default_rss_interval": DEFAULT_RSS_INTERVAL
    }
    return {**default_settings, **settings}


@router.post("/settings")
def set_settings(s: Settings, rss: RSSManager = Depends(get_rss_manager)):
    # Pydantic模型会自动验证设置
    rss.storage["settings"] = s.dict()
    rss.save_storage()
    return {"ok": True}


# -------------------------------
# Frontend-compatible /api/feeds endpoints
# -------------------------------
@router.get("/feeds")
def list_feeds(rss: RSSManager = Depends(get_rss_manager)):
    rss_items = rss.list_rss()
    feeds = [_convert_rss_to_feed(rss_id, rss_data) for rss_id, rss_data in rss_items.items()]
    return feeds


@router.post("/feeds")
def add_feed(feed_data: dict, rss: RSSManager = Depends(get_rss_manager)):
    # 检查URL是否重复
    feed_url = feed_data.get("url", "").strip()
    if not feed_url:
        raise HTTPException(status_code=400, detail="URL不能为空")
    
    # 检查现有feeds中是否有相同的URL
    existing_feeds = rss.list_rss()
    for feed_id, feed_info in existing_feeds.items():
        if feed_info.get("url", "").strip() == feed_url:
            raise HTTPException(status_code=400, detail=f"URL已存在：{feed_info.get('name', '未命名')}")
    
    # 如果没有指定interval，使用默认值
    settings = rss.storage.get("settings", {})
    default_interval = settings.get("default_rss_interval", DEFAULT_RSS_INTERVAL)
    
    feed_id = str(uuid.uuid4())
    rss_item = RSSItem(
        id=feed_id,
        name=feed_data.get("name", ""),
        url=feed_url,
        path=feed_data.get("path", ""),
        interval=feed_data.get("interval", default_interval)
    )
    
    try:
        rss.add_rss(rss_item)
    except Exception as e:
        # 如果添加失败，确保不会留下部分数据
        if feed_id in rss.storage["rss"]:
            rss.storage["rss"].pop(feed_id, None)
            rss.save_storage()
        raise HTTPException(status_code=500, detail=f"添加RSS失败: {str(e)}")
    
    return {"ok": True, "id": feed_id}


@router.put("/feeds/{feed_id}")
def update_feed(feed_id: str, feed_data: dict, rss: RSSManager = Depends(get_rss_manager)):
    if feed_id not in rss.storage["rss"]:
        raise HTTPException(status_code=404, detail="Feed not found")
    existing = rss.storage["rss"][feed_id]
    rss_item = RSSItem(
        id=feed_id,
        name=feed_data.get("name", existing.get("name", "")),
        url=feed_data.get("url", existing.get("url", "")),
        path=feed_data.get("path", existing.get("path", "")),
        interval=feed_data.get("interval", existing.get("interval", 10)),
        last_fetch=existing.get("last_fetch"),
        last_hash=existing.get("last_hash")
    )
    rss.add_rss(rss_item)
    return {"ok": True}


@router.delete("/feeds/{feed_id}")
def delete_feed(feed_id: str, rss: RSSManager = Depends(get_rss_manager)):
    if feed_id not in rss.storage["rss"]:
        raise HTTPException(status_code=404, detail="Feed not found")
    rss.delete_rss(feed_id)
    return {"ok": True}


@router.post("/feeds/{feed_id}/check")
def check_feed(feed_id: str, rss: RSSManager = Depends(get_rss_manager)):
    if feed_id not in rss.storage["rss"]:
        raise HTTPException(status_code=404, detail="Feed not found")
    rss.check_rss(feed_id)
    return {"ok": True, "newItems": []}  # TODO: Return actual new items count


@router.get("/feeds/{feed_id}/logs")
def get_feed_logs(feed_id: str, rss: RSSManager = Depends(get_rss_manager)):
    if feed_id not in rss.storage["rss"]:
        raise HTTPException(status_code=404, detail="Feed not found")
    log_content = rss.get_logs(feed_id)
    # Convert log string to array format expected by frontend
    logs = []
    for line in log_content.split("\n"):
        if line.strip():
            # Parse log line format: [timestamp] message
            parts = line.split("] ", 1)
            if len(parts) == 2:
                ts = parts[0].replace("[", "")
                msg = parts[1]
                logs.append({"ts": ts, "level": "info", "msg": msg})
    return logs


@router.post("/feeds/{feed_id}/send")
def send_to_transmission(feed_id: str, payload: dict, rss: RSSManager = Depends(get_rss_manager)):
    # This endpoint is for sending specific items to Transmission
    # For now, we'll trigger a check which will send new items automatically
    if feed_id not in rss.storage["rss"]:
        raise HTTPException(status_code=404, detail="Feed not found")
    rss.check_rss(feed_id)
    return {"ok": True}

