from datetime import date


def brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


# TODO Etapa 4: substituir por leitura do Google Sheets
CARDAPIOS = {
    0: {
        "dia": "Segunda-feira",
        "pratos": ["Frango grelhado", "Carne de panela", "Peixe grelhado", "Calabresa acebolada"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrao alho e oleo", "Chuchu refogado"],
        "especial": None,
    },
    1: {
        "dia": "Terca-feira",
        "pratos": ["Frango grelhado", "Bife acebolado", "Peixe grelhado", "Linguica calabresa"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrao alho e oleo", "Legumes assados"],
        "especial": None,
    },
    2: {
        "dia": "Quarta-feira",
        "pratos": ["Frango grelhado", "Carne de panela", "Peixe grelhado", "Calabresa acebolada"],
        "acompanhamentos": ["Farofa", "Fritas", "Couve refogada", "Macarrao alho e oleo"],
        "especial": "FEIJOADA COMPLETA\n(acompanha: arroz, couve, farofa, torresmo, banana a milanesa e vinagrete)",
    },
    3: {
        "dia": "Quinta-feira",
        "pratos": ["Frango grelhado", "Bife grelhado", "Peixe grelhado", "Frango a milanesa"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrao alho e oleo", "Brocolis refogado"],
        "especial": None,
    },
    4: {
        "dia": "Sexta-feira",
        "pratos": ["Frango grelhado", "Bife a milanesa", "Coxa desossada assada", "Peixe grelhado"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrao alho e oleo", "Legumes assados", "Couve-flor gratinada"],
        "especial": "PARMEGIANA DE CARNE",
    },
    5: {
        "dia": "Sabado",
        "pratos": ["Cupim assado", "Frango grelhado", "Linguica calabresa", "Frango a milanesa"],
        "acompanhamentos": ["Salada de beterraba", "Macarrao alho e oleo", "Farofa", "Brocolis com bacon", "Fritas"],
        "especial": "FEIJOADA COMPLETA\n(acompanha: arroz, couve, farofa, torresmo, banana a milanesa e vinagrete)",
    },
}

PRECOS = {
    "Mini":      21.90,
    "Normal":    23.90,
    "Executiva": 24.90,
    "Churrasco": 27.90,
}


def get_cardapio_hoje() -> dict:
    return CARDAPIOS.get(date.today().weekday(), CARDAPIOS[0])


def formatar_cardapio() -> str:
    c = get_cardapio_hoje()
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
    for nome, valor in PRECOS.items():
        linhas.append(f"• {nome} — {brl(valor)}")

    linhas.append("\nVila Branca: entrega gratis")

    return "\n".join(linhas)


def get_acompanhamentos_hoje() -> list:
    return [a.lower() for a in get_cardapio_hoje()["acompanhamentos"]]


def get_pratos_hoje() -> list:
    c = get_cardapio_hoje()
    pratos = [p.lower() for p in c["pratos"]]
    if c["especial"]:
        pratos.append("feijoada")
        pratos.append("parmegiana")
    return pratos
