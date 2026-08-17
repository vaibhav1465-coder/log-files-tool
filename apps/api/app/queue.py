import json

from redis import Redis

from .config import get_settings


STREAM = "express:jobs"
GROUP = "express-workers"


def enqueue_job(payload: dict) -> str:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return redis.xadd(STREAM, {"payload": json.dumps(payload, separators=(",", ":"))}, maxlen=100_000, approximate=True)
