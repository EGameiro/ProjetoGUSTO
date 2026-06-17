import httpx
import config

# Headers padrão para todas as chamadas ao UAZAPI
_HEADERS = {
    "token": config.UAZAPI_TOKEN,
    "Content-Type": "application/json",
}

_BASE = f"{config.UAZAPI_BASE_URL}/{config.UAZAPI_INSTANCE}"


async def enviar_texto(numero: str, mensagem: str) -> dict:
    """Envia mensagem de texto para um número WhatsApp."""
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
    Retorna None se for mensagem do próprio bot (fromMe) ou tipo não suportado.

    Estrutura esperada do UAZAPI:
    {
      "type": "message",
      "data": {
        "key": { "remoteJid": "5512999999999@s.whatsapp.net", "fromMe": false },
        "message": {
          "conversation": "texto da mensagem",
          "imageMessage": { "url": "...", "caption": "..." },
          "audioMessage": { "url": "..." }
        },
        "messageType": "conversation" | "imageMessage" | "audioMessage"
      }
    }
    """
    if payload.get("type") != "message":
        return None

    data = payload.get("data", {})
    key  = data.get("key", {})

    if key.get("fromMe"):
        return None

    jid    = key.get("remoteJid", "")
    numero = jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

    if "@g.us" in jid:
        return None  # ignora grupos

    msg_type = data.get("messageType", "")
    message  = data.get("message", {})

    texto     = None
    url_midia = None

    if msg_type == "conversation":
        texto = message.get("conversation", "").strip()
    elif msg_type == "extendedTextMessage":
        texto = message.get("extendedTextMessage", {}).get("text", "").strip()
    elif msg_type == "imageMessage":
        texto     = message.get("imageMessage", {}).get("caption", "").strip()
        url_midia = message.get("imageMessage", {}).get("url")
    elif msg_type == "audioMessage":
        url_midia = message.get("audioMessage", {}).get("url")
    else:
        return None  # tipo não tratado (sticker, documento, etc.)

    return {
        "numero":     numero,
        "tipo_midia": "imagem" if msg_type == "imageMessage" else
                      "audio"  if msg_type == "audioMessage"  else "texto",
        "texto":      texto,
        "url_midia":  url_midia,
    }
