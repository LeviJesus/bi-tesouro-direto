# BI Tesouro Direto

Projeto da disciplina de Business Intelligence e Analytics (Fase 2). A assessoria de investimentos do caso precisa decidir a alocação entre títulos do Tesouro Direto e não confia nas planilhas manuais. Aqui o processo é um pipeline em Python que coleta dados públicos, monta um data warehouse, calcula KPIs e publica um dashboard.

Dashboard: https://levijesus.github.io/bi-tesouro-direto/

## Dados

- Tesouro Transparente: taxas e preços históricos dos títulos (CSV).
- Banco Central, SGS: Meta Selic (série 432) e IPCA mensal (série 433).

Por padrão usa os últimos 5 anos (`ANOS_HISTORICO` em `config.py`). Os dados baixados ficam em `data/` e não vão para o git.

## Como rodar

Localmente:

```
pip install -r requirements.txt
python run.py
```

`python run.py --sem-coleta` reaproveita os arquivos já baixados. Cada etapa também roda sozinha, por exemplo `python -m src.metricas`. O pipeline leva poucos segundos fora o download, só CPU.

No Colab, abrir `notebooks/analise.ipynb`; a primeira célula clona o repositório e instala as dependências.

## Estrutura

```
config.py        parâmetros (anos, título âncora, séries do SGS)
run.py           pipeline completo
src/coleta.py    baixa Tesouro e SGS
src/limpeza.py   tipos, decimais, datas, inconsistências
src/warehouse.py DW em DuckDB (fato + dimensões)
src/metricas.py  KPIs
src/preditivo.py regressão e baseline
src/dashboards.py gráficos Plotly e docs/index.html
notebooks/       análise e interpretação
docs/            dashboard publicado (GitHub Pages)
```

## SEMMA

- Sample: `coleta.py`, download e recorte da janela.
- Explore: seção de exploração do notebook (nulos, contagens, estatística descritiva).
- Modify: `limpeza.py` e `warehouse.py`.
- Model: `metricas.py` (KPIs) e `preditivo.py`.
- Assess: métricas do modelo (MAE, RMSE, R²) e `dashboards.py`.

## KPIs

Rentabilidade acumulada, volatilidade da taxa, taxa atual e variação em 30/90/365 dias, spread sobre a Selic, spread real sobre o IPCA, drawdown máximo e duration aproximada. Fórmulas e limitações estão em `dicionario_de_dados.md`.

## Previsão

Regressão linear para a taxa de venda de um título prefixado (o vencimento com mais observações), com tendência, duas defasagens e a Selic, comparada com uma média móvel de 30 dias. Split temporal 80/20. Na última execução (Tesouro Prefixado 2029) o modelo teve R² de 0,89 contra 0,31 da média móvel. Esse teste é de um passo à frente, que favorece o modelo com defasagem, então a projeção de 30 dias úteis deve ser lida como indicativa.

## Alguns achados

Posição em 25/11/2026, com Meta Selic em 13,75% a.a.:

- Os prefixados pagam em média cerca de 14,8% (curtos perto da Selic, longos até 15,4%), e os IPCA+ cerca de 7,7% reais.
- Em 12 meses as taxas dos prefixados subiram em média uns 150 bps, e nos últimos 30 dias a maioria dos vencimentos recuou.
- Títulos longos têm quedas de PU bem maiores (drawdown de mais de 40% nos Renda+ mais longos), e o Tesouro Selic quase não oscila.

Os números mudam a cada execução com os dados novos.

## Observações

Trabalho acadêmico, não é recomendação de investimento.
