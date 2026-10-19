"""
C06-AE-02/04: entrenamiento Python con trazabilidad completa en MLflow (CML Experiments + Model Registry).
Traza: parametros, metricas, codigo (commit Git del proyecto) y DATOS (snapshot Iceberg exacto usado).
Ejecutar en CML (sesion JupyterLab Python 3.10+, perfil 4 vCPU/16 GB) como sb_cient01.
Produce tambien: data/features_creditos.csv (para R) y data/referencia_drift.csv (para C06-AE-06).
"""
import os
import subprocess
import sys

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import consulta  # noqa: E402

os.makedirs("/home/cdsw/data", exist_ok=True)
_, hist, _ = consulta("DESCRIBE HISTORY sb_curated.creditos", rol="cientifico")
# DESCRIBE HISTORY: creation_time, snapshot_id, parent_id, is_current_ancestor -> snapshot vigente mas reciente
vigentes = [h for h in hist if str(h[3]).upper() == "TRUE"] or hist
snapshot = max(vigentes, key=lambda h: str(h[0]))[1]

SQL = f"""
SELECT cr.monto_original, cr.saldo_pendiente, cr.tasa_interes, cr.plazo_meses, cr.dias_mora,
       c.ingreso_mensual, c.segmento, c.region, cr.default_12m
FROM (SELECT * FROM sb_curated.creditos FOR SYSTEM_VERSION AS OF {snapshot}) cr
JOIN sb_curated.clientes c ON c.identificacion = cr.identificacion_cliente
"""
cols, filas, ms = consulta(SQL, rol="cientifico")
df = pd.DataFrame(filas, columns=cols)
for c in ["monto_original", "saldo_pendiente", "tasa_interes", "ingreso_mensual"]:
    df[c] = df[c].astype(float)
df["carga_financiera"] = df["saldo_pendiente"] / (df["ingreso_mensual"] * 12)
df.to_csv("/home/cdsw/data/features_creditos.csv", index=False)
print(f"{len(df)} filas leidas en {ms:.0f} ms desde el snapshot {snapshot}")

# Exploracion (C06-PRE-03)
print(df.describe().T[["mean", "std", "min", "max"]])
print("Tasa de default por segmento:\n", df.groupby("segmento")["default_12m"].mean())
print("Tasa de default por region:\n", df.groupby("region")["default_12m"].mean())

X = pd.get_dummies(df.drop(columns=["default_12m"]), columns=["segmento", "region"], dtype=float)
y = df["default_12m"].astype(int)
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
X_tr.assign(default_12m=y_tr).to_csv("/home/cdsw/data/referencia_drift.csv", index=False)

params = {"max_iter": 200, "learning_rate": 0.08, "max_depth": 6}
mlflow.set_experiment("sb-riesgo-credito")
with mlflow.start_run(run_name="gbm-python"):
    modelo = HistGradientBoostingClassifier(**params).fit(X_tr, y_tr)
    p = modelo.predict_proba(X_te)[:, 1]
    mlflow.log_params(params)
    mlflow.log_metrics({"auc": roc_auc_score(y_te, p), "average_precision": average_precision_score(y_te, p)})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd="/home/cdsw").stdout.strip()
    mlflow.set_tags({"datos.tabla": "sb_curated.creditos", "datos.snapshot_iceberg": str(snapshot),
                     "codigo.commit": commit or "sin-git", "autor": os.environ.get("HADOOP_USER_NAME", "")})
    mlflow.sklearn.log_model(modelo, "modelo", registered_model_name="sb-riesgo-credito")
    joblib.dump({"modelo": modelo, "columnas": list(X.columns)}, "/home/cdsw/data/modelo_riesgo.joblib")
    print("AUC:", round(roc_auc_score(y_te, p), 4))
