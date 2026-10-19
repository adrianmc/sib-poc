"""
C02-PRE-07 / C02-AE-08 / C06-PRE-02: workload de entrenamiento acelerado por GPU, separado del computo CPU.

Ejecutar en Cloudera AI como sesion o Job con perfil de recursos que incluya 1 GPU (runtime con CUDA,
por ejemplo "Python 3.10 Nvidia GPU"). El grupo de instancias GPU del workspace escala de 0 a N:
al iniciar la sesion se aprovisiona el nodo GPU; al detenerla, el grupo vuelve a 0 (pausa/apagado).
  pip install xgboost
  python fase3/c06/c06_gpu_entrenamiento.py --dispositivo cuda
  python fase3/c06/c06_gpu_entrenamiento.py --dispositivo cpu      # misma carga en CPU para comparar
Entrada: /home/cdsw/data/features_creditos.csv (generado por c06_ae04_entrenar_python.py).
"""
import argparse
import subprocess
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

ap = argparse.ArgumentParser()
ap.add_argument("--dispositivo", choices=["cuda", "cpu"], default="cuda")
ap.add_argument("--replicas", type=int, default=20, help="multiplica el dataset para generar carga representativa")
a = ap.parse_args()

if a.dispositivo == "cuda":
    print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu", "--format=csv"],
                         capture_output=True, text=True).stdout)

df = pd.read_csv("/home/cdsw/data/features_creditos.csv")
X = pd.get_dummies(df.drop(columns=["default_12m"]), columns=["segmento", "region"], dtype=float)
y = df["default_12m"].astype(int)
X = pd.concat([X] * a.replicas, ignore_index=True)
X += np.random.default_rng(0).normal(0, 0.01, X.shape)        # evita duplicados exactos
y = pd.concat([y] * a.replicas, ignore_index=True)
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"Filas de entrenamiento: {len(X_tr):,}")

modelo = xgb.XGBClassifier(n_estimators=600, max_depth=8, learning_rate=0.05, tree_method="hist",
                           device=a.dispositivo, eval_metric="auc")
t0 = time.perf_counter()
modelo.fit(X_tr, y_tr)
dur = time.perf_counter() - t0
auc = roc_auc_score(y_te, modelo.predict_proba(X_te)[:, 1])
print(f"Dispositivo: {a.dispositivo} | tiempo de entrenamiento: {dur:.1f} s | AUC: {auc:.4f}")
print(f"Rendimiento: {len(X_tr) / (dur * 1000):.2f} registros/ms")
