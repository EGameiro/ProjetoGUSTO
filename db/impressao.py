"""
Funções usadas pelo Windows Service para gerir a fila de impressão.
O agente FastAPI NUNCA importa este módulo — só o Windows Service o usa.

Contrato:
  - buscar_pendentes()  → lista de pedidos com impresso = 0
  - marcar_impresso(id) → seta impresso = 1
"""

import mysql.connector
import os


def _conn():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        database=os.getenv("MYSQL_DB", "gusto_agent"),
        user=os.getenv("MYSQL_USER", "gusto"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        charset="utf8mb4",
    )


def buscar_pendentes() -> list[dict]:
    """
    Retorna lista de dicts com:
      pedido: { id, tipo, empresa_id, numero_whatsapp, data_pedido, horario_pedido,
                endereco_entrega, hora_retirada, forma_pgto }
      itens:  lista de { nome_pessoa, mistura, tamanho, acomp_1, acomp_2,
                          observacoes, valor_unitario }
    """
    conn = _conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT p.id, p.tipo, p.empresa_id, p.numero_whatsapp,
                   p.data_pedido, p.horario_pedido,
                   p.endereco_entrega, p.hora_retirada, p.forma_pgto
              FROM pedidos p
             WHERE p.impresso = 0
               AND p.status != 'cancelado'
             ORDER BY p.criado_em ASC
        """)
        pedidos = cur.fetchall()

        resultado = []
        for p in pedidos:
            cur.execute("""
                SELECT nome_pessoa, mistura, tamanho,
                       acomp_1, acomp_2, observacoes, valor_unitario
                  FROM itens_pedido
                 WHERE pedido_id = %s
            """, (p["id"],))
            itens = cur.fetchall()
            resultado.append({"pedido": p, "itens": itens})

        return resultado
    finally:
        conn.close()


def buscar_nome_empresa(empresa_id: int) -> str:
    conn = _conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT nome_empresa FROM empresas_convenio WHERE id = %s",
            (empresa_id,)
        )
        row = cur.fetchone()
        return row["nome_empresa"] if row else "EMPRESA"
    finally:
        conn.close()


def marcar_impresso(pedido_id: int):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE pedidos SET impresso = 1 WHERE id = %s",
            (pedido_id,)
        )
        conn.commit()
    finally:
        conn.close()
