"""
C05-AE-02/04/05 (version Cloudera AI, sin CDE): despliega una version del pipeline en un ambiente.

Dos vias (--via):
  cola (por defecto, la que usa GitHub Actions): el runner NO llama a la API de Cloudera AI.
       Inserta una solicitud en sb_gov.solicitudes_despliegue (Impala) y espera a que el despachador
       (fase3/c05/despachador_cai.py, Application dentro de Cloudera AI) la ejecute y marque EXITOSO o FALLIDO.
       Motivo: el balanceador del workspace de Cloudera AI no admite la IP del runner (26-oct); Impala si.
  api: llamada directa a la API v2 de Cloudera AI (cuando la red lo permite, ej. desde una sesion de CAI).

El despliegue en ambos casos: apunta el Job "sib-pipeline-<ambiente>" a la version (--ref), lo ejecuta,
verifica el estado final y registra en sb_gov.despliegues. Rollback = desplegar una version previa (tag o commit).

  python fase3/c05/desplegar_cai.py --ambiente test                  # version = commit actual (HEAD)
  python fase3/c05/desplegar_cai.py --ambiente prod --version v1.0.0 # rollback a un tag
"""
import argparse
import subprocess
import sys
import time
import uuid
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import RAIZ, error_ci, impala, leer_argumentos  # noqa: E402

TABLA_COLA = "sb_gov.solicitudes_despliegue"
DDL_COLA = (f"CREATE TABLE IF NOT EXISTS {TABLA_COLA} (id STRING, ambiente STRING, version STRING, autor STRING, "
            "estado STRING, run_id STRING, mensaje STRING, solicitado TIMESTAMP, actualizado TIMESTAMP) "
            "STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')")


def limpio(x):
    return str(x).replace("'", "")


def via_cola(a):
    con = impala("admin")
    cur = con.cursor()
    cur.execute(DDL_COLA)
    sid = f"{a.ambiente}-{a.version}-{uuid.uuid4().hex[:6]}"
    cur.execute(f"INSERT INTO {TABLA_COLA} VALUES ('{sid}', '{a.ambiente}', '{limpio(a.version)}', '{limpio(a.autor)}', "
                f"'PENDIENTE', NULL, NULL, now(), now())")
    print(f"Solicitud {sid}: version {a.version} -> {a.ambiente} (PENDIENTE)", flush=True)
    if a.sin_verificar:
        return
    limite = time.time() + a.timeout * 60
    estado_previo = None
    while time.time() < limite:
        time.sleep(15)
        cur.execute(f"SELECT estado, coalesce(run_id, ''), coalesce(mensaje, '') FROM {TABLA_COLA} WHERE id = '{sid}'")
        estado, run_id, mensaje = cur.fetchall()[0]
        if estado != estado_previo:
            print(f"  estado: {estado} {('run ' + run_id) if run_id else ''} {mensaje}", flush=True)
            estado_previo = estado
        if estado == "EXITOSO":
            print("Verificacion OK")
            return
        if estado == "FALLIDO":
            error_ci(f"Verificacion fallida: {mensaje} (run {run_id})")
            sys.exit(1)
    error_ci(f"Sin respuesta del despachador en {a.timeout} min. Revisar que la Application 'sib-despachador' "
             f"este Running en Cloudera AI. Solicitud {sid}")
    sys.exit(1)


def via_api(a):
    from lib.sbpoc import cai_api, cai_ejecutar_job, cai_job_id
    job = f"sib-pipeline-{a.ambiente}"
    s, api, pid = cai_api()
    r = s.patch(f"{api}/projects/{pid}/jobs/{cai_job_id(job)}",
                json={"arguments": f"--ref {a.version} --ambiente {a.ambiente}"}, timeout=60)
    print(f"Job {job} -> version {a.version}: {r.status_code}")
    r.raise_for_status()
    con = impala("admin")
    con.cursor().execute(f"INSERT INTO sb_gov.despliegues VALUES ('sib-pipeline', '{a.ambiente}', '{limpio(a.version)}', "
                         f"'despliegues/{a.ambiente}', '{limpio(a.autor)}', now())")
    print("Despliegue registrado en sb_gov.despliegues")
    if a.sin_verificar:
        return
    run_id, estado = cai_ejecutar_job(job, esperar=True)
    if estado != "ENGINE_SUCCEEDED":
        error_ci(f"Verificacion fallida: {job} run {run_id} termino en {estado}")
        sys.exit(1)
    print("Verificacion OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ambiente", choices=["dev", "test", "prod"], required=True)
    ap.add_argument("--version", help="commit o tag; por defecto el commit actual")
    ap.add_argument("--autor", default="pipeline")
    ap.add_argument("--via", choices=["cola", "api"], default="cola")
    ap.add_argument("--timeout", type=int, default=30, help="minutos de espera de la verificacion (via cola)")
    ap.add_argument("--sin-verificar", action="store_true")
    a = leer_argumentos(ap)
    if not a.version:
        a.version = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                                   cwd=RAIZ).stdout.strip()
    via_cola(a) if a.via == "cola" else via_api(a)


if __name__ == "__main__":
    main()
