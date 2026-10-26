"""
C05 (version Cloudera AI, sin CDE): ejecuta UNA VERSION FIJA del pipeline.
Cada version se materializa una sola vez como worktree de Git inmutable en
/home/cdsw/despliegues/<ambiente>/<commit> (equivalente al recurso inmutable de CDE).
El Job del ambiente solo cambia de argumento --ref al desplegar; el rollback apunta de nuevo a una version previa,
que sigue intacta en disco y en el historial.

Protecciones (leccion del 26-oct, un tag viejo apuntaba a un commit sin el pipeline):
- fetch de tags con --force: si un tag se movio en GitHub, se usa el destino nuevo.
- la carpeta se nombra por COMMIT, no por tag: un tag movido nunca reutiliza una version vieja.
- antes de ejecutar valida que la version contenga el pipeline; si no, error claro y accionable.

Jobs de Cloudera AI (crear una vez, ver LEEME_CICD.md): sib-pipeline-dev, sib-pipeline-test, sib-pipeline-prod
  script: fase3/c05/ejecutar_version.py   argumentos: --ref <commit o tag> --ambiente <dev|test|prod>
"""
import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

RAIZ = Path("/home/cdsw")
PIPELINE = "fase3/c02/c02_pipeline_sql.py"


def leer_argumentos(parser):
    """En Jobs de Cloudera AI los argumentos llegan en JOB_ARGUMENTS (el script corre en un kernel)."""
    if os.environ.get("JOB_ARGUMENTS") is not None:
        return parser.parse_known_args(shlex.split(os.environ["JOB_ARGUMENTS"]))[0]
    return parser.parse_known_args([x for x in sys.argv[1:] if not x.endswith(".json") and x != "-f"])[0]


def git(*args):
    return subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)


def fallar(msg):
    print(f"ERROR: {msg}", flush=True)
    sys.exit(1)


ap = argparse.ArgumentParser()
ap.add_argument("--ref", help="commit o tag a ejecutar")
ap.add_argument("--ambiente", choices=["dev", "test", "prod"])
a = leer_argumentos(ap)
if not a.ref or not a.ambiente:
    fallar("faltan argumentos del Job. Deben ser: --ref <tag o commit> --ambiente <dev|test|prod>")

# 1. Traer ramas y tags de GitHub (force: acepta tags movidos)
r = git("fetch", "origin", "--tags", "--force", "--prune")
if r.returncode:
    fallar(f"no se pudo hacer git fetch desde GitHub: {r.stderr.strip()}")

# 2. Resolver la referencia a un commit
r = git("rev-parse", "--verify", "--quiet", f"{a.ref}^{{commit}}")
if r.returncode:
    fallar(f"la version '{a.ref}' no existe en GitHub. Revisar con: git ls-remote --tags origin")
commit = r.stdout.strip()[:7]
print(f"Version solicitada: {a.ref} -> commit {commit}", flush=True)

# 3. Validar que esa version contenga el pipeline ANTES de materializarla
if git("cat-file", "-e", f"{commit}:{PIPELINE}").returncode:
    fallar(f"la version '{a.ref}' (commit {commit}) no contiene {PIPELINE}. "
           f"El tag apunta a un commit anterior al pipeline: mover el tag al commit correcto "
           f"(git tag -f {a.ref} <commit> && git push -f origin {a.ref}).")

# 4. Materializar (una sola vez por commit: inmutable)
destino = RAIZ / "despliegues" / a.ambiente / commit
if destino.exists() and not (destino / PIPELINE).exists():
    git("worktree", "remove", "--force", str(destino))      # restos de un intento fallido
if not destino.exists():
    git("worktree", "prune")
    r = git("worktree", "add", "--detach", str(destino), commit)
    if r.returncode:
        fallar(f"no se pudo materializar la version: {r.stderr.strip()}")
    print(f"Version {a.ref} ({commit}) materializada en {destino} (inmutable)", flush=True)
else:
    print(f"Version {a.ref} ({commit}) ya existe en {destino}; se reutiliza sin cambios", flush=True)

# 5. Ejecutar el pipeline de ESA version
entorno = dict(os.environ, SBPOC_CONFIG=str(RAIZ / "config" / "config.yaml"))
entorno.pop("JOB_ARGUMENTS", None)   # el pipeline hijo recibe sus argumentos por linea de comandos
r = subprocess.run([sys.executable, str(destino / PIPELINE), "--version", a.ref, "--ambiente", a.ambiente], env=entorno)
if r.returncode:     # solo salir con error; sys.exit(0) en un Job se reporta como fallo
    fallar(f"el pipeline de la version {a.ref} ({commit}) termino con codigo {r.returncode}")
