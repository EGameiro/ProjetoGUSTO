"""
Cliente HTTP para a API de impressão do GUSTO.
Substitui o acesso direto ao MySQL — o poller nunca toca o banco.
"""

import os
import httpx

API_URL = os.getenv("API_URL", "").rstrip("/")
API_KEY = os.getenv("API_KEY", "")

_HEADERS = {"X-API-Key": API_KEY}
_TIMEOUT = 10


def buscar_pendentes() -> list[dict]:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{API_URL}/api/impressao/pendentes", headers=_HEADERS)
        resp.raise_for_status()
        return resp.json().get("pedidos", [])


def marcar_impresso(pedido_id: int):
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{API_URL}/api/impressao/{pedido_id}/marcar", headers=_HEADERS)
        resp.raise_for_status()


def buscar_nome_empresa(empresa_id: int) -> str:
    # Já vem resolvido no payload da API — fallback caso não venha
    return "EMPRESA"
