-- =====================================================================
-- FASE 2 - Paso 07b: poblar las capas SIN CDE, solo con SQL en CDW (Impala).
-- Herramienta: Hue -> editor Impala (VW impala-depto-a), usuario admin. Ejecutar DESPUES de 07_ddl_lakehouse.sql.
-- Reemplazar CAMBIAR_BUCKET. Ejecutar bloque por bloque (cada bloque termina con su validacion).
--
-- Que resuelve:
--   1. Volumen masivo (PG-06): genera ~25M transacciones en Parquet con Impala (reemplaza el job Spark 02).
--   2. Capa curada: clientes, cuentas y creditos desde los CSV de RDS en S3; transacciones desde los 4 formatos.
--   3. Capa consumible: los mismos 4 pasos del pipeline (limpieza, deduplicacion, enriquecimiento,
--      conciliacion FULL OUTER + agregacion con ranking) expresados en SQL.
-- Ventaja: Atlas captura el linaje de Impala automaticamente (C08-AE-02).
-- Cuando CDE este disponible, c02_pipeline_batch.py reescribe estas mismas tablas (es idempotente).
--
-- Prerrequisito en S3 (cada CSV de RDS en su propia carpeta):
--   s3a://CAMBIAR_BUCKET/sb/landing/rds/clientes/clientes.csv
--   s3a://CAMBIAR_BUCKET/sb/landing/rds/cuentas/cuentas.csv
--   s3a://CAMBIAR_BUCKET/sb/landing/rds/creditos/creditos.csv
-- =====================================================================

