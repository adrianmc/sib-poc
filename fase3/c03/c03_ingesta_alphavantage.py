"""
C03-AE-02: consumir APIs externas AUTENTICADAS de datos financieros (Alpha Vantage, autenticacion por API key)
e ingerir la respuesta en el lakehouse: JSON crudo (capa cruda) + estructura tabular (capa curada).

Fuentes (varias APIs / endpoints con la misma credencial), definidas en FUENTES:
  - Acciones:        TIME_SERIES_DAILY (ej. IBM)
  - Tipo de cambio:  FX_DAILY (USD -> EUR)
  - Indicadores:     TREASURY_YIELD (10 anos, mensual) y FEDERAL_FUNDS_RATE (mensual)

Ejecutar en Cloudera AI (sesion Python o Job programado), usuario sb_ing01:
  python fase3/c03/c03_ingesta_alphavantage.py                 # todas las fuentes
  python fase3/c03/c03_ingesta_alphavantage.py --solo fx_usd_eur
  python fase3/c03/c03_ingesta_alphavantage.py --sin-clave     # demo de fallo: la API rechaza y se registra el error

Clave: config.yaml -> apis.alphavantage_key (clave gratuita de alphavantage.co/support). Nunca en el codigo.
Limite del plan gratuito: 25 solicitudes/dia. Una corrida completa usa 4. Planificar ensayos con eso en mente;
el script guarda la respuesta en data/cache_api/ y --desde-cache permite repetir la demo sin gastar cuota.
Nota: Alpha Vantage responde HTTP 200 incluso con errores (claves "Information", "Note", "Error Message");
el script los detecta y falla con mensaje accionable.
Red: el workspace necesita salida a internet (NAT de la VPC).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, impala, RAIZ  # noqa: E402

URL = "https://www.alphavantage.co/query"
FUENTES = {
    "accion_ibm":   {"params": {"function": "TIME_SERIES_DAILY", "symbol": "IBM", "outputsize": "compact"},
                     "campo_valor": "4. close", "unidad": "USD"},
    "fx_usd_eur":   {"params": {"function": "FX_DAILY", "from_symbol": "USD", "to_symbol": "EUR", "outputsize": "compact"},
                     "campo_valor": "4. close", "unidad": "EUR por USD"},
    "tesoro_10a":   {"params": {"function": "TREASURY_YIELD", "interval": "monthly", "maturity": "10year"},
                     "campo_valor": "value", "unidad": "porcentaje"},
    "tasa_fed":     {"params": {"function": "FEDERAL_FUNDS_RATE", "interval": "monthly"},
                     "campo_valor": "value", "unidad": "porcentaje"},
}
CACHE = RAIZ / "data" / "cache_api"


def llamar(nombre, fuente, clave, desde_cache):
    archivo = CACHE / f"{nombre}.json"
    if desde_cache and archivo.exists():
        return json.loads(archivo.read_text())
    r = requests.get(URL, params={**fuente["params"], "apikey": clave}, timeout=60)
    r.raise_for_status()
    cuerpo = r.json()
    for k in ("Error Message", "Information", "Note"):
        if k in cuerpo:
            raise RuntimeError(f"[{nombre}] la API respondio '{k}': {str(cuerpo[k])[:200]} "
                               f"-> revisar clave, simbolo o cuota diaria (25 solicitudes en plan gratuito)")
    CACHE.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(cuerpo))
    return cuerpo


def a_filas(nombre, fuente, cuerpo):
    """Normaliza dos formas de respuesta: series temporales {'Time Series ...': {fecha: {...}}} e indicadores {'data': [...]}."""
    filas = []
    if "data" in cuerpo:
        for d in cuerpo["data"]:
            if d.get("value") not in (None, "", "."):
                filas.append((nombre, d["date"], float(d["value"])))
    else:
        clave_serie = next((k for k in cuerpo if k.startswith("Time Series")), None)
        if not clave_serie:
            raise RuntimeError(f"[{nombre}] estructura inesperada: claves {list(cuerpo)[:5]}")
        for fecha, v in cuerpo[clave_serie].items():
            filas.append((nombre, fecha, float(v[fuente["campo_valor"]])))
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", choices=list(FUENTES))
    ap.add_argument("--desde-cache", action="store_true")
    ap.add_argument("--sin-clave", action="store_true")
    a = ap.parse_args()
    clave = "" if a.sin_clave else cfg().get("apis", {}).get("alphavantage_key", "")
    con = impala("ingeniero")
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sb_raw.api_alphavantage (
        fuente STRING, funcion STRING, payload_json STRING, ingesta_ts TIMESTAMP)
        STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sb_curated.mercado_series (
        serie STRING COMMENT 'Serie financiera externa', fecha DATE COMMENT 'Fecha del dato',
        valor DOUBLE COMMENT 'Valor (cierre o indicador)', unidad STRING COMMENT 'Unidad',
        fuente_api STRING COMMENT 'Proveedor externo', ingesta_ts TIMESTAMP COMMENT 'Momento de ingesta')
        STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')""")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for nombre, fuente in FUENTES.items():
        if a.solo and nombre != a.solo:
            continue
        t0 = time.perf_counter()
        cuerpo = llamar(nombre, fuente, clave, a.desde_cache)
        payload = json.dumps(cuerpo).replace("\\", "\\\\").replace("'", "\\'")
        cur.execute(f"INSERT INTO sb_raw.api_alphavantage VALUES ('{nombre}', '{fuente['params']['function']}', "
                    f"'{payload}', CAST('{ts}' AS TIMESTAMP))")
        filas = a_filas(nombre, fuente, cuerpo)
        # Idempotente: reemplaza la serie completa en la capa curada
        cur.execute(f"DELETE FROM sb_curated.mercado_series WHERE serie = '{nombre}'")
        for i in range(0, len(filas), 500):
            valores = ",".join(f"('{s}', CAST('{f}' AS DATE), {v}, '{fuente['unidad']}', 'alphavantage', "
                               f"CAST('{ts}' AS TIMESTAMP))" for s, f, v in filas[i:i + 500])
            cur.execute(f"INSERT INTO sb_curated.mercado_series VALUES {valores}")
        print(f"{nombre}: {len(filas)} filas en {(time.perf_counter() - t0) * 1000:.0f} ms")
        if not a.desde_cache and not a.solo:
            time.sleep(2)   # cortesia con el limite por minuto
    cur.execute("SELECT serie, COUNT(*), MIN(fecha), MAX(fecha) FROM sb_curated.mercado_series GROUP BY serie")
    for f in cur.fetchall():
        print(f)
    con.close()


if __name__ == "__main__":
    main()
