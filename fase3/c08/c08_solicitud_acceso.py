"""
C08-AE-08 (workaround; no existe flujo nativo de solicitud de acceso en el catalogo de Cloudera):
flujo minimo solicitar -> aprobar -> provisionar en Ranger -> validar -> revocar, con trazabilidad en
sb_gov.solicitudes_acceso. En produccion el mismo patron se implementa con ServiceNow/Power Automate o
IDMC Data Marketplace + Ranger REST API.

Dos interfaces sobre la misma logica:
  - Terminal (este archivo, plan B).
  - Portal web: fase3/c08/c08_portal_accesos.py (Application de Cloudera AI).

Demo: el analista user005 (rol sb_analista) lee curada y consumible pero NO la capa cruda sb_raw.
  python fase3/c08/c08_solicitud_acceso.py solicitar --usuario user005 --tabla sb_raw.entidades_financieras --motivo "Conciliacion de maestra"
  python fase3/c08/c08_solicitud_acceso.py listar
  python fase3/c08/c08_solicitud_acceso.py aprobar --id <id_solicitud> --dias 7     # acceso temporal (vence solo)
  python fase3/c08/c08_solicitud_acceso.py rechazar --id <id_solicitud>
  python fase3/c08/c08_solicitud_acceso.py revocar --id <id_solicitud>              # retiro inmediato
El aprobador por defecto es el usuario admin del config (user001); cada paso queda en sb_gov.solicitudes_acceso
y los cambios de politica en Ranger > Audit > Admin.
"""
import argparse
import datetime as dt
import sys
import uuid
from pathlib import Path

# En Jobs/Applications de Cloudera AI el script puede correr sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, impala, knox  # noqa: E402

TABLA = "sb_gov.solicitudes_acceso"


def ejecutar(sql, rol="admin"):
    con = impala(rol)
    try:
        cur = con.cursor()
        cur.execute(sql)
        return cur.fetchall() if cur.description else []
    finally:
        con.close()


def limpio(t):
    return str(t or "").replace("'", "").replace("\\", "").strip()[:300]


def nombre_politica(sid):
    return f"sb_solicitud_{limpio(sid)}"


def solicitar(usuario, tabla, motivo=""):
    if not usuario or "." not in (tabla or ""):
        raise ValueError("usuario y tabla (base.tabla) son obligatorios")
    sid = uuid.uuid4().hex[:8]
    ejecutar(f"INSERT INTO {TABLA} VALUES ('{sid}', '{limpio(usuario)}', '{limpio(tabla)}', "
             f"'{limpio(motivo)}', 'PENDIENTE', NULL, now(), NULL)")
    return sid


def listar(limite=50):
    """Filas: id, usuario, recurso, justificacion, estado, aprobador, fecha_solicitud, fecha_resolucion."""
    return ejecutar(f"SELECT id_solicitud, usuario, recurso, justificacion, estado, coalesce(aprobador, ''), "
                    f"cast(fecha_solicitud AS STRING), coalesce(cast(fecha_resolucion AS STRING), '') "
                    f"FROM {TABLA} ORDER BY fecha_solicitud DESC LIMIT {int(limite)}")


def _pendiente(sid):
    fila = ejecutar(f"SELECT usuario, recurso FROM {TABLA} WHERE id_solicitud = '{limpio(sid)}' AND estado = 'PENDIENTE'")
    if not fila:
        raise ValueError(f"Solicitud {sid} no encontrada o ya resuelta")
    return fila[0]


