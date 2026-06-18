from datetime import date
from db import connection as db


async def listar_pedidos_hoje() -> list[dict]:
    """Retorna todos os pedidos de hoje com seus itens (single JOIN query)."""
    hoje = date.today().isoformat()
    rows = await db.fetchall(
        """
        SELECT p.id, p.tipo, p.numero_whatsapp, p.data_pedido, p.horario_pedido,
               p.endereco_entrega, p.hora_retirada, p.forma_pgto,
               p.status, p.impresso, p.criado_em,
               e.nome_empresa,
               i.nome_pessoa, i.mistura, i.tamanho,
               i.acomp_1, i.acomp_2, i.observacoes, i.valor_unitario
          FROM pedidos p
          LEFT JOIN empresas_convenio e ON e.id = p.empresa_id
          LEFT JOIN itens_pedido i ON i.pedido_id = p.id
         WHERE p.data_pedido = %s
         ORDER BY p.criado_em ASC, i.id ASC
        """,
        (hoje,)
    )

    # Agrupa itens por pedido em Python
    pedidos: dict[int, dict] = {}
    for row in rows:
        pid = row["id"]
        if pid not in pedidos:
            pedidos[pid] = {
                "id":               row["id"],
                "tipo":             row["tipo"],
                "numero_whatsapp":  row["numero_whatsapp"],
                "data_pedido":      row["data_pedido"],
                "horario_pedido":   row["horario_pedido"],
                "endereco_entrega": row["endereco_entrega"],
                "hora_retirada":    row["hora_retirada"],
                "forma_pgto":       row["forma_pgto"],
                "status":           row["status"],
                "impresso":         row["impresso"],
                "criado_em":        row["criado_em"],
                "nome_empresa":     row["nome_empresa"],
                "itens":            [],
            }
        if row["mistura"]:  # pedido pode não ter itens (raro)
            pedidos[pid]["itens"].append({
                "nome_pessoa":   row["nome_pessoa"],
                "mistura":       row["mistura"],
                "tamanho":       row["tamanho"],
                "acomp_1":       row["acomp_1"],
                "acomp_2":       row["acomp_2"],
                "observacoes":   row["observacoes"],
                "valor_unitario": row["valor_unitario"],
            })

    return list(pedidos.values())


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
