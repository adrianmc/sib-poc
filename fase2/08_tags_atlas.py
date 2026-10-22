"""
FASE 2 - Paso 08: crea clasificaciones (tags) en Atlas y las asigna a columnas.
Estas tags alimentan las politicas tag-based de Ranger (ABAC por atributo del dato).
Ejecutar DESPUES de 07_ddl_lakehouse.sql (Atlas debe tener las tablas; esperar ~2-5 min).

  python fase2/08_tags_atlas.py
"""
import sys
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import atlas_guid, cfg, knox  # noqa: E402

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
            guid, tipo = atlas_guid(s, atlas, qn, "column")
            if not guid:
                print(f"{qn} <- {tag}: NO ENCONTRADA en Atlas (ni iceberg_column ni hive_column)")
                continue
            r = s.post(f"{atlas}/entity/guid/{guid}/classifications", json=[{"typeName": tag, "propagate": True}])
            if r.status_code in (200, 204):
                estado = "OK"
            elif "already" in r.text.lower() or r.status_code == 409:
                estado = "OK (ya tenia el tag)"
            else:
                estado = f"{r.status_code} {r.text[:120]}"
            print(f"{qn} [{tipo}] <- {tag}: {estado}")
    print("Ranger TagSync aplica las tags a las politicas en unos minutos.")


if __name__ == "__main__":
    main()
