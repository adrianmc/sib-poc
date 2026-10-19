-- =====================================================================
-- FASE 2 - Paso 07: Lakehouse de la PoC (capas cruda, curada, consumible)
-- Herramienta: Hue -> editor Impala (VW impala-depto-a), usuario sb_admin01.
-- Reemplazar CAMBIAR_BUCKET (buscar y reemplazar en VS Code).
-- Notas Impala: comentarios de columna se declaran en el CREATE (COMMENT ON COLUMN
-- no aplica en Iceberg de CDW); particionamiento Iceberg en Impala usa DAY().
-- =====================================================================

CREATE DATABASE IF NOT EXISTS sb_raw         COMMENT 'Capa cruda: datos tal como llegan del origen';
CREATE DATABASE IF NOT EXISTS sb_curated     COMMENT 'Capa curada: Iceberg V2, limpia, deduplicada y gobernada';
CREATE DATABASE IF NOT EXISTS sb_consumption COMMENT 'Capa consumible: modelos para BI, metricas oficiales';
CREATE DATABASE IF NOT EXISTS sb_sandbox_depto_a COMMENT 'Sandbox de desarrollo Departamento A';
CREATE DATABASE IF NOT EXISTS sb_sandbox_depto_b COMMENT 'Sandbox de desarrollo Departamento B';
CREATE DATABASE IF NOT EXISTS sb_gov         COMMENT 'Tablas operativas de gobierno (solicitudes, despliegues)';
CREATE DATABASE IF NOT EXISTS sb_share       COMMENT 'Datos enmascarados para compartir con entes externos';

