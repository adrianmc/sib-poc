"""
C06-AE-05: funcion de prediccion para desplegar como CML Model (Models > New Model):
  Archivo: fase3/c06/c06_ae05_modelo_endpoint.py   Funcion: predecir   Metricas: habilitadas
  Ejemplo de entrada: {"monto_original": 15000, "saldo_pendiente": 9000, "tasa_interes": 14.5, "plazo_meses": 60,
                       "dias_mora": 35, "ingreso_mensual": 1800, "segmento": "PERSONAL", "region": "CENTRAL"}
La consola del modelo muestra replicas, latencia, solicitudes y errores. Alternativa: AI Inference Service
desde el Model Registry (modelo "sb-riesgo-credito").
"""
import joblib
import pandas as pd
import cml.metrics_v1 as metrics
import cml.models_v1 as models

# El build del Model NO incluye archivos ignorados por .gitignore (data/, *.joblib): el artefacto se copia a
# fase3/c06/modelo_riesgo.pkl antes de desplegar (cp data/modelo_riesgo.joblib fase3/c06/modelo_riesgo.pkl)
ART = joblib.load("/home/cdsw/fase3/c06/modelo_riesgo.pkl")


@models.cml_model(metrics=True)
def predecir(args):
    fila = pd.DataFrame([args])
    fila["carga_financiera"] = float(args["saldo_pendiente"]) / (float(args["ingreso_mensual"]) * 12)
    X = pd.get_dummies(fila, columns=["segmento", "region"], dtype=float).reindex(columns=ART["columnas"], fill_value=0.0)
    prob = float(ART["modelo"].predict_proba(X)[0, 1])
    metrics.track_metric("probabilidad_default", prob)   # track_metric vive en cml.metrics_v1, no en models_v1
    return {"probabilidad_default": round(prob, 4), "decision": "REVISAR" if prob >= 0.5 else "APROBAR"}
