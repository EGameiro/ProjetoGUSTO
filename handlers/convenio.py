import logging
from services import session as sess
from services.uazapi import enviar_texto

log = logging.getLogger(__name__)


async def processar(msg: dict, empresa: dict):
    """
    Processa mensagem de cliente convênio (lote de pedidos).
    msg:     { numero, tipo_midia, texto, url_midia }
    empresa: linha da tabela empresas_convenio
    """
    numero        = msg["numero"]
    nome_empresa  = empresa["nome_empresa"]
    texto         = (msg["texto"] or "").strip().lower()

    sessao = await sess.get_session(numero)
    etapa  = sessao.get("etapa", "inicio")

    log.info(f"[{numero}] Convênio [{nome_empresa}] | etapa={etapa} | texto={texto!r}")

    # ── Etapa 5 implementará o handler completo ───────────────
    await enviar_texto(numero, f"✅ [Convênio - {nome_empresa}] Mensagem recebida. Handler em breve!")
