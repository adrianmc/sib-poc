"""
FASE 2 - Paso 05: carga clientes, cuentas y creditos (salida/rds/*.csv del generador) a la base origen SQL Server.
Corre en una sesion de Cloudera AI (Terminal). pymssql no requiere driver ODBC.
Requiere: 03_sqlserver_origen.sql ejecutado y 1433 abierto desde la VPC hacia la EC2.

  python fase2/05_cargar_sqlserver.py                 # las 3 tablas
  python fase2/05_cargar_sqlserver.py --solo creditos
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import RAIZ, cfg, leer_argumentos  # noqa: E402

TABLAS = ["clientes", "cuentas", "creditos"]
LOTE = 5_000
TEXTO = {"identificacion": str, "telefono": str, "identificacion_cliente": str}


def filas(chunk):
    """Tipos numpy -> Python nativo; NaN -> NULL."""
    chunk = chunk.astype(object).where(pd.notnull(chunk), None)
    return [tuple(v.item() if hasattr(v, "item") else v for v in r) for r in chunk.itertuples(index=False, name=None)]


def cargar(con, datos: Path, tabla: str):
    cur = con.cursor()
    cur.execute(f"SELECT COUNT(*) FROM dbo.{tabla}")
    if cur.fetchone()[0]:
        print(f"{tabla}: ya tiene filas, se omite (vaciar con TRUNCATE TABLE dbo.{tabla} para recargar)")
        return
    total = 0
    for chunk in pd.read_csv(datos / f"{tabla}.csv", chunksize=LOTE, dtype=TEXTO):
        cols = list(chunk.columns)
        por_sentencia = 2000 // len(cols)          # limite de SQL Server: 2100 parametros por sentencia
        fila_sql = "(" + ", ".join(["%s"] * len(cols)) + ")"
        datos_lote = filas(chunk)
        for i in range(0, len(datos_lote), por_sentencia):
            parte = datos_lote[i:i + por_sentencia]
            sql = f"INSERT INTO dbo.{tabla} ({', '.join(cols)}) VALUES " + ", ".join([fila_sql] * len(parte))
            cur.execute(sql, tuple(v for f in parte for v in f))
        con.commit()
        total += len(chunk)
        print(f"{tabla}: {total}", end="\r")
    print(f"{tabla}: {total} filas cargadas")


def main():
    import pymssql
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default=str(RAIZ / "salida" / "rds"))
    ap.add_argument("--solo", choices=TABLAS)
    a = leer_argumentos(ap)
    c = cfg()["sqlserver"]
    con = pymssql.connect(server=c["host"], port=c["port"], user=c["user"], password=c["password"],
                          database=c["database"], login_timeout=15)
    for t in ([a.solo] if a.solo else TABLAS):
        cargar(con, Path(a.datos), t)
    con.close()


if __name__ == "__main__":
    main()
