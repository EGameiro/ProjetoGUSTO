import logging
from services import session as sess
from services.uazapi import enviar_texto

log = logging.getLogger(__name__)


async def processar(msg: dict):
    """
    Processa mensagem de cliente individual.
    msg: { numero, tipo_midia, texto, url_midia }
    """
    numero = msg["numero"]
    texto  = (msg["texto"] or "").strip().lower()

    sessao = await sess.get_session(numero)
    etapa  = sessao.get("etapa", "inicio")

    log.info(f"[{numero}] Individual | etapa={etapa} | texto={texto!r}")

    # ── Etapa 3 implementará o dialog flow completo ───────────
    # Por enquanto confirma recebimento para teste de ponta a ponta
    await enviar_texto(numero, "✅ [Individual] Mensagem recebida. Dialog flow em breve!")
