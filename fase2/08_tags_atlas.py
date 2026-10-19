"""
FASE 2 - Paso 08: crea clasificaciones (tags) en Atlas y las asigna a columnas.
Estas tags alimentan las politicas tag-based de Ranger (ABAC por atributo del dato).
Ejecutar DESPUES de 07_ddl_lakehouse.sql (Atlas debe tener las tablas; esperar ~2-5 min).

  python fase2/08_tags_atlas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sbpoc import cfg, knox  # noqa: E402

TAGS = {
    "PII": "Dato personal identificable. Se enmascara salvo roles autorizados.",
    "CONFIDENCIAL": "Dato financiero confidencial. Requiere atributo attr_acceso_confidencial.",
    "PUBLICO": "Dato sin restricciones de sensibilidad.",
}
ASIGNACIONES = {
    "sb_curated.clientes": {"identificacion": "PII", "nombre": "PII", "email": "PII", "telefono": "PII",
                            "region": "PUBLICO", "segmento": "PUBLICO"},
    "sb_curated.creditos": {"identificacion_cliente": "PII", "saldo_pendiente": "CONFIDENCIAL",
                            "calificacion_riesgo": "CONFIDENCIAL"},
    "sb_consumption.conciliacion_cliente_credito": {"identificacion": "PII"},
}


def main():
    s, atlas = knox("atlas")
    sufijo = cfg()["datalake"]["atlas_sufijo_cluster"]
    defs = {"classificationDefs": [{"name": n, "description": d, "superTypes": [], "attributeDefs": []}
                                   for n, d in TAGS.items()]}
    r = s.post(f"{atlas}/types/typedefs", json=defs)
    print("Tags:", r.status_code, "(409 = ya existian)" if r.status_code == 409 else "")
    for tabla, cols in ASIGNACIONES.items():
        for col, tag in cols.items():
            qn = f"{tabla}.{col}@{sufijo}"
            r = s.post(f"{atlas}/entity/uniqueAttribute/type/hive_column/classifications",
                       params={"attr:qualifiedName": qn}, json=[{"typeName": tag, "propagate": True}])
            estado = "OK" if r.status_code in (200, 204) else f"{r.status_code} {r.text[:120]}"
            print(f"{qn} <- {tag}: {estado}")
    print("Ranger TagSync aplica las tags a las politicas en unos minutos.")


if __name__ == "__main__":
    main()
