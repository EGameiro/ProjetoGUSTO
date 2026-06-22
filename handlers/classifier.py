import logging
from db import connection as db
from services.uazapi import enviar_texto

log = logging.getLogger(__name__)


async def eh_convenio(numero: str) -> bool:
    """
    Verifica se o número pertence a uma empresa conveniada.
    Se sim, envia mensagem orientando e retorna True para encerrar o fluxo.
    """
    try:
        row = await db.fetchone(
            "SELECT id FROM empresas_convenio WHERE numero_whatsapp = %s AND ativo = 1",
            (numero,)
        )
        if row:
            log.info(f"[{numero}] Número de convênio — enviando orientação")
            await enviar_texto(
                numero,
                "Este número de WhatsApp está associado a uma empresa conveniada e não pode realizar pedidos por aqui. "
                "Para fazer seu pedido, acesse o portal da sua empresa ou entre em contato com o restaurante. 🍽️"
            )
            return True
    except Exception as e:
        log.error(f"[{numero}] Erro ao consultar empresas_convenio: {e}")

    return False
