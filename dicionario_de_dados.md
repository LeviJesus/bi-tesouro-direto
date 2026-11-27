# Dicionário de dados

Fontes: Tesouro Transparente (taxas e preços dos títulos) e Banco Central, SGS (séries 432 e 433).
O DW fica em `data/processed/tesouro_dw.duckdb`, em modelo estrela.

## fato_titulo_dia
Um registro por título, vencimento e dia de negociação.

| Coluna | Tipo | Unidade | Origem | Descrição |
|---|---|---|---|---|
| id_titulo | INTEGER | | dim_titulo | Chave do título (tipo + vencimento) |
| id_tempo | INTEGER | aaaammdd | dim_tempo | Chave da data |
| taxa_compra | DOUBLE | % a.a. | Taxa Compra Manha | Taxa de compra pelo investidor no início do dia |
| taxa_venda | DOUBLE | % a.a. | Taxa Venda Manha | Taxa de resgate (venda pelo investidor) |
| pu_compra | DOUBLE | R$ | PU Compra Manha | Preço unitário de compra |
| pu_venda | DOUBLE | R$ | PU Venda Manha | Preço unitário de resgate |
| pu_base | DOUBLE | R$ | PU Base Manha | Preço unitário base |

A taxa do Tesouro Selic é o ágio/deságio sobre a Selic, não a taxa total. Nos IPCA+, IGPM+, Educa+ e Renda+ a taxa é a parte real (acima da inflação).

## dim_titulo
| Coluna | Tipo | Descrição |
|---|---|---|
| id_titulo | INTEGER | Chave |
| tipo_titulo | VARCHAR | Nome do título conforme o Tesouro |
| indexador | VARCHAR | PREFIXADO, SELIC, IPCA ou IGPM (Educa+ e Renda+ entram como IPCA) |
| data_vencimento | DATE | Vencimento |
| nome_titulo | VARCHAR | Tipo + ano de vencimento, usado nos gráficos |

## dim_tempo
| Coluna | Tipo | Descrição |
|---|---|---|
| id_tempo | INTEGER | aaaammdd |
| data | DATE | Data base |
| ano, mes, trimestre, dia_semana | INTEGER | Atributos da data |

## dim_macro
Valores vigentes em cada data (último valor conhecido até o dia, via `merge_asof`).

| Coluna | Tipo | Unidade | Origem | Descrição |
|---|---|---|---|---|
| id_tempo | INTEGER | | | Chave da data |
| selic_meta | DOUBLE | % a.a. | SGS 432 | Meta Selic definida pelo Copom |
| ipca_mensal | DOUBLE | % | SGS 433 | IPCA, variação mensal |
| ipca_12m | DOUBLE | % | calculado | Acumulado de 12 meses, composição dos fatores mensais |

O IPCA mensal tem data do primeiro dia do mês de referência no SGS, então o 12m de uma data pode usar um valor que na prática ainda não tinha sido divulgado. Para este trabalho a diferença é pequena.

## KPIs (`src/metricas.py`, saída em `data/processed/kpis.csv`)
Calculados só para títulos vigentes na última data, com pelo menos 30 observações. A janela de cada título começa na sua primeira data dentro do recorte (default 5 anos), então títulos novos têm janela mais curta.

| KPI | Coluna | Fórmula |
|---|---|---|
| Rentabilidade acumulada (%) | rentabilidade_acum | (PU venda final / PU venda inicial - 1) * 100 |
| Volatilidade da taxa (p.p.) | vol_taxa | Desvio-padrão da taxa_venda na janela |
| Volatilidade do PU (% a.a.) | vol_pu_anual | Desvio-padrão dos retornos diários do PU * raiz(252) * 100 |
| Taxa atual (%) | taxa_atual | taxa_venda na última data |
| Variação da taxa (bps) | var_30d_bps, var_90d_bps, var_365d_bps | (taxa atual - taxa 30/90/365 dias antes) * 100; usa a última taxa disponível até a data |
| Spread sobre a Selic (p.p.) | spread_selic | taxa nominal equivalente - Meta Selic |
| Spread real vs. IPCA (p.p.) | spread_real_ipca | IPCA+/IGPM+/Educa+/Renda+: a própria taxa real. Demais: taxa nominal equivalente - IPCA 12m |
| Drawdown máximo (%) | drawdown_max | Menor valor de (PU / maior PU até então - 1) * 100 |
| Duration aproximada (anos) | duration_anos | (vencimento - data de referência) / 365,25 |

Taxa nominal equivalente: prefixado = taxa; Selic = Meta Selic + taxa; indexados à inflação = (1 + taxa real) * (1 + IPCA 12m) - 1.

Limitações: o PU dos títulos com juros semestrais cai quando o cupom é pago, então rentabilidade e drawdown desses títulos ficam subestimados. O IGPM+ usa o IPCA como aproximação da inflação. Duration é só o prazo até o vencimento, não a duration de Macaulay.

## Previsão (`src/preditivo.py`)
Alvo: taxa_venda do título âncora. Features: tendência (ordinal da data), taxa defasada em 1 e 2 dias e Meta Selic. Regressão linear com split temporal 80/20. Baseline: média das 30 taxas anteriores. Métricas: MAE, RMSE e R².
