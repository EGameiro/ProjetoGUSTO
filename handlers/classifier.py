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
            log.info(f"[{numero}] Número de convênio — ignorando mensagem")
            return True
    except Exception as e:
        log.error(f"[{numero}] Erro ao consultar empresas_convenio: {e}")

    return False
