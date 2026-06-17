from datetime import date

# TODO Etapa 4: substituir por leitura do Google Sheets
CARDAPIOS = {
    0: {  # Segunda
        "dia": "Segunda-feira",
        "pratos": ["Frango grelhado", "Carne de panela", "Peixe grelhado", "Calabresa acebolada"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrão alho e óleo", "Chuchu refogado"],
        "especial": None,
    },
    1: {  # Terça
        "dia": "Terça-feira",
        "pratos": ["Frango grelhado", "Bife acebolado", "Peixe grelhado", "Linguiça calabresa"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrão alho e óleo", "Legumes assados"],
        "especial": None,
    },
    2: {  # Quarta
        "dia": "Quarta-feira",
        "pratos": ["Frango grelhado", "Carne de panela", "Peixe grelhado", "Calabresa acebolada"],
        "acompanhamentos": ["Farofa", "Fritas", "Couve refogada", "Macarrão alho e óleo"],
        "especial": "🍲 FEIJOADA COMPLETA\n(acompanha: arroz, couve, farofa, torresmo, banana à milanesa e vinagrete)",
    },
    3: {  # Quinta
        "dia": "Quinta-feira",
        "pratos": ["Frango grelhado", "Bife grelhado", "Peixe grelhado", "Frango à milanesa"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrão alho e óleo", "Brócolis refogado"],
        "especial": None,
    },
    4: {  # Sexta
        "dia": "Sexta-feira",
        "pratos": ["Frango grelhado", "Bife à milanesa", "Coxa desossada assada", "Peixe grelhado"],
        "acompanhamentos": ["Farofa", "Fritas", "Macarrão alho e óleo", "Legumes assados", "Couve-flor gratinada"],
        "especial": "🍖 PARMEGIANA DE CARNE",
    },
    5: {  # Sábado
        "dia": "Sábado",
        "pratos": ["Cupim assado", "Frango grelhado", "Linguiça calabresa", "Frango à milanesa"],
        "acompanhamentos": ["Salada de beterraba", "Macarrão alho e óleo", "Farofa", "Brócolis com bacon", "Fritas"],
        "especial": "🍲 FEIJOADA COMPLETA\n(acompanha: arroz, couve, farofa, torresmo, banana à milanesa e vinagrete)",
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
    linhas = [f"🍽️ *Cardápio — {c['dia']}*\n"]

    if c["especial"]:
        linhas.append(f"⭐ *Especial do dia:*\n{c['especial']}\n")

    linhas.append("*Pratos do dia:*")
    for p in c["pratos"]:
        linhas.append(f"• {p}")

    linhas.append("\n*Acompanhamentos* (escolha até 2):")
    for a in c["acompanhamentos"]:
        linhas.append(f"• {a}")

    linhas.append("\n*Tamanhos e valores:*")
    linhas.append(f"• Mini — R$ {PRECOS['Mini']:.2f}")
    linhas.append(f"• Normal — R$ {PRECOS['Normal']:.2f}")
    linhas.append(f"• Executiva — R$ {PRECOS['Executiva']:.2f}")
    linhas.append(f"• Churrasco — R$ {PRECOS['Churrasco']:.2f}")

    linhas.append("\n_Vila Branca: entrega grátis_ 🛵")

    return "\n".join(linhas)


def get_acompanhamentos_hoje() -> list[str]:
    return [a.lower() for a in get_cardapio_hoje()["acompanhamentos"]]


def get_pratos_hoje() -> list[str]:
    c = get_cardapio_hoje()
    pratos = [p.lower() for p in c["pratos"]]
    if c["especial"]:
        pratos.append("feijoada")
        pratos.append("parmegiana")
    return pratos
