"""
C02-AE-04: ejecucion automatica al detectar actualizacion en la capa bronce (landing).
Arquitectura: S3 Event Notification (ObjectCreated, prefijo sb/landing/transacciones/) -> SQS -> este proceso
-> API de CDE -> job Airflow "sb-orquestacion".
Ejecutar como Application de Cloudera AI (larga duracion, visible en la demo):
  python fase3/c02/c02_trigger_bronce.py
Prerrequisito (Fase 0/1): cola SQS + notificacion del bucket + permiso sqs:ReceiveMessage/DeleteMessage.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import boto3
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.sbpoc import cfg, cde_token, cde_api  # noqa: E402

JOB = "sb-orquestacion"


def disparar(motivo):
    token = cde_token("ingeniero")
    r = requests.post(f"{cde_api('a')}/jobs/{JOB}/run", headers={"Authorization": f"Bearer {token}"},
                      json={}, timeout=60)
    print(f"[{datetime.now():%H:%M:%S}] {motivo} -> run {JOB}: {r.status_code} {r.text[:200]}")


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
