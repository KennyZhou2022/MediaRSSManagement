from fastapi import APIRouter, Response
import json
from src.general import general_constant as GC

router = APIRouter()


@router.get('/constants.js')
def constants_js():
    # Build a safe payload for the frontend (do not expose secrets)
    payload = {
        'DEFAULTS': {
            'TRANSMISSION_URL': getattr(GC, 'DEFAULT_TRANSMISSION_URL', 'localhost'),
            'TRANSMISSION_PORT': getattr(GC, 'DEFAULT_TRANSMISSION_PORT', 9091),
            'DEFAULT_RSS_INTERVAL': getattr(GC, 'DEFAULT_RSS_INTERVAL', 10),
            'AUTO_REFRESH_MS': getattr(GC, 'AUTO_REFRESH_MS', 15000)
        },
        'STRINGS': getattr(GC, 'STRINGS', {}),
        'LISTS': getattr(GC, 'LISTS', {})
    }
    # Serialize with ensure_ascii=False to keep Unicode readable in JS
    body = 'window.GENERAL_CONSTANTS = ' + json.dumps(payload, ensure_ascii=False) + ';'
    return Response(content=body, media_type='application/javascript')
