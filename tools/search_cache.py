import time

_cache: dict[int, dict] = {}
_ttl: int = 300


def setup(ttl: int):
    global _ttl
    _ttl = ttl


def store(user_id: int, shift_index: int, query: str, results: list, total: int):
    _cache[user_id] = {
        "shift_index": shift_index,
        "query": query,
        "results": results,
        "total": total,
        "timestamp": time.time(),
    }


def get(user_id: int) -> dict | None:
    entry = _cache.get(user_id)
    if entry and time.time() - entry["timestamp"] < _ttl:
        return entry
    return None


def cleanup_expired():
    now = time.time()
    expired = [uid for uid, entry in _cache.items() if now - entry["timestamp"] >= _ttl]
    for uid in expired:
        del _cache[uid]
