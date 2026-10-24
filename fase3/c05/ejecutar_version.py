"""
C05 (version Cloudera AI, sin CDE): ejecuta UNA VERSION FIJA del pipeline.
Cada version se materializa una sola vez como worktree de Git inmutable en /home/cdsw/despliegues/<ambiente>/<ref>
(equivalente al recurso inmutable de CDE). El Job del ambiente solo cambia de argumento --ref al desplegar;
el rollback apunta de nuevo a una version previa, que sigue intacta en disco y en el historial.

Jobs de Cloudera AI (crear una vez, ver LEEME_CICD.md): sib-pipeline-dev, sib-pipeline-test, sib-pipeline-prod
  script: fase3/c05/ejecutar_version.py   argumentos: --ref <commit> --ambiente <dev|test|prod>
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path("/home/cdsw")

def _leer_argumentos(parser):
    """En Jobs de Cloudera AI los argumentos llegan en JOB_ARGUMENTS (el script corre en un kernel)."""
    import os
    import shlex
    if os.environ.get("JOB_ARGUMENTS") is not None:
        return parser.parse_known_args(shlex.split(os.environ["JOB_ARGUMENTS"]))[0]
    return parser.parse_known_args([x for x in sys.argv[1:] if not x.endswith(".json") and x != "-f"])[0]


ap = argparse.ArgumentParser()
ap.add_argument("--ref", required=True, help="commit o tag a ejecutar")
ap.add_argument("--ambiente", required=True, choices=["dev", "test", "prod"])
a = _leer_argumentos(ap)

destino = RAIZ / "despliegues" / a.ambiente / a.ref
if not destino.exists():
    subprocess.run(["git", "-C", str(RAIZ), "fetch", "--all", "--tags", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(RAIZ), "worktree", "add", "--detach", str(destino), a.ref], check=True)
    print(f"Version {a.ref} materializada en {destino} (inmutable)")
else:
    print(f"Version {a.ref} ya existe en {destino}; se reutiliza sin cambios")

entorno = dict(os.environ, SBPOC_CONFIG=str(RAIZ / "config" / "config.yaml"))
entorno.pop("JOB_ARGUMENTS", None)   # el pipeline hijo recibe sus argumentos por linea de comandos
r = subprocess.run([sys.executable, str(destino / "fase3" / "c02" / "c02_pipeline_sql.py"),
                    "--version", a.ref, "--ambiente", a.ambiente], env=entorno)
if r.returncode:     # solo salir con error; sys.exit(0) en un Job se reporta como fallo
    sys.exit(r.returncode)
