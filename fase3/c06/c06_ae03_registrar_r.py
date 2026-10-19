"""
C06-PRE-03 / AE-03 / AE-04: registra la corrida del modelo R en el MISMO experimento MLflow que el modelo Python
(metricas, parametros y artefacto .rds), para comparar ambos en la UI de Experiments.
Honestidad: el Model Registry versiona el modelo Python (sabor sklearn). El modelo R queda trazado como corrida
del experimento con su artefacto; registrarlo en el Registry requeriria empaquetarlo con un sabor MLflow para R.
  python fase3/c06/c06_ae03_registrar_r.py
"""
import mlflow
import pandas as pd

res = pd.read_csv("/home/cdsw/data/resultado_r.csv").iloc[0]
mlflow.set_experiment("sb-riesgo-credito")
with mlflow.start_run(run_name="glm-R"):
    mlflow.log_params({"lenguaje": "R", "algoritmo": "glm binomial", "filas_entreno": int(res["filas_entreno"])})
    mlflow.log_metric("auc", float(res["auc"]))
    mlflow.log_artifact("/home/cdsw/data/modelo_glm_r.rds")
    mlflow.log_artifact("/home/cdsw/fase3/c06/c06_ae03_entrenar_r.R")
print("Corrida R registrada en el experimento sb-riesgo-credito")
