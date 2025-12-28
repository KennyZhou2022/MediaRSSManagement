from pydantic import BaseModel, field_validator
from typing import Optional

class RSSItem(BaseModel):
    id: str
    name: str
    url: str
    path: str
    interval: int  # minutes
    last_fetch: Optional[str] = None
    last_title: Optional[str] = None
    pt_site: str
    key_words: Optional[str] = None


class Settings(BaseModel):
    transmission_url: str = "localhost"
    transmission_port: int = 9091
    username: str = ""
    password: str = ""
    default_rss_interval: int = 10  # default interval is 10 minutes
    
    @field_validator('default_rss_interval')
    def validate_interval(cls, v):
        if v < 5:
            raise ValueError("Default RSS interval must be at least 5 minutes")
        if v > 1440:  # 24 hours
            raise ValueError("Default RSS interval cannot exceed 1440 minutes (24 hours)")
        return v

