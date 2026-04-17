import json
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def log_event(event: str, level: str = 'INFO', **kwargs) -> None:
    payload = {
        'ts': _utc_now_iso(),
        'level': level,
        'event': event,
    }
    payload.update(kwargs)
    print(json.dumps(payload, ensure_ascii=False))
