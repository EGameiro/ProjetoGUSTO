import json
import logging
import time
from datetime import date
from google.oauth2.service_account import Credentials
import gspread
import config

log = logging.getLogger(__name__)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Cache em memória: (timestamp, dados)
_cache: tuple[float, dict] | None = None
_CACHE_TTL = 1800  # 30 minutos

# Mapeamento weekday() → coluna B-G (índice 1-6)
_DIA_COL = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}  # seg=0 … sab=5


def brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def _buscar_planilha() -> dict:
    """Lê a aba Cardapio e devolve um dict {campo: valor_do_dia}."""
    if config.GOOGLE_CREDENTIALS_JSON:
        log.info("Usando credenciais da variavel de ambiente GOOGLE_CREDENTIALS_JSON")
        info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        log.info(f"Usando arquivo de credenciais: {config.GOOGLE_CREDENTIALS_FILE}")
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=_SCOPES
        )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
    ws = sh.worksheet("Cardapio")
    rows = ws.get_all_values()  # lista de listas

    dia_idx = _DIA_COL.get(date.today().weekday(), 1)  # fallback segunda

    resultado = {}
    for row in rows[1:]:  # pula cabeçalho
        if not row:
            continue
        campo = row[0].strip()
        valor = row[dia_idx].strip() if len(row) > dia_idx else ""
        resultado[campo] = valor

    return resultado


def _get_dados() -> dict:
    global _cache
    agora = time.monotonic()
    if _cache and (agora - _cache[0]) < _CACHE_TTL:
        return _cache[1]

    try:
        dados = _buscar_planilha()
        _cache = (agora, dados)
        log.info("Cardapio recarregado do Google Sheets")
        return dados
    except Exception as e:
        log.error(f"Erro ao ler Google Sheets: {e}")
        if _cache:
            log.warning("Usando cache anterior")
            return _cache[1]
        return {}


def _get_precos(dados: dict) -> dict:
    def _f(campo: str, fallback: float) -> float:
        try:
            return float(dados.get(campo, fallback))
        except ValueError:
            return fallback

    return {
        "Mini":       _f("PRECO_MINI",      21.90),
        "Normal":     _f("PRECO_NORMAL",    23.90),
        "Executiva":  _f("PRECO_EXECUTIVA", 24.90),
        "Churrasco":  _f("PRECO_CHURRASCO", 27.90),
    }


def get_cardapio_hoje() -> dict:
    """Retorna dict com pratos, acompanhamentos, precos e especial do dia."""
    dados = _get_dados()
    precos = _get_precos(dados)

    pratos = [
        dados[f"PRATO_{i}"]
        for i in range(1, 10)
        if dados.get(f"PRATO_{i}")
    ]

    acompanhamentos = [
        dados[f"ACOMP_{i}"]
        for i in range(1, 10)
        if dados.get(f"ACOMP_{i}")
    ]

    dias = ["Segunda-feira", "Terca-feira", "Quarta-feira",
            "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
    dia_nome = dias[min(date.today().weekday(), 6)]

    return {
        "dia":             dia_nome,
        "pratos":          pratos,
        "acompanhamentos": acompanhamentos,
        "especial":        dados.get("ESPECIAL") or None,
        "precos":          precos,
    }


def formatar_cardapio() -> str:
    c = get_cardapio_hoje()
    precos = c["precos"]
    linhas = [f"*Cardapio — {c['dia']}*\n"]

    if c["especial"]:
        linhas.append(f"Especial do dia:\n{c['especial']}\n")

    linhas.append("*Pratos do dia:*")
    for p in c["pratos"]:
        linhas.append(f"• {p}")

    linhas.append("\n*Acompanhamentos* (escolha ate 2):")
    for a in c["acompanhamentos"]:
        linhas.append(f"• {a}")

    linhas.append("\n*Tamanhos e valores:*")
    for nome, valor in precos.items():
        linhas.append(f"• {nome} — {brl(valor)}")

    linhas.append("\nVila Branca: entrega gratis")
    return "\n".join(linhas)


def get_acompanhamentos_hoje() -> list:
    return [a.lower() for a in get_cardapio_hoje()["acompanhamentos"]]


def get_precos_hoje() -> dict:
    return get_cardapio_hoje()["precos"]
