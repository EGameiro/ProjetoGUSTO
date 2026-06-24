import logging
from services import session as sess
from services.uazapi import enviar_texto
from services.cardapio import formatar_cardapio, get_acompanhamentos_hoje, get_precos_hoje, get_cardapio_hoje
from services.extrator import extrair_pedido, responder_pergunta, _nada_extraido
from db.pedidos import salvar_pedido_individual, buscar_nome_cliente

log = logging.getLogger(__name__)


def brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


async def processar(msg: dict, restaurante_id: int = 1):
    numero    = msg["numero"]
    texto     = (msg["texto"] or "").strip()
    push_name = msg.get("push_name", "")

    sessao = await sess.get_session(numero)
    etapa  = sessao.get("etapa", "inicio")

    log.info(f"[{numero}] etapa={etapa} | texto={texto!r}")

    _SAUDACOES = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "hey", "hello", "hi"}
    if texto.lower().strip() in _SAUDACOES and etapa != "aguardando_confirmacao":
        await sess.delete_session(numero)
        await _inicio(numero, push_name, restaurante_id)
        return

    if etapa == "inicio":
        await _inicio(numero, push_name, restaurante_id)

    elif etapa == "coletando":
        await _coletando(numero, sessao, texto, restaurante_id)

    elif etapa == "aguardando_confirmacao":
        await _receber_confirmacao(numero, sessao, texto)

    else:
        log.warning(f"[{numero}] Estado desconhecido '{etapa}', reiniciando sessão")
        await sess.delete_session(numero)
        await _inicio(numero, restaurante_id=restaurante_id)


# ── Etapas ────────────────────────────────────────────────────────────────────

async def _inicio(numero: str, push_name: str = "", restaurante_id: int = 1):
    nome = await buscar_nome_cliente(numero) or push_name or ""
    saudacao = f"Olá, *{nome.split()[0]}*! " if nome else "Olá! "

    cardapio = await formatar_cardapio(restaurante_id)
    await enviar_texto(numero, f"{saudacao}Bem-vindo ao *GUSTO* 🍽️\n\n{cardapio}")
    await enviar_texto(numero, "Qual prato você vai querer hoje?")
    await sess.set_session(numero, {
        "etapa": "coletando",
        "restaurante_id": restaurante_id,
        "nome": nome,
        "itens": [],
        "tipo_entrega": None,
        "endereco": None,
        "hora_retirada": None,
    })


async def _coletando(numero: str, sessao: dict, texto: str, restaurante_id: int = 1):
    c = await get_cardapio_hoje(restaurante_id)
    pratos          = [nome for nome, _ in c["pratos"]]
    acompanhamentos = c["acompanhamentos"]

    extraido = await extrair_pedido(texto, pratos=pratos, acompanhamentos=acompanhamentos)
    log.info(f"[{numero}] extraido={extraido}")

    if _nada_extraido(extraido):
        cardapio = await formatar_cardapio(restaurante_id)
        resposta = await responder_pergunta(texto, cardapio)
        if resposta:
            await enviar_texto(numero, resposta)
        else:
            await enviar_texto(numero, "Não entendi bem. Pode me dizer qual prato você gostaria?")
        return

    await _mesclar(sessao, extraido, restaurante_id)

    faltando = _campos_faltando(sessao)

    if faltando:
        sessao["etapa"] = "coletando"
        await sess.set_session(numero, sessao)
        await enviar_texto(numero, await _montar_pergunta_faltando(sessao, faltando, restaurante_id))
    else:
        sessao["etapa"] = "aguardando_confirmacao"
        await sess.set_session(numero, sessao)
        await _enviar_resumo(numero, sessao)


async def _receber_confirmacao(numero: str, sessao: dict, texto: str):
    if texto.lower() in ["sim", "s", "yes", "confirmo", "ok", "pode", "pode ser"]:
        try:
            pedido_id = await salvar_pedido_individual(sessao, numero)
            await sess.delete_session(numero)
            await enviar_texto(
                numero,
                f"Pedido anotado! 😉\n\n"
                f"Número do pedido: *#{pedido_id}*\n"
                f"Tempo estimado: 35 a 50 min"
            )
            log.info(f"[{numero}] Pedido #{pedido_id} salvo com sucesso")
        except Exception as e:
            log.error(f"[{numero}] Erro ao salvar pedido: {e}")
            await enviar_texto(numero, "Ops, tivemos um problema ao registrar seu pedido. Tente novamente.")

    elif texto.lower() in ["não", "nao", "n", "cancelar", "cancela"]:
        await sess.delete_session(numero)
        await enviar_texto(numero, "Pedido cancelado. Quando quiser, é só chamar!")

    else:
        await _enviar_resumo(numero, sessao)


# ── Lógica de campos ──────────────────────────────────────────────────────────

