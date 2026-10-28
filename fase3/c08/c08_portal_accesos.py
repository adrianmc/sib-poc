"""
C08-AE-08: Portal de solicitudes de acceso a datos (Application de Cloudera AI).
Interfaz grafica sobre la misma logica de fase3/c08/c08_solicitud_acceso.py (la Terminal queda como plan B):
  solicitar -> bandeja de pendientes (Aprobar con vigencia en dias / Rechazar) -> politica en Ranger -> historial -> Revocar.
Trazabilidad: sb_gov.solicitudes_acceso (estado, aprobador, fechas) y Ranger > Audit > Admin (alta y baja de la politica).

Crear una vez: Cloudera AI > proyecto sib-poc > Applications > New Application
  Name: sib-accesos | Subdomain: sib-accesos | Script: fase3/c08/c08_portal_accesos.py
  Runtime Python 3.10 | 1 vCPU / 2 GB. Sin dependencias adicionales (solo biblioteca estandar + lib/sbpoc).

Honestidad: el portal ejecuta las acciones con el usuario admin del config. El aprobador que se registra es el usuario
que Cloudera AI identifica en la sesion web si lo entrega en los encabezados; si no, el admin del config (se indica
en pantalla). En produccion: SSO del IdP + segregacion solicitante/aprobador (ServiceNow, Power Automate o IDMC).
"""
import html
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, "/home/cdsw")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/home/cdsw/fase3/c08")
import c08_solicitud_acceso as sa  # noqa: E402
from lib.sbpoc import cfg  # noqa: E402

CAPAS = ["sb_raw", "sb_curated", "sb_consumption"]
ENCABEZADOS_USUARIO = ["Remote-User", "X-Remote-User", "X-Forwarded-User", "X-Auth-Request-User", "X-Cdsw-User"]
TABLAS = []


def cargar_tablas():
    for db in CAPAS:
        try:
            TABLAS.extend(f"{db}.{f[0]}" for f in sa.ejecutar(f"SHOW TABLES IN {db}"))
        except Exception:
            traceback.print_exc()


def aprobador(headers):
    for h in ENCABEZADOS_USUARIO:
        if headers.get(h):
            return headers[h].strip(), f"sesion de Cloudera AI ({h})"
    return cfg()["usuarios"]["admin"]["user"], "usuario admin del config (Cloudera AI no entrego la identidad de la sesion)"


