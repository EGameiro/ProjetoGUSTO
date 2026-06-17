import redis.asyncio as aioredis
import config

_client = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def close_redis():
    global _client
    if _client:
        await _client.aclose()
        _client = None
