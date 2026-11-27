"""[Model] KPIs de renda fixa calculados a partir do DW.

Observação: o PU dos títulos com cupom (juros semestrais) cai no pagamento do cupom,
então rentabilidade e drawdown desses títulos ficam subestimados. Está documentado no
dicionário de dados.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.warehouse import abrir_dw, carregar_base


def adicionar_taxas_equivalentes(df):
    """Cria a taxa nominal equivalente (% a.a.) para comparar títulos de indexadores diferentes.

    - Prefixado: a própria taxa.
    - Selic: Meta Selic + taxa (a taxa do Tesouro Selic é o ágio/deságio sobre a Selic).
    - IPCA/IGPM: (1 + taxa real) * (1 + IPCA 12m) - 1.
    """
    df = df.copy()
    ind = df["indexador"]
    nominal = np.where(
        ind == "PREFIXADO", df["taxa_venda"],
        np.where(ind == "SELIC", df["selic_meta"] + df["taxa_venda"],
                 ((1 + df["taxa_venda"] / 100) * (1 + df["ipca_12m"] / 100) - 1) * 100),
    )
    df["taxa_nominal_eq"] = nominal
    # spread sobre a Selic (p.p.)
    df["spread_selic"] = df["taxa_nominal_eq"] - df["selic_meta"]
    # taxa real: IPCA+ já é real; nos demais, nominal - IPCA 12m
    df["taxa_real"] = np.where(ind.isin(["IPCA", "IGPM"]), df["taxa_venda"], df["taxa_nominal_eq"] - df["ipca_12m"])
    return df


def _taxa_em(serie_data, serie_taxa, data_alvo):
    """Última taxa disponível até data_alvo (ou NaN se o título ainda não existia)."""
    s = serie_taxa[serie_data <= data_alvo]
    return s.iloc[-1] if len(s) else np.nan


def calcular_kpis(base=None):
    """Retorna um DataFrame com uma linha por título vigente na última data."""
    if base is None:
        con = abrir_dw()
        base = carregar_base(con)
        con.close()
    base = adicionar_taxas_equivalentes(base)
    data_ref = base["data"].max()

    linhas = []
    for (id_t, nome), g in base.groupby(["id_titulo", "nome_titulo"]):
        g = g.sort_values("data")
        if g["data"].iloc[-1] != data_ref or len(g) < 30:
            continue  # só títulos vigentes e com histórico mínimo
        ultimo = g.iloc[-1]
        pu = g["pu_venda"].values
        taxa = g["taxa_venda"]

        # 1. rentabilidade acumulada: (PU final / PU inicial - 1) * 100
        rent = (pu[-1] / pu[0] - 1) * 100
        # 2. volatilidade da taxa (desvio-padrão em p.p.) e dos retornos diários anualizada
        vol_taxa = taxa.std()
        ret = pd.Series(pu).pct_change().dropna()
        vol_pu = ret.std() * np.sqrt(252) * 100
        # 3. variação da taxa em bps frente a 30/90/365 dias
        var = {}
        for dias in (30, 90, 365):
            ant = _taxa_em(g["data"], taxa, data_ref - pd.Timedelta(days=dias))
            var[f"var_{dias}d_bps"] = (ultimo["taxa_venda"] - ant) * 100
        # 6. drawdown máximo do PU: maior queda em relação ao pico anterior
        pico = np.maximum.accumulate(pu)
        drawdown = ((pu / pico) - 1).min() * 100
        # 7. duration aproximada: anos até o vencimento
        duration = (ultimo["data_vencimento"] - data_ref).days / 365.25

        linhas.append({
            "id_titulo": id_t, "nome_titulo": nome, "tipo_titulo": ultimo["tipo_titulo"],
            "indexador": ultimo["indexador"], "data_vencimento": ultimo["data_vencimento"],
            "data_inicio": g["data"].iloc[0], "data_ref": data_ref, "n_obs": len(g),
            "taxa_atual": ultimo["taxa_venda"], **var,
            "rentabilidade_acum": rent, "vol_taxa": vol_taxa, "vol_pu_anual": vol_pu,
            "spread_selic": ultimo["spread_selic"], "spread_real_ipca": ultimo["taxa_real"],
            "drawdown_max": drawdown, "duration_anos": duration,
        })
    kpis = pd.DataFrame(linhas).sort_values(["tipo_titulo", "data_vencimento"]).reset_index(drop=True)
    return kpis


def salvar_kpis(kpis):
    config.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    kpis.to_csv(config.DIR_PROCESSED / "kpis.csv", index=False)


if __name__ == "__main__":
    k = calcular_kpis()
    salvar_kpis(k)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(k[["nome_titulo", "taxa_atual", "var_30d_bps", "rentabilidade_acum", "vol_taxa",
             "spread_selic", "spread_real_ipca", "drawdown_max", "duration_anos"]].round(2).to_string())
