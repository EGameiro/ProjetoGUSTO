"""
Extrai dados de pedido de uma mensagem em linguagem natural usando Claude.
Retorna um dict com os campos encontrados (None para os não encontrados).
"""
import json
import logging
import re
import httpx
import config

log = logging.getLogger(__name__)

_URL = "https://api.anthropic.com/v1/messages"
_HEADERS = {
    "x-api-key": config.ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

_SYSTEM_EXTRATOR_BASE = """\
Você é um assistente que extrai dados de pedido de uma mensagem de WhatsApp de restaurante.
Extraia APENAS o que estiver claramente mencionado. Não invente dados.
Responda SOMENTE com JSON válido, sem texto adicional.

O cliente pode pedir UM ou MAIS pratos na mesma mensagem.
Retorne SEMPRE no formato abaixo:

{
  "itens": [
    {
      "mistura": "nome do prato (string ou null)",
      "quantidade": 1,
      "tamanho": "Mini | Normal | Executiva (string ou null)",
      "acomp_1": "primeiro acompanhamento, nome EXATO da lista (string ou null)",
      "acomp_2": "segundo acompanhamento, se houver (string ou null)",
      "sem_acompanhamento": true se disse que não quer acompanhamento (bool ou null),
      "observacoes": "observações especiais (string ou null)"
    }
  ],
  "tipo_entrega": "entrega | retirada (string ou null)",
  "endereco": "endereço completo se for entrega (string ou null)",
  "hora_retirada": "horário se for retirada (string ou null)"
}

REGRAS:
- Se o cliente pediu N pratos DIFERENTES, retorne N objetos dentro de "itens"
- Se o cliente pediu N unidades do MESMO prato (ex: "3 feijoadas"), retorne 1 objeto com quantidade=3
- Se mencionou apenas um prato sem quantidade, use quantidade=1
- Para acompanhamentos: faça correspondência parcial com a lista fornecida e use o nome EXATO
- tamanho e acompanhamentos mencionados sem especificar o prato se aplicam a TODOS os itens
"""

_SYSTEM_ASSISTENTE = """\
Você é o atendente virtual do restaurante GUSTO, em Vila Branca, Jacareí-SP.
Trabalhamos com marmitas executivas. O cardápio do dia é informado na conversa.
Tamanhos disponíveis: Mini (R$21,90), Normal (R$23,90), Executiva (R$24,90), Churrasco (R$27,90).
O tamanho "Churrasco" é uma marmita maior, não é churrasco de grelha.
Entregamos gratuitamente em Vila Branca.

Responda a dúvida do cliente de forma simpática e curta (máximo 2 frases).
Não invente informações. Se não souber, diga que vai verificar.
Ao final, redirecione sutilmente para o pedido.
"""


_ITEM_VAZIO = {
    "mistura": None, "quantidade": 1, "tamanho": None,
    "acomp_1": None, "acomp_2": None,
    "sem_acompanhamento": None, "observacoes": None,
}

_RESULTADO_VAZIO = {
    "itens": [], "tipo_entrega": None,
    "endereco": None, "hora_retirada": None,
}


def _normalizar_item(item: dict) -> dict:
    if item.get("tamanho"):
        item["tamanho"] = item["tamanho"].strip().title()
    for campo in ("acomp_1", "acomp_2"):
        if item.get(campo):
            item[campo] = item[campo].strip().title()
    return {**_ITEM_VAZIO, **item}


async def extrair_pedido(texto: str, pratos: list[str] | None = None, acompanhamentos: list[str] | None = None) -> dict:
    """
    Extrai pedido da mensagem. Retorna dict com:
      itens: lista de {mistura, tamanho, acomp_1, acomp_2, sem_acompanhamento, observacoes}
      tipo_entrega, endereco, hora_retirada
    """
    system = _SYSTEM_EXTRATOR_BASE
    if pratos:
        system += f"\nPratos disponíveis hoje: {', '.join(pratos)}"
    if acompanhamentos:
        system += f"\nAcompanhamentos disponíveis (use o nome EXATO): {', '.join(acompanhamentos)}"

    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": system,
            "messages": [{"role": "user", "content": texto}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_URL, json=payload, headers=_HEADERS)
            if not resp.is_success:
                log.warning(f"Extrator: erro HTTP {resp.status_code}")
                return _RESULTADO_VAZIO
            data = resp.json()
            raw = data["content"][0]["text"].strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()
            log.info(f"Extrator raw: {raw}")
            resultado = json.loads(raw)

            itens = [_normalizar_item(i) for i in resultado.get("itens", [])]
            return {
                "itens": itens,
                "tipo_entrega": resultado.get("tipo_entrega"),
                "endereco": resultado.get("endereco"),
                "hora_retirada": resultado.get("hora_retirada"),
            }
    except Exception as e:
        log.warning(f"Extrator: falha ao extrair pedido — {type(e).__name__}: {e}")
        return _RESULTADO_VAZIO


def _nada_extraido(resultado: dict) -> bool:
    """Retorna True se o extrator não encontrou nenhum campo útil."""
    itens = resultado.get("itens", [])
    tem_dado = any(
        i.get("mistura") or i.get("tamanho") or i.get("acomp_1") or i.get("sem_acompanhamento")
        for i in itens
    )
    return not tem_dado and not resultado.get("tipo_entrega") and not resultado.get("endereco") and not resultado.get("hora_retirada")


async def responder_pergunta(texto: str, cardapio_texto: str) -> str | None:
    """
    Quando o usuário manda uma dúvida em vez de um pedido,
    gera uma resposta contextual curta. Retorna None se falhar.
    """
    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "system": _SYSTEM_ASSISTENTE,
            "messages": [
                {"role": "user", "content": f"Cardápio de hoje:\n{cardapio_texto}\n\nCliente disse: {texto}"}
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_URL, json=payload, headers=_HEADERS)
            if not resp.is_success:
                return None
            data = resp.json()
            return data["content"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Assistente: falha — {e}")
        return None
