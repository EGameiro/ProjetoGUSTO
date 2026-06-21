import logging
from services import session as sess
from services.uazapi import enviar_texto
from services.cardapio import formatar_cardapio, get_acompanhamentos_hoje, get_precos_hoje
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
        await _inicio(numero, push_name)
        return

    if etapa == "inicio":
        await _inicio(numero, push_name)

    elif etapa == "coletando":
        await _coletando(numero, sessao, texto)

    elif etapa == "aguardando_confirmacao":
        await _receber_confirmacao(numero, sessao, texto)

    else:
        # Estado desconhecido (sessão antiga) — reinicia
        log.warning(f"[{numero}] Estado desconhecido '{etapa}', reiniciando sessão")
        await sess.delete_session(numero)
        await _inicio(numero)


# ── Etapas ────────────────────────────────────────────────────────────────────

async def _inicio(numero: str, push_name: str = ""):
    nome = await buscar_nome_cliente(numero) or push_name or ""
    saudacao = f"Olá, *{nome.split()[0]}*! " if nome else "Olá! "

    cardapio = formatar_cardapio()
    await enviar_texto(numero, f"{saudacao}Bem-vindo ao *GUSTO* 🍽️\n\n{cardapio}")
    await enviar_texto(numero, "Qual prato você vai querer hoje?")
    await sess.set_session(numero, {"etapa": "coletando"})


async def _coletando(numero: str, sessao: dict, texto: str):
    """
    A cada mensagem: extrai dados, mescla com sessão, pergunta só o que falta.
    """
    # Extrai campos da mensagem atual
    extraido = await extrair_pedido(texto)
    log.info(f"[{numero}] extraido={extraido}")

    # Se não extraiu nada útil, é uma dúvida — responde e aguarda pedido
    if _nada_extraido(extraido):
        cardapio = formatar_cardapio()
        resposta = await responder_pergunta(texto, cardapio)
        if resposta:
            await enviar_texto(numero, resposta)
        else:
            await enviar_texto(numero, "Não entendi bem. Pode me dizer qual prato você gostaria?")
        return  # mantém etapa=coletando, aguarda próxima mensagem

    # Mescla na sessão (nunca sobrescreve com None o que já estava preenchido)
    _mesclar(sessao, extraido)

    # Verifica o que falta
    faltando = _campos_faltando(sessao)

    if faltando:
        sessao["etapa"] = "coletando"
        await sess.set_session(numero, sessao)
        await enviar_texto(numero, _montar_pergunta_faltando(sessao, faltando))
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


# ── Lógica de campos faltando ─────────────────────────────────────────────────

def _mesclar(sessao: dict, extraido: dict):
    """Copia do extraido para sessao, sem sobrescrever campos já preenchidos com None."""
    campos = ["mistura", "tamanho", "acomp_1", "acomp_2",
              "observacoes", "tipo_entrega", "endereco", "hora_retirada"]
    for campo in campos:
        valor = extraido.get(campo)
        if valor is not None and not sessao.get(campo):
            sessao[campo] = valor

    # marca explicitamente que não quer acompanhamento
    if extraido.get("sem_acompanhamento"):
        sessao["sem_acompanhamento"] = True

    # normaliza tamanho para title case e valida
    if sessao.get("tamanho"):
        precos = get_precos_hoje()
        t = sessao["tamanho"].strip().title()
        if t in precos:
            sessao["tamanho"]        = t
            sessao["valor_unitario"] = precos[t]
        else:
            sessao.pop("tamanho", None)
            sessao.pop("valor_unitario", None)

    # se mistura ainda não está e texto é simples, usa o texto direto
    # (tratado em _coletando)


def _campos_faltando(sessao: dict) -> list:
    faltando = []

    if not sessao.get("mistura"):
        faltando.append("mistura")

    if not sessao.get("tamanho"):
        faltando.append("tamanho")

    if not sessao.get("acomp_1") and not sessao.get("sem_acompanhamento"):
        faltando.append("acomp")

    tipo = sessao.get("tipo_entrega")
    if not tipo:
        faltando.append("entrega")
    elif tipo == "entrega" and not sessao.get("endereco"):
        faltando.append("endereco")
    elif tipo == "retirada" and not sessao.get("hora_retirada"):
        faltando.append("horario")

    return faltando


def _montar_pergunta_faltando(sessao: dict, faltando: list) -> str:
    partes = ["Ainda preciso de algumas informações:\n"]

    for campo in faltando:
        if campo == "mistura":
            partes.append("• *Qual prato* você quer?")
        elif campo == "tamanho":
            opcoes = " | ".join(f"{k} ({brl(v)})" for k, v in get_precos_hoje().items())
            partes.append(f"• *Tamanho:* {opcoes}")
        elif campo == "acomp":
            acomps = get_acompanhamentos_hoje()
            lista  = ", ".join(a.title() for a in acomps)
            partes.append(f"• *Acompanhamentos* (até 2): {lista}")
        elif campo == "entrega":
            partes.append("• *Entrega ou retirada?*\n  Se entrega, informe o endereço.\n  Se retirada, informe o horário.")
        elif campo == "endereco":
            partes.append("• *Endereço* de entrega?")
        elif campo == "horario":
            partes.append("• *Que horas* você busca?")

    return "\n".join(partes)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enviar_resumo(numero: str, sessao: dict):
    acomps = []
    if sessao.get("acomp_1"):
        acomps.append(sessao["acomp_1"])
    if sessao.get("acomp_2"):
        acomps.append(sessao["acomp_2"])
    acomps_texto = " + ".join(acomps) if acomps else "Nenhum"

    entrega = (
        f"Retirada as {sessao.get('hora_retirada')}"
        if sessao.get("tipo_entrega") == "retirada"
        else f"Entrega em: {sessao.get('endereco')}"
    )

    obs = f"\nObs: {sessao['observacoes']}" if sessao.get("observacoes") else ""

    resumo = (
        f"*Resumo do pedido:*\n\n"
        f"Prato: {sessao.get('mistura')} — {sessao.get('tamanho')}\n"
        f"Acompanhamentos: {acomps_texto}\n"
        f"Valor: {brl(sessao.get('valor_unitario', 0))}"
        f"{obs}\n\n"
        f"{entrega}\n\n"
        f"*Confirma?* Responda *sim* ou *não*."
    )

    await enviar_texto(numero, resumo)
