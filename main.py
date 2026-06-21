import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from db.connection import get_pool, close_pool
from db import dashboard as dash_db
from services.redis_client import get_redis, close_redis
from services.uazapi import normalizar_payload
from handlers.classifier import eh_convenio
from handlers import individual

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
app.mount("/static", StaticFiles(directory="dashboard"), name="static")


class StatusUpdate(BaseModel):
    status: str


def _extrair_restaurante_id(tenant: str) -> int | None:
    """
    Extrai o restaurante_id do parâmetro de rota.
    Formato esperado: '{slug}-{id}'  ex: 'gusto-1', 'sabor-2'
    Retorna None se o formato for inválido.
    """
    try:
        return int(tenant.rsplit("-", 1)[-1])
    except (ValueError, IndexError):
        return None


async def _processar_webhook(payload: dict, restaurante_id: int):
    """Lógica comum para processar um payload de webhook."""
    event_type = payload.get("EventType", "")
    msg_type   = payload.get("message", {}).get("type", "")
    if event_type == "messages" and msg_type not in ("text", "image", "audio"):
        log.info(f"[restaurante={restaurante_id}] Tipo desconhecido — EventType={event_type} | msg.type={msg_type}")

    msg = normalizar_payload(payload)
    if msg is None:
        return

    log.info(f"[restaurante={restaurante_id}] Mensagem de {msg['numero']} | tipo={msg['tipo_midia']} | texto={msg['texto']!r}")

    if await eh_convenio(msg["numero"]):
        return

    await individual.processar(msg, restaurante_id=restaurante_id)


@app.post("/webhook/{tenant}")
async def webhook_tenant(tenant: str, request: Request):
    """
    Webhook multi-tenant. Cada instância UAZAPI aponta para:
        POST /webhook/{slug}-{restaurante_id}
    Exemplo: POST /webhook/gusto-1
    """
    restaurante_id = _extrair_restaurante_id(tenant)
    if restaurante_id is None:
        log.warning(f"Webhook com tenant inválido: {tenant!r}")
        return JSONResponse({"status": "ok"})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})

    await _processar_webhook(payload, restaurante_id)
    return JSONResponse({"status": "ok"})


@app.post("/webhook")
async def webhook(request: Request):
    """Webhook legado — compatibilidade com instância GUSTO (restaurante_id=1)."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})

    await _processar_webhook(payload, restaurante_id=1)
    return JSONResponse({"status": "ok"})


@app.get("/dashboard")
async def dashboard():
    """Serve a interface operacional do dashboard."""
    return FileResponse("dashboard/index.html")


@app.get("/api/dashboard")
async def api_dashboard():
    """Retorna dados do dia: fila de pedidos + totais financeiros."""
    pedidos = await dash_db.listar_pedidos_hoje()
    totais  = await dash_db.totais_hoje()

    # Serializa campos não-JSON-serializáveis (date, time, Decimal)
    for p in pedidos:
        p["data_pedido"]   = str(p["data_pedido"])   if p.get("data_pedido")   else None
        p["horario_pedido"] = str(p["horario_pedido"]) if p.get("horario_pedido") else None
        p["criado_em"]     = str(p["criado_em"])     if p.get("criado_em")     else None
        for item in p.get("itens", []):
            if item.get("valor_unitario") is not None:
                item["valor_unitario"] = float(item["valor_unitario"])

    if totais.get("faturamento_total") is not None:
        totais["faturamento_total"] = float(totais["faturamento_total"])

    return {"pedidos": pedidos, "totais": totais}


STATUS_VALIDOS = {"pendente", "preparo", "saiu", "entregue"}

@app.post("/pedidos/{pedido_id}/status")
async def atualizar_status(pedido_id: int, body: StatusUpdate):
    """Atualiza o status de um pedido (pendente → preparo → saiu → entregue)."""
    if body.status not in STATUS_VALIDOS:
        raise HTTPException(400, f"Status inválido. Use: {', '.join(STATUS_VALIDOS)}")
    await dash_db.atualizar_status(pedido_id, body.status)
    return {"ok": True, "pedido_id": pedido_id, "status": body.status}


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
