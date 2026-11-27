"""Parâmetros do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_DOCS = RAIZ / "docs"
ARQ_DW = DIR_PROCESSED / "tesouro_dw.duckdb"

# quantos anos de histórico entram na análise
ANOS_HISTORICO = 5

# Tesouro Transparente (CKAN)
CKAN_PACKAGE_ID = "df56aa42-484a-4a59-8184-7676580c81e3"
URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)
URL_CKAN_API = f"https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id={CKAN_PACKAGE_ID}"

# séries do SGS/BACEN
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
SERIES_SGS = {
    "selic_meta": 432,  # Meta Selic (% a.a.)
    "ipca_mensal": 433,  # IPCA, variação mensal (%)
}

# título âncora da análise preditiva (o vencimento é escolhido pelo mais líquido,
# ou seja, o que tem mais observações na janela)
TITULO_ANCORA = "Tesouro Prefixado"
VENCIMENTO_ANCORA = None  # None = escolhe automaticamente

# modelo preditivo
HORIZONTE_PREVISAO = 30  # dias úteis à frente
JANELA_MEDIA_MOVEL = 30
PROPORCAO_TREINO = 0.8