def aprobar(sid, aprobador, dias=0):
    usuario, recurso = _pendiente(sid)
    db, tabla = recurso.split(".", 1)
    s, ranger = knox("ranger")
    politica = {"service": cfg()["datalake"]["ranger_hive_service"], "name": nombre_politica(sid),
                "policyType": 0, "isEnabled": True,
                "description": f"Aprobada por {limpio(aprobador)} (solicitud {limpio(sid)}, C08-AE-08)",
                "resources": {"database": {"values": [db]}, "table": {"values": [tabla]}, "column": {"values": ["*"]}},
                "policyItems": [{"users": [usuario], "accesses": [{"type": "select", "isAllowed": True}]}]}
    if dias:
        # Hora de Costa Rica explicita (UTC-6, sin horario de verano): el contenedor de Cloudera AI corre en UTC y
        # Ranger interpreta las fechas en el timeZone indicado. Leccion 28-oct: con now() del contenedor (UTC) y
        # timeZone America/Costa_Rica la politica nacia 6 h en el futuro y el acceso no se activaba.
        ahora = dt.datetime.now(dt.timezone(dt.timedelta(hours=-6))).replace(tzinfo=None) - dt.timedelta(minutes=5)
        politica["validitySchedules"] = [{"startTime": f"{ahora:%Y/%m/%d %H:%M:%S}",
                                          "endTime": f"{ahora + dt.timedelta(days=int(dias)):%Y/%m/%d %H:%M:%S}",
                                          "timeZone": "America/Costa_Rica"}]
    r = s.post(f"{ranger}/service/public/v2/api/policy", json=politica, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"Ranger {r.status_code}: {r.text[:200]}")
    ejecutar(f"UPDATE {TABLA} SET estado = 'APROBADA', aprobador = '{limpio(aprobador)}', "
             f"fecha_resolucion = now() WHERE id_solicitud = '{limpio(sid)}'")
    return usuario, recurso


def rechazar(sid, aprobador):
    _pendiente(sid)
    ejecutar(f"UPDATE {TABLA} SET estado = 'RECHAZADA', aprobador = '{limpio(aprobador)}', "
             f"fecha_resolucion = now() WHERE id_solicitud = '{limpio(sid)}'")


def revocar(sid, aprobador):
    s, ranger = knox("ranger")
    r = s.delete(f"{ranger}/service/public/v2/api/policy",
                 params={"servicename": cfg()["datalake"]["ranger_hive_service"], "policyname": nombre_politica(sid)},
                 timeout=30)
    if r.status_code >= 300 and r.status_code != 404:
        raise RuntimeError(f"Ranger {r.status_code}: {r.text[:200]}")
    ejecutar(f"UPDATE {TABLA} SET estado = 'REVOCADA', aprobador = '{limpio(aprobador)}', "
             f"fecha_resolucion = now() WHERE id_solicitud = '{limpio(sid)}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["solicitar", "listar", "aprobar", "rechazar", "revocar"])
    ap.add_argument("--usuario")
    ap.add_argument("--tabla")
    ap.add_argument("--motivo", default="")
    ap.add_argument("--id")
    ap.add_argument("--aprobador", default=cfg()["usuarios"]["admin"]["user"])
    ap.add_argument("--dias", type=int, default=0, help="vigencia del acceso en dias (0 = sin vencimiento)")
    a = ap.parse_args()

    if a.accion == "solicitar":
        print(f"Solicitud {solicitar(a.usuario, a.tabla, a.motivo)} registrada (PENDIENTE)")
    elif a.accion == "listar":
        for f in listar():
            print(f)
    elif a.accion == "aprobar":
        usuario, recurso = aprobar(a.id, a.aprobador, a.dias)
        vence = f", vence en {a.dias} dias" if a.dias else ""
        print(f"Ranger: politica {nombre_politica(a.id)} creada. Aprobada{vence}. "
              f"{usuario} puede consultar {recurso} en ~30 s (refresco de politicas Ranger).")
    elif a.accion == "rechazar":
        rechazar(a.id, a.aprobador)
        print(f"Solicitud {a.id} rechazada.")
    else:
        revocar(a.id, a.aprobador)
        print(f"Revocada. Politica {nombre_politica(a.id)} eliminada; el acceso se retira en ~30 s.")


if __name__ == "__main__":
    main()
