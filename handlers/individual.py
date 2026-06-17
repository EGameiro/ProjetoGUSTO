import logging
from services import session as sess
from services.uazapi import enviar_texto
from services.cardapio import formatar_cardapio, get_acompanhamentos_hoje, PRECOS
from db.pedidos import salvar_pedido_individual

log = logging.getLogger(__name__)

TAMANHOS = ["mini", "normal", "executiva", "churrasco"]


def brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


async def processar(msg: dict):
    numero = msg["numero"]
    texto  = (msg["texto"] or "").strip()

    sessao = await sess.get_session(numero)
    etapa  = sessao.get("etapa", "inicio")

    log.info(f"[{numero}] etapa={etapa} | texto={texto!r}")

    if etapa == "inicio":
        await _inicio(numero, sessao)

    elif etapa == "aguardando_mistura":
        await _receber_mistura(numero, sessao, texto)

    elif etapa == "aguardando_tamanho":
        await _receber_tamanho(numero, sessao, texto)

    elif etapa == "aguardando_acomp":
        await _receber_acomp(numero, sessao, texto)

    elif etapa == "aguardando_obs":
        await _receber_obs(numero, sessao, texto)

    elif etapa == "aguardando_entrega":
        await _receber_entrega(numero, sessao, texto)

    elif etapa == "aguardando_horario":
        await _receber_horario(numero, sessao, texto)

    elif etapa == "aguardando_confirmacao":
        await _receber_confirmacao(numero, sessao, texto)


# ── Etapas ────────────────────────────────────────────────────────────────────

async def _inicio(numero: str, sessao: dict):
    cardapio = formatar_cardapio()
    await enviar_texto(numero, f"Olá! Bem-vindo ao *GUSTO* 🍽️\n\n{cardapio}")
    await enviar_texto(numero, "Qual prato você vai querer hoje?")
    await sess.set_session(numero, {"etapa": "aguardando_mistura"})


async def _receber_mistura(numero: str, sessao: dict, texto: str):
    if not texto:
        await enviar_texto(numero, "Por favor, me diga qual prato você escolheu.")
        return

    sessao["mistura"] = texto.title()
    sessao["etapa"]   = "aguardando_tamanho"
    await sess.set_session(numero, sessao)

    await enviar_texto(
        numero,
        "Qual tamanho?\n\n"
        f"• *Mini* — {brl(PRECOS['Mini'])}\n"
        f"• *Normal* — {brl(PRECOS['Normal'])}\n"
        f"• *Executiva* — {brl(PRECOS['Executiva'])}\n"
        f"• *Churrasco* — {brl(PRECOS['Churrasco'])}"
    )


async def _receber_tamanho(numero: str, sessao: dict, texto: str):
    tamanho = texto.strip().title()

    if tamanho.lower() not in TAMANHOS:
        await enviar_texto(
            numero,
            "Tamanho inválido. Escolha:\n• Mini\n• Normal\n• Executiva\n• Churrasco"
        )
        return

    sessao["tamanho"]       = tamanho
    sessao["valor_unitario"] = PRECOS[tamanho]
    sessao["etapa"]         = "aguardando_acomp"
    await sess.set_session(numero, sessao)

    acomps = get_acompanhamentos_hoje()
    lista  = "\n".join(f"• {a.title()}" for a in acomps)
    await enviar_texto(
        numero,
        f"Escolha até 2 acompanhamentos:\n\n{lista}\n\n"
        "_Separe por vírgula se quiser 2. Ex: Fritas, Farofa_"
    )


async def _receber_acomp(numero: str, sessao: dict, texto: str):
    partes  = [p.strip().title() for p in texto.split(",") if p.strip()]
    acomp_1 = partes[0] if len(partes) > 0 else None
    acomp_2 = partes[1] if len(partes) > 1 else None

    sessao["acomp_1"] = acomp_1
    sessao["acomp_2"] = acomp_2
    sessao["etapa"]   = "aguardando_obs"
    await sess.set_session(numero, sessao)

    await enviar_texto(
        numero,
        "Alguma observação? (ex: sem feijão, frango bem passado)\n\n"
        "_Ou responda *não* para continuar._"
    )


