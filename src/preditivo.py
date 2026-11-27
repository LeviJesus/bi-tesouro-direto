"""[Model/Assess] Previsão da taxa do título âncora: regressão linear x média móvel.

Alvo: taxa de venda do título âncora. Features: tendência (ordinal da data), duas
defasagens da taxa e a Meta Selic. Split temporal 80/20, sem embaralhar.
O desempenho no teste é de previsão um passo à frente (usa a taxa real do dia anterior);
a projeção para o horizonte usa as próprias previsões como defasagens (recursiva).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.warehouse import abrir_dw, carregar_base

FEATURES = ["tendencia", "lag1", "lag2", "selic"]


def escolher_titulo_ancora(base):
    """Título do tipo âncora, ainda vigente, com mais observações na janela."""
    b = base[base["tipo_titulo"] == config.TITULO_ANCORA]
    if config.VENCIMENTO_ANCORA is not None:
        b = b[b["data_vencimento"] == pd.Timestamp(config.VENCIMENTO_ANCORA)]
    vigentes = b[b["data"] == base["data"].max()]["id_titulo"]
    b = b[b["id_titulo"].isin(vigentes)]
    if b.empty:
        raise ValueError(f"Nenhum título vigente do tipo '{config.TITULO_ANCORA}'.")
    id_t = b.groupby("id_titulo").size().idxmax()
    return b[b["id_titulo"] == id_t].sort_values("data").reset_index(drop=True)


def montar_features(serie):
    df = pd.DataFrame({"data": serie["data"], "taxa": serie["taxa_venda"], "selic": serie["selic_meta"]})
    df["selic"] = df["selic"].ffill().bfill()
    df["tendencia"] = df["data"].map(pd.Timestamp.toordinal)
    df["lag1"] = df["taxa"].shift(1)
    df["lag2"] = df["taxa"].shift(2)
    df["media_movel"] = df["taxa"].shift(1).rolling(config.JANELA_MEDIA_MOVEL).mean()
    return df.dropna().reset_index(drop=True)


def _metricas(y, pred):
    return {"MAE": mean_absolute_error(y, pred),
            "RMSE": float(np.sqrt(mean_squared_error(y, pred))),
            "R2": r2_score(y, pred)}


def projetar(modelo, df, horizonte):
    """Previsão recursiva para os próximos dias úteis, com a Selic mantida no último valor."""
    ult = df.iloc[-1]
    lag1, lag2 = ult["taxa"], ult["lag1"]
    datas = pd.bdate_range(ult["data"] + pd.Timedelta(days=1), periods=horizonte)
    prev = []
    for d in datas:
        x = pd.DataFrame([[d.toordinal(), lag1, lag2, ult["selic"]]], columns=FEATURES)
        y = float(modelo.predict(x)[0])
        prev.append(y)
        lag2, lag1 = lag1, y
    return pd.DataFrame({"data": datas, "previsao": prev})


def treinar_e_avaliar(base=None):
    if base is None:
        con = abrir_dw()
        base = carregar_base(con)
        con.close()
    serie = escolher_titulo_ancora(base)
    nome = serie["nome_titulo"].iloc[0]
    df = montar_features(serie)

    corte = int(len(df) * config.PROPORCAO_TREINO)
    treino, teste = df.iloc[:corte], df.iloc[corte:].copy()

    modelo = LinearRegression().fit(treino[FEATURES], treino["taxa"])
    teste["pred_modelo"] = modelo.predict(teste[FEATURES])
    # baseline ingênuo: média das últimas N taxas
    teste["pred_baseline"] = teste["media_movel"]

    metricas = {"modelo": _metricas(teste["taxa"], teste["pred_modelo"]),
                "baseline": _metricas(teste["taxa"], teste["pred_baseline"])}

    # para a projeção, reajusta com todos os dados
    modelo_final = LinearRegression().fit(df[FEATURES], df["taxa"])
    previsao = projetar(modelo_final, df, config.HORIZONTE_PREVISAO)

    resultado = {"titulo": nome, "historico": df[["data", "taxa"]], "teste": teste,
                 "previsao": previsao, "metricas": metricas,
                 "coeficientes": dict(zip(FEATURES, modelo_final.coef_)), "n_treino": len(treino),
                 "n_teste": len(teste)}
    return resultado


if __name__ == "__main__":
    r = treinar_e_avaliar()
    print(r["titulo"], "| treino", r["n_treino"], "teste", r["n_teste"])
    for nome, m in r["metricas"].items():
        print(f"{nome:9s} MAE {m['MAE']:.3f}  RMSE {m['RMSE']:.3f}  R2 {m['R2']:.3f}")
    print("coeficientes:", {k: round(v, 5) for k, v in r["coeficientes"].items()})
    print(r["previsao"].iloc[[0, -1]])
