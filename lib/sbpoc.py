"""Utilidades comunes de la PoC SIB: configuracion, Impala, Knox (Ranger/Atlas), CDE y Cloudera AI (API v2)."""
from pathlib import Path
import os
import time
import requests
import yaml

RAIZ = Path(__file__).resolve().parents[1]


def cfg():
    """Lee config/config.yaml. SBPOC_CONFIG permite apuntar a otro archivo (despliegues versionados de C05)."""
    ruta = os.environ.get("SBPOC_CONFIG") or (RAIZ / "config" / "config.yaml")
    with open(ruta, encoding="utf-8") as f:
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


def atlas_guid(sesion, atlas, qualified_name, nivel="column"):
    """Busca una tabla o columna en Atlas probando los tipos Iceberg y Hive.
    En CDP 7.3.x las tablas Iceberg se registran como iceberg_table / iceberg_column;
    las tablas externas y vistas, como hive_table / hive_column. Devuelve (guid, tipo) o (None, None)."""
    for tipo in (f"iceberg_{nivel}", f"hive_{nivel}"):
        r = sesion.get(f"{atlas}/entity/uniqueAttribute/type/{tipo}", params={"attr:qualifiedName": qualified_name})
        if r.status_code == 200:
            return r.json()["entity"]["guid"], tipo
    return None, None



# ---------------------------------------------------------------------------------------------
# Cloudera AI (API v2 REST). Reemplaza a CDE como orquestador mientras CDE no este disponible.
# Clave: Cloudera AI > User Settings > API Keys > Create API Key (API v2). Va en config cai.api_key.
# ---------------------------------------------------------------------------------------------
def cai_api():
    """Devuelve (sesion, url_base_api, project_id)."""
    c = cfg().get("cai", {})
    url = (c.get("url") or ("https://" + os.environ.get("CDSW_DOMAIN", ""))).rstrip("/")
    pid = c.get("project_id") or os.environ.get("CDSW_PROJECT_ID")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {c.get('api_key') or os.environ.get('CDSW_APIV2_KEY', '')}",
                      "Content-Type": "application/json"})
    return s, f"{url}/api/v2", pid


def cai_job_id(nombre):
    """Busca un job del proyecto por nombre exacto."""
    import json
    s, api, pid = cai_api()
    r = s.get(f"{api}/projects/{pid}/jobs", params={"search_filter": json.dumps({"name": nombre})}, timeout=60)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        if j["name"] == nombre:
            return j["id"]
    raise RuntimeError(f"No existe el job '{nombre}' en el proyecto {pid}")


def cai_ejecutar_job(nombre, esperar=False, intervalo=20):
    """Lanza un job de Cloudera AI. Con esperar=True devuelve el estado final (ENGINE_SUCCEEDED, ENGINE_FAILED...)."""
    s, api, pid = cai_api()
    jid = cai_job_id(nombre)
    r = s.post(f"{api}/projects/{pid}/jobs/{jid}/runs", json={}, timeout=60)
    r.raise_for_status()
    run_id = r.json()["id"]
    if not esperar:
        return run_id, "LANZADO"
    while True:
        time.sleep(intervalo)
        estado = s.get(f"{api}/projects/{pid}/jobs/{jid}/runs/{run_id}", timeout=60).json().get("status", "")
        print("  estado:", estado)
        if estado in ("ENGINE_SUCCEEDED", "ENGINE_FAILED", "ENGINE_STOPPED", "ENGINE_TIMEDOUT"):
            return run_id, estado
