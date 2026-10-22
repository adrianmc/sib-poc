"""
C02-AE-04: ejecucion automatica al detectar actualizacion en la capa bronce (landing).
Arquitectura: S3 Event Notification (ObjectCreated, prefijo sb/landing/transacciones/) -> SQS -> este proceso
-> API v2 de Cloudera AI -> Job "sib-pipeline" (c02_pipeline_sql.py). Con CDE disponible, el destino seria su API.
Ejecutar como Application de Cloudera AI (larga duracion, visible en la demo):
  python fase3/c02/c02_trigger_bronce.py
Prerrequisito (Fase 0/1): cola SQS + notificacion del bucket + permiso sqs:ReceiveMessage/DeleteMessage.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import boto3

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, cai_ejecutar_job  # noqa: E402

JOB = "sib-pipeline"   # Job de Cloudera AI (antes: job Airflow de CDE)


def disparar(motivo):
    try:
        run_id, estado = cai_ejecutar_job(JOB)
        print(f"[{datetime.now():%H:%M:%S}] {motivo} -> job {JOB} lanzado (run {run_id})")
    except Exception as e:  # noqa: BLE001
        print(f"[{datetime.now():%H:%M:%S}] {motivo} -> ERROR al lanzar {JOB}: {e}")


def main():
    c = cfg()
    sqs = boto3.client("sqs", region_name=c["s3"]["region"])
    url = c["aws"]["sqs_bronce_url"]
    print("Escuchando eventos de la capa bronce...")
    while True:
        resp = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=20)
        archivos = []
        for m in resp.get("Messages", []):
            cuerpo = json.loads(m["Body"])
            for rec in cuerpo.get("Records", []):
                archivos.append(rec["s3"]["object"]["key"])
            sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
        if archivos:   # un solo disparo por lote de archivos
            disparar(f"{len(archivos)} archivo(s) nuevo(s): {archivos[:3]}")


if __name__ == "__main__":
    main()
