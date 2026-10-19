"""
FASE 2 - Paso 05 (alternativa, Python): carga clientes/cuentas a RDS Oracle y creditos a RDS SQL Server.
Opcion recomendada: 05b_cargar_rds_spark.py en CDE. Esta version sirve desde una sesion de Cloudera AI
o cualquier cliente en la VPC con ODBC Driver 18 for SQL Server instalado.

  python fase2/05_cargar_rds.py --datos salida/rds
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sbpoc import cfg  # noqa: E402

LOTE = 50_000


def filas_nativas(chunk):
    """Convierte tipos numpy a tipos Python nativos para los drivers."""
    return [tuple(v.item() if hasattr(v, "item") else v for v in r) for r in chunk.itertuples(index=False, name=None)]


def cargar_oracle(datos: Path):
    import oracledb
    c = cfg()["rds"]["oracle"]
    con = oracledb.connect(user=c["user"], password=c["password"],
                           dsn=f'{c["host"]}:{c["port"]}/{c["service"]}')
    cur = con.cursor()
    sqls = {
        "clientes": ("INSERT INTO SBCORE.CLIENTES VALUES (:1,:2,:3,:4,:5,TO_DATE(:6,'YYYY-MM-DD'),:7,:8,:9,"
                     "TO_DATE(:10,'YYYY-MM-DD'),TO_TIMESTAMP(:11,'YYYY-MM-DD HH24:MI:SS'))"),
        "cuentas": "INSERT INTO SBCORE.CUENTAS VALUES (:1,:2,:3,:4,:5,:6,TO_DATE(:7,'YYYY-MM-DD'),:8)",
    }
    for tabla, sql in sqls.items():
        total = 0
        for chunk in pd.read_csv(datos / f"{tabla}.csv", chunksize=LOTE, dtype={"identificacion": str, "telefono": str}):
            cur.executemany(sql, filas_nativas(chunk))
            con.commit()
            total += len(chunk)
            print(f"Oracle {tabla}: {total}", end="\r")
        print()
    con.close()


def cargar_sqlserver(datos: Path):
    import pyodbc
    c = cfg()["rds"]["sqlserver"]
    con = pyodbc.connect(
        f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={c["host"]},{c["port"]};DATABASE={c["database"]};'
        f'UID={c["user"]};PWD={c["password"]};TrustServerCertificate=yes')
    cur = con.cursor()
    cur.fast_executemany = True
    sql = "INSERT INTO dbo.creditos VALUES (?,?,?,?,?,?,?,?,?,?,?)"
    total = 0
    for chunk in pd.read_csv(datos / "creditos.csv", chunksize=LOTE, dtype={"identificacion_cliente": str}):
        cur.executemany(sql, filas_nativas(chunk))
        con.commit()
        total += len(chunk)
        print(f"SQL Server creditos: {total}", end="\r")
    print()
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="salida/rds")
    ap.add_argument("--solo", choices=["oracle", "sqlserver"])
    a = ap.parse_args()
    if a.solo in (None, "oracle"):
        cargar_oracle(Path(a.datos))
    if a.solo in (None, "sqlserver"):
        cargar_sqlserver(Path(a.datos))
