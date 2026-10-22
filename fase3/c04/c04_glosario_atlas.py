"""
C04-AE-06 / C08-AE-01: glosario institucional en Atlas con la definicion oficial de metricas,
asignado a las columnas de las vistas. Marca como NO OFICIAL la definicion en conflicto.
  python fase3/c04/c04_glosario_atlas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.sbpoc import atlas_guid, cfg, knox  # noqa: E402

TERMINOS = {
    "Indice de Morosidad": ("OFICIAL. Saldo con mas de 90 dias de atraso / saldo total de cartera. "
                            "Propietario: Direccion de Riesgo. Fuente: sb_consumption.m_indice_morosidad_oficial",
                            "sb_consumption.m_indice_morosidad_oficial.indice_morosidad"),
    "Ticket Promedio": ("OFICIAL. Monto total transado / numero de transacciones del mes. "
                        "Propietario: Direccion de Analisis. Fuente: sb_consumption.m_transaccionalidad_mensual",
                        "sb_consumption.m_transaccionalidad_mensual.ticket_promedio"),
    "Indice de Morosidad (30 dias) - NO OFICIAL": (
        "NO OFICIAL. Variante del equipo B con > 30 dias. No usar en reportes regulatorios.",
        "sb_sandbox_depto_b.m_indice_morosidad_equipo_b.indice_morosidad"),
}


def main():
    s, atlas = knox("atlas")
    sufijo = cfg()["datalake"]["atlas_sufijo_cluster"]
    r = s.post(f"{atlas}/glossary", json={"name": "SB_Glosario", "shortDescription": "Glosario institucional PoC SB"})
    if r.status_code in (200, 201):
        gid = r.json()["guid"]
    else:
        gid = next(g["guid"] for g in s.get(f"{atlas}/glossary").json() if g["name"] == "SB_Glosario")
    for nombre, (definicion, columna) in TERMINOS.items():
        r = s.post(f"{atlas}/glossary/term", json={"name": nombre, "shortDescription": definicion[:250],
                                                   "longDescription": definicion, "anchor": {"glossaryGuid": gid}})
        if r.status_code not in (200, 201):
            print(f"Termino {nombre}: {r.status_code} {r.text[:120]}")
            continue
        tguid = r.json()["guid"]
        cguid, _ = atlas_guid(s, atlas, f"{columna}@{sufijo}", "column")
        if not cguid:
            print(f"Columna no encontrada en Atlas: {columna} (esperar sincronizacion y reintentar)")
            continue
        r = s.post(f"{atlas}/glossary/terms/{tguid}/assignedEntities", json=[{"guid": cguid}])
        print(f"{nombre} -> {columna}: {r.status_code}")


if __name__ == "__main__":
    main()
