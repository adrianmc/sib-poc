"""
C06-AE-06: deteccion de drift con PSI (Population Stability Index) y prueba KS, sin dependencias de versiones.
Se ejecuta como CML Job programado; si hay drift sale con codigo 1 -> CML marca el job como fallido y
envia la notificacion por correo configurada en el job (alerta nativa).
  python fase3/c06/c06_ae06_drift.py --simular   # desplaza ingreso y mora para provocar drift en la demo
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

UMBRAL_PSI = 0.2
VARIABLES = ["ingreso_mensual", "dias_mora", "tasa_interes", "carga_financiera", "monto_original"]


def psi(ref, act, bins=10):
    cortes = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    r = np.histogram(ref, cortes)[0] / len(ref) + 1e-6
    a = np.histogram(np.clip(act, cortes[0], cortes[-1]), cortes)[0] / len(act) + 1e-6
    return float(np.sum((a - r) * np.log(a / r)))


ap = argparse.ArgumentParser()
ap.add_argument("--simular", action="store_true")
a = ap.parse_args()
ref = pd.read_csv("/home/cdsw/data/referencia_drift.csv")
act = pd.read_csv("/home/cdsw/data/features_creditos.csv").sample(frac=0.3, random_state=7)
if a.simular:
    act["ingreso_mensual"] *= 0.65                     # caida de ingresos (escenario de estres)
    act["dias_mora"] = act["dias_mora"] + np.random.default_rng(1).integers(0, 60, len(act))
    act["carga_financiera"] = act["saldo_pendiente"] / (act["ingreso_mensual"] * 12)

resultado = {}
for v in VARIABLES:
    resultado[v] = {"psi": round(psi(ref[v].values, act[v].values), 4),
                    "ks_pvalue": float(ks_2samp(ref[v], act[v]).pvalue)}
alertas = [v for v, m in resultado.items() if m["psi"] > UMBRAL_PSI]
print(json.dumps(resultado, indent=2))
filas = "".join(f"<tr><td>{v}</td><td>{m['psi']}</td><td>{m['ks_pvalue']:.2e}</td>"
                f"<td>{'DRIFT' if v in alertas else 'OK'}</td></tr>" for v, m in resultado.items())
with open("/home/cdsw/data/reporte_drift.html", "w") as f:
    f.write(f"<h2>Reporte de drift - modelo sb-riesgo-credito</h2><p>Umbral PSI: {UMBRAL_PSI}</p>"
            f"<table border=1><tr><th>Variable</th><th>PSI</th><th>KS p-value</th><th>Estado</th></tr>{filas}</table>")
if alertas:
    print(f"ALERTA DE DRIFT en: {alertas}")
    sys.exit(1)
print("Sin drift significativo")
