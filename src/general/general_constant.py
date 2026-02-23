import os


def _load_app_version():
    env_version = os.getenv("APP_VERSION", "").strip()
    if env_version:
        return env_version

    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "VERSION")),
        "/VERSION",
        "/app/VERSION",
        os.path.abspath("VERSION"),
    ]
    for version_file in candidates:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                version = f.read().strip()
                if version:
                    return version
        except OSError:
            continue
    return "0.0.0"

# Storage
STORAGE_DIR = "storage"
STORAGE_PATH = os.path.join(STORAGE_DIR, "storage.json")
LOG_DIR = os.path.join(STORAGE_DIR, "logs")

# Transmission defaults
DEFAULT_TRANSMISSION_URL = "localhost"
DEFAULT_TRANSMISSION_PORT = 9091

# Application defaults
DEFAULT_RSS_INTERVAL = 10
APP_VERSION = _load_app_version()

# PT site names
HHCLUB = 'HHCLUB'
AUDIENCES = 'Audiences'
CHDBits = 'CHDBits'

# Default PT site
DEFAULT_PT_SITE = HHCLUB

# Supported PT sites
SUPPORTED_PT_SITES = [HHCLUB, AUDIENCES, CHDBits]

# PT site type definitions
DIRECT = 'direct'
FILTER = 'filter'
PT_SITE_TYPES = {
    HHCLUB: DIRECT,        # fetch RSS and download directly
    AUDIENCES: FILTER,     # fetch RSS, then filter by keywords before downloading
    CHDBits: DIRECT        # fetch RSS and download directly
}

# Date and time format used in RSS feeds
DATETIME_FORMAT = "%Y-%m-%d %A %H:%M:%S"
TIME_ZONE = "Asia/Shanghai"

###########################
### Frontend constants ### 
###########################

# Frontend / shared defaults
AUTO_REFRESH_MS = 15000
UI_FONT_STORAGE_KEY = "mm_font"
UI_DEFAULT_FONT_ID = "space"

# Frontend strings (kept here so backend and frontend share the same source)
STRINGS = {
	'TITLE': 'Media RSS Management',
	'SETTINGS': 'Settings',
	'ADD_FEED': 'Add Feed',
	'REFRESH': 'Refresh',
	'FEEDS_HEADER': 'Feeds',
	'AUTO_REFRESH_MSG': 'Auto-refresh every 15s',
	'LOADING': 'Loading...',
	'NO_FEEDS': 'No feeds added yet.',
	'NAME_LABEL': 'Name',
	'RSS_URL_LABEL': 'RSS URL',
	'PATH_LABEL': 'Download Path',
	'INTERVAL_LABEL': 'Interval (minutes)',
	'SAVE_BUTTON': 'Save',
	'CANCEL_BUTTON': 'Cancel',
	'TRANSMISSION_RPC_LABEL': 'Transmission RPC URL',
	'TRANSMISSION_PORT_LABEL': 'Transmission Port',
	'USERNAME_LABEL': 'Username',
	'PASSWORD_LABEL': 'Password',
	'DEFAULT_RSS_INTERVAL_LABEL': 'Default RSS Interval (minutes)',
	'PLACEHOLDER_TRANS_URL': 'localhost',
	'PLACEHOLDER_PATH': 'Optional, Transmission download save path',
	'BTN_EDIT': 'Edit',
	'BTN_CHECK': 'Check',
	'BTN_LOGS': 'Logs',
	'BTN_DELETE': 'Delete',
	'BTN_CLOSE': 'Close',
	'BTN_COPY': 'Copy',
	'LOGS_NO': 'No logs',
	'TOAST_COPIED': 'Copied logs',
	'FAILED_LOAD_FEEDS': 'Failed to load feeds',
	'FIX_ERRORS': 'Please fix errors in settings',
	'SETTINGS_SAVED': 'Settings saved',
	'SAVE_FAILED': 'Save failed',
	'FEED_UPDATED': 'Feed updated',
	'FEED_ADDED': 'Feed added',
	'DELETED': 'Deleted',
	'DELETE_FAILED': 'Delete failed',
	'CONFIRM_DELETE': 'Delete this feed?',
	'CHECK_DONE': 'Check done, new items',
	'CHECK_FAILED': 'Check failed',
	'LOAD_LOGS_FAILED': 'Load logs failed'
}

# Lists used by frontend
LISTS = {
	'PT_SITES': SUPPORTED_PT_SITES,
    'PT_SITE_TYPES': PT_SITE_TYPES,
    'FONT_OPTIONS': [
        {
            'id': 'space',
            'label': 'Space Grotesk',
            'value': '"Space Grotesk", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif'
        },
        {
            'id': 'manrope',
            'label': 'Manrope',
            'value': '"Manrope", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif'
        },
        {
            'id': 'jakarta',
            'label': 'Plus Jakarta Sans',
            'value': '"Plus Jakarta Sans", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif'
        },
        {
            'id': 'ibm',
            'label': 'IBM Plex Sans',
            'value': '"IBM Plex Sans", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif'
        },
        {
            'id': 'sora',
            'label': 'Sora',
            'value': '"Sora", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif'
        }
    ],
    'PT_SITE_TAG_COLORS': {
        'hhclub': 'border-blue-300 bg-blue-100 text-blue-800',
        'audiences': 'border-amber-300 bg-amber-100 text-amber-800',
        'chdbits': 'border-emerald-300 bg-emerald-100 text-emerald-800',
        'default': 'border-slate-300 bg-slate-100 text-slate-700'
    }
}