-- ---------------------------------------------------------------------
-- BLOQUE 1. Tablas crudas sobre los CSV exportados de RDS
-- ---------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.clientes_rds (
  id_cliente BIGINT, identificacion STRING, nombre STRING, email STRING, telefono STRING,
  fecha_nacimiento STRING, region STRING, segmento STRING, ingreso_mensual DOUBLE,
  fecha_alta STRING, fecha_actualizacion STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/rds/clientes/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.cuentas_rds (
  id_cuenta BIGINT, id_cliente BIGINT, tipo_cuenta STRING, moneda STRING, saldo DOUBLE,
  estado STRING, fecha_apertura STRING, id_entidad INT)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/rds/cuentas/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.creditos_rds (
  id_credito BIGINT, identificacion_cliente STRING, id_producto INT, monto_original DOUBLE,
  saldo_pendiente DOUBLE, tasa_interes DOUBLE, plazo_meses INT, dias_mora INT,
  calificacion_riesgo STRING, fecha_desembolso STRING, default_12m INT)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/rds/creditos/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- Validacion: 1.000.000 / 2.000.000 / 500.000
SELECT 'clientes' t, COUNT(*) FROM sb_raw.clientes_rds UNION ALL
SELECT 'cuentas', COUNT(*) FROM sb_raw.cuentas_rds UNION ALL
SELECT 'creditos', COUNT(*) FROM sb_raw.creditos_rds;

-- ---------------------------------------------------------------------
-- BLOQUE 2. Volumen masivo en Parquet (~25M) generado con Impala
-- 250.000 transacciones base x 100 productos del catalogo = 25.000.000 filas con valores variados.
-- Se escribe en la tabla externa Parquet sb_raw.transacciones_masivo (definida en 07).
-- ---------------------------------------------------------------------
INSERT INTO sb_raw.transacciones_masivo
SELECT
  concat('TXM', lpad(cast(p.id_producto AS STRING), 3, '0'), '_', t.id_transaccion)            AS id_transaccion,
  pmod(fnv_hash(concat(t.id_transaccion, cast(p.id_producto AS STRING))), 2000000) + 1         AS id_cuenta,
  from_unixtime(unix_timestamp('2026-01-01 00:00:00')
                + pmod(fnv_hash(concat(cast(p.id_producto AS STRING), t.id_transaccion)), 18316800)) AS fecha_hora,
  t.tipo,
  t.canal,
  round(t.monto * (0.5 + pmod(fnv_hash(concat(t.id_transaccion, 'm', cast(p.id_producto AS STRING))), 1000) / 1000.0), 2) AS monto,
  t.moneda,
  pmod(t.id_entidad_destino + p.id_producto, 50) + 1                                            AS id_entidad_destino,
  t.descripcion
FROM sb_raw.transacciones_parquet t
CROSS JOIN sb_curated.catalogo_productos p;

-- Validacion: ~25.000.000 y ids unicos
SELECT COUNT(*) filas, COUNT(DISTINCT id_transaccion) ids FROM sb_raw.transacciones_masivo;

-- ---------------------------------------------------------------------
-- BLOQUE 3. Capa curada: clientes, cuentas, creditos (tipado y limpieza)
-- ---------------------------------------------------------------------
TRUNCATE TABLE sb_curated.clientes;
INSERT INTO sb_curated.clientes
SELECT id_cliente, identificacion, nombre, email, telefono,
       CAST(fecha_nacimiento AS DATE), upper(trim(region)), upper(trim(segmento)),
       CAST(ingreso_mensual AS DECIMAL(14,2)), CAST(fecha_alta AS DATE),
       CAST(fecha_actualizacion AS TIMESTAMP), now()
FROM sb_raw.clientes_rds
WHERE id_cliente IS NOT NULL;

TRUNCATE TABLE sb_curated.cuentas;
INSERT INTO sb_curated.cuentas
SELECT id_cuenta, id_cliente, tipo_cuenta, moneda, CAST(saldo AS DECIMAL(16,2)), estado,
       CAST(fecha_apertura AS DATE), id_entidad, now()
FROM sb_raw.cuentas_rds
WHERE id_cuenta IS NOT NULL;

TRUNCATE TABLE sb_curated.creditos;
INSERT INTO sb_curated.creditos
SELECT id_credito, identificacion_cliente, id_producto,
       CAST(monto_original AS DECIMAL(16,2)), CAST(saldo_pendiente AS DECIMAL(16,2)),
       CAST(tasa_interes AS DECIMAL(6,2)), plazo_meses, dias_mora, calificacion_riesgo,
       CAST(fecha_desembolso AS DATE), default_12m, now()
FROM sb_raw.creditos_rds
WHERE id_credito IS NOT NULL;

-- Validacion: 1.000.000 / 2.000.000 / 500.000
SELECT 'clientes' t, COUNT(*) FROM sb_curated.clientes UNION ALL
SELECT 'cuentas', COUNT(*) FROM sb_curated.cuentas UNION ALL
SELECT 'creditos', COUNT(*) FROM sb_curated.creditos;

-- ---------------------------------------------------------------------
-- BLOQUE 4. Capa curada: transacciones (pasos 1 a 3 del pipeline)
--   Paso 1 limpieza y tipado de 4 fuentes (CSV, Avro, Parquet, Parquet masivo; JSON se procesa en Hive)
--   Paso 2 deduplicacion con ROW_NUMBER
--   Paso 3 enriquecimiento con la maestra de entidades
-- Tarda varios minutos (~26M filas con ventana); depende del tamano del VW.
-- ---------------------------------------------------------------------
TRUNCATE TABLE sb_curated.transacciones;
INSERT INTO sb_curated.transacciones
SELECT d.id_transaccion, d.id_cuenta, d.fecha_hora, d.tipo, d.canal, d.monto, d.moneda,
       d.id_entidad_destino, e.nombre, d.formato_origen, now()
FROM (
  SELECT u.*, ROW_NUMBER() OVER (PARTITION BY u.id_transaccion ORDER BY u.fecha_hora DESC) rn
  FROM (
    SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP) fecha_hora, upper(trim(tipo)) tipo,
           upper(trim(canal)) canal, CAST(monto AS DECIMAL(18,2)) monto, moneda,
           CAST(id_entidad_destino AS INT) id_entidad_destino, 'csv' formato_origen
    FROM sb_raw.transacciones_csv
    UNION ALL
    SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
           CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'avro'
    FROM sb_raw.transacciones_avro
    UNION ALL
    SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
           CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'parquet'
    FROM sb_raw.transacciones_parquet
    UNION ALL
    SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
           CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'parquet'
    FROM sb_raw.transacciones_masivo
  ) u
  WHERE u.monto > 0 AND u.fecha_hora IS NOT NULL AND u.id_cuenta IS NOT NULL
) d
LEFT JOIN sb_curated.entidades_financieras e ON e.id_entidad = d.id_entidad_destino
WHERE d.rn = 1;

