"""
C08-AE-08 (workaround; no existe flujo nativo de solicitud de acceso en el catalogo de Cloudera):
flujo minimo solicitar -> aprobar -> provisionar en Ranger -> validar, con trazabilidad en sb_gov.solicitudes_acceso.
En produccion el mismo patron se implementa con ServiceNow/Power Automate o IDMC Data Marketplace + Ranger REST API.

  python fase3/c08/c08_solicitud_acceso.py solicitar --usuario sb_analista01 --tabla sb_consumption.m_transaccionalidad_mensual --motivo "Informe trimestral"
  python fase3/c08/c08_solicitud_acceso.py listar
  python fase3/c08/c08_solicitud_acceso.py aprobar --id <id_solicitud> --aprobador sb_admin01
"""
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
    ap.add_argument("accion", choices=["solicitar", "listar", "aprobar"])
    ap.add_argument("--usuario")
    ap.add_argument("--tabla")
    ap.add_argument("--motivo", default="")
    ap.add_argument("--id")
    ap.add_argument("--aprobador", default="sb_admin01")
    a = ap.parse_args()

    if a.accion == "solicitar":
        sid = uuid.uuid4().hex[:8]
        ejecutar(f"INSERT INTO sb_gov.solicitudes_acceso VALUES ('{sid}', '{limpio(a.usuario)}', '{limpio(a.tabla)}', "
                 f"'{limpio(a.motivo)}', 'PENDIENTE', NULL, now(), NULL)")
        print(f"Solicitud {sid} registrada (PENDIENTE)")
    elif a.accion == "listar":
        for f in ejecutar("SELECT * FROM sb_gov.solicitudes_acceso ORDER BY fecha_solicitud DESC"):
            print(f)
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
        r = s.post(f"{ranger}/service/public/v2/api/policy", json=politica)
        print("Ranger:", r.status_code, r.text[:150])
        r.raise_for_status()
        ejecutar(f"UPDATE sb_gov.solicitudes_acceso SET estado = 'APROBADA', aprobador = '{limpio(a.aprobador)}', "
                 f"fecha_resolucion = now() WHERE id_solicitud = '{limpio(a.id)}'")
        print(f"Aprobada. {usuario} puede consultar {recurso} en ~30 s (refresco de politicas Ranger).")


if __name__ == "__main__":
    main()
