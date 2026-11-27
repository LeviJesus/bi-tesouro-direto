"""[Modify] Limpeza e padronização dos dados brutos."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

COLUNAS = {
    "Tipo Titulo": "tipo_titulo",
    "Data Vencimento": "data_vencimento",
    "Data Base": "data_base",
    "Taxa Compra Manha": "taxa_compra",
    "Taxa Venda Manha": "taxa_venda",
    "PU Compra Manha": "pu_compra",
    "PU Venda Manha": "pu_venda",
    "PU Base Manha": "pu_base",
}


def indexador(tipo):
    """Classifica o título pelo indexador."""
    t = tipo.upper()
    if "IPCA" in t or "RENDA+" in t or "EDUCA+" in t:
        return "IPCA"
    if "IGPM" in t:
        return "IGPM"
    if "SELIC" in t:
        return "SELIC"
    return "PREFIXADO"


def limpar_tesouro(anos=None, caminho=None):
    anos = anos or config.ANOS_HISTORICO
    caminho = caminho or config.DIR_RAW / "PrecoTaxaTesouroDireto.csv"
    try:
        df = pd.read_csv(caminho, sep=";", decimal=",", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(caminho, sep=";", decimal=",", encoding="latin-1")

    faltando = set(COLUNAS) - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes no arquivo do Tesouro: {faltando}")
    df = df[list(COLUNAS)].rename(columns=COLUNAS)

    df["tipo_titulo"] = df["tipo_titulo"].str.strip()
    for c in ("data_vencimento", "data_base"):
        df[c] = pd.to_datetime(df[c], format="%d/%m/%Y", errors="coerce")

    n0 = len(df)
    df = df.dropna()
    # recorte da janela
    corte = df["data_base"].max() - pd.DateOffset(years=anos)
    df = df[df["data_base"] >= corte]
    n_janela = len(df)

    # inconsistências: preços não positivos, vencimento antes da data base, duplicatas
    df = df[(df["pu_venda"] > 0) & (df["pu_compra"] > 0)]
    df = df[df["data_vencimento"] > df["data_base"]]
    # a taxa pode ser zero/negativa em alguns casos (ex.: Selic), então não filtra por ela
    df = df.drop_duplicates(subset=["tipo_titulo", "data_vencimento", "data_base"])

    df["indexador"] = df["tipo_titulo"].map(indexador)
    df = df.sort_values(["tipo_titulo", "data_vencimento", "data_base"]).reset_index(drop=True)
    print(f"Tesouro: {n0} linhas brutas, {n_janela} na janela, {len(df)} após limpeza")
    return df


def _ler_sgs(nome, codigo):
    dados = json.loads((config.DIR_RAW / f"sgs_{codigo}_{nome}.json").read_text(encoding="utf-8"))
    s = pd.DataFrame(dados)
    s["data"] = pd.to_datetime(s["data"], format="%d/%m/%Y")
    s["valor"] = pd.to_numeric(s["valor"], errors="coerce")
    return s.dropna().drop_duplicates("data").sort_values("data").reset_index(drop=True)


def limpar_macro(datas):
    """Monta uma tabela diária (Selic meta, IPCA mensal e IPCA acumulado 12m)
    alinhada às datas de negociação do Tesouro."""
    selic = _ler_sgs("selic_meta", config.SERIES_SGS["selic_meta"]).rename(columns={"valor": "selic_meta"})
    ipca = _ler_sgs("ipca_mensal", config.SERIES_SGS["ipca_mensal"]).rename(columns={"valor": "ipca_mensal"})

    # acumulado 12 meses (composição dos fatores mensais)
    fator = 1 + ipca["ipca_mensal"] / 100
    ipca["ipca_12m"] = (fator.rolling(12).apply(np.prod, raw=True) - 1) * 100

    base = pd.DataFrame({"data": pd.Series(sorted(set(datas)))})
    # merge_asof: usa o último valor conhecido até a data
    base = pd.merge_asof(base, selic[["data", "selic_meta"]], on="data")
    base = pd.merge_asof(base, ipca[["data", "ipca_mensal", "ipca_12m"]], on="data")
    return base


def limpar(anos=None):
    tesouro = limpar_tesouro(anos)
    macro = limpar_macro(tesouro["data_base"].unique())
    config.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    tesouro.to_csv(config.DIR_PROCESSED / "tesouro_limpo.csv", index=False)
    macro.to_csv(config.DIR_PROCESSED / "macro_diario.csv", index=False)
    return tesouro, macro


if __name__ == "__main__":
    t, m = limpar()
    print(t.head())
    print(m.tail())
