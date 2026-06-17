from datetime import date, datetime
from db import connection as db


async def salvar_pedido_individual(sessao: dict, numero: str) -> int:
    pedido_id = await db.execute(
        """
        INSERT INTO pedidos
            (tipo, cliente_id, empresa_id, numero_whatsapp,
             data_pedido, horario_pedido, endereco_entrega,
             hora_retirada, forma_pgto, status, impresso)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            "individual",
            None,
            None,
            numero,
            date.today(),
            datetime.now().strftime("%H:%M:%S"),
            sessao.get("endereco"),
            sessao.get("hora_retirada"),
            None,
            "pendente",
            0,
        )
    )

    await db.execute(
        """
        INSERT INTO itens_pedido
            (pedido_id, nome_pessoa, mistura, tamanho,
             acomp_1, acomp_2, observacoes, valor_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            pedido_id,
            sessao.get("nome", "Cliente"),
            sessao.get("mistura"),
            sessao.get("tamanho"),
            sessao.get("acomp_1"),
            sessao.get("acomp_2"),
            sessao.get("observacoes") or None,
            sessao.get("valor_unitario"),
        )
    )

    await upsert_cliente(numero, sessao)

    return pedido_id


async def upsert_cliente(numero: str, sessao: dict):
    existente = await db.fetchone(
        "SELECT id FROM clientes WHERE numero_whatsapp = %s", (numero,)
    )
    tipo_entrega = "retirada" if sessao.get("hora_retirada") else "entrega"
    endereco     = sessao.get("endereco")

    if existente:
        await db.execute(
            """
            UPDATE clientes
               SET nome = COALESCE(%s, nome),
                   tipo_entrega_pref = %s,
                   endereco_padrao   = COALESCE(%s, endereco_padrao),
                   ultima_interacao  = NOW()
             WHERE numero_whatsapp = %s
            """,
            (sessao.get("nome"), tipo_entrega, endereco, numero)
        )
    else:
        await db.execute(
            """
            INSERT INTO clientes
                (numero_whatsapp, nome, tipo_entrega_pref, endereco_padrao, ultima_interacao)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (numero, sessao.get("nome"), tipo_entrega, endereco)
        )
