import json

import redis

from app.core.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

HISTORY_TTL_SECONDS = 60 * 60 * 24  # auto-expire old sessions after 24 hours


def _key(session_id: str) -> str:
    return f"chat:{session_id}"


def get_history(session_id: str) -> list[dict]:
    """Return this session's past turns, oldest first. Empty list if it's a new session."""
    raw = redis_client.get(_key(session_id))
    return json.loads(raw) if raw else []


def append_message(session_id: str, role: str, content: str) -> None:
    """Add one turn to the session's history and refresh its expiry."""
    history = get_history(session_id)
    history.append({"role": role, "content": content})
    redis_client.set(_key(session_id), json.dumps(history), ex=HISTORY_TTL_SECONDS)