from datetime import date
from db import connection as db


async def listar_pedidos_hoje() -> list[dict]:
    """Retorna todos os pedidos de hoje com seus itens."""
    hoje = date.today().isoformat()
    pedidos = await db.fetchall(
        """
        SELECT p.id, p.tipo, p.numero_whatsapp, p.data_pedido, p.horario_pedido,
               p.endereco_entrega, p.hora_retirada, p.forma_pgto,
               p.status, p.impresso, p.criado_em,
               e.nome_empresa
          FROM pedidos p
          LEFT JOIN empresas_convenio e ON e.id = p.empresa_id
         WHERE p.data_pedido = %s
         ORDER BY p.criado_em ASC
        """,
        (hoje,)
    )

    resultado = []
    for p in pedidos:
        itens = await db.fetchall(
            """
            SELECT nome_pessoa, mistura, tamanho,
                   acomp_1, acomp_2, observacoes, valor_unitario
              FROM itens_pedido
             WHERE pedido_id = %s
            """,
            (p["id"],)
        )
        resultado.append({**p, "itens": itens})

    return resultado


async def totais_hoje() -> dict:
    hoje = date.today().isoformat()
    row = await db.fetchone(
        """
        SELECT
            COUNT(DISTINCT p.id)                                      AS total_pedidos,
            SUM(CASE WHEN p.tipo = 'individual' THEN 1 ELSE 0 END)   AS individuais,
            SUM(CASE WHEN p.tipo = 'convenio'   THEN 1 ELSE 0 END)   AS convenios,
            SUM(CASE WHEN p.status = 'entregue' THEN 1 ELSE 0 END)   AS entregues,
            SUM(CASE WHEN p.impresso = 0        THEN 1 ELSE 0 END)   AS aguardando_impressao,
            COALESCE(SUM(i.valor_unitario), 0)                        AS faturamento_total,
            COUNT(i.id)                                               AS total_marmitas
          FROM pedidos p
          LEFT JOIN itens_pedido i ON i.pedido_id = p.id
         WHERE p.data_pedido = %s
        """,
        (hoje,)
    )
    return row or {}


async def atualizar_status(pedido_id: int, novo_status: str):
    await db.execute(
        "UPDATE pedidos SET status = %s WHERE id = %s",
        (novo_status, pedido_id)
    )
