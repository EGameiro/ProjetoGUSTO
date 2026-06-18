import logging
import httpx
import config
from services import session as sess
from services.uazapi import enviar_texto
from services.parser_planilha import parsear
from services.cardapio import brl, get_precos_hoje
from db.pedidos import salvar_lote_convenio

log = logging.getLogger(__name__)

_HEADERS_UAZAPI = {"token": config.UAZAPI_TOKEN}


async def processar(msg: dict, empresa: dict):
    numero    = msg["numero"]
    tipo      = msg["tipo_midia"]
    texto     = (msg["texto"] or "").strip()
    url_midia = msg.get("url_midia")

    sessao = await sess.get_session(numero)
    etapa  = sessao.get("etapa", "aguardando_documento")

    log.info(f"[CONVENIO][{numero}] etapa={etapa} | tipo={tipo}")

    if etapa == "aguardando_documento":
        if tipo == "documento" and url_midia:
            await _processar_planilha(numero, sessao, empresa, url_midia)
        else:
            await enviar_texto(
                numero,
                f"Olá, *{empresa.get('nome_empresa', 'empresa')}*! 👋\n\n"
                "Para registrar os pedidos, envie a planilha Excel (.xlsx) com os pedidos do dia."
            )
            await sess.set_session(numero, {"etapa": "aguardando_documento"})

    elif etapa == "aguardando_confirmacao":
        await _receber_confirmacao(numero, sessao, texto, empresa)


# ── Internos ──────────────────────────────────────────────────────────────────

async def _processar_planilha(numero: str, sessao: dict, empresa: dict, url_midia: str):
    await enviar_texto(numero, "Recebi a planilha! Processando os pedidos... ⏳")

    try:
        conteudo = await _baixar_arquivo(url_midia)
    except Exception as e:
        log.error(f"[CONVENIO][{numero}] Erro ao baixar arquivo: {e}")
        await enviar_texto(numero, "Não consegui baixar o arquivo. Tente enviar novamente.")
        return

    pedidos = parsear(conteudo)

    if not pedidos:
        await enviar_texto(
            numero,
            "Não consegui identificar os pedidos na planilha. "
            "Verifique o formato e tente novamente."
        )
        return

    sessao["etapa"]      = "aguardando_confirmacao"
    sessao["pedidos"]    = pedidos
    sessao["empresa_id"] = empresa.get("id")
    sessao["endereco"]   = empresa.get("endereco_padrao")
    await sess.set_session(numero, sessao)

    resumo = _montar_resumo(pedidos)
    await enviar_texto(numero, resumo)


async def _receber_confirmacao(numero: str, sessao: dict, texto: str, empresa: dict):
    if texto.lower() in ["sim", "s", "yes", "confirmo", "ok", "pode", "confirmar"]:
        pedidos    = sessao.get("pedidos", [])
        empresa_id = sessao.get("empresa_id") or empresa.get("id")

        try:
            ids = await salvar_lote_convenio(pedidos, numero, empresa_id)
            await sess.delete_session(numero)
            await enviar_texto(
                numero,
                f"Pedidos confirmados! ✅\n\n"
                f"*{len(ids)} pedido(s)* registrado(s) com sucesso.\n"
                f"Números: {', '.join(f'#{i}' for i in ids)}\n\n"
                f"Previsão de entrega: *{empresa.get('horario_padrao', 'a confirmar')}* 🛵"
            )
            log.info(f"[CONVENIO][{numero}] {len(ids)} pedidos salvos: {ids}")
        except Exception as e:
            log.error(f"[CONVENIO][{numero}] Erro ao salvar lote: {e}")
            await enviar_texto(numero, "Erro ao registrar os pedidos. Tente novamente.")

    elif texto.lower() in ["não", "nao", "n", "cancelar", "cancela"]:
        await sess.delete_session(numero)
        await enviar_texto(numero, "Pedidos cancelados. Envie uma nova planilha quando quiser. 👍")

    else:
        pedidos = sessao.get("pedidos", [])
        resumo  = _montar_resumo(pedidos)
        await enviar_texto(numero, resumo)


def _montar_resumo(pedidos: list[dict]) -> str:
    precos = get_precos_hoje()
    linhas = [f"*Resumo dos pedidos ({len(pedidos)} itens):*\n"]

    for i, p in enumerate(pedidos, 1):
        acomps = " + ".join(filter(None, [p.get("acomp_1"), p.get("acomp_2")])) or "—"
        valor  = precos.get(p["tamanho"], 0)
        obs    = f" ⚠️ _{p['observacoes']}_" if p.get("observacoes") else ""
        linhas.append(
            f"{i}. *{p['nome']}* — {p['mistura']} ({p['tamanho']}) | {acomps} | {brl(valor)}{obs}"
        )

    total = sum(precos.get(p["tamanho"], 0) for p in pedidos)
    linhas.append(f"\n💰 *Total: {brl(total)}*")
    linhas.append("\nResponda *sim* para confirmar ou *não* para cancelar.")
    return "\n".join(linhas)


async def _baixar_arquivo(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_HEADERS_UAZAPI)
        resp.raise_for_status()
        return resp.content
