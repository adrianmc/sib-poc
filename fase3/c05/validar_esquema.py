"""C05: valida que las tablas en CDW cumplan el contrato de datos versionado. Sale con codigo 1 si difiere."""
import sys
from pathlib import Path

import yaml

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import RAIZ, consulta, error_ci  # noqa: E402

contrato = yaml.safe_load(open(RAIZ / "fase3" / "c05" / "esquemas" / "contrato_datos.yaml"))
errores = 0
for tabla, esperado in contrato.items():
    _, filas, _ = consulta(f"DESCRIBE {tabla}", rol="ingeniero")
    real = {f[0].lower(): f[1].lower() for f in filas}
    for col, tipo in esperado.items():
        if real.get(col) != tipo.lower():
            error_ci(f"{tabla}.{col}: esperado {tipo}, encontrado {real.get(col)}")
            errores += 1
    print(f"{tabla}: {'OK' if not errores else 'DIFERENCIAS'}")
if errores:
    sys.exit(1)
