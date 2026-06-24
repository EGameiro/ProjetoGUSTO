import logging
from services import session as sess
from services.uazapi import enviar_texto
from services.cardapio import formatar_cardapio, get_acompanhamentos_hoje, get_precos_hoje, get_cardapio_hoje
from services.extrator import extrair_pedido, responder_pergunta, _nada_extraido
from db.pedidos import salvar_pedido_individual, buscar_nome_cliente, buscar_pedido_aberto

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

    _SAUDACOES = {"oi", "oie", "ola", "olá", "eai", "eaí", "opa", "bom dia", "boa tarde", "boa noite", "hey", "hello", "hi"}
    if texto.lower().strip() in _SAUDACOES:
        await sess.delete_session(numero)
        await _inicio(numero, push_name, restaurante_id)
        return

    if etapa == "inicio":
        await _inicio(numero, push_name, restaurante_id)

    elif etapa == "coletando":
        await _coletando(numero, sessao, texto, restaurante_id)

    elif etapa == "aguardando_confirmacao":
        await _receber_confirmacao(numero, sessao, texto)

    elif etapa == "aguardando_intencao":
        await _receber_intencao(numero, sessao, texto, restaurante_id)

    else:
        log.warning(f"[{numero}] Estado desconhecido '{etapa}', reiniciando sessão")
        await sess.delete_session(numero)
        await _inicio(numero, restaurante_id=restaurante_id)


# ── Etapas ────────────────────────────────────────────────────────────────────

async def _inicio(numero: str, push_name: str = "", restaurante_id: int = 1):
    nome = await buscar_nome_cliente(numero) or push_name or ""
    primeiro_nome = nome.split()[0] if nome else ""
    saudacao = f"Olá, *{primeiro_nome}*! " if primeiro_nome else "Olá! "

    pedido_aberto = await buscar_pedido_aberto(numero)
    if pedido_aberto:
        _STATUS_LABEL = {
            "preparo": "em preparo 🍳",
            "saiu":    "saiu para entrega 🛵",
        }
        status_texto = _STATUS_LABEL.get(pedido_aberto["status"], pedido_aberto["status"])

        linhas_itens = []
        for item in pedido_aberto.get("itens", []):
            acomps = [a for a in [item.get("acomp_1"), item.get("acomp_2")] if a]
            acomp_txt = " + ".join(acomps) if acomps else ""
            linha = f"• *{item.get('mistura')}* — {item.get('tamanho')}"
            if acomp_txt:
                linha += f" | {acomp_txt}"
            linhas_itens.append(linha)

        itens_txt = "\n".join(linhas_itens)
        await enviar_texto(
            numero,
            f"{saudacao}Vi que você tem um pedido aqui que está *{status_texto}*:\n\n"
            f"{itens_txt}\n\n"
            f"Deseja fazer outro pedido ou era só para saber como está o seu pedido?"
        )
        await sess.set_session(numero, {
            "etapa": "aguardando_intencao",
            "restaurante_id": restaurante_id,
            "nome": nome,
        })
        return

    await _iniciar_coleta(numero, nome, saudacao, restaurante_id)


async def _iniciar_coleta(numero: str, nome: str, saudacao: str, restaurante_id: int):
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
    if not sessao.get("itens"):
        await sess.delete_session(numero)
        await _inicio(numero, restaurante_id=sessao.get("restaurante_id", 1))
        return

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


async def _receber_intencao(numero: str, sessao: dict, texto: str, restaurante_id: int):
    _SIM = {"sim", "s", "yes", "quero", "outro", "outro pedido", "fazer pedido", "pode", "ok"}
    _NAO = {"não", "nao", "n", "só queria saber", "so queria saber", "era so isso", "era só isso", "obrigado", "obrigada", "valeu"}

    t = texto.lower().strip()
    nome = sessao.get("nome", "")
    saudacao = f"*{nome.split()[0]}*" if nome else "você"

    if t in _SIM or any(p in t for p in ["outro", "novo pedido", "fazer", "quero"]):
        await _iniciar_coleta(numero, nome, f"Ótimo, {saudacao}! ", restaurante_id)
    elif t in _NAO or any(p in t for p in ["só", "so", "obrigad", "valeu", "saber"]):
        await sess.delete_session(numero)
        await enviar_texto(numero, f"Tudo certo, {saudacao}! Qualquer coisa é só chamar. 😊")
    else:
        await enviar_texto(
            numero,
            "Deseja fazer um *novo pedido* ou era só para saber como está o seu pedido atual?"
        )


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

    # Itens sem mistura: aplicar tamanho/acomp ao primeiro item incompleto da sessão
    itens_sem_mistura = [i for i in itens_extraidos if not (i.get("mistura") or "").strip()]
    itens_com_mistura = [i for i in itens_extraidos if (i.get("mistura") or "").strip()]

    for item_ext in itens_com_mistura:
        mistura_ext = item_ext["mistura"].lower()
        quantidade = max(1, int(item_ext.get("quantidade") or 1))

        # Resolve nome oficial e preço do cardápio
        preco = None
        nome_oficial = item_ext["mistura"]
        for nome_prato, p in c["pratos"]:
            if nome_prato.lower() in mistura_ext or mistura_ext in nome_prato.lower():
                preco = p
                nome_oficial = nome_prato
                break

        # Procura todos os itens existentes com essa mistura
        existentes = [i for i in itens_sessao if (i.get("mistura") or "").lower() == nome_oficial.lower()]

        if existentes:
            # Atualiza campos faltantes em todos os itens com essa mistura
            for item_existente in existentes:
                for campo in ("tamanho", "acomp_1", "acomp_2", "observacoes"):
                    if item_ext.get(campo) and not item_existente.get(campo):
                        item_existente[campo] = item_ext[campo]
                if item_ext.get("sem_acompanhamento"):
                    item_existente["sem_acompanhamento"] = True
        else:
            # Novo(s) item(ns) — cria quantidade cópias
            for _ in range(quantidade):
                novo = {**item_ext, "mistura": nome_oficial, "valor_unitario": preco}
                novo.pop("quantidade", None)
                itens_sessao.append(novo)

    # Tamanho/acomp sem prato → aplica ao primeiro item incompleto da sessão
    for item_ext in itens_sem_mistura:
        tem_dado = item_ext.get("tamanho") or item_ext.get("acomp_1") or item_ext.get("sem_acompanhamento")
        if not tem_dado:
            continue
        alvo = next(
            (i for i in itens_sessao if not i.get("tamanho") or not i.get("acomp_1")),
            None
        )
        if alvo:
            # Aplica a TODOS os itens com a mesma mistura do alvo
            mistura_alvo = (alvo.get("mistura") or "").lower()
            alvos = [i for i in itens_sessao if (i.get("mistura") or "").lower() == mistura_alvo] if mistura_alvo else [alvo]
            for a in alvos:
                for campo in ("tamanho", "acomp_1", "acomp_2", "observacoes"):
                    if item_ext.get(campo) and not a.get(campo):
                        a[campo] = item_ext[campo]
                if item_ext.get("sem_acompanhamento"):
                    a["sem_acompanhamento"] = True

    sessao["itens"] = itens_sessao