async def _mesclar(sessao: dict, extraido: dict, restaurante_id: int = 1):
    """Mescla os dados extraídos na sessão, suportando múltiplos itens."""
    c = await get_cardapio_hoje(restaurante_id)

    # Mescla campos globais
    for campo in ("tipo_entrega", "endereco", "hora_retirada"):
        if extraido.get(campo) and not sessao.get(campo):
            sessao[campo] = extraido[campo]

    itens_sessao = sessao.get("itens", [])
    itens_extraidos = extraido.get("itens", [])

    for item_ext in itens_extraidos:
        mistura_ext = (item_ext.get("mistura") or "").lower()
        if not mistura_ext:
            continue

        # Procura item existente na sessão com a mesma mistura
        item_existente = next(
            (i for i in itens_sessao if (i.get("mistura") or "").lower() == mistura_ext),
            None
        )

        if item_existente:
            # Atualiza campos faltantes do item existente
            for campo in ("tamanho", "acomp_1", "acomp_2", "observacoes"):
                if item_ext.get(campo) and not item_existente.get(campo):
                    item_existente[campo] = item_ext[campo]
            if item_ext.get("sem_acompanhamento"):
                item_existente["sem_acompanhamento"] = True
        else:
            # Novo item — resolve preço pelo cardápio
            preco = None
            for nome_prato, p in c["pratos"]:
                if nome_prato.lower() in mistura_ext or mistura_ext in nome_prato.lower():
                    preco = p
                    # Usa o nome oficial do prato
                    item_ext["mistura"] = nome_prato
                    break
            item_ext["valor_unitario"] = preco
            itens_sessao.append(item_ext)

    # Se chegou tamanho/acomp global (sem prato especificado), aplica a todos os itens sem esse campo
    tamanho_global = extraido.get("itens", [{}])[0].get("tamanho") if len(extraido.get("itens", [])) == 1 and not extraido["itens"][0].get("mistura") else None
    if tamanho_global:
        for item in itens_sessao:
            if not item.get("tamanho"):
                item["tamanho"] = tamanho_global

    sessao["itens"] = itens_sessao


def _campos_faltando(sessao: dict) -> list:
    """Retorna lista de campos faltando, considerando todos os itens."""
    faltando = []

    if not sessao.get("itens"):
        faltando.append("mistura")
        return faltando

    # Verifica campos faltando por item
    for i, item in enumerate(sessao["itens"]):
        label = item.get("mistura") or f"Item {i+1}"

        if not item.get("tamanho"):
            faltando.append(("tamanho", label))

        if not item.get("acomp_1") and not item.get("sem_acompanhamento"):
            faltando.append(("acomp", label))

    # Campos globais
    tipo = sessao.get("tipo_entrega")
    if not tipo:
        faltando.append("entrega")
    elif tipo == "entrega" and not sessao.get("endereco"):
        faltando.append("endereco")
    elif tipo == "retirada" and not sessao.get("hora_retirada"):
        faltando.append("horario")

    return faltando


async def _montar_pergunta_faltando(sessao: dict, faltando: list, restaurante_id: int = 1) -> str:
    partes = ["Ainda preciso de algumas informações:\n"]

    for campo in faltando:
        if campo == "mistura":
            partes.append("• *Qual prato* você quer?")

        elif isinstance(campo, tuple) and campo[0] == "tamanho":
            _, label = campo
            c = await get_cardapio_hoje(restaurante_id)
            opcoes = " | ".join(c["tamanhos"])
            partes.append(f"• *Tamanho* do {label}: {opcoes}")

        elif isinstance(campo, tuple) and campo[0] == "acomp":
            _, label = campo
            acomps = await get_acompanhamentos_hoje(restaurante_id)
            lista  = ", ".join(a.title() for a in acomps)
            partes.append(f"• *Acompanhamentos* do {label} (até 2): {lista}")

        elif campo == "entrega":
            partes.append("• *Entrega ou retirada?*\n  Se entrega, informe o endereço.\n  Se retirada, informe o horário.")
        elif campo == "endereco":
            partes.append("• *Endereço* de entrega?")
        elif campo == "horario":
            partes.append("• *Que horas* você busca?")

    return "\n".join(partes)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enviar_resumo(numero: str, sessao: dict):
    itens = sessao.get("itens", [])
    total = 0.0
    linhas_itens = []

    for i, item in enumerate(itens, 1):
        acomps = [a for a in [item.get("acomp_1"), item.get("acomp_2")] if a]
        acomps_texto = " + ".join(acomps) if acomps else "Nenhum"
        valor = item.get("valor_unitario") or 0
        total += valor
        obs = f"\n   Obs: {item['observacoes']}" if item.get("observacoes") else ""
        linhas_itens.append(
            f"{i}. *{item.get('mistura')}* — {item.get('tamanho')}\n"
            f"   Acomp: {acomps_texto} | {brl(valor)}{obs}"
        )

    entrega = (
        f"Retirada às {sessao.get('hora_retirada')}"
        if sessao.get("tipo_entrega") == "retirada"
        else f"Entrega em: {sessao.get('endereco')}"
    )

    itens_texto = "\n".join(linhas_itens)
    resumo = (
        f"*Resumo do pedido:*\n\n"
        f"{itens_texto}\n\n"
        f"*Total: {brl(total)}*\n"
        f"{entrega}\n\n"
        f"*Confirma?* Responda *sim* ou *não*."
    )

    await enviar_texto(numero, resumo)
