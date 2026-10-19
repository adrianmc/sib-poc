-- C01-AE-07: metadatos tecnicos del lakehouse. Hue -> Impala, sb_admin01.
DESCRIBE FORMATTED sb_curated.transacciones;   -- ubicacion, formato, propiedades Iceberg (seccion Table Parameters)
DESCRIBE HISTORY sb_curated.transacciones;     -- snapshots, operacion, fecha
SHOW PARTITIONS sb_curated.transacciones;      -- particiones y conteos
SHOW FILES IN sb_curated.transacciones;        -- archivos fisicos en S3, tamanos
SHOW CREATE TABLE sb_curated.transacciones;
COMPUTE STATS sb_curated.transacciones;
SHOW COLUMN STATS sb_curated.transacciones;
-- Si la version de Impala soporta tablas de metadata Iceberg:
-- SELECT * FROM sb_curated.transacciones.snapshots;
-- SELECT file_path, record_count, file_size_in_bytes FROM sb_curated.transacciones.files LIMIT 20;
-- Complemento visual: Atlas (tipo hive_table, pestanas Properties, Schema, Lineage) y Hue Table Browser.