def e(x):
    return html.escape(str(x))


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
"""


def pagina(headers, mensaje="", tipo="ok"):
    quien, origen = aprobador(headers)
    try:
        filas = sa.listar(100)
        error_lista = ""
    except Exception as ex:
        filas, error_lista = [], f"No se pudo leer {sa.TABLA}: {ex}"
    pendientes = [f for f in filas if f[4] == "PENDIENTE"]
    opciones = "".join(f"<option value='{e(t)}'>" for t in TABLAS)

    def fila_pend(f):
        sid, usuario, recurso, motivo, _, _, fsol, _ = f
        return (f"<tr><td><b>{e(usuario)}</b></td><td><code>{e(recurso)}</code></td><td class='ocultable'>{e(motivo)}</td>"
                f"<td class='ocultable'>{e(fsol[:19])}</td><td><div class='acciones'>"
                f"<form method='post' action='/aprobar' class='acciones'><input type='hidden' name='id' value='{e(sid)}'>"
                f"<input class='dias' type='number' name='dias' min='0' value='7' title='Vigencia en dias (0 = sin vencimiento)'>"
                f"<span class='pie'>dias</span><button class='b-verde'>Aprobar</button></form>"
                f"<form method='post' action='/rechazar'><input type='hidden' name='id' value='{e(sid)}'>"
                f"<button class='b-rojo'>Rechazar</button></form></div></td></tr>")

    def fila_hist(f):
        sid, usuario, recurso, motivo, estado, apr, fsol, fres = f
        revocar = (f"<form method='post' action='/revocar'><input type='hidden' name='id' value='{e(sid)}'>"
                   f"<button class='b-rojo'>Revocar</button></form>") if estado == "APROBADA" else ""
        return (f"<tr><td><code>{e(sid)}</code></td><td>{e(usuario)}</td><td><code>{e(recurso)}</code></td>"
                f"<td><span class='est {e(estado)}'>{e(estado)}</span></td><td class='ocultable'>{e(apr)}</td>"
                f"<td class='ocultable'>{e(fsol[:19])}</td><td class='ocultable'>{e(fres[:19])}</td><td>{revocar}</td></tr>")

    aviso = f"<div class='aviso {tipo}'>{e(mensaje)}</div>" if mensaje else ""
    if error_lista:
        aviso += f"<div class='aviso err'>{e(error_lista)}</div>"
    tabla_pend = ("<table><tr><th>Solicitante</th><th>Recurso</th><th class='ocultable'>Motivo</th>"
                  "<th class='ocultable'>Solicitada</th><th>Decision</th></tr>" + "".join(map(fila_pend, pendientes)) +
                  "</table>") if pendientes else "<div class='vacio'>No hay solicitudes pendientes.</div>"
    tabla_hist = ("<table><tr><th>Id</th><th>Usuario</th><th>Recurso</th><th>Estado</th><th class='ocultable'>Aprobador</th>"
                  "<th class='ocultable'>Solicitada</th><th class='ocultable'>Resuelta</th><th></th></tr>" +
                  "".join(map(fila_hist, filas)) + "</table>") if filas else "<div class='vacio'>Sin solicitudes.</div>"
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Solicitudes de acceso</title>
<style>{ESTILO}</style></head><body>
<header><h1>Solicitudes de acceso a datos</h1>
<p>Solicitud, aprobacion y revocacion gobernadas con Apache Ranger. Registro en {e(sa.TABLA)}.</p></header><main>
{aviso}
<section class="tarjeta"><h2>Nueva solicitud</h2><div class="cuerpo">
<form method="post" action="/solicitar" class="fila">
<label>Usuario<input name="usuario" required placeholder="user005"></label>
<label>Tabla (base.tabla)<input name="tabla" list="tablas" required placeholder="sb_raw.entidades_financieras"></label>
<datalist id="tablas">{opciones}</datalist>
<label>Motivo<input name="motivo" required placeholder="Conciliacion de maestra"></label>
<button class="b-azul">Enviar solicitud</button></form></div></section>
<section class="tarjeta pend"><h2>Pendientes de aprobacion ({len(pendientes)})</h2><div class="cuerpo">{tabla_pend}</div></section>
<section class="tarjeta"><h2>Historial</h2><div class="cuerpo">{tabla_hist}</div></section>
<p class="pie">Aprobador registrado: <b>{e(quien)}</b> ({e(origen)}). Las politicas se llaman sb_solicitud_&lt;id&gt; en el
servicio {e(cfg()["datalake"]["ranger_hive_service"])} y tardan ~30 s en aplicarse.</p>
</main></body></html>"""


class Portal(BaseHTTPRequestHandler):
    def responder(self, cuerpo, codigo=200):
        datos = cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        self.responder(pagina(self.headers, q.get("m", [""])[0], q.get("t", ["ok"])[0]))

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        f = {k: v[0] for k, v in parse_qs(self.rfile.read(largo).decode()).items()}
        quien, _ = aprobador(self.headers)
        accion = urlparse(self.path).path.strip("/")
        try:
            if accion == "solicitar":
                sid = sa.solicitar(f.get("usuario"), f.get("tabla"), f.get("motivo"))
                msg = f"Solicitud {sid} registrada: {f.get('usuario')} pide {f.get('tabla')} (PENDIENTE)."
            elif accion == "aprobar":
                dias = int(f.get("dias") or 0)
                usuario, recurso = sa.aprobar(f["id"], quien, dias)
                vence = f", vence en {dias} dias" if dias else ", sin vencimiento"
                msg = f"Aprobada por {quien}{vence}. Politica {sa.nombre_politica(f['id'])} creada en Ranger: {usuario} lee {recurso} en ~30 s."
            elif accion == "rechazar":
                sa.rechazar(f["id"], quien)
                msg = f"Solicitud {f['id']} rechazada por {quien}."
            elif accion == "revocar":
                sa.revocar(f["id"], quien)
                msg = f"Acceso de la solicitud {f['id']} revocado por {quien}: politica eliminada, se retira en ~30 s."
            else:
                raise ValueError("accion desconocida")
            tipo = "ok"
        except Exception as ex:
            traceback.print_exc()
            msg, tipo = f"Error en {accion}: {ex}", "err"
        print(f"[{accion}] {msg}", flush=True)
        self.send_response(303)
        self.send_header("Location", f"/?m={quote(msg)}&t={tipo}")
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    cargar_tablas()
    puerto = int(os.environ.get("CDSW_APP_PORT") or os.environ.get("CDSW_READONLY_PORT") or 8100)
    print(f"Portal de accesos en el puerto {puerto} ({len(TABLAS)} tablas en la lista)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", puerto), Portal).serve_forever()
