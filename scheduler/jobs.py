import logging
from db import connection as db
from services.cardapio import formatar_cardapio
from services.uazapi import enviar_texto

log = logging.getLogger(__name__)


async def broadcast_cardapio():
    """Envia o cardápio do dia para todos os números de convênio ativos."""
    try:
        cardapio = formatar_cardapio()
    except Exception as e:
        log.error(f"[broadcast] Erro ao montar cardápio: {e}")
        return

    try:
        convenios = await db.fetchall(
            "SELECT numero_whatsapp, nome_empresa FROM empresas_convenio WHERE ativo = 1"
        )
    except Exception as e:
        log.error(f"[broadcast] Erro ao buscar convênios: {e}")
        return

    if not convenios:
        log.info("[broadcast] Nenhum convênio ativo encontrado")
        return

    log.info(f"[broadcast] Enviando cardápio para {len(convenios)} convênio(s)")
    for c in convenios:
        numero = c["numero_whatsapp"]
        nome   = c.get("nome_empresa", "")
        try:
            await enviar_texto(numero, f"Bom dia, *{nome}*! 🍽️\n\n{cardapio}")
            log.info(f"[broadcast] Cardápio enviado para {nome} ({numero})")
        except Exception as e:
            log.error(f"[broadcast] Erro ao enviar para {nome} ({numero}): {e}")
