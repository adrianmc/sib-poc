"""
C05 - Despachador de despliegues DENTRO de Cloudera AI (Application "sib-despachador").

GitHub Actions (runner en la EC2) no puede llamar a la API de Cloudera AI por red; si llega a Impala.
El runner deja una solicitud PENDIENTE en sb_gov.solicitudes_despliegue y este proceso, que corre dentro de CAI:
  1. toma la solicitud (EN_EJECUCION),
  2. apunta el Job sib-pipeline-<ambiente> a la version (--ref) via API v2 de CAI,
  3. registra el despliegue en sb_gov.despliegues,
  4. ejecuta el Job y espera el estado final,
  5. marca la solicitud EXITOSO o FALLIDO (el runner lo lee y pone el check verde o rojo en GitHub).

Crear una vez: Cloudera AI > proyecto sib-poc > Applications > New Application
  Name: sib-despachador | Subdomain: sib-despachador | Script: fase3/c05/despachador_cai.py
  Runtime Python 3.10 | 1 vCPU / 2 GB. Abrir la URL de la Application muestra la cola (util en la demo).
"""
import html
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cai_api, cai_ejecutar_job, cai_job_id, impala  # noqa: E402

TABLA = "sb_gov.solicitudes_despliegue"
DDL = (f"CREATE TABLE IF NOT EXISTS {TABLA} (id STRING, ambiente STRING, version STRING, autor STRING, "
       "estado STRING, run_id STRING, mensaje STRING, solicitado TIMESTAMP, actualizado TIMESTAMP) "
       "STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')")
INTERVALO = 15
ultimas = []          # filas para la pagina de estado


def sql(consulta, devolver=False):
    con = impala("admin")
    try:
        cur = con.cursor()
        cur.execute(consulta)
        return cur.fetchall() if devolver else None
    finally:
        con.close()


def marcar(sid, estado, run_id="", mensaje=""):
    m = str(mensaje).replace("'", "")[:300]
    sql(f"UPDATE {TABLA} SET estado = '{estado}', run_id = '{run_id}', mensaje = '{m}', actualizado = now() "
        f"WHERE id = '{sid}'")
    print(f"[{time.strftime('%H:%M:%S')}] {sid}: {estado} {run_id} {m}", flush=True)


def atender(sid, ambiente, version, autor):
    job = f"sib-pipeline-{ambiente}"
    marcar(sid, "EN_EJECUCION", mensaje=f"apuntando {job} a {version}")
    s, api, pid = cai_api()
    r = s.patch(f"{api}/projects/{pid}/jobs/{cai_job_id(job)}",
                json={"arguments": f"--ref {version} --ambiente {ambiente}"}, timeout=60)
    r.raise_for_status()
    sql(f"INSERT INTO sb_gov.despliegues VALUES ('sib-pipeline', '{ambiente}', '{version}', "
        f"'despliegues/{ambiente}', '{autor}', now())")
    run_id, estado = cai_ejecutar_job(job, esperar=True)
    if estado == "ENGINE_SUCCEEDED":
        marcar(sid, "EXITOSO", run_id, f"{job} en version {version}")
    else:
        marcar(sid, "FALLIDO", run_id, f"{job} termino en {estado}; ver el log del run en Jobs")


def ciclo():
    sql(DDL)
    print(f"Despachador activo: revisa {TABLA} cada {INTERVALO} s", flush=True)
    while True:
        try:
            pendientes = sql(f"SELECT id, ambiente, version, autor FROM {TABLA} WHERE estado = 'PENDIENTE' "
                             "ORDER BY solicitado", devolver=True)
            for sid, ambiente, version, autor in pendientes:
                try:
                    atender(sid, ambiente, version, autor)
                except Exception as e:      # una solicitud fallida no detiene el despachador
                    traceback.print_exc()
                    marcar(sid, "FALLIDO", mensaje=f"error del despachador: {e}")
            ultimas[:] = sql(f"SELECT id, estado, coalesce(run_id,''), coalesce(mensaje,''), "
                             f"cast(actualizado AS STRING) FROM {TABLA} ORDER BY solicitado DESC LIMIT 15",
                             devolver=True)
        except Exception:
            traceback.print_exc()
        time.sleep(INTERVALO)


class Pagina(BaseHTTPRequestHandler):
    def do_GET(self):
        filas = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in f) + "</tr>" for f in ultimas)
        cuerpo = ("<html><head><meta http-equiv='refresh' content='10'><title>sib-despachador</title></head><body>"
                  "<h3>Cola de despliegues (sb_gov.solicitudes_despliegue)</h3><table border=1 cellpadding=4>"
                  "<tr><th>id</th><th>estado</th><th>run</th><th>mensaje</th><th>actualizado</th></tr>"
                  f"{filas}</table></body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=ciclo, daemon=True).start()
    puerto = int(os.environ.get("CDSW_APP_PORT") or os.environ.get("CDSW_READONLY_PORT") or 8100)
    HTTPServer(("127.0.0.1", puerto), Pagina).serve_forever()
