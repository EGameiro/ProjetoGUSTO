"""
Parseia a planilha de pedidos do convênio.

Estrutura esperada (baseada no exemplo real):
  Linha 0: cabeçalho (horários de entrega)
  Linha 1: nomes dos funcionários (colunas B em diante)
  Linha 2: "PRATO PRINCIPAL" (label)
  Linhas 3-7: pratos com X nas colunas dos que pediram
  Linha 8: "ACOMPANHAMENTO" (label)
  Linhas 9-13: acompanhamentos com X
  Linha 14: tamanho (MINI / NORMAL / EXECUTIVA / CHURRASCO)
  Linhas 15+: observações (texto livre na coluna E/F)
"""
import io
import logging
import pandas as pd

log = logging.getLogger(__name__)

_LABELS_IGNORAR = {
    "prato principal", "acompanhamento", "acompanhamentos",
    "observações", "observacoes", "nan", ""
}


def _is_x(val) -> bool:
    return str(val).strip().upper() in ("X", "✓", "✔", "SIM", "S", "1")


def parsear(conteudo: bytes) -> list[dict]:
    """
    Recebe bytes do arquivo xlsx e retorna lista de pedidos:
    [{"nome": str, "mistura": str, "tamanho": str,
      "acomp_1": str|None, "acomp_2": str|None, "observacoes": str|None}, ...]
    """
    df = pd.read_excel(io.BytesIO(conteudo), header=None, dtype=str)
    df = df.fillna("")

    # ── Encontra a linha dos nomes (primeira linha com 3+ valores não-vazios) ──
    linha_nomes = None
    for i, row in df.iterrows():
        valores = [v for v in row if v.strip() and v.strip().lower() not in _LABELS_IGNORAR]
        if len(valores) >= 3:
            linha_nomes = i
            break

    if linha_nomes is None:
        log.error("Não foi possível identificar a linha de nomes")
        return []

    nomes_row = df.iloc[linha_nomes]

    # Colunas com nomes válidos (ignora coluna 0 = labels e colunas vazias)
    colunas_pessoas = [
        (col, nome.strip())
        for col, nome in enumerate(nomes_row)
        if col > 0 and nome.strip() and nome.strip().lower() not in _LABELS_IGNORAR
    ]

    if not colunas_pessoas:
        log.error("Nenhuma pessoa encontrada na planilha")
        return []

    # ── Extrai pratos, acompanhamentos e tamanho por seção ──
    pratos: list[str] = []
    acomps: list[str] = []
    tamanho_row: pd.Series | None = None
    obs_linhas: list[str] = []

    secao = None
    for i in range(linha_nomes + 1, len(df)):
        row = df.iloc[i]
        label = str(row.iloc[0]).strip().lower()

        if "prato" in label:
            secao = "prato"
            continue
        if "acomp" in label:
            secao = "acomp"
            continue
        if "observa" in label:
            secao = "obs"
            continue

        if secao == "prato":
            nome_prato = str(row.iloc[0]).strip()
            if nome_prato and nome_prato.lower() not in _LABELS_IGNORAR:
                pratos.append(nome_prato)
            elif not nome_prato:
                secao = None

        elif secao == "acomp":
            nome_acomp = str(row.iloc[0]).strip()
            if nome_acomp and nome_acomp.lower() not in _LABELS_IGNORAR:
                # detecta linha de tamanho se todos os valores forem tamanhos
                vals = [str(row.iloc[c]).strip().upper() for c, _ in colunas_pessoas]
                if all(v in ("MINI", "NORMAL", "EXECUTIVA", "CHURRASCO", "") for v in vals):
                    tamanho_row = row
                    secao = None
                    continue
                acomps.append(nome_acomp)

        elif secao is None:
            # linha de tamanho (sem seção explícita)
            vals = [str(row.iloc[c]).strip().upper() for c, _ in colunas_pessoas]
            if any(v in ("MINI", "NORMAL", "EXECUTIVA", "CHURRASCO") for v in vals):
                tamanho_row = row
                continue
            # observações livres
            texto_linha = " ".join(str(v).strip() for v in row if str(v).strip())
            if texto_linha:
                obs_linhas.append(texto_linha)

    # ── Monta pedido por pessoa ──
    pedidos = []
    for col, nome in colunas_pessoas:
        mistura = None
        for idx_p, prato in enumerate(pratos):
            row_prato = df.iloc[linha_nomes + 2 + idx_p]  # +2 pula label "PRATO PRINCIPAL"
            if _is_x(row_prato.iloc[col]):
                mistura = prato
                break

        acomp_list = []
        # linha da seção ACOMP começa após pratos + label "ACOMPANHAMENTO"
        offset_acomp = linha_nomes + 2 + len(pratos) + 1
        for idx_a, acomp in enumerate(acomps):
            try:
                row_acomp = df.iloc[offset_acomp + idx_a]
                if _is_x(row_acomp.iloc[col]):
                    acomp_list.append(acomp)
            except IndexError:
                pass

        tamanho = "Mini"
        if tamanho_row is not None:
            t = str(tamanho_row.iloc[col]).strip().title()
            if t in ("Mini", "Normal", "Executiva", "Churrasco"):
                tamanho = t

        # observações específicas da pessoa
        obs_pessoa = None
        for linha_obs in obs_linhas:
            if nome.upper() in linha_obs.upper():
                # extrai a parte após o nome
                partes = linha_obs.split(":", 1)
                obs_pessoa = partes[1].strip() if len(partes) > 1 else linha_obs
                break

        if not mistura:
            log.warning(f"Pessoa '{nome}' sem prato identificado — ignorada")
            continue

        pedidos.append({
            "nome":        nome,
            "mistura":     mistura,
            "tamanho":     tamanho,
            "acomp_1":     acomp_list[0] if len(acomp_list) > 0 else None,
            "acomp_2":     acomp_list[1] if len(acomp_list) > 1 else None,
            "observacoes": obs_pessoa,
        })

    log.info(f"Parser: {len(pedidos)} pedidos extraídos de {len(colunas_pessoas)} pessoas")
    return pedidos
