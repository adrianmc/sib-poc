"""
C08-PRE-01/02, AE-01, AE-02, AE-06: completa en Atlas lo que no se captura automaticamente:
  - Metadata de negocio (Business Metadata "Gobierno_SB": dominio, propietario de negocio, criticidad) + owner.
  - Tramo de ORIGEN del linaje: tablas Oracle/SQL Server -> proceso CDC/JDBC -> tablas curadas.
  - Tramo de CONSUMO del linaje: tablas/vistas -> refresh -> dashboard Power BI; documentos -> indexacion -> agente RAG.
El tramo intermedio (Spark en CDE, Impala/Hive: curada -> consumible) lo captura Atlas automaticamente.
Honestidad: los tramos de origen y consumo son registro por API (workaround, desarrollo minimo). El linaje
automatico hasta BI y desde las bases origen requiere Octopai o el escaner de IDMC.
  python fase3/c08/c08_registro_activos_y_linaje_bi.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.sbpoc import cfg, knox  # noqa: E402

S, ATLAS = knox("atlas")
SUF = cfg()["datalake"]["atlas_sufijo_cluster"]

TIPOS = {"entityDefs": [
    {"name": "powerbi_dashboard", "superTypes": ["DataSet"], "attributeDefs": [
        {"name": "workspace", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"}]},
    {"name": "ai_agente", "superTypes": ["DataSet"], "attributeDefs": [
        {"name": "modelo_llm", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"}]},
    {"name": "documento_normativo", "superTypes": ["DataSet"], "attributeDefs": []},
    {"name": "powerbi_refresh", "superTypes": ["Process"], "attributeDefs": []},
    {"name": "rag_indexacion", "superTypes": ["Process"], "attributeDefs": []},
    {"name": "tabla_sistema_origen", "superTypes": ["DataSet"], "attributeDefs": [
        {"name": "sistema", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"}]},
    {"name": "proceso_ingesta", "superTypes": ["Process"], "attributeDefs": [
        {"name": "mecanismo", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"}]},
]}
METADATA_NEGOCIO = {"businessMetadataDefs": [{"name": "Gobierno_SB", "description": "Metadata institucional de gobierno",
    "attributeDefs": [{"name": n, "typeName": "string", "isOptional": True, "cardinality": "SINGLE",
                       "options": {"applicableEntityTypes": '["hive_table"]', "maxStrLength": "200"}}
                      for n in ["dominio", "propietario_negocio", "custodio", "criticidad"]]}]}
ACTIVOS_NEGOCIO = {
    "sb_curated.clientes": {"dominio": "Clientes", "propietario_negocio": "Direccion de Supervision",
                            "custodio": "sb_ing01", "criticidad": "ALTA"},
    "sb_curated.creditos": {"dominio": "Riesgo de Credito", "propietario_negocio": "Direccion de Riesgo",
                            "custodio": "sb_ing01", "criticidad": "ALTA"},
    "sb_curated.entidades_financieras": {"dominio": "Datos Maestros", "propietario_negocio": "Direccion de Registro",
                                         "custodio": "sb_ing01", "criticidad": "ALTA"},
}


def guid_tabla(nombre):
    r = S.get(f"{ATLAS}/entity/uniqueAttribute/type/hive_table", params={"attr:qualifiedName": f"{nombre}@{SUF}"})
    r.raise_for_status()
    return r.json()["entity"]["guid"]


def crear(tipo, qn, nombre, extra=None):
    ent = {"typeName": tipo, "attributes": {"qualifiedName": qn, "name": nombre, "owner": "sb_admin01", **(extra or {})}}
    r = S.post(f"{ATLAS}/entity", json={"entity": ent})
    print(f"{tipo} {nombre}: {r.status_code}")
    return r


def main():
    r = S.post(f"{ATLAS}/types/typedefs", json=TIPOS)
    print("Tipos custom:", r.status_code, "(409 = ya existian)" if r.status_code == 409 else "")

    r = S.post(f"{ATLAS}/types/typedefs", json=METADATA_NEGOCIO)
    print("Business Metadata Gobierno_SB:", r.status_code, "(409 = ya existia)" if r.status_code == 409 else "")
    for tabla, attrs in ACTIVOS_NEGOCIO.items():
        g = guid_tabla(tabla)
        S.put(f"{ATLAS}/entity/guid/{g}", params={"name": "owner"}, json=attrs["propietario_negocio"])
        r = S.post(f"{ATLAS}/entity/guid/{g}/businessmetadata", params={"isOverwrite": "true"}, json={"Gobierno_SB": attrs})
        print(f"Metadata de negocio {tabla}: {r.status_code}")

    # Tramo de origen: Oracle (CDC Debezium) y SQL Server (JDBC Spark) hacia la capa curada
    for qn, nombre, sistema, mecanismo, destino in [
            ("oracle://sbcore/SBCORE.CLIENTES", "SBCORE.CLIENTES", "Oracle RDS core", "CDC Debezium + Spark MERGE", "sb_curated.clientes"),
            ("oracle://sbcore/SBCORE.CUENTAS", "SBCORE.CUENTAS", "Oracle RDS core", "CDC Debezium + Spark MERGE", "sb_curated.cuentas"),
            ("sqlserver://sbcreditos/dbo.creditos", "dbo.creditos", "SQL Server RDS creditos", "Spark JDBC (sb-pipeline-batch)", "sb_curated.creditos")]:
        crear("tabla_sistema_origen", qn, nombre, {"sistema": sistema})
        proc = {"typeName": "proceso_ingesta", "attributes": {
            "qualifiedName": f"ingesta://{nombre}", "name": f"Ingesta {nombre}", "mecanismo": mecanismo,
            "inputs": [{"typeName": "tabla_sistema_origen", "uniqueAttributes": {"qualifiedName": qn}}],
            "outputs": [{"guid": guid_tabla(destino)}]}}
        print(f"Linaje origen {nombre} -> {destino}:", S.post(f"{ATLAS}/entity", json={"entity": proc}).status_code)

    crear("powerbi_dashboard", "pbi://sb-poc/Tablero_Cartera_Crediticia", "Tablero Cartera Crediticia",
          {"workspace": "SB PoC", "description": "Reporte Power BI sobre v_cartera_crediticia y morosidad oficial"})
    proc = {"typeName": "powerbi_refresh", "attributes": {
        "qualifiedName": "pbi://sb-poc/refresh/Tablero_Cartera_Crediticia", "name": "Refresh Tablero Cartera",
        "inputs": [{"guid": guid_tabla("sb_curated.transacciones")},
                   {"guid": guid_tabla("sb_consumption.v_cartera_crediticia")},
                   {"guid": guid_tabla("sb_consumption.m_indice_morosidad_oficial")}],
        "outputs": [{"typeName": "powerbi_dashboard",
                     "uniqueAttributes": {"qualifiedName": "pbi://sb-poc/Tablero_Cartera_Crediticia"}}]}}
    print("Linaje vistas -> dashboard:", S.post(f"{ATLAS}/entity", json={"entity": proc}).status_code)

    docs = []
    for d in ["reglamento_gestion_liquidez", "reglamento_riesgo_credito", "norma_conozca_su_cliente",
              "lineamiento_ciberseguridad", "lineamiento_gobierno_datos"]:
        qn = f"s3a://{cfg()['s3']['bucket']}/sb/landing/documentos/{d}.pdf"
        crear("documento_normativo", qn, f"{d}.pdf")
        docs.append({"typeName": "documento_normativo", "uniqueAttributes": {"qualifiedName": qn}})
    crear("ai_agente", "agente://sb-poc/asistente_normativo", "Asistente normativo RAG",
          {"modelo_llm": cfg()["inferencia"]["llm_modelo"], "description": "Aplicacion CML fase3/c06/rag/app.py"})
    proc_rag = {"typeName": "rag_indexacion", "attributes": {
        "qualifiedName": "agente://sb-poc/indexacion", "name": "Indexacion RAG", "inputs": docs,
        "outputs": [{"typeName": "ai_agente", "uniqueAttributes": {"qualifiedName": "agente://sb-poc/asistente_normativo"}}]}}
    print("Linaje documentos -> agente:", S.post(f"{ATLAS}/entity", json={"entity": proc_rag}).status_code)


if __name__ == "__main__":
    main()
