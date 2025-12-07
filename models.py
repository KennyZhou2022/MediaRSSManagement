from pydantic import BaseModel
from typing import Dict, Optional

class RSSItem(BaseModel):
    id: str
    name: str
    url: str
    interval: int  # minutes
    last_fetch: Optional[str] = None
    last_hash: Optional[str] = None


class Settings(BaseModel):
    transmission_url: str = "http://transmission:9091/transmission/rpc"
    username: str = ""
    password: str = ""
