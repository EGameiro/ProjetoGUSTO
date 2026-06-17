"""
Extrai dados de pedido de uma mensagem em linguagem natural usando Claude.
Retorna um dict com os campos encontrados (None para os não encontrados).
"""
import json
import logging
import httpx
import config

log = logging.getLogger(__name__)

_URL = "https://api.anthropic.com/v1/messages"
_HEADERS = {
    "x-api-key": config.ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

_SYSTEM = """\
Você é um assistente que extrai dados de pedido de uma mensagem de WhatsApp de restaurante.
Extraia APENAS o que estiver claramente mencionado. Não invente dados.
Responda SOMENTE com JSON válido, sem texto adicional.

Campos a extrair:
- mistura: nome do prato/proteína (string ou null)
- tamanho: "Mini", "Normal", "Executiva" ou "Churrasco" (string ou null)
- acomp_1: primeiro acompanhamento (string ou null)
- acomp_2: segundo acompanhamento, se houver (string ou null)
- observacoes: observações especiais, ex "sem feijão" (string ou null)
- tipo_entrega: "entrega" ou "retirada" (string ou null)
- endereco: endereço completo se for entrega (string ou null)
- hora_retirada: horário se for retirada (string ou null)
"""


async def extrair_pedido(texto: str) -> dict:
    """
    Tenta extrair campos do pedido da mensagem.
    Retorna dict com chaves: mistura, tamanho, acomp_1, acomp_2,
    observacoes, tipo_entrega, endereco, hora_retirada.
    Valores None = não encontrado.
    """
    vazio = {
        "mistura": None, "tamanho": None,
        "acomp_1": None, "acomp_2": None,
        "observacoes": None, "tipo_entrega": None,
        "endereco": None, "hora_retirada": None,
    }

    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": texto}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_URL, json=payload, headers=_HEADERS)
            if not resp.is_success:
                log.warning(f"Extrator: erro HTTP {resp.status_code}")
                return vazio
            data = resp.json()
            raw = data["content"][0]["text"].strip()
            # remove markdown code fences se o modelo as incluir
            if raw.startswith("```"):
                raw = raw.split("```", 2)[-1] if raw.count("```") >= 2 else raw
                raw = raw.lstrip("json").strip().rstrip("```").strip()
            log.info(f"Extrator raw: {raw}")
            resultado = json.loads(raw)
            # normaliza tamanho para title case
            if resultado.get("tamanho"):
                resultado["tamanho"] = resultado["tamanho"].strip().title()
            # normaliza acompanhamentos
            for campo in ("acomp_1", "acomp_2"):
                if resultado.get(campo):
                    resultado[campo] = resultado[campo].strip().title()
            return {**vazio, **resultado}
    except Exception as e:
        log.warning(f"Extrator: falha ao extrair pedido — {type(e).__name__}: {e}")
        return vazio
