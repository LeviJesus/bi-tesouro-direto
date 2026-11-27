"""[Sample] Coleta dos dados do Tesouro Direto e das séries do BACEN (SGS)."""
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

HEADERS = {"User-Agent": "bi-tesouro-direto/1.0"}


def _url_tesouro():
    """Tenta a URL direta; se falhar, descobre o recurso CSV pela API CKAN."""
    try:
        r = requests.head(config.URL_TESOURO, headers=HEADERS, timeout=30, allow_redirects=True)
        if r.status_code == 200:
            return config.URL_TESOURO
    except requests.RequestException:
        pass

    print("URL direta falhou, consultando a API CKAN...")
    try:
        r = requests.get(config.URL_CKAN_API, headers=HEADERS, timeout=30)
        r.raise_for_status()
        recursos = r.json()["result"]["resources"]
    except (requests.RequestException, KeyError, ValueError) as e:
        raise RuntimeError(f"Não foi possível localizar o arquivo do Tesouro Direto: {e}")

    for rec in recursos:
        url = rec.get("url", "")
        if url.lower().endswith(".csv") and "PrecoTaxa" in url:
            return url
    raise RuntimeError("Nenhum recurso CSV 'PrecoTaxa' encontrado no dataset do Tesouro.")


def baixar_tesouro(destino=None):
    destino = Path(destino or config.DIR_RAW / "PrecoTaxaTesouroDireto.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = _url_tesouro()
    print(f"Baixando {url}")
    try:
        with requests.get(url, headers=HEADERS, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(destino, "wb") as f:
                for pedaco in r.iter_content(chunk_size=1 << 20):
                    f.write(pedaco)
    except requests.RequestException as e:
        raise RuntimeError(f"Falha ao baixar o arquivo do Tesouro Direto: {e}")
    print(f"Salvo em {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
    return destino


def baixar_sgs(nome, codigo, anos=None, destino=None):
    """Baixa uma série do SGS e salva em JSON. O SGS limita consultas diárias longas,
    então a consulta usa dataInicial/dataFinal."""
    anos = anos or config.ANOS_HISTORICO
    destino = Path(destino or config.DIR_RAW / f"sgs_{codigo}_{nome}.json")
    # pega um ano a mais para ter IPCA acumulado de 12 meses desde o início da janela
    inicio = date.today() - timedelta(days=365 * (anos + 1))
    params = {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": date.today().strftime("%d/%m/%Y"),
    }
    try:
        r = requests.get(config.URL_SGS.format(codigo=codigo), params=params, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Falha ao consultar a série SGS {codigo}: {e}")
    destino.write_text(r.text, encoding="utf-8")
    print(f"Série {codigo} ({nome}): {len(r.json())} registros")
    return destino


def coletar(anos=None):
    config.DIR_RAW.mkdir(parents=True, exist_ok=True)
    baixar_tesouro()
    for nome, codigo in config.SERIES_SGS.items():
        baixar_sgs(nome, codigo, anos)


if __name__ == "__main__":
    coletar()
