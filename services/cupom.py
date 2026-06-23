"""
Formata cupons de impressão para pedidos individuais e de convênio.
Saída em texto puro (UTF-8) para impressora térmica de 42 colunas.
"""

from datetime import datetime

LARGURA = 42
SEP_SIMPLES = "─" * LARGURA
SEP_DUPLO   = "═" * LARGURA


def _centralizar(texto: str) -> str:
    return texto.center(LARGURA)


def _linha_kv(chave: str, valor: str) -> str:
    espacos = LARGURA - len(chave) - len(valor)
    if espacos < 1:
        espacos = 1
    return f"{chave}{' ' * espacos}{valor}"


def montar_cupom_individual(pedido: dict, itens: list[dict]) -> str:
    """
    pedido: linha da tabela `pedidos`
    itens:  lista de linhas da tabela `itens_pedido` (geralmente 1 item)
    """
    agora = datetime.now().strftime("%d/%m  %H:%M")
    linhas = [
        _linha_kv(agora, "INDIVIDUAL"),
        SEP_SIMPLES,
    ]

    numero = pedido.get("numero_whatsapp") or ""
    for item in itens:
        nome = (item.get("nome_pessoa") or "CLIENTE").upper()
        mistura = item.get("mistura") or ""
        tamanho = item.get("tamanho") or ""
        linhas.append(f"{nome}  {numero}")
        linhas.append(f"{mistura}  {tamanho}")

        acomps = [a for a in [item.get("acomp_1"), item.get("acomp_2")] if a]
        if acomps:
            linhas.append(" + ".join(a.title() for a in acomps))

        obs = item.get("observacoes") or ""
        if obs.strip():
            linhas.append(f"⚠ {obs}")

    entrega = pedido.get("endereco_entrega") or ""
    hora_ret = pedido.get("hora_retirada") or ""
    if hora_ret:
        linhas.append(f"Retirada ~{hora_ret}")
    elif entrega:
        linhas.append(f"Entrega: {entrega}")

    linhas.append(SEP_SIMPLES)
    return "\n".join(linhas)


def montar_cupom_convenio(pedido: dict, itens: list[dict], nome_empresa: str) -> str:
    """
    pedido:       linha da tabela `pedidos`
    itens:        lista de itens_pedido do lote
    nome_empresa: nome da empresa (de empresas_convenio)
    """
    agora = datetime.now().strftime("%d/%m  %H:%M")
    hora_ent = pedido.get("hora_retirada") or pedido.get("horario_entrega") or "—"

    linhas = [
        _centralizar(f"★ {nome_empresa.upper()} ★"),
        _centralizar(f"Entrega {hora_ent}"),
        SEP_DUPLO,
    ]

    total_valor = 0.0
    for item in itens:
        nome    = (item.get("nome_pessoa") or "").upper()
        mistura = item.get("mistura") or ""
        tamanho = item.get("tamanho") or ""
        valor   = float(item.get("valor_unitario") or 0)
        obs     = item.get("observacoes") or ""

        valor_str = f"R${valor:.2f}".replace(".", ",") if valor else ""

        linhas.append(nome)
        linha_prato = f"  {mistura}  {tamanho}"
        if valor_str:
            linha_prato = _linha_kv(f"  {mistura}  {tamanho}", valor_str)
        linhas.append(linha_prato)

        if obs.strip():
            linhas.append(f"  ⚠ {obs}")

        linhas.append(SEP_SIMPLES)
        total_valor += valor

    forma_pgto = pedido.get("forma_pgto") or "Convênio mensal"
    total_str  = f"R${total_valor:.2f}".replace(".", ",")

    linhas.append(_linha_kv(f"TOTAL: {len(itens)} marmita(s)", total_str))
    linhas.append(f"Forma pgto: {forma_pgto}")
    linhas.append(SEP_DUPLO)

    return "\n".join(linhas)
