import logging
import httpx
import config

log = logging.getLogger(__name__)

# Headers padrão para todas as chamadas ao UAZAPI
_HEADERS = {
    "token": config.UAZAPI_TOKEN,
    "Content-Type": "application/json",
}

_BASE = f"{config.UAZAPI_BASE_URL}/{config.UAZAPI_INSTANCE}"


async def enviar_texto(numero: str, mensagem: str) -> dict:
    """
    Envia mensagem de texto para um número WhatsApp.
    numero: apenas dígitos, ex: '5511992846459'
    O endpoint de envio não usa a instância na URL.
    """
    url = f"{config.UAZAPI_BASE_URL}/send/text"
    payload = {
        "number": numero,
        "text": mensagem,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_HEADERS)
        if not resp.is_success:
            log.error(f"Erro ao enviar mensagem [{resp.status_code}]: {resp.text}")
            return {}
        return resp.json()


def normalizar_payload(payload: dict) -> dict | None:
    """
    Extrai os campos relevantes do payload bruto do UAZAPI.
    Retorna None se for mensagem do próprio bot (fromMe), grupo ou tipo não suportado.
    """
    if payload.get("EventType") != "messages":
        return None

    msg = payload.get("message", {})

    if msg.get("fromMe"):
        return None

    if msg.get("isGroup"):
        return None

    msg_type = msg.get("type", "").lower()
    jid      = msg.get("sender_pn", "")
    numero   = jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

    if not numero:
        return None

    texto     = None
    url_midia = None

    if msg_type == "text":
        texto = (msg.get("text") or msg.get("content") or "").strip()
    elif msg_type == "image":
        texto     = (msg.get("text") or msg.get("content") or "").strip()
        url_midia = msg.get("mediaUrl") or msg.get("url")
    elif msg_type == "audio":
        url_midia = msg.get("mediaUrl") or msg.get("url")
    elif msg_type == "document":
        url_midia = msg.get("mediaUrl") or msg.get("url")
        texto     = msg.get("fileName") or msg.get("filename") or "documento"
    else:
        return None

    return {
        "numero":     numero,
        "tipo_midia": "imagem"    if msg_type == "image"    else
                      "audio"     if msg_type == "audio"    else
                      "documento" if msg_type == "document" else "texto",
        "texto":      texto,
        "url_midia":  url_midia,
    }
