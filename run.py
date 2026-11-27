"""Executa o pipeline completo: coleta, limpeza, warehouse, métricas, preditivo e dashboards."""
import argparse
import time

import config
from src import coleta, dashboards, limpeza, metricas, preditivo, warehouse


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--anos", type=int, default=config.ANOS_HISTORICO, help="anos de histórico")
    ap.add_argument("--sem-coleta", action="store_true", help="reaproveita os arquivos de data/raw")
    args = ap.parse_args()

    inicio = time.time()
    if not args.sem_coleta:
        print("[1/6] Coleta")
        coleta.coletar(args.anos)
    print("[2/6] Limpeza")
    tesouro, macro = limpeza.limpar(args.anos)
    print("[3/6] Warehouse")
    warehouse.construir_dw(tesouro, macro)
    print("[4/6] Métricas")
    kpis = metricas.calcular_kpis()
    metricas.salvar_kpis(kpis)
    print(f"{len(kpis)} títulos vigentes com KPIs")
    print("[5/6] Preditivo")
    prev = preditivo.treinar_e_avaliar()
    print(prev["titulo"], {k: round(v["R2"], 3) for k, v in prev["metricas"].items()})
    print("[6/6] Dashboards")
    dashboards.gerar_dashboard(previsao=prev)
    print(f"Pronto em {time.time() - inicio:.1f}s")


if __name__ == "__main__":
    main()
