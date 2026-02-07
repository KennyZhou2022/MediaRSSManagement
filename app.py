from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.rss_manager import RSSManager
from src.api.routes import router, set_rss_manager
from src.api.constants import router as constants_router

app = FastAPI()
rss = RSSManager()
# Set the RSSManager instance for API routes
set_rss_manager(rss)

# Mount static files
static_dir = os.path.join("src", "static")
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
