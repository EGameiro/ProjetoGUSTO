import json
from services.redis_client import get_redis

TTL = 4 * 3600  # 4 horas


def _key(numero: str) -> str:
    return f"sessao:{numero}"


async def get_session(numero: str) -> dict:
    r = get_redis()
    raw = await r.get(_key(numero))
    return json.loads(raw) if raw else {}


async def set_session(numero: str, data: dict):
    r = get_redis()
    await r.set(_key(numero), json.dumps(data, ensure_ascii=False), ex=TTL)


async def delete_session(numero: str):
    r = get_redis()
    await r.delete(_key(numero))


async def atualizar_session(numero: str, **campos):
    """Atualiza campos individuais sem sobrescrever a sessão inteira."""
    sessao = await get_session(numero)
    sessao.update(campos)
    await set_session(numero, sessao)
