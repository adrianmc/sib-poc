"""
C05-AE-02/04/05 (version Cloudera AI, sin CDE): despliega una version del pipeline en un ambiente.
1. Apunta el Job "sib-pipeline-<ambiente>" a la version (argumento --ref).
2. Lo ejecuta y espera el estado final (verificacion): sale con codigo 1 si falla.
3. Registra el despliegue en sb_gov.despliegues (version, ambiente, autor, fecha).
Rollback = desplegar una version previa (tag o commit): el Job vuelve a esa version inmutable; el historial conserva ambas.

  python fase3/c05/desplegar_cai.py --ambiente test                 # version = commit actual (HEAD)
  python fase3/c05/desplegar_cai.py --ambiente prod --version v1.0.0 # rollback a un tag
Requiere config cai.url, cai.api_key y cai.project_id (el runner de GitHub tambien los necesita).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.sbpoc import RAIZ, cai_api, cai_ejecutar_job, cai_job_id, error_ci, impala  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ambiente", choices=["dev", "test", "prod"], required=True)
    ap.add_argument("--version", help="commit o tag; por defecto el commit actual")
    ap.add_argument("--autor", default="pipeline")
    ap.add_argument("--sin-verificar", action="store_true")
    a = ap.parse_args()
    if not a.version:
        a.version = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                                   cwd=RAIZ).stdout.strip()
    job = f"sib-pipeline-{a.ambiente}"

    s, api, pid = cai_api()
    jid = cai_job_id(job)
    r = s.patch(f"{api}/projects/{pid}/jobs/{jid}", json={"arguments": f"--ref {a.version} --ambiente {a.ambiente}"},
                timeout=60)
    print(f"Job {job} -> version {a.version}: {r.status_code}")
    r.raise_for_status()

    con = impala("admin")
    cur = con.cursor()
    cur.execute(f"INSERT INTO sb_gov.despliegues VALUES ('sib-pipeline', '{a.ambiente}', '{a.version}', "
                f"'despliegues/{a.ambiente}/{a.version}', '{a.autor.replace(chr(39), '')}', now())")
    con.close()
    print("Despliegue registrado en sb_gov.despliegues")

    if a.sin_verificar:
        return
    print("Verificacion: ejecutando la version desplegada ...")
    run_id, estado = cai_ejecutar_job(job, esperar=True)
    if estado != "ENGINE_SUCCEEDED":
        error_ci(f"Verificacion fallida: {job} run {run_id} termino en {estado}")
        sys.exit(1)
    print("Verificacion OK")


if __name__ == "__main__":
    main()