-- Validacion: ~26.000.000, sin duplicados, nombre de entidad poblado
SELECT COUNT(*) filas, COUNT(DISTINCT id_transaccion) ids, COUNT(nombre_entidad) con_entidad
FROM sb_curated.transacciones;
SELECT formato_origen, COUNT(*) FROM sb_curated.transacciones GROUP BY formato_origen;

-- ---------------------------------------------------------------------
-- BLOQUE 5. Capa consumible (paso 4 del pipeline)
-- ---------------------------------------------------------------------
-- 4a. Conciliacion clientes vs creditos con FULL OUTER JOIN
TRUNCATE TABLE sb_consumption.conciliacion_cliente_credito;
INSERT INTO sb_consumption.conciliacion_cliente_credito
SELECT coalesce(c.identificacion, cr.identificacion),
       c.id_cliente,
       CAST(coalesce(cr.num_creditos, 0) AS BIGINT),
       CASE WHEN c.id_cliente IS NULL THEN 'CREDITO_SIN_CLIENTE'
            WHEN cr.num_creditos IS NULL THEN 'CLIENTE_SIN_CREDITO'
            ELSE 'OK' END,
       now()
FROM (SELECT identificacion, id_cliente FROM sb_curated.clientes) c
FULL OUTER JOIN (SELECT identificacion_cliente identificacion, COUNT(*) num_creditos
                 FROM sb_curated.creditos GROUP BY identificacion_cliente) cr
  ON c.identificacion = cr.identificacion;

-- 4b. Agregacion mensual por cliente con DISTINCT y ranking por region
TRUNCATE TABLE sb_consumption.resumen_cliente_mensual;
INSERT INTO sb_consumption.resumen_cliente_mensual
SELECT a.id_cliente, a.region, a.segmento, a.mes, a.num_transacciones, a.monto_total, a.canales_distintos,
       CAST(ROW_NUMBER() OVER (PARTITION BY a.region, a.mes ORDER BY a.monto_total DESC) AS INT),
       now()
FROM (
  SELECT cl.id_cliente, cl.region, cl.segmento,
         CAST(trunc(t.fecha_hora, 'MM') AS DATE) mes,
         COUNT(*) num_transacciones,
         CAST(SUM(t.monto) AS DECIMAL(20,2)) monto_total,
         COUNT(DISTINCT t.canal) canales_distintos
  FROM sb_curated.transacciones t
  JOIN sb_curated.cuentas cu ON cu.id_cuenta = t.id_cuenta
  JOIN sb_curated.clientes cl ON cl.id_cliente = cu.id_cliente
  GROUP BY cl.id_cliente, cl.region, cl.segmento, CAST(trunc(t.fecha_hora, 'MM') AS DATE)
) a;

-- Registro de la corrida (misma tabla que usa el pipeline Spark)
INSERT INTO sb_consumption.pipeline_runs
SELECT uuid(), 'sql-poblado-inicial', 'v1', now(), now(), 'EXITOSO', COUNT(*), 'Poblado inicial via Impala (07b)'
FROM sb_consumption.resumen_cliente_mensual;

-- Validacion final
SELECT estado_conciliacion, COUNT(*) FROM sb_consumption.conciliacion_cliente_credito GROUP BY estado_conciliacion;
SELECT region, COUNT(*) filas, SUM(monto_total) monto FROM sb_consumption.resumen_cliente_mensual GROUP BY region;

-- Estadisticas para el optimizador (consultas y pruebas de carga)
COMPUTE STATS sb_curated.clientes;
COMPUTE STATS sb_curated.cuentas;
COMPUTE STATS sb_curated.creditos;
COMPUTE STATS sb_curated.transacciones;
COMPUTE STATS sb_consumption.resumen_cliente_mensual;
