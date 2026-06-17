import logging
from db import connection as db

log = logging.getLogger(__name__)


async def classificar(numero: str) -> tuple[str, dict | None]:
    """
    Verifica se o número pertence a um cliente convênio.

    Retorna:
        ('convenio', empresa_row)  — se encontrado em empresas_convenio
        ('individual', None)       — caso contrário
    """
    try:
        empresa = await db.fetchone(
            "SELECT * FROM empresas_convenio WHERE numero_whatsapp = %s AND ativo = 1",
            (numero,)
        )
        if empresa:
            log.info(f"[{numero}] Classificado como CONVÊNIO — {empresa['nome_empresa']}")
            return "convenio", empresa

    except Exception as e:
        log.error(f"[{numero}] Erro ao consultar empresas_convenio: {e}")

    log.info(f"[{numero}] Classificado como INDIVIDUAL")
    return "individual", None
