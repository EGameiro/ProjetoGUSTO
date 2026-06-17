import httpx
import config

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
    """
    url = f"{_BASE}/send/text"
    payload = {
        "number": numero,
        "text": mensagem,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()


async def registrar_webhook(webhook_url: str) -> dict:
    """
    Registra a URL do webhook no UAZAPI.
    OBRIGATÓRIO — sem essa chamada o UAZAPI não sabe para onde enviar
    as mensagens recebidas e elas nunca chegam ao servidor.
    """
    url = f"{_BASE}/webhook"
    payload = {
        "url": webhook_url,
        "enabled": True,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()


def normalizar_payload(payload: dict) -> dict | None:
    """
    Extrai os campos relevantes do payload bruto do UAZAPI.
    Retorna None se for mensagem do próprio bot (fromMe), grupo ou tipo não suportado.

    Estrutura real do UAZAPI:
    {
      "EventType": "messages",
      "message": {
        "fromMe": false,
        "isGroup": false,
        "type": "text",
        "text": "ola",
        "content": "ola",
        "sender_pn": "5511992846459@s.whatsapp.net",
        "mediaType": ""
      }
    }
    """
    if payload.get("EventType") != "messages":
        return None

    msg = payload.get("message", {})

    if msg.get("fromMe"):
        return None

    if msg.get("isGroup"):
        return None

    msg_type = msg.get("type", "").lower()       # "text", "image", "audio", etc.
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
    else:
        return None  # sticker, documento, reação, etc.

    return {
        "numero":     numero,
        "tipo_midia": "imagem" if msg_type == "image" else
                      "audio"  if msg_type == "audio" else "texto",
        "texto":      texto,
        "url_midia":  url_midia,
    }
