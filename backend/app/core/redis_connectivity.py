from redis import Redis
from redis.exceptions import RedisError

from app.core.settings import settings


def redis_is_reachable() -> bool:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return bool(client.ping())
    except RedisError:
        return False
