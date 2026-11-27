"""[Modify] Data warehouse em DuckDB (modelo estrela).

Fato: fato_titulo_dia (um registro por título/vencimento/dia).
Dimensões: dim_titulo, dim_tempo e dim_macro (Selic e IPCA do dia).
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def construir_dw(tesouro, macro, caminho=None):
    caminho = Path(caminho or config.ARQ_DW)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()
    con = duckdb.connect(str(caminho))
    con.register("t", tesouro)
    con.register("m", macro)

    con.execute("""
        CREATE TABLE dim_titulo AS
        SELECT row_number() OVER (ORDER BY tipo_titulo, data_vencimento) AS id_titulo,
               tipo_titulo, indexador, data_vencimento,
               tipo_titulo || ' ' || strftime(data_vencimento, '%Y') AS nome_titulo
        FROM (SELECT DISTINCT tipo_titulo, indexador, data_vencimento FROM t)
    """)

    con.execute("""
        CREATE TABLE dim_tempo AS
        SELECT CAST(strftime(data_base, '%Y%m%d') AS INTEGER) AS id_tempo,
               data_base AS data,
               year(data_base) AS ano, month(data_base) AS mes,
               quarter(data_base) AS trimestre, dayofweek(data_base) AS dia_semana
        FROM (SELECT DISTINCT data_base FROM t)
    """)

    con.execute("""
        CREATE TABLE dim_macro AS
        SELECT CAST(strftime(data, '%Y%m%d') AS INTEGER) AS id_tempo,
               selic_meta, ipca_mensal, ipca_12m
        FROM m
    """)

    con.execute("""
        CREATE TABLE fato_titulo_dia AS
        SELECT d.id_titulo,
               CAST(strftime(t.data_base, '%Y%m%d') AS INTEGER) AS id_tempo,
               t.taxa_compra, t.taxa_venda, t.pu_compra, t.pu_venda, t.pu_base
        FROM t
        JOIN dim_titulo d
          ON d.tipo_titulo = t.tipo_titulo AND d.data_vencimento = t.data_vencimento
    """)
    con.close()
    print(f"DW criado em {caminho}")
    return caminho


def abrir_dw(caminho=None):
    return duckdb.connect(str(caminho or config.ARQ_DW), read_only=True)


def carregar_base(con=None):
    """Junta fato e dimensões numa tabela única para análise."""
    con = con or abrir_dw()
    return con.execute("""
        SELECT d.id_titulo, d.nome_titulo, d.tipo_titulo, d.indexador, d.data_vencimento,
               tp.data, f.taxa_compra, f.taxa_venda, f.pu_compra, f.pu_venda, f.pu_base,
               m.selic_meta, m.ipca_mensal, m.ipca_12m
        FROM fato_titulo_dia f
        JOIN dim_titulo d USING (id_titulo)
        JOIN dim_tempo tp USING (id_tempo)
        LEFT JOIN dim_macro m USING (id_tempo)
        ORDER BY d.id_titulo, tp.data
    """).df()


if __name__ == "__main__":
    t = pd.read_csv(config.DIR_PROCESSED / "tesouro_limpo.csv", parse_dates=["data_vencimento", "data_base"])
    m = pd.read_csv(config.DIR_PROCESSED / "macro_diario.csv", parse_dates=["data"])
    construir_dw(t, m)
    con = abrir_dw()
    for tab in ("dim_titulo", "dim_tempo", "dim_macro", "fato_titulo_dia"):
        print(tab, con.execute(f"select count(*) from {tab}").fetchone()[0])
