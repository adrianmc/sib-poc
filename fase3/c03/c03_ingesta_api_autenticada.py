"""
C03-AE-02: consumir una API externa autenticada e ingerir la respuesta en una tabla Iceberg de trabajo
(JSON crudo + campos parseados). El patron (token -> paginacion -> Iceberg) es el mismo para cualquier API.
Las fuentes sharepoint/dataverse son OPCIONALES: solo si la SB aporta su propio tenant. C03-AE-04/05 se
cubren con el escenario documental (c03_apis_y_diagramas.md), que el criterio de la SB acepta.

  python fase3/c03/c03_ingesta_api_autenticada.py --fuente sharepoint   # lista de SharePoint via Microsoft Graph
  python fase3/c03/c03_ingesta_api_autenticada.py --fuente dataverse    # cuentas de Dynamics 365 (Dataverse Web API)

Ejecutar en una sesion CML (Python). Requiere App Registration en Entra con permisos:
  Graph: Sites.Read.All (application) | Dataverse: usuario de aplicacion creado en el ambiente de D365.
Honestidad: no son conectores nativos de Cloudera; es integracion via API estandar (workaround con desarrollo minimo).
En NiFi el mismo patron es InvokeHTTP + StandardOauth2AccessTokenProvider + PutIceberg.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, impala  # noqa: E402


def token(scope):
    e = cfg()["entra"]
    r = requests.post(f"https://login.microsoftonline.com/{e['tenant_id']}/oauth2/v2.0/token",
                      data={"grant_type": "client_credentials", "client_id": e["client_id"],
                            "client_secret": e["client_secret"], "scope": scope}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def paginar(url, headers, clave_siguiente):
    while url:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        cuerpo = r.json()
        yield from cuerpo.get("value", [])
        url = cuerpo.get(clave_siguiente)


def sharepoint():
    e = cfg()["entra"]
    h = {"Authorization": f"Bearer {token('https://graph.microsoft.com/.default')}"}
    url = (f"https://graph.microsoft.com/v1.0/sites/{e['sharepoint_site_id']}/lists/"
           f"{e['sharepoint_list_id']}/items?expand=fields&$top=200")
    return [(str(i["id"]), json.dumps(i.get("fields", {}), ensure_ascii=False)) for i in paginar(url, h, "@odata.nextLink")]


def dataverse():
    base = cfg()["entra"]["dataverse_url"].rstrip("/")
    h = {"Authorization": f"Bearer {token(base + '/.default')}", "Accept": "application/json",
         "OData-MaxVersion": "4.0", "OData-Version": "4.0"}
    url = f"{base}/api/data/v9.2/accounts?$select=accountid,name,accountnumber,revenue,modifiedon"
    return [(i["accountid"], json.dumps(i, ensure_ascii=False)) for i in paginar(url, h, "@odata.nextLink")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["sharepoint", "dataverse"], required=True)
    a = ap.parse_args()
    filas = sharepoint() if a.fuente == "sharepoint" else dataverse()
    tabla = f"sb_raw.api_{a.fuente}"
    con = impala("ingeniero")
    cur = con.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {tabla} (id_registro STRING, payload_json STRING,
                    fuente STRING, ingesta_ts TIMESTAMP) STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')""")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lote = 200
    for i in range(0, len(filas), lote):
        valores = ",".join(
            "('{}','{}','{}',CAST('{}' AS TIMESTAMP))".format(fid.replace("'", ""), p.replace("\\", "\\\\").replace("'", "\\'"), a.fuente, ts)
            for fid, p in filas[i:i + lote])
        cur.execute(f"INSERT INTO {tabla} VALUES {valores}")
    print(f"{len(filas)} registros ingeridos en {tabla}")
    campo = "Title" if a.fuente == "sharepoint" else "name"
    cur.execute(f"SELECT id_registro, get_json_object(payload_json, '$.{campo}') FROM {tabla} LIMIT 5")
    for f in cur.fetchall():
        print(f)
    con.close()


if __name__ == "__main__":
    main()
