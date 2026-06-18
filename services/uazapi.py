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

    msg_type   = msg.get("type", "").lower()
    media_type = msg.get("mediaType", "").lower()  # "document", "image", etc.
    jid        = msg.get("sender_pn", "")
    numero     = jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

    if not numero:
        return None

    content   = msg.get("content", {}) if isinstance(msg.get("content"), dict) else {}
    texto     = None
    url_midia = None
    msg_id    = msg.get("messageid", "")
    chat_id   = msg.get("chatid", "")

    if msg_type == "text":
        texto = (msg.get("text") or "").strip()

    elif msg_type == "media" and media_type == "document":
        # documento Excel/PDF — URL criptografada, precisa baixar via UAZAPI
        texto     = content.get("fileName") or content.get("title") or "documento"
        # guarda o messageid e chatid para download via UAZAPI
        url_midia = f"__uazapi_download__{msg_id}__{chat_id}"

    elif msg_type == "media" and media_type == "image":
        texto     = (content.get("caption") or msg.get("text") or "").strip()
        url_midia = content.get("URL") or msg.get("mediaUrl")

    elif msg_type == "media" and media_type == "audio":
        url_midia = content.get("URL") or msg.get("mediaUrl")

    elif msg_type == "image":
        texto     = (msg.get("text") or "").strip()
        url_midia = msg.get("mediaUrl") or msg.get("url")

    elif msg_type == "audio":
        url_midia = msg.get("mediaUrl") or msg.get("url")

    else:
        return None

    tipo_midia = "documento" if (media_type == "document") else \
                 "imagem"    if (media_type == "image" or msg_type == "image") else \
                 "audio"     if (media_type == "audio" or msg_type == "audio") else "texto"

    return {
        "numero":     numero,
        "tipo_midia": tipo_midia,
        "texto":      texto,
        "url_midia":  url_midia,
    }


async def baixar_midia_uazapi(url_midia: str) -> bytes:
    """
    Baixa mídia via endpoint do UAZAPI.
    url_midia: string no formato '__uazapi_download__{messageid}__{chatid}'
    Docs: POST {BASE}/{instance}/message/download  payload: {"id": msg_id, "return_link": true}
    Resposta: {"fileURL": "...", ...}
    """
    partes  = url_midia.split("__")
    msg_id  = partes[2]
    url     = f"{config.UAZAPI_BASE_URL}/message/download"
    payload = {"id": msg_id, "return_link": True}
    headers = {"token": config.UAZAPI_TOKEN, "Content-Type": "application/json"}

    log.info(f"UAZAPI download: POST {url} id={msg_id}")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if not resp.is_success:
            raise Exception(f"UAZAPI download falhou [{resp.status_code}]: {resp.text}")

        data    = resp.json()
        log.info(f"UAZAPI download resposta: {data}")
        file_url = data.get("fileURL") or data.get("fileUrl") or data.get("url")
        if not file_url:
            raise Exception(f"fileURL não encontrado na resposta: {data}")

        r2 = await client.get(file_url)
        r2.raise_for_status()
        return r2.content
