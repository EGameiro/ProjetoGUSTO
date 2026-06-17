import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import config
from db.connection import get_pool, close_pool
from services.redis_client import get_redis, close_redis
from services.uazapi import normalizar_payload
from handlers.classifier import classificar
from handlers import individual, convenio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    log.info("Iniciando GUSTO Agent...")

    # Testa conexão MySQL
    await get_pool()
    log.info("MySQL: conexão OK")

    # Testa conexão Redis
    r = get_redis()
    await r.ping()
    log.info("Redis: conexão OK")

    # Webhook configurado manualmente no painel do UAZAPI
    log.info(f"Webhook endpoint disponível em: {config.WEBHOOK_URL}/webhook")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    log.info("Encerrando GUSTO Agent...")
    await close_pool()
    await close_redis()


app = FastAPI(title="GUSTO Agent", lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request):
    """
    Recebe eventos do UAZAPI.
    Deve retornar 200 imediatamente — o UAZAPI não reencaminha
    se demorar ou receber erro.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})  # retorna 200 mesmo com payload inválido

    log.info(f"Webhook recebido: {payload}")

    msg = normalizar_payload(payload)
    if msg is None:
        # fromMe, grupo, tipo não suportado — ignora silenciosamente
        return JSONResponse({"status": "ok"})

    log.info(f"Mensagem de {msg['numero']} | tipo={msg['tipo_midia']} | texto={msg['texto']!r}")

    # ── Classifier → roteamento ───────────────────────────────
    tipo, empresa = await classificar(msg["numero"])

    if tipo == "convenio":
        await convenio.processar(msg, empresa)
    else:
        await individual.processar(msg)

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    """Verificação rápida de saúde do serviço."""
    r = get_redis()
    redis_ok = False
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "redis": "ok" if redis_ok else "erro",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=True)
