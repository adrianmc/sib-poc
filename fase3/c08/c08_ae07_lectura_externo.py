"""
C08-AE-07 (plan B, sin Data Sharing en el tenant) y C01-AE-06: un ente EXTERNO lee la tabla enmascarada
sb_share.clientes_externo SIN cuenta en la plataforma, sin exportacion y con acceso temporal y revocable.

Como se gobierna:
  - Sin cuenta CDP: el externo solo tiene una credencial IAM de solo lectura (usuario IAM sib-externo).
  - Solo esa tabla: la politica IAM (c08_politica_iam_externo.json) limita s3:GetObject al prefijo de clientes_externo.
  - Enmascarado: la tabla ya viene enmascarada (identificacion en hash, sin nombre/email/telefono, ingreso redondeado);
    este camino lee archivos y no pasa por Ranger, por eso se comparte una copia ya enmascarada.
  - Temporal: la politica IAM vence sola (condicion aws:CurrentTime).
  - Revocable: IAM > usuario sib-externo > Security credentials > Deactivate de la access key -> la lectura falla.
Con el entitlement CDP_DATA_SHARE_ADMIN el camino nativo es Data Catalog > Data Sharing (REST Catalog de Iceberg).

Laptop del externo (fuera de la plataforma):
  pip install "pyiceberg[pyarrow]"
  aws configure --profile sib-externo         (access key del usuario IAM sib-externo, region us-east-2)
  AWS_PROFILE=sib-externo python c08_ae07_lectura_externo.py --metadata s3://<bucket>/.../metadata/<n>.metadata.json
El metadata se obtiene en Hue: DESCRIBE FORMATTED sb_share.clientes_externo -> metadata_location (s3a:// -> s3://).
"""
import argparse

from pyiceberg.table import StaticTable

ap = argparse.ArgumentParser()
ap.add_argument("--metadata", required=True, help="s3://.../metadata/xxxxx.metadata.json")
ap.add_argument("--region", default="us-east-2")
a = ap.parse_args()

tabla = StaticTable.from_metadata(a.metadata.replace("s3a://", "s3://"), properties={"s3.region": a.region})
print("Snapshot:", tabla.current_snapshot().snapshot_id)
print("Columnas:", [c.name for c in tabla.schema().fields])
df = tabla.scan().to_pandas()
print(f"Filas leidas: {len(df):,}")
print(df.groupby(["region", "segmento"]).size().sort_values(ascending=False).head(8).to_string())
print(df.head(5).to_string(index=False))
