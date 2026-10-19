"""
C01-AE-06 PLAN B (si el ambiente no tiene Iceberg REST Catalog): un motor externo (DuckDB) lee la tabla Iceberg
directamente desde S3, sin exportacion ni conversion. Solo necesita acceso de lectura al bucket.

1. En Hue (Impala): DESCRIBE FORMATTED sb_share.clientes_externo;  -> copiar el valor de 'metadata_location'
   (s3a://.../metadata/xxxxx.metadata.json) y cambiar el prefijo s3a:// por s3://
2. En la laptop (fuera de la plataforma): pip install duckdb
3. python c01_ae06_lectura_externa_duckdb.py --metadata s3://CAMBIAR_BUCKET/.../metadata/xxxxx.metadata.json
Credenciales: perfil AWS local con permiso s3:GetObject/ListBucket sobre el bucket (cadena de credenciales estandar).
Declarar: este camino lee archivos, no pasa por Ranger; por eso se usa la tabla ya enmascarada (sb_share).
"""
import argparse

import duckdb

ap = argparse.ArgumentParser()
ap.add_argument("--metadata", required=True)
ap.add_argument("--region", default="us-east-1")
a = ap.parse_args()

con = duckdb.connect()
for ext in ("httpfs", "iceberg"):
    con.install_extension(ext)
    con.load_extension(ext)
con.execute(f"CREATE SECRET s3 (TYPE s3, PROVIDER credential_chain, REGION '{a.region}')")
print(con.execute(f"SELECT COUNT(*) AS filas FROM iceberg_scan('{a.metadata}')").fetchall())
print(con.execute(f"SELECT region, segmento, COUNT(*) n FROM iceberg_scan('{a.metadata}') "
                  "GROUP BY region, segmento ORDER BY n DESC").fetchdf())
print(con.execute(f"SELECT * FROM iceberg_snapshots('{a.metadata}')").fetchdf())
