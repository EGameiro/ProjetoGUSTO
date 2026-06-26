import logging
import time
from datetime import date
from db.connection import fetchall

log = logging.getLogger(__name__)

# Cache por restaurante_id: { restaurante_id: (timestamp, dados) }
_cache: dict[int, tuple[float, dict]] = {}
_CACHE_TTL = 900  # 15 minutos

# weekday() → dia_semana no banco (0=Seg … 5=Sab)
_DIA_SEMANA = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


def brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


async def _buscar_mysql(restaurante_id: int) -> dict:
    """Lê cardapio_web do MySQL e retorna dict com pratos, acompanhamentos e preços."""
    dia = _DIA_SEMANA.get(date.today().weekday(), 0)

    rows = await fetchall(
        """
        SELECT tipo, nome, preco_mini, preco_normal, preco_executiva
        FROM cardapio_web
        WHERE restaurante_id = %s
          AND dia_semana = %s
          AND empresa_id IS NULL
          AND ativo = 1
        ORDER BY tipo, ordem, nome
        """,
        (restaurante_id, dia),
    )

    # Lista de tuplas (nome, {Mini: x, Normal: x, Executiva: x}) para cada prato
    pratos = [
        (r["nome"], {
            "Mini":      float(r["preco_mini"])      if r["preco_mini"]      else None,
            "Normal":    float(r["preco_normal"])    if r["preco_normal"]    else None,
            "Executiva": float(r["preco_executiva"]) if r["preco_executiva"] else None,
        })
        for r in rows if r["tipo"] == "prato"
    ]
    acompanhamentos = [r["nome"] for r in rows if r["tipo"] == "acompanhamento"]
    tamanhos = ["Mini", "Normal", "Executiva"]

    return {
        "pratos":          pratos,
        "acompanhamentos": acompanhamentos,
        "tamanhos":        tamanhos,
    }


async def _get_dados(restaurante_id: int) -> dict:
    agora = time.monotonic()
    cached = _cache.get(restaurante_id)
    if cached and (agora - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        dados = await _buscar_mysql(restaurante_id)
        _cache[restaurante_id] = (agora, dados)
        log.info(f"[restaurante={restaurante_id}] Cardápio recarregado do MySQL")
        return dados
    except Exception as e:
        log.error(f"[restaurante={restaurante_id}] Erro ao ler cardápio do MySQL: {e}")
        if cached:
            log.warning(f"[restaurante={restaurante_id}] Usando cache anterior")
            return cached[1]
        return {"pratos": [], "acompanhamentos": [], "precos": {}}


async def get_cardapio_hoje(restaurante_id: int = 1) -> dict:
    """Retorna dict com pratos, acompanhamentos e precos do dia."""
    dados = await _get_dados(restaurante_id)

    dias = ["Segunda-feira", "Terça-feira", "Quarta-feira",
            "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    dia_nome = dias[min(date.today().weekday(), 6)]

    return {
        "dia":             dia_nome,
        "pratos":          dados["pratos"],
        "acompanhamentos": dados["acompanhamentos"],
        "tamanhos":        dados["tamanhos"],
    }


async def formatar_cardapio(restaurante_id: int = 1) -> str:
    c = await get_cardapio_hoje(restaurante_id)
    linhas = [f"*Cardápio — {c['dia']}*\n"]

    if c["pratos"]:
        linhas.append("*Pratos do dia:*")
        for nome, precos in c["pratos"]:
            partes = []
            for tam in ["Mini", "Normal", "Executiva"]:
                p = precos.get(tam)
                if p:
                    partes.append(f"{tam} {brl(p)}")
            if partes:
                linhas.append(f"• {nome} — {' | '.join(partes)}")
            else:
                linhas.append(f"• {nome}")
    else:
        linhas.append("_Cardápio ainda não configurado para hoje._")

    if c["acompanhamentos"]:
        linhas.append("\n*Acompanhamentos* (escolha até 2):")
        for a in c["acompanhamentos"]:
            linhas.append(f"• {a}")

    if c["tamanhos"]:
        linhas.append("\n*Tamanhos disponíveis:*")
        for t in c["tamanhos"]:
            linhas.append(f"• {t}")

    linhas.append("\nVila Branca: entrega grátis")
    return "\n".join(linhas)


async def get_acompanhamentos_hoje(restaurante_id: int = 1) -> list:
    c = await get_cardapio_hoje(restaurante_id)
    return [a.lower() for a in c["acompanhamentos"]]


async def get_preco_prato(nome_prato: str, tamanho: str, restaurante_id: int = 1) -> float:
    """Retorna o preço de um prato específico para um tamanho específico."""
    c = await get_cardapio_hoje(restaurante_id)
    nome_lower = nome_prato.lower()
    for nome, precos in c["pratos"]:
        if nome.lower() == nome_lower:
            return precos.get(tamanho) or 0.0
    return 0.0
