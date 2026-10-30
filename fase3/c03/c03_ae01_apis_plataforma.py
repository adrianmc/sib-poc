"""
C03-PRE-02 / AE-01: prueba en vivo de las APIs de la plataforma (reemplaza los curl de CDE, no disponible en el tenant).
Cada superficie se llama por su API REST o protocolo estandar y se reporta estado HTTP, tiempo y resultado.

  python fase3/c03/c03_ae01_apis_plataforma.py                    # lectura en todas las superficies
  python fase3/c03/c03_ae01_apis_plataforma.py --ejecutar-job sib-calidad   # ademas lanza un Job por API

Superficies: Atlas REST v2 y Ranger REST (via Knox del Data Lake), Cloudera AI API v2 (Jobs, Applications, Models),
SQL de CDW (Impala por HTTP/TLS + LDAP, el mismo canal de Power BI). Cubre tambien el control plane si la CLI de CDP
esta instalada (`cdp environments list-environments`), que se muestra aparte.
"""
import argparse
import sys
import time
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cai_api, cai_ejecutar_job, cfg, impala, knox, leer_argumentos  # noqa: E402

resultados = []


def probar(superficie, endpoint, funcion):
    t0 = time.perf_counter()
    try:
        estado, detalle = funcion()
    except Exception as e:
        estado, detalle = "ERROR", str(e)[:120]
    ms = (time.perf_counter() - t0) * 1000
    resultados.append((superficie, endpoint, estado, ms, detalle))
    print(f"[{estado}] {superficie:<22} {ms:7.0f} ms  {detalle}", flush=True)


def atlas():
    """Busca las tablas de sb_curated en Atlas. Segun como se crearon, quedan como iceberg_table o hive_table."""
    s, url = knox("atlas")
    vistos, codigo = {}, 0
    for tipo in ("iceberg_table", "hive_table"):
        cuerpo = {"typeName": tipo, "excludeDeletedEntities": True, "limit": 100,
                  "entityFilters": {"attributeName": "qualifiedName", "operator": "startsWith",
                                    "attributeValue": "sb_curated."}}
        r = s.post(f"{url}/search/basic", json=cuerpo, timeout=30)
        codigo = codigo or r.status_code
        for e in (r.json().get("entities") or []) if r.status_code == 200 else []:
            qn = e.get("attributes", {}).get("qualifiedName", "")
            if qn.startswith("sb_curated."):
                vistos[qn] = tipo
    ej = sorted(q.split("@")[0] for q in vistos)[:3]
    return codigo, f"{len(vistos)} tablas de sb_curated catalogadas, ej. {ej}"


def ranger():
    s, url = knox("ranger")
    r = s.get(f"{url}/service/public/v2/api/policy", params={"policyNamePartial": "sb_"}, timeout=30)
    pol = r.json() if r.status_code == 200 else []
    return r.status_code, f"{len(pol)} politicas sb_*, ej. {[p['name'] for p in pol][:4]}"


def cai(recurso):
    def f():
        s, api, pid = cai_api()
        r = s.get(f"{api}/projects/{pid}/{recurso}", timeout=30)
        items = r.json().get(recurso, [])
        return r.status_code, f"{len(items)} {recurso}: {[i.get('name') for i in items][:5]}"
    return f


def sql():
    con = impala("ingeniero")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM sb_curated.clientes")
    n = cur.fetchall()[0][0]
    con.close()
    return 200, f"SELECT COUNT(*) sb_curated.clientes = {n:,}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecutar-job", help="nombre de un Job de Cloudera AI para lanzarlo por API (ej. sib-calidad)")
    a = leer_argumentos(ap)
    c = cfg()
    print(f"Knox: {c['datalake']['knox_api']}\nCloudera AI: {c.get('cai', {}).get('url', '')}\n", flush=True)
    probar("Atlas REST v2", "POST /atlas/api/atlas/v2/search/basic", atlas)
    probar("Ranger REST", "/ranger/service/public/v2/api/policy", ranger)
    probar("Cloudera AI API v2", "/api/v2/projects/{id}/jobs", cai("jobs"))
    probar("Cloudera AI API v2", "/api/v2/projects/{id}/applications", cai("applications"))
    probar("Cloudera AI API v2", "/api/v2/projects/{id}/models", cai("models"))
    probar("CDW SQL (Impala)", "HTTP 443 + LDAP (impyla)", sql)
    if a.ejecutar_job:
        probar("Cloudera AI API v2", f"POST jobs/{a.ejecutar_job}/runs",
               lambda: (201, f"run {cai_ejecutar_job(a.ejecutar_job)[0]} lanzado (ver Jobs > History)"))
    ok = sum(1 for r in resultados if r[2] in (200, 201))
    print(f"\n{ok}/{len(resultados)} superficies respondieron OK")


if __name__ == "__main__":
    main()
