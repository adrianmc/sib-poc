"""
C01-AE-06 y C08-AE-07: lectura de una tabla Iceberg desde un motor EXTERNO a Cloudera, sin exportacion.

Opcion A (recomendada): Cloudera Iceberg REST Catalog (runtime 7.3.2), OAuth via Knox + Ranger.
  1. Data Catalog > Data Sharing (UI nueva en 7.3.2): crear el Data Share con sb_share.clientes_externo y el usuario externo.
     Las topologias de Knox se despliegan solas en 7.3.2; la vigencia del share = vida del token de Knox.
  2. Copiar la URI del REST Catalog y las credenciales OAuth que entrega Data Catalog para ese consumidor.
  3. Ejecutar este script desde un equipo FUERA de CDP (laptop o EC2):  pip install "pyiceberg[pyarrow]"
Opcion B: Amazon Athena (notebook Spark) con spark.sql.catalog.<cat>.type=rest (ver guion).

Nota honesta: el motor externo lee los archivos Parquet directamente; el masking de columnas de Ranger
NO aplica en ese camino. Por eso se comparte una tabla ya enmascarada (sb_share.*, ver C08).
"""
from pyiceberg.catalog import load_catalog

catalogo = load_catalog(
    "cloudera",
    **{
        "type": "rest",
        "uri": "CAMBIAR_URI_REST_CATALOG",          # la que muestra Data Catalog / documentacion del Data Lake
        "credential": "CAMBIAR_CLIENT_ID:CAMBIAR_CLIENT_SECRET",
        "oauth2-server-uri": "CAMBIAR_URI_TOKEN_OAUTH",
        "scope": "CAMBIAR_SCOPE_SI_APLICA",
    },
)
print("Namespaces:", catalogo.list_namespaces())
tabla = catalogo.load_table("sb_share.clientes_externo")
print("Snapshot actual:", tabla.current_snapshot().snapshot_id)
print("Esquema:", tabla.schema())
df = tabla.scan(limit=20).to_pandas()
print(df.head(20))
