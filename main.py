import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from db.connection import get_pool, close_pool
from db import dashboard as dash_db
from services.redis_client import get_redis, close_redis
from services.uazapi import normalizar_payload
from handlers.classifier import classificar
from handlers import individual, convenio
from scheduler.jobs import broadcast_cardapio

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

    # ── APScheduler — broadcast do cardápio ──────────────────
    hora, minuto = config.HORARIO_BROADCAST_CARDAPIO.split(":")
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        broadcast_cardapio,
        CronTrigger(hour=int(hora), minute=int(minuto)),
        id="broadcast_cardapio",
        replace_existing=True,
    )
    scheduler.start()
    log.info(f"Scheduler iniciado — broadcast do cardápio agendado para {config.HORARIO_BROADCAST_CARDAPIO}")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    log.info("Encerrando GUSTO Agent...")
    scheduler.shutdown(wait=False)
    await close_pool()
    await close_redis()


app = FastAPI(title="GUSTO Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="dashboard"), name="static")


class StatusUpdate(BaseModel):
    status: str


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

    # log temporário para debug de tipos desconhecidos
    event_type = payload.get("EventType", "")
    msg_type   = payload.get("message", {}).get("type", "")
    if event_type == "messages" and msg_type not in ("text", "image", "audio"):
        log.info(f"Payload tipo desconhecido — EventType={event_type} | msg.type={msg_type} | payload={payload}")


    msg = normalizar_payload(payload)
    if msg is None:
        return JSONResponse({"status": "ok"})

    log.info(f"Mensagem de {msg['numero']} | tipo={msg['tipo_midia']} | texto={msg['texto']!r}")

    # ── Classifier → roteamento ───────────────────────────────
    tipo, empresa = await classificar(msg["numero"])

    if tipo == "convenio":
        await convenio.processar(msg, empresa)
    else:
        await individual.processar(msg)

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
