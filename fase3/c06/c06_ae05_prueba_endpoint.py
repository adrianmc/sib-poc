"""C06-AE-05: prueba de carga del endpoint: latencia, tasa de error y throughput.
  python fase3/c06/c06_ae05_prueba_endpoint.py --url CAMBIAR_URL_MODELO --clave CAMBIAR_ACCESS_KEY --n 500 --hilos 10
"""
import argparse
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--clave", required=True)
ap.add_argument("--token", default="", help="Bearer token si el endpoint lo exige")
ap.add_argument("--n", type=int, default=500)
ap.add_argument("--hilos", type=int, default=10)
a = ap.parse_args()
h = {"Authorization": f"Bearer {a.token}"} if a.token else {}


def llamada(_):
    req = {"monto_original": random.uniform(1000, 50000), "saldo_pendiente": random.uniform(500, 40000),
           "tasa_interes": random.uniform(6, 28), "plazo_meses": random.choice([12, 36, 60]),
           "dias_mora": random.choice([0, 0, 0, 15, 45, 120]), "ingreso_mensual": random.uniform(500, 5000),
           "segmento": "PERSONAL", "region": random.choice(["CENTRAL", "NORTE"])}
    t0 = time.perf_counter()
    try:
        r = requests.post(a.url, json={"accessKey": a.clave, "request": req}, headers=h, timeout=30)
        return (time.perf_counter() - t0) * 1000, r.status_code == 200
    except requests.RequestException:
        return (time.perf_counter() - t0) * 1000, False


t0 = time.time()
with ThreadPoolExecutor(a.hilos) as ex:
    res = list(ex.map(llamada, range(a.n)))
dur = time.time() - t0
lat = sorted(r[0] for r in res)
print(f"Solicitudes: {a.n} | errores: {sum(not r[1] for r in res)} ({100 * sum(not r[1] for r in res) / a.n:.1f}%)")
print(f"Latencia p50 {statistics.median(lat):.0f} ms | p95 {lat[int(len(lat) * .95) - 1]:.0f} ms | throughput {a.n / dur:.1f} req/s")
