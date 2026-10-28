"""
C08-AE-08 (workaround; no existe flujo nativo de solicitud de acceso en el catalogo de Cloudera):
flujo minimo solicitar -> aprobar -> provisionar en Ranger -> validar, con trazabilidad en sb_gov.solicitudes_acceso.
En produccion el mismo patron se implementa con ServiceNow/Power Automate o IDMC Data Marketplace + Ranger REST API.

Demo: el analista user005 (rol sb_analista) lee curada y consumible pero NO la capa cruda sb_raw.
  python fase3/c08/c08_solicitud_acceso.py solicitar --usuario user005 --tabla sb_raw.entidades_financieras --motivo "Conciliacion de maestra"
  python fase3/c08/c08_solicitud_acceso.py listar
  python fase3/c08/c08_solicitud_acceso.py aprobar --id <id_solicitud> --dias 7     # acceso temporal (vence solo)
  python fase3/c08/c08_solicitud_acceso.py revocar --id <id_solicitud>              # retiro inmediato
El aprobador por defecto es el usuario admin del config (user001); cada paso queda en sb_gov.solicitudes_acceso
y los cambios de politica en Ranger > Audit > Admin.
"""
import datetime as dt
import argparse
import sys
import uuid
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, impala, knox  # noqa: E402


def ejecutar(sql, rol="admin"):
    con = impala(rol)
    cur = con.cursor()
    cur.execute(sql)
    filas = cur.fetchall() if cur.description else []
    con.close()
    return filas


def limpio(t):
    return str(t).replace("'", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["solicitar", "listar", "aprobar", "revocar"])
    ap.add_argument("--usuario")
    ap.add_argument("--tabla")
    ap.add_argument("--motivo", default="")
    ap.add_argument("--id")
    ap.add_argument("--aprobador", default=cfg()["usuarios"]["admin"]["user"])
    ap.add_argument("--dias", type=int, default=0, help="vigencia del acceso en dias (0 = sin vencimiento)")
    a = ap.parse_args()

    if a.accion == "solicitar":
        sid = uuid.uuid4().hex[:8]
        ejecutar(f"INSERT INTO sb_gov.solicitudes_acceso VALUES ('{sid}', '{limpio(a.usuario)}', '{limpio(a.tabla)}', "
                 f"'{limpio(a.motivo)}', 'PENDIENTE', NULL, now(), NULL)")
        print(f"Solicitud {sid} registrada (PENDIENTE)")
    elif a.accion == "listar":
        for f in ejecutar("SELECT * FROM sb_gov.solicitudes_acceso ORDER BY fecha_solicitud DESC"):
            print(f)
    elif a.accion == "revocar":
        s, ranger = knox("ranger")
        r = s.delete(f"{ranger}/service/public/v2/api/policy",
                     params={"servicename": cfg()["datalake"]["ranger_hive_service"], "policyname": f"sb_solicitud_{a.id}"})
        print("Ranger:", r.status_code, r.text[:150])
        r.raise_for_status()
        ejecutar(f"UPDATE sb_gov.solicitudes_acceso SET estado = 'REVOCADA', fecha_resolucion = now() "
                 f"WHERE id_solicitud = '{limpio(a.id)}'")
        print(f"Revocada. El acceso se retira en ~30 s (refresco de politicas Ranger).")
    else:
        fila = ejecutar(f"SELECT usuario, recurso FROM sb_gov.solicitudes_acceso WHERE id_solicitud = '{limpio(a.id)}' "
                        f"AND estado = 'PENDIENTE'")
        if not fila:
            sys.exit("Solicitud no encontrada o ya resuelta")
        usuario, recurso = fila[0]
        db, tabla = recurso.split(".")
        s, ranger = knox("ranger")
        politica = {"service": cfg()["datalake"]["ranger_hive_service"], "name": f"sb_solicitud_{a.id}",
                    "policyType": 0, "isEnabled": True, "description": f"Aprobada por {a.aprobador} (solicitud {a.id})",
                    "resources": {"database": {"values": [db]}, "table": {"values": [tabla]}, "column": {"values": ["*"]}},
                    "policyItems": [{"users": [usuario], "accesses": [{"type": "select", "isAllowed": True}]}]}
        if a.dias:
            ahora = dt.datetime.now()
            politica["validitySchedules"] = [{"startTime": f"{ahora:%Y/%m/%d %H:%M:%S}",
                                              "endTime": f"{ahora + dt.timedelta(days=a.dias):%Y/%m/%d %H:%M:%S}",
                                              "timeZone": "America/Costa_Rica"}]
        r = s.post(f"{ranger}/service/public/v2/api/policy", json=politica)
        print("Ranger:", r.status_code, r.text[:150])
        r.raise_for_status()
        ejecutar(f"UPDATE sb_gov.solicitudes_acceso SET estado = 'APROBADA', aprobador = '{limpio(a.aprobador)}', "
                 f"fecha_resolucion = now() WHERE id_solicitud = '{limpio(a.id)}'")
        vence = f", vence en {a.dias} dias" if a.dias else ""
        print(f"Aprobada{vence}. {usuario} puede consultar {recurso} en ~30 s (refresco de politicas Ranger).")


if __name__ == "__main__":
    main()
