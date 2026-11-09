import json
import time
import logging
from typing import Any, Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisWorkingMemory:
    """Redis 7 Working Memory & Cache with local in-memory fallback."""

    def __init__(self):
        self._redis = None
        self._in_memory_store: Dict[str, tuple[Any, Optional[float]]] = {}
        self._use_redis = False
        self._connect()

    def _connect(self):
        try:
            import redis
            client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5
            )
            client.ping()
            self._redis = client
            self._use_redis = True
            logger.info("Connected to Redis working memory successfully.")
        except Exception as e:
            logger.debug(f"Redis not available ({e}). Using in-memory fallback dictionary.")
            self._redis = None
            self._use_redis = False

    @property
    def is_connected(self) -> bool:
        if self._redis and self._use_redis:
            try:
                return bool(self._redis.ping())
            except Exception:
                self._use_redis = False
                return False
        return False

    def get(self, key: str) -> Optional[str]:
        if self.is_connected:
            try:
                return self._redis.get(key)
            except Exception as e:
                logger.debug(f"Redis get error: {e}")

        # In-memory fallback
        item = self._in_memory_store.get(key)
        if not item:
            return None
        val, expiry = item
        if expiry is not None and time.time() > expiry:
            del self._in_memory_store[key]
            return None
        return val

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if self.is_connected:
            try:
                return bool(self._redis.set(key, value, ex=ex))
            except Exception as e:
                logger.debug(f"Redis set error: {e}")

        # In-memory fallback
        expiry = time.time() + ex if ex else None
        self._in_memory_store[key] = (str(value), expiry)
        return True

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, data: Any, ex: Optional[int] = None) -> bool:
        try:
            serialized = json.dumps(data, ensure_ascii=False)
            return self.set(key, serialized, ex=ex)
        except Exception as e:
            logger.error(f"Error caching JSON in working memory: {e}")
            return False

    def delete(self, key: str) -> bool:
        if self.is_connected:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._in_memory_store.pop(key, None)
        return True

    def clear(self) -> bool:
        if self.is_connected:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        self._in_memory_store.clear()
        return True


cache = RedisWorkingMemory()

