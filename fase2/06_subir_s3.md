# Fase 2 - Paso 06: subir archivos a S3 (landing)

Herramienta: **Terminal** (AWS CLI) en el equipo donde se corrió el generador.
Si el generador se corrió en una sesión de Cloudera AI, subir con el cliente Hadoop de la sesión (credenciales via IDBroker),
reemplazando `aws s3 cp <origen> s3://...` por `hdfs dfs -put -f <origen> s3a://...`.
Reemplaza `CAMBIAR_BUCKET` por el nombre real del bucket (buscar y reemplazar en VS Code).

```
aws s3 cp salida/rds/ s3://CAMBIAR_BUCKET/sb/landing/rds/ --recursive
aws s3 cp salida/landing/transacciones/csv/ s3://CAMBIAR_BUCKET/sb/landing/transacciones/csv/ --recursive
aws s3 cp salida/landing/transacciones/json/ s3://CAMBIAR_BUCKET/sb/landing/transacciones/json/ --recursive
aws s3 cp salida/landing/transacciones/avro/ s3://CAMBIAR_BUCKET/sb/landing/transacciones/avro/ --recursive
aws s3 cp salida/landing/transacciones/parquet/ s3://CAMBIAR_BUCKET/sb/landing/transacciones/parquet/ --recursive
aws s3 cp salida/landing/maestras/entidades_financieras.csv s3://CAMBIAR_BUCKET/sb/landing/maestras/entidades/entidades_financieras.csv
aws s3 cp salida/landing/maestras/catalogo_productos.csv s3://CAMBIAR_BUCKET/sb/landing/maestras/productos/catalogo_productos.csv
aws s3 cp salida/landing/maestras/catalogo_productos.xlsx s3://CAMBIAR_BUCKET/sb/landing/maestras/excel/catalogo_productos.xlsx
aws s3 cp salida/landing/documentos/ s3://CAMBIAR_BUCKET/sb/landing/documentos/ --recursive
```

Nota para la demo C01-AE-01: la conversión Excel a tabla se muestra en vivo con un flujo NiFi
(ListS3 -> FetchS3Object -> ConvertExcelToCSVProcessor -> PutS3Object en `sb/landing/maestras/productos/`).
El `.csv` que se sube aquí es el respaldo por si el flujo no está listo.

Luego ejecutar en CDE los jobs `05b_cargar_rds_spark.py` (carga RDS) y `02_transacciones_masivas_spark.py` (volumen 20-50M).
