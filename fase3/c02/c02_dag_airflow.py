"""
C02-AE-01/04/05/06: orquestacion en Airflow de CDE.
Job CDE tipo Airflow "sb-orquestacion" con este DAG. Reintentos automaticos = recuperacion ante fallo.
El trigger por evento (c02_trigger_bronce.py) ejecuta este job cuando llega un archivo a la capa bronce.
"""
from datetime import datetime, timedelta

from airflow import DAG
from cloudera.cdp.airflow.operators.cde_operator import CDEJobRunOperator

default_args = {
    "owner": "sb_ing01",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "depends_on_past": False,
}

with DAG(
    dag_id="sb_orquestacion",
    default_args=default_args,
    start_date=datetime(2026, 8, 1),
    schedule_interval="0 2 * * *",   # diario; ademas se dispara por evento
    catchup=False,
    tags=["sb-poc"],
) as dag:
    pipeline = CDEJobRunOperator(task_id="pipeline_batch", job_name="sb-pipeline-batch")