async def _receber_obs(numero: str, sessao: dict, texto: str):
    nao = texto.lower() in ["não", "nao", "n", "nenhuma", "nenhuma observacao", "nenhuma observação"]
    sessao["observacoes"] = None if nao else texto
    sessao["etapa"]       = "aguardando_entrega"
    await sess.set_session(numero, sessao)

    await enviar_texto(
        numero,
        "Entrega ou retirada?\n\n"
        "• Se *entrega*, me mande o endereço completo.\n"
        "• Se *retirada*, responda _retirada_."
    )


async def _receber_entrega(numero: str, sessao: dict, texto: str):
    if texto.lower() in ["retirada", "vou buscar", "buscar", "pegar"]:
        sessao["tipo_entrega"] = "retirada"
        sessao["endereco"]     = None
        sessao["etapa"]        = "aguardando_horario"
        await sess.set_session(numero, sessao)
        await enviar_texto(numero, "Que horas você busca? (ex: 12h, 12:30)")
    else:
        sessao["tipo_entrega"] = "entrega"
        sessao["endereco"]     = texto
        sessao["etapa"]        = "aguardando_confirmacao"
        await sess.set_session(numero, sessao)
        await _enviar_resumo(numero, sessao)


async def _receber_horario(numero: str, sessao: dict, texto: str):
    sessao["hora_retirada"] = texto
    sessao["etapa"]         = "aguardando_confirmacao"
    await sess.set_session(numero, sessao)
    await _enviar_resumo(numero, sessao)


async def _receber_confirmacao(numero: str, sessao: dict, texto: str):
    if texto.lower() in ["sim", "s", "yes", "confirmo", "ok", "pode", "pode ser"]:
        try:
            pedido_id = await salvar_pedido_individual(sessao, numero)
            await sess.delete_session(numero)
            await enviar_texto(
                numero,
                f"✅ *Pedido anotado!* 😉\n\n"
                f"Número do pedido: *#{pedido_id}*\n"
                f"Tempo estimado: 35 a 50 min 🛵"
            )
            log.info(f"[{numero}] Pedido #{pedido_id} salvo com sucesso")
        except Exception as e:
            log.error(f"[{numero}] Erro ao salvar pedido: {e}")
            await enviar_texto(numero, "Ops, tivemos um problema ao registrar seu pedido. Tente novamente.")

    elif texto.lower() in ["não", "nao", "n", "cancelar", "cancela"]:
        await sess.delete_session(numero)
        await enviar_texto(numero, "Pedido cancelado. Quando quiser, é só chamar! 😊")

    else:
        await _enviar_resumo(numero, sessao)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _enviar_resumo(numero: str, sessao: dict):
    acomps = []
    if sessao.get("acomp_1"):
        acomps.append(sessao["acomp_1"])
    if sessao.get("acomp_2"):
        acomps.append(sessao["acomp_2"])
    acomps_texto = " + ".join(acomps) if acomps else "Nenhum"

    entrega = (
        f"Retirada às {sessao.get('hora_retirada')}"
        if sessao.get("tipo_entrega") == "retirada"
        else f"Entrega em: {sessao.get('endereco')}"
    )

    obs = f"\n⚠️ Obs: {sessao['observacoes']}" if sessao.get("observacoes") else ""

    resumo = (
        f"📋 *Resumo do pedido:*\n\n"
        f"🍽️ {sessao.get('mistura')} — {sessao.get('tamanho')}\n"
        f"🥗 {acomps_texto}\n"
        f"💰 {brl(sessao.get('valor_unitario', 0))}"
        f"{obs}\n\n"
        f"🏠 {entrega}\n\n"
        f"*Confirma?* Responda *sim* ou *não*."
    )

    await enviar_texto(numero, resumo)
