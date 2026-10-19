"""Utilidades comunes de la PoC SB: configuracion, Impala, Knox (Ranger/Atlas) y CDE."""
from pathlib import Path
import time
import requests
import yaml

RAIZ = Path(__file__).resolve().parents[1]


def cfg():
    with open(RAIZ / "config" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def impala(rol="admin", depto="a"):
    """Conexion impyla a un Virtual Warehouse Impala de CDW (LDAP sobre HTTP/TLS)."""
    from impala.dbapi import connect
    c = cfg()
    u = c["usuarios"][rol]
    return connect(host=c["impala"][f"host_depto_{depto}"], port=c["impala"]["port"],
                   auth_mechanism="LDAP", use_ssl=True, use_http_transport=True,
                   http_path=c["impala"]["http_path"], user=u["user"], password=u["password"])


def consulta(sql, rol="admin", depto="a"):
    """Ejecuta SQL y devuelve (columnas, filas, milisegundos)."""
    con = impala(rol, depto)
    cur = con.cursor()
    t0 = time.perf_counter()
    cur.execute(sql)
    filas = cur.fetchall() if cur.description else []
    ms = (time.perf_counter() - t0) * 1000
    cols = [d[0] for d in cur.description] if cur.description else []
    cur.close()
    con.close()
    return cols, filas, ms


def knox(servicio, rol="admin"):
    """Devuelve (sesion, url_base) para 'ranger' o 'atlas' via Knox del Data Lake."""
    c = cfg()
    u = c["usuarios"][rol]
    s = requests.Session()
    s.auth = (u["user"], u["password"])
    s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    base = c["datalake"]["knox_api"].rstrip("/")
    rutas = {"ranger": f"{base}/ranger", "atlas": f"{base}/atlas/api/atlas/v2"}
    return s, rutas[servicio]


def cde_token(rol="admin"):
    c = cfg()
    u = c["usuarios"][rol]
    r = requests.get(c["cde"]["token_url"], auth=(u["user"], u["password"]), timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def cde_api(depto="a"):
    return cfg()["cde"][f"jobs_api_depto_{depto}"].rstrip("/")


def error_ci(mensaje):
    """Anota un error visible en el runner de CI (GitHub Actions, Azure Pipelines o consola)."""
    import os
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error::{mensaje}")
    elif os.environ.get("TF_BUILD"):
        print(f"##vso[task.logissue type=error]{mensaje}")
    else:
        print(f"ERROR: {mensaje}")
