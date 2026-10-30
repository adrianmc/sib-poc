"""
C02-AE-05/06: crea, borra o muestra el marcador de fallo controlado del pipeline, sin variables de entorno.
El bucket sale de config/config.yaml (s3.bucket). Ruta: s3a://<bucket>/sb/control/fallar_paso_<N>.

  python fase3/c02/c02_marcador.py ver              # lista la carpeta de control (debe estar vacia antes de la sesion)
  python fase3/c02/c02_marcador.py crear            # crea fallar_paso_3: el paso 3 del pipeline falla con mensaje accionable
  python fase3/c02/c02_marcador.py borrar           # lo borra: el siguiente reintento del paso 3 termina EXITOSO
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg  # noqa: E402


def hdfs(*args):
    r = subprocess.run(["hdfs", "dfs", *args], capture_output=True, text=True)
    salida = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if " WARN " not in l and l.strip())
    return r.returncode, salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["ver", "crear", "borrar"])
    ap.add_argument("--paso", type=int, default=3)
    a = ap.parse_args()
    bucket = cfg()["s3"]["bucket"]
    carpeta = f"s3a://{bucket}/sb/control"
    marcador = f"{carpeta}/fallar_paso_{a.paso}"
    hdfs("-mkdir", "-p", carpeta)
    if a.accion == "crear":
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("fallo controlado C02-AE-05\n")
        rc, out = hdfs("-put", "-f", f.name, marcador)
        print(f"Marcador creado: {marcador}" if rc == 0 else f"ERROR al crear: {out}")
    elif a.accion == "borrar":
        rc, out = hdfs("-rm", "-f", marcador)
        print(f"Marcador borrado: {marcador}" if rc == 0 else f"ERROR al borrar: {out}")
    rc, out = hdfs("-ls", carpeta)
    archivos = [l.split()[-1] for l in out.splitlines() if l.startswith("-")]
    print(f"Carpeta {carpeta}: " + (", ".join(archivos) if archivos else "vacia (sin marcadores)"))
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    main()
