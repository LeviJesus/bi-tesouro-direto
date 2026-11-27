"""[Assess] Gera os gráficos Plotly e exporta o dashboard para docs/index.html."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.preditivo import treinar_e_avaliar
from src.metricas import adicionar_taxas_equivalentes, calcular_kpis
from src.warehouse import abrir_dw, carregar_base

CORES = {
    "Tesouro Selic": "#1b9e77",
    "Tesouro Prefixado": "#d95f02",
    "Tesouro Prefixado com Juros Semestrais": "#e6ab02",
    "Tesouro IPCA+": "#1f4e9c",
    "Tesouro IPCA+ com Juros Semestrais": "#6baed6",
    "Tesouro IGPM+ com Juros Semestrais": "#7570b3",
    "Tesouro Educa+": "#a6761d",
    "Tesouro Renda+ Aposentadoria Extra": "#666666",
}
LAYOUT = dict(template="plotly_white", font=dict(family="Arial, sans-serif", size=13),
              margin=dict(l=60, r=30, t=70, b=50), legend=dict(font=dict(size=11)))


def fig_evolucao_taxas(base):
    """Taxa de venda por título; o menu filtra por tipo de título."""
    base = base.sort_values(["nome_titulo", "data"])
    tipos = sorted(base["tipo_titulo"].unique())
    fig = go.Figure()
    tipo_de_traco = []
    for nome, g in base.groupby("nome_titulo"):
        tipo = g["tipo_titulo"].iloc[0]
        fig.add_trace(go.Scatter(x=g["data"], y=g["taxa_venda"], name=nome, mode="lines",
                                 line=dict(width=1.5), visible=(tipo == tipos[0]),
                                 hovertemplate="%{x|%d/%m/%Y}: %{y:.2f}%<extra>" + nome + "</extra>"))
        tipo_de_traco.append(tipo)
    botoes = [dict(label=t, method="update",
                   args=[{"visible": [x == t for x in tipo_de_traco]},
                         {"title": f"Evolução da taxa de venda — {t}"}]) for t in tipos]
    fig.update_layout(**LAYOUT, title=f"Evolução da taxa de venda — {tipos[0]}",
                      yaxis_title="Taxa de venda (% a.a.)",
                      updatemenus=[dict(buttons=botoes, x=0, y=1.18, xanchor="left", direction="down")])
    return fig


def fig_rentabilidade(kpis):
    k = kpis.sort_values("rentabilidade_acum")
    fig = go.Figure(go.Bar(
        x=k["rentabilidade_acum"], y=k["nome_titulo"], orientation="h",
        marker_color=[CORES.get(t) for t in k["tipo_titulo"]],
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
    layout = {**LAYOUT, "margin": dict(l=300, r=30, t=70, b=50)}
    fig.update_layout(**layout, title="Rentabilidade acumulada no período (variação do PU de venda)",
                      xaxis_title="%", height=max(500, 18 * len(k)))
    return fig


def fig_risco_retorno(kpis):
    fig = go.Figure()
    for tipo, g in kpis.groupby("tipo_titulo"):
        fig.add_trace(go.Scatter(
            x=g["vol_taxa"], y=g["rentabilidade_acum"], mode="markers", name=tipo,
            marker=dict(color=CORES.get(tipo), size=9 + g["duration_anos"].clip(upper=30) / 3, opacity=0.8),
            text=g["nome_titulo"],
            hovertemplate="%{text}<br>Volatilidade: %{x:.2f} p.p.<br>Rentabilidade: %{y:.1f}%<extra></extra>"))
    fig.update_layout(**LAYOUT, title="Risco × retorno (tamanho do ponto = duration)",
                      xaxis_title="Volatilidade da taxa (desvio-padrão, p.p.)",
                      yaxis_title="Rentabilidade acumulada (%)")
    return fig


def fig_spread_selic(base):
    """Spread médio por tipo de título (taxa nominal equivalente menos Meta Selic)."""
    b = adicionar_taxas_equivalentes(base)
    medio = b.groupby(["tipo_titulo", "data"], as_index=False)["spread_selic"].mean()
    selic = b.drop_duplicates("data").sort_values("data")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for tipo, g in medio.groupby("tipo_titulo"):
        fig.add_trace(go.Scatter(x=g["data"], y=g["spread_selic"], name=tipo, mode="lines",
                                 line=dict(color=CORES.get(tipo), width=1.5)), secondary_y=False)
    fig.add_trace(go.Scatter(x=selic["data"], y=selic["selic_meta"], name="Meta Selic (eixo direito)",
                             mode="lines", line=dict(color="black", dash="dot", width=2)), secondary_y=True)
    fig.add_hline(y=0, line_width=1, line_color="#999")
    fig.update_layout(**LAYOUT, title="Spread sobre a Selic ao longo do tempo")
    fig.update_yaxes(title_text="Spread (p.p.)", secondary_y=False)
    fig.update_yaxes(title_text="Meta Selic (% a.a.)", secondary_y=True, showgrid=False)
    return fig


def fig_painel_kpis(kpis):
    cols = [("nome_titulo", "Título", None), ("taxa_atual", "Taxa atual (%)", 2),
            ("var_30d_bps", "Var. 30d (bps)", 0), ("var_90d_bps", "Var. 90d (bps)", 0),
            ("var_365d_bps", "Var. 365d (bps)", 0), ("rentabilidade_acum", "Rent. acum. (%)", 1),
            ("vol_taxa", "Vol. taxa (p.p.)", 2), ("spread_selic", "Spread Selic (p.p.)", 2),
            ("spread_real_ipca", "Taxa real (p.p.)", 2), ("drawdown_max", "Drawdown máx. (%)", 1),
            ("duration_anos", "Duration (anos)", 1)]
    valores = [kpis[c].round(d) if d is not None else kpis[c] for c, _, d in cols]
    fig = go.Figure(go.Table(
        columnwidth=[3] + [1] * (len(cols) - 1),
        header=dict(values=[r for _, r, _ in cols], fill_color="#1f4e9c", font=dict(color="white", size=12),
                    align="left"),
        cells=dict(values=valores, align="left", height=24,
                   fill_color=[["#f5f7fa" if i % 2 == 0 else "white" for i in range(len(kpis))]] * len(cols))))
    data_ref = kpis["data_ref"].iloc[0]
    fig.update_layout(**LAYOUT, title=f"Painel de KPIs — posição em {pd.Timestamp(data_ref):%d/%m/%Y}",
                      height=26 * len(kpis) + 150)
    return fig


def fig_projecao(prev):
    """Histórico + previsão do modelo + baseline para o título âncora."""
    h, p, t = prev["historico"], prev["previsao"], prev["teste"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h["data"], y=h["taxa"], name="Histórico", line=dict(color="#333", width=1.5)))
    fig.add_trace(go.Scatter(x=t["data"], y=t["pred_modelo"], name="Modelo (período de teste)",
                             line=dict(color="#d95f02", width=1.5)))
    fig.add_trace(go.Scatter(x=t["data"], y=t["pred_baseline"], name="Baseline (média móvel)",
                             line=dict(color="#1f4e9c", width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=p["data"], y=p["previsao"], name="Previsão",
                             line=dict(color="#d95f02", width=2.5, dash="dash")))
    m = prev["metricas"]
    nota = (f"Teste, modelo: MAE {m['modelo']['MAE']:.3f} | RMSE {m['modelo']['RMSE']:.3f} | R² {m['modelo']['R2']:.3f}<br>"
            f"Teste, baseline: MAE {m['baseline']['MAE']:.3f} | RMSE {m['baseline']['RMSE']:.3f} | R² {m['baseline']['R2']:.3f}")
    layout = {**LAYOUT, "margin": dict(l=60, r=30, t=70, b=110)}
    fig.update_layout(**layout, title=f"Projeção da taxa — {prev['titulo']}", yaxis_title="Taxa de venda (% a.a.)",
                      annotations=[dict(text=nota, xref="paper", yref="paper", x=0, y=-0.18, showarrow=False,
                                        align="left", font=dict(size=11))])
    return fig


PAGINA = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BI Tesouro Direto</title>
<style>
 body {{ font-family: Arial, sans-serif; max-width: 1150px; margin: 0 auto; padding: 0 16px 40px; color: #222; }}
 header {{ border-bottom: 3px solid #1f4e9c; padding: 24px 0 12px; margin-bottom: 8px; }}
 h1 {{ margin: 0 0 6px; font-size: 26px; }}
 header p {{ margin: 0; color: #555; }}
 section {{ margin: 28px 0; }}
 footer {{ border-top: 1px solid #ddd; padding-top: 12px; font-size: 13px; color: #666; }}
</style>
</head>
<body>
<header>
 <h1>BI e Analytics para decisão de alocação no Tesouro Direto</h1>
 <p>Comparação de títulos por rentabilidade, risco e spread sobre a Selic, com dados públicos. Atualizado em {hoje}.</p>
</header>
{secoes}
<footer>
 Fontes: Tesouro Transparente (Taxas dos Títulos Ofertados pelo Tesouro Direto) e Banco Central do Brasil, SGS séries 432 (Meta Selic) e 433 (IPCA).
 Projeto acadêmico, não é recomendação de investimento.
</footer>
</body>
</html>
"""


def gerar_dashboard(previsao=None, destino=None):
    destino = Path(destino or config.DIR_DOCS / "index.html")
    con = abrir_dw()
    base = carregar_base(con)
    con.close()
    kpis = calcular_kpis(base)

    figs = [fig_painel_kpis(kpis), fig_evolucao_taxas(base), fig_rentabilidade(kpis),
            fig_risco_retorno(kpis), fig_spread_selic(base)]
    if previsao is not None:
        figs.append(fig_projecao(previsao))

    secoes = []
    for i, f in enumerate(figs):
        html = f.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)
        secoes.append(f"<section>{html}</section>")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(PAGINA.format(hoje=date.today().strftime("%d/%m/%Y"), secoes="\n".join(secoes)),
                       encoding="utf-8")
    print(f"Dashboard salvo em {destino}")
    return destino


if __name__ == "__main__":
    gerar_dashboard(previsao=treinar_e_avaliar())
