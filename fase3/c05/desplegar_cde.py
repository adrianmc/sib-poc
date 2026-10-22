"""
C05-AE-04/05: despliega el pipeline en CDE con trazabilidad de version.
Cada version se sube a un recurso INMUTABLE "sb-codigo-<ambiente>-<version>"; el job apunta a ese recurso.
Rollback real = redesplegar un tag previo: el job vuelve a apuntar al recurso de esa version y ambas quedan en el historial.
Verificacion: lanza una ejecucion del job desplegado y espera su estado final; sale con codigo 1 si falla.

  python fase3/c05/desplegar_cde.py --ambiente test --version a1b2c3d --autor "sb_ing01"
"""
import argparse
import sys
import time
from pathlib import Path

import requests

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cde_api, cde_token, cfg, error_ci, impala, RAIZ  # noqa: E402

ARCHIVOS = [RAIZ / "fase3" / "c02" / "c02_pipeline_batch.py"]
CONF = {
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "spark.sql.catalog.spark_catalog": "org.apache.iceberg.spark.SparkSessionCatalog",
    "spark.sql.catalog.spark_catalog.type": "hive",
    "spark.sql.iceberg.handle-timestamp-without-timezone": "true",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ambiente", choices=["dev", "test", "prod"], required=True)
    ap.add_argument("--version", help="por defecto: commit corto de HEAD (rollback reutiliza el recurso de esa version)")
    ap.add_argument("--autor", default="pipeline")
    ap.add_argument("--sin-verificar", action="store_true")
    a = ap.parse_args()
    if not a.version:
        import subprocess
        a.version = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                                   cwd=RAIZ).stdout.strip()
    a.version = a.version[:7]
    c = cfg()
    api = cde_api("a")
    h = {"Authorization": f"Bearer {cde_token('ingeniero')}"}
    recurso, job = f"sb-codigo-{a.ambiente}-{a.version}", f"sb-pipeline-batch-{a.ambiente}"

    r = requests.post(f"{api}/resources", headers=h, json={"name": recurso, "type": "files"})
    if r.status_code == 409:
        print("Recurso", recurso, "ya existe: version inmutable, se reutiliza sin modificar (caso rollback)")
    else:
        r.raise_for_status()
        for f in ARCHIVOS:
            with open(f, "rb") as fh:
                r = requests.put(f"{api}/resources/{recurso}/{f.name}", headers=h, files={"file": (f.name, fh)})
                r.raise_for_status()
        print("Recurso", recurso, "creado con", [f.name for f in ARCHIVOS])

    rds = c["rds"]["sqlserver"]
    cuerpo = {
        "name": job, "type": "spark",
        "mounts": [{"resourceName": recurso}, {"resourceName": "sb-drivers"}],   # sb-drivers: mssql-jdbc.jar
        "spark": {"file": "c02_pipeline_batch.py", "conf": {**CONF, "spark.sb.version": a.version},
                  "jars": ["mssql-jdbc.jar"],
                  "args": ["--bucket", c["s3"]["bucket"],
                           "--jdbc-url", f"jdbc:sqlserver://{rds['host']}:{rds['port']};databaseName={rds['database']};encrypt=false",
                           "--jdbc-user", rds["user"], "--jdbc-password", rds["password"], "--version", a.version]},
    }
    r = requests.post(f"{api}/jobs", headers=h, json=cuerpo)
    if r.status_code == 409:
        r = requests.patch(f"{api}/jobs/{job}", headers=h, json=cuerpo)
    print("Job", job, "->", recurso, r.status_code, r.text[:200])
    r.raise_for_status()

    con = impala("admin")
    cur = con.cursor()
    cur.execute(f"INSERT INTO sb_gov.despliegues VALUES ('sb-pipeline-batch', '{a.ambiente}', '{a.version}', "
                f"'{recurso}', '{a.autor.replace(chr(39), '')}', now())")
    con.close()
    print("Despliegue registrado en sb_gov.despliegues")
    if a.sin_verificar:
        return
    r = requests.post(f"{api}/jobs/{job}/run", headers=h, json={})
    r.raise_for_status()
    run_id = r.json()["id"]
    print(f"Verificacion: ejecucion {run_id} lanzada; esperando estado final...")
    while True:
        time.sleep(20)
        estado = requests.get(f"{api}/job-runs/{run_id}", headers=h).json().get("status", "desconocido")
        print("  estado:", estado)
        if estado in ("succeeded", "failed", "killed"):
            break
    if estado != "succeeded":
        error_ci(f"Verificacion fallida: ejecucion {run_id} termino en {estado}")
        sys.exit(1)
    print("Verificacion OK")


if __name__ == "__main__":
    main()
