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
estado_app = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "revision": "", "error": ""}


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
            ultimas[:] = sql(f"SELECT id, ambiente, version, coalesce(autor,''), estado, coalesce(run_id,''), "
                             f"coalesce(mensaje,''), cast(solicitado AS STRING), cast(actualizado AS STRING) "
                             f"FROM {TABLA} ORDER BY solicitado DESC LIMIT 20", devolver=True)
            estado_app["revision"] = time.strftime("%Y-%m-%d %H:%M:%S")
            estado_app["error"] = ""
        except Exception as e:
            traceback.print_exc()
            estado_app["error"] = str(e)[:300]
        time.sleep(INTERVALO)


ESTILO = """
:root{--fondo:#f5f6f8;--tarjeta:#fff;--texto:#1f2328;--suave:#59636e;--borde:#d1d9e0;--verde:#1f883d;--rojo:#cf222e;
--ambar:#9a6700;--azul:#0969da;--gris:#6e7781}
@media (prefers-color-scheme:dark){:root{--fondo:#0d1117;--tarjeta:#151b23;--texto:#e6edf3;--suave:#9198a1;--borde:#3d444d;
--verde:#2ea043;--rojo:#f85149;--ambar:#d29922;--azul:#4493f8;--gris:#9198a1}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--texto);
font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{background:var(--tarjeta);border-bottom:1px solid var(--borde);padding:16px 24px}
header h1{margin:0;font-size:20px}header p{margin:2px 0 0;color:var(--suave)}
main{max-width:1100px;margin:0 auto;padding:20px 16px 40px}
.tarjeta{background:var(--tarjeta);border:1px solid var(--borde);border-radius:8px;margin-bottom:18px}
.tarjeta h2{margin:0;padding:12px 16px;font-size:15px;border-bottom:1px solid var(--borde)}
.cuerpo{padding:14px 16px}
.fila{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
label{display:flex;flex-direction:column;font-size:12px;color:var(--suave);gap:4px;flex:1;min-width:160px}
input{font:inherit;padding:6px 8px;border:1px solid var(--borde);border-radius:6px;background:var(--fondo);color:var(--texto)}
input.dias{width:64px}
button{font:inherit;font-weight:600;padding:6px 14px;border-radius:6px;border:1px solid var(--borde);cursor:pointer;
background:var(--tarjeta);color:var(--texto)}
.b-verde{background:var(--verde);border-color:var(--verde);color:#fff}
.b-rojo{color:var(--rojo)}.b-azul{background:var(--azul);border-color:var(--azul);color:#fff}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 10px;border-top:1px solid var(--borde);
vertical-align:middle}th{font-size:12px;color:var(--suave);font-weight:600;border-top:none}
.pend{border-left:4px solid var(--ambar)}
.aviso{padding:10px 14px;border-radius:6px;margin-bottom:16px;border:1px solid}
.ok{border-color:var(--verde);color:var(--verde)}.err{border-color:var(--rojo);color:var(--rojo)}
.est{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid}
.PENDIENTE{color:var(--ambar)}.APROBADA{color:var(--verde)}.RECHAZADA,.REVOCADA{color:var(--gris)}
.vacio{color:var(--suave);padding:6px 0}.pie{color:var(--suave);font-size:12px}
.acciones{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
@media (max-width:700px){.ocultable{display:none}}

.EN_EJECUCION{color:var(--azul)}.EXITOSO{color:var(--verde)}.FALLIDO{color:var(--rojo)}
.resumen{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.kpi{background:var(--tarjeta);border:1px solid var(--borde);border-radius:8px;padding:10px 16px;min-width:130px}
.kpi b{display:block;font-size:22px}.kpi span{font-size:12px;color:var(--suave)}
.amb{display:inline-block;padding:1px 8px;border-radius:6px;font-size:12px;font-weight:600;border:1px solid var(--borde)}
.prod{border-color:var(--rojo);color:var(--rojo)}.msg{color:var(--suave);max-width:320px}
.est,code,td.f{white-space:nowrap}
"""


def e(x):
    return html.escape(str(x))


def pagina():
    filas = list(ultimas)
    conteo = {k: sum(1 for f in filas if f[4] == k) for k in ("PENDIENTE", "EN_EJECUCION", "EXITOSO", "FALLIDO")}
    kpis = "".join(f"<div class='kpi'><b class='{k}'>{n}</b><span>{k.replace('_', ' ').capitalize()}</span></div>"
                   for k, n in conteo.items())

    def fila(f):
        sid, amb, ver, autor, est, run, msg, sol, act = f
        clase_amb = "amb prod" if amb == "prod" else "amb"
        return (f"<tr><td><span class='{clase_amb}'>{e(amb.upper())}</span></td><td><code>{e(ver)}</code></td>"
                f"<td><span class='est {e(est)}'>{e(est.replace('_', ' '))}</span></td><td class='ocultable'>{e(autor)}</td>"
                f"<td class='ocultable'><code>{e(run)}</code></td><td class='msg ocultable'>{e(msg)}</td>"
                f"<td class='ocultable f'>{e(sol[:16])}</td><td class='f'>{e(act[:16])}</td></tr>")

    tabla = ("<table><tr><th>Ambiente</th><th>Version</th><th>Estado</th><th class='ocultable'>Autor</th>"
             "<th class='ocultable'>Run</th><th class='ocultable'>Mensaje</th><th class='ocultable'>Solicitado (UTC)</th>"
             "<th>Actualizado (UTC)</th></tr>" + "".join(map(fila, filas)) + "</table>"
             ) if filas else "<div class='vacio'>Sin solicitudes de despliegue.</div>"
    aviso = f"<div class='aviso err'>Error al leer la cola: {e(estado_app['error'])}</div>" if estado_app["error"] else ""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="10">
<title>Despachador de despliegues</title><style>{ESTILO}</style></head><body>
<header><h1>Despachador de despliegues</h1>
<p>GitHub Actions deja la solicitud en {e(TABLA)}; este servicio la ejecuta en Cloudera AI y devuelve el resultado al pipeline.</p></header>
<main>{aviso}<div class="resumen">{kpis}</div>
<section class="tarjeta"><h2>Cola de despliegues (ultimas 20)</h2><div class="cuerpo">{tabla}</div></section>
<p class="pie">Activo desde {e(estado_app['inicio'])} UTC. Revisa la cola cada {INTERVALO} s; ultima revision
{e(estado_app['revision'] or 'pendiente')} UTC. La pagina se actualiza sola cada 10 s.</p></main></body></html>"""


class Pagina(BaseHTTPRequestHandler):
    def do_GET(self):
        cuerpo = pagina().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=ciclo, daemon=True).start()
    puerto = int(os.environ.get("CDSW_APP_PORT") or os.environ.get("CDSW_READONLY_PORT") or 8100)
    HTTPServer(("127.0.0.1", puerto), Pagina).serve_forever()