def _campos_faltando(sessao: dict) -> list:
    """
    Retorna lista de campos faltando. Itens com a mesma mistura são agrupados:
    pergunta-se uma vez e aplica-se a todos.
    Entradas: strings simples (campos globais) ou tuplas ("tipo", "label", qtd).
    """
    faltando = []

    if not sessao.get("itens"):
        faltando.append("mistura")
        return faltando

    # Agrupa itens por mistura para não perguntar N vezes a mesma coisa
    vistos: set[str] = set()
    for item in sessao["itens"]:
        mistura = item.get("mistura") or ""
        chave = mistura.lower()
        qtd = sum(1 for i in sessao["itens"] if (i.get("mistura") or "").lower() == chave)
        label = f"{qtd}x {mistura}" if qtd > 1 else mistura

        if chave not in vistos:
            vistos.add(chave)
            if not item.get("tamanho"):
                faltando.append(("tamanho", label, chave))
            if not item.get("acomp_1") and not item.get("sem_acompanhamento"):
                faltando.append(("acomp", label, chave))

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
    c = await get_cardapio_hoje(restaurante_id)

    campos_item = [f for f in faltando if isinstance(f, tuple)]
    campos_globais = [f for f in faltando if not isinstance(f, tuple)]

    if campos_item:
        # Pega o primeiro grupo de mistura com campos faltando
        primeiro_label = campos_item[0][1]
        primeiro_chave = campos_item[0][2]
        campos_desse_item = [f for f in campos_item if f[2] == primeiro_chave]

        partes = [f"Sobre *{primeiro_label}*:\n"]
        for tipo, _, _ in campos_desse_item:
            if tipo == "tamanho":
                opcoes = " | ".join(c["tamanhos"])
                partes.append(f"• *Tamanho:* {opcoes}")
            elif tipo == "acomp":
                lista = ", ".join(a.title() for a in c["acompanhamentos"])
                partes.append(f"• *Acompanhamentos* (até 2): {lista}")
        return "\n".join(partes)

    # Só campos globais
    partes = ["Ainda preciso de algumas informações:\n"]
    for campo in campos_globais:
        if campo == "mistura":
            partes.append("• *Qual prato* você quer?")
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

    # Agrupa itens iguais para exibir "3x Feijoada" em vez de 3 linhas idênticas
    vistos: dict[str, dict] = {}
    for item in itens:
        chave = f"{item.get('mistura')}|{item.get('tamanho')}|{item.get('acomp_1')}|{item.get('acomp_2')}"
        if chave in vistos:
            vistos[chave]["_qtd"] += 1
        else:
            vistos[chave] = {**item, "_qtd": 1}

    for i, item in enumerate(vistos.values(), 1):
        qtd = item["_qtd"]
        acomps = [a for a in [item.get("acomp_1"), item.get("acomp_2")] if a]
        acomps_texto = " + ".join(acomps) if acomps else "Nenhum"
        valor_unit = item.get("valor_unitario") or 0
        valor_linha = valor_unit * qtd
        total += valor_linha
        obs = f"\n   Obs: {item['observacoes']}" if item.get("observacoes") else ""
        prefixo = f"{qtd}x " if qtd > 1 else ""
        linhas_itens.append(
            f"{i}. {prefixo}*{item.get('mistura')}* — {item.get('tamanho')}\n"
            f"   Acomp: {acomps_texto} | {brl(valor_linha)}{obs}"
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
