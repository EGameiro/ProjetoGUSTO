import re
import logging
import config
from services.redis_client import get_redis
from db.connection import fetchone

log = logging.getLogger(__name__)

_PAUSA_KEY = "pausa:{restaurante_id}"


def _parse_duracao(texto: str) -> int | None:
    """
    Converte duração em segundos.
    Formatos aceitos: '1h', '2hs', '30m', '10m'
    Retorna None se não reconhecer.
    """
    texto = texto.strip().lower()
    m = re.fullmatch(r"(\d+)\s*(hs?|m)", texto)
    if not m:
        return None
    valor, unidade = int(m.group(1)), m.group(2)
    if unidade.startswith("h"):
        return valor * 3600
    return valor * 60


async def eh_admin(numero: str, restaurante_id: int) -> bool:
    """Verifica se o número é do proprietário do restaurante (campo telefone em restaurantes)."""
    row = await fetchone(
        """
        SELECT id FROM restaurantes
        WHERE id = %s
          AND REPLACE(REPLACE(REPLACE(telefone, ' ', ''), '-', ''), '(', '') = %s
        LIMIT 1
        """,
        (restaurante_id, numero),
    )
    return row is not None


async def pausar(restaurante_id: int, segundos: int):
    r = get_redis()
    key = _PAUSA_KEY.format(restaurante_id=restaurante_id)
    await r.setex(key, segundos, "1")
    log.info(f"[restaurante={restaurante_id}] Agente pausado por {segundos}s")


async def esta_pausado(restaurante_id: int) -> bool:
    r = get_redis()
    key = _PAUSA_KEY.format(restaurante_id=restaurante_id)
    return await r.exists(key) == 1


async def retomar(restaurante_id: int):
    r = get_redis()
    key = _PAUSA_KEY.format(restaurante_id=restaurante_id)
    await r.delete(key)
    log.info(f"[restaurante={restaurante_id}] Agente retomado manualmente")


# ── Pausa por conversa (intervenção manual via WhatsApp Web) ──────────────────

_PAUSA_NUMERO_KEY = "pausa_numero:{restaurante_id}:{numero}"


async def pausar_numero(restaurante_id: int, numero: str):
    """Pausa o bot para um número específico por PAUSA_ATENDIMENTO_MINUTOS."""
    r = get_redis()
    key = _PAUSA_NUMERO_KEY.format(restaurante_id=restaurante_id, numero=numero)
    segundos = config.PAUSA_ATENDIMENTO_MINUTOS * 60
    await r.setex(key, segundos, "1")
    log.info(
        f"[restaurante={restaurante_id}] Atendimento pausado para {numero} "
        f"por {config.PAUSA_ATENDIMENTO_MINUTOS}min (intervenção manual)"
    )


async def numero_esta_pausado(restaurante_id: int, numero: str) -> bool:
    r = get_redis()
    key = _PAUSA_NUMERO_KEY.format(restaurante_id=restaurante_id, numero=numero)
    return await r.exists(key) == 1