-- ---------------------------------------------------------------------
-- CAPA CRUDA: tablas externas sobre archivos originales, sin conversion
-- ---------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.transacciones_csv (
  id_transaccion STRING, id_cuenta BIGINT, fecha_hora STRING, tipo STRING, canal STRING,
  monto DOUBLE, moneda STRING, id_entidad_destino BIGINT, descripcion STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/transacciones/csv/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.transacciones_avro (
  id_transaccion STRING, id_cuenta BIGINT, fecha_hora STRING, tipo STRING, canal STRING,
  monto DOUBLE, moneda STRING, id_entidad_destino BIGINT, descripcion STRING)
STORED AS AVRO
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/transacciones/avro/';

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.transacciones_parquet (
  id_transaccion STRING, id_cuenta BIGINT, fecha_hora STRING, tipo STRING, canal STRING,
  monto DOUBLE, moneda STRING, id_entidad_destino BIGINT, descripcion STRING)
STORED AS PARQUET
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/transacciones/parquet/';

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.transacciones_masivo (
  id_transaccion STRING, id_cuenta BIGINT, fecha_hora STRING, tipo STRING, canal STRING,
  monto DOUBLE, moneda STRING, id_entidad_destino BIGINT, descripcion STRING)
STORED AS PARQUET
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/transacciones/parquet_masivo/';

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.entidades_financieras (
  id_entidad INT, codigo STRING, nombre STRING, tipo STRING, pais STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/maestras/entidades/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.catalogo_productos (
  id_producto INT, nombre_producto STRING, tipo_producto STRING, tasa_referencia DOUBLE, activo STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/maestras/productos/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- JSON: Impala no lee JsonSerDe. Crear ESTA tabla en Hue -> editor HIVE (Hive VW).
-- CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.transacciones_json (
--   id_transaccion STRING, id_cuenta BIGINT, fecha_hora STRING, tipo STRING, canal STRING,
--   monto DOUBLE, moneda STRING, id_entidad_destino BIGINT, descripcion STRING)
-- ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
-- STORED AS TEXTFILE
-- LOCATION 's3a://CAMBIAR_BUCKET/sb/landing/transacciones/json/';

-- ---------------------------------------------------------------------
-- CAPA CURADA: Iceberg V2 (ACID, evolucion de esquema, time travel)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sb_curated.clientes (
  id_cliente          BIGINT        COMMENT 'Identificador interno del cliente',
  identificacion      STRING        COMMENT 'Documento de identidad. Dato personal (PII)',
  nombre              STRING        COMMENT 'Nombre completo. Dato personal (PII)',
  email               STRING        COMMENT 'Correo electronico. Dato personal (PII)',
  telefono            STRING        COMMENT 'Telefono. Dato personal (PII)',
  fecha_nacimiento    DATE          COMMENT 'Fecha de nacimiento',
  region              STRING        COMMENT 'Region geografica del cliente (atributo ABAC)',
  segmento            STRING        COMMENT 'Segmento comercial: PERSONAL, PYME, CORPORATIVO',
  ingreso_mensual     DECIMAL(14,2) COMMENT 'Ingreso mensual declarado',
  fecha_alta          DATE          COMMENT 'Fecha de alta del cliente',
  fecha_actualizacion TIMESTAMP     COMMENT 'Ultima actualizacion en el origen',
  cdc_ts              TIMESTAMP     COMMENT 'Momento del cambio capturado por CDC')
STORED AS ICEBERG
TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_curated.cuentas (
  id_cuenta      BIGINT        COMMENT 'Identificador de la cuenta',
  id_cliente     BIGINT        COMMENT 'Cliente titular',
  tipo_cuenta    STRING        COMMENT 'AHORRO, CORRIENTE, PLAZO',
  moneda         STRING        COMMENT 'LOCAL o USD',
  saldo          DECIMAL(16,2) COMMENT 'Saldo actual',
  estado         STRING        COMMENT 'ACTIVA, INACTIVA, CERRADA',
  fecha_apertura DATE          COMMENT 'Fecha de apertura',
  id_entidad     INT           COMMENT 'Entidad financiera',
  cdc_ts         TIMESTAMP     COMMENT 'Momento del cambio capturado por CDC')
STORED AS ICEBERG
TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_curated.creditos (
  id_credito             BIGINT        COMMENT 'Identificador del credito',
  identificacion_cliente STRING        COMMENT 'Documento del deudor. Dato personal (PII)',
  id_producto            INT           COMMENT 'Producto crediticio',
  monto_original         DECIMAL(16,2) COMMENT 'Monto desembolsado',
  saldo_pendiente        DECIMAL(16,2) COMMENT 'Saldo pendiente. Dato confidencial',
  tasa_interes           DECIMAL(6,2)  COMMENT 'Tasa de interes anual',
  plazo_meses            INT           COMMENT 'Plazo en meses',
  dias_mora              INT           COMMENT 'Dias de atraso',
  calificacion_riesgo    STRING        COMMENT 'Categoria A-E. Dato confidencial',
  fecha_desembolso       DATE          COMMENT 'Fecha de desembolso',
  default_12m            INT           COMMENT 'Incumplimiento en 12 meses (variable objetivo ML)',
  fecha_proceso          TIMESTAMP     COMMENT 'Momento de carga')
STORED AS ICEBERG
TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_curated.transacciones (
  id_transaccion     STRING        COMMENT 'Identificador unico de la transaccion',
  id_cuenta          BIGINT        COMMENT 'Cuenta origen',
  fecha_hora         TIMESTAMP     COMMENT 'Fecha y hora de la transaccion',
  tipo               STRING        COMMENT 'DEPOSITO, RETIRO, TRANSFERENCIA, PAGO',
  canal              STRING        COMMENT 'APP, WEB, ATM, SUCURSAL',
  monto              DECIMAL(18,2) COMMENT 'Monto de la transaccion',
  moneda             STRING        COMMENT 'LOCAL o USD',
  id_entidad_destino INT           COMMENT 'Entidad destino',
  nombre_entidad     STRING        COMMENT 'Nombre de la entidad destino (enriquecido)',
  formato_origen     STRING        COMMENT 'Formato del archivo de origen: csv, json, avro, parquet',
  fecha_proceso      TIMESTAMP     COMMENT 'Momento de procesamiento')
PARTITIONED BY SPEC (DAY(fecha_hora))
STORED AS ICEBERG
TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_curated.transacciones_rt (
  id_transaccion STRING        COMMENT 'Identificador del evento',
  id_cuenta      BIGINT        COMMENT 'Cuenta origen',
  tipo           STRING        COMMENT 'Tipo de transaccion',
  canal          STRING        COMMENT 'Canal',
  monto          DECIMAL(18,2) COMMENT 'Monto',
  evento_ts      TIMESTAMP     COMMENT 'Momento en que se genero el evento',
  ingesta_ts     TIMESTAMP     COMMENT 'Momento en que se escribio en el lakehouse')
PARTITIONED BY SPEC (DAY(evento_ts))
STORED AS ICEBERG
TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_curated.entidades_financieras (
  id_entidad INT COMMENT 'Identificador de la entidad', codigo STRING COMMENT 'Codigo regulatorio',
  nombre STRING COMMENT 'Nombre de la entidad', tipo STRING COMMENT 'Tipo de entidad', pais STRING COMMENT 'Pais')
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

CREATE TABLE IF NOT EXISTS sb_curated.catalogo_productos (
  id_producto INT COMMENT 'Identificador del producto', nombre_producto STRING COMMENT 'Nombre comercial',
  tipo_producto STRING COMMENT 'Tipo de producto', tasa_referencia DECIMAL(6,2) COMMENT 'Tasa de referencia',
  activo STRING COMMENT 'S/N')
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

INSERT OVERWRITE sb_curated.entidades_financieras SELECT * FROM sb_raw.entidades_financieras;
INSERT OVERWRITE sb_curated.catalogo_productos
  SELECT id_producto, nombre_producto, tipo_producto, CAST(tasa_referencia AS DECIMAL(6,2)), activo FROM sb_raw.catalogo_productos;

-- ---------------------------------------------------------------------
-- CAPA CONSUMIBLE (la pueblan los pipelines de C02) + tablas operativas
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sb_consumption.resumen_cliente_mensual (
  id_cliente BIGINT COMMENT 'Cliente', region STRING COMMENT 'Region', segmento STRING COMMENT 'Segmento',
  mes DATE COMMENT 'Primer dia del mes', num_transacciones BIGINT COMMENT 'Cantidad de transacciones',
  monto_total DECIMAL(20,2) COMMENT 'Monto total transado', canales_distintos BIGINT COMMENT 'Canales usados',
  ranking_region INT COMMENT 'Posicion del cliente por monto dentro de su region',
  fecha_proceso TIMESTAMP COMMENT 'Momento de procesamiento')
PARTITIONED BY SPEC (MONTH(mes))
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2', 'write.parquet.compression-codec'='zstd');

CREATE TABLE IF NOT EXISTS sb_consumption.conciliacion_cliente_credito (
  identificacion STRING COMMENT 'Documento (PII)', id_cliente BIGINT COMMENT 'Cliente si existe',
  num_creditos BIGINT COMMENT 'Creditos asociados', estado_conciliacion STRING COMMENT 'OK, CLIENTE_SIN_CREDITO, CREDITO_SIN_CLIENTE',
  fecha_proceso TIMESTAMP COMMENT 'Momento de procesamiento')
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

CREATE TABLE IF NOT EXISTS sb_consumption.pipeline_runs (
  run_id STRING, pipeline STRING, version STRING, inicio TIMESTAMP, fin TIMESTAMP,
  estado STRING, filas_salida BIGINT, mensaje STRING)
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

CREATE TABLE IF NOT EXISTS sb_consumption.metricas_rendimiento (
  prueba STRING, usuarios_concurrentes INT, consultas BIGINT, errores BIGINT, p50_ms DOUBLE, p95_ms DOUBLE,
  registros_por_ms DOUBLE, registros_por_dolar DOUBLE, fecha TIMESTAMP)
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

-- Zona consumible del flujo streaming (C02-AE-02): vista sin copia sobre la tabla Iceberg de tiempo real
CREATE VIEW IF NOT EXISTS sb_consumption.v_transacciones_rt AS
  SELECT id_transaccion, id_cuenta, tipo, canal, monto, evento_ts, ingesta_ts FROM sb_curated.transacciones_rt;

CREATE TABLE IF NOT EXISTS sb_consumption.latencia_streaming (
  id_evento STRING COMMENT 'Evento de medicion', tasa_eventos_seg INT COMMENT 'Carga de fondo durante la medicion',
  enviado_ts TIMESTAMP COMMENT 'Envio a Kafka', disponible_ts TIMESTAMP COMMENT 'Primer momento visible en la zona consumible',
  latencia_s DOUBLE COMMENT 'Latencia extremo a extremo en segundos')
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

CREATE TABLE IF NOT EXISTS sb_gov.despliegues (
  artefacto STRING, ambiente STRING, version STRING, recurso_cde STRING, autor STRING, fecha TIMESTAMP)
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

CREATE TABLE IF NOT EXISTS sb_gov.solicitudes_acceso (
  id_solicitud STRING, usuario STRING, recurso STRING, justificacion STRING, estado STRING,
  aprobador STRING, fecha_solicitud TIMESTAMP, fecha_resolucion TIMESTAMP)
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');

-- Validacion rapida
SELECT 'csv' f, COUNT(*) FROM sb_raw.transacciones_csv UNION ALL
SELECT 'avro', COUNT(*) FROM sb_raw.transacciones_avro UNION ALL
SELECT 'parquet', COUNT(*) FROM sb_raw.transacciones_parquet UNION ALL
SELECT 'masivo', COUNT(*) FROM sb_raw.transacciones_masivo;
