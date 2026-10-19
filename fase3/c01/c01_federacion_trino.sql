-- =====================================================================
-- PG-10 / C02-AE-07 / C03-PRE-01: consulta federada con Trino Virtual Warehouse (CDW, ultima version).
-- La base Oracle origen del cliente (RDS) se consulta EN VIVO junto con el lakehouse Iceberg, sin copiar datos.
-- Herramienta: Hue (Data Explorer) -> editor Trino del VW trino-sb. Usuarios: sb_analista02 y sb_admin01.
-- Prerrequisitos (Fase 1):
--   * Trino VW "trino-sb" (auto-suspend desactivado, minimo 1 worker: problema conocido de metadata en Hue).
--   * Secreto registrado en el ambiente con la contrasena de SBCORE.
--   * Federation Connector CERTIFICADO Oracle, catalogo "oracle_core",
--     URL jdbc:oracle:thin:@//CAMBIAR_RDS_ORACLE:1521/ORCL, usuario SBCORE, asociado al VW.
--   * Politicas Ranger cm_trino: fase2/politicas_ranger/10 y 11 (endurecer la postura por defecto de cm_trino).
-- Validar en el primer ensayo con SHOW CATALOGS: nombre real del catalogo del lakehouse (asumido "iceberg")
-- y si los nombres de esquema/tabla Oracle llegan en minusculas (asumido sbcore.clientes).
-- =====================================================================

SHOW CATALOGS;
SHOW SCHEMAS FROM oracle_core;
SHOW TABLES FROM oracle_core.sbcore;

-- 1. Lectura en vivo de la base origen. sb_analista02: identificacion en hash (politica sb_11). sb_admin01: en claro.
SELECT id_cliente, identificacion, region, segmento FROM oracle_core.sbcore.clientes LIMIT 10;

-- 2. Consulta federada: clientes vivos en Oracle + transacciones historicas en Iceberg, una sola sentencia
SELECT o.region,
       o.segmento,
       count(*)                     AS transacciones,
       sum(t.monto)                 AS monto_total,
       count(DISTINCT o.id_cliente) AS clientes
FROM oracle_core.sbcore.clientes o
JOIN iceberg.sb_curated.cuentas c       ON c.id_cliente = o.id_cliente
JOIN iceberg.sb_curated.transacciones t ON t.id_cuenta = c.id_cuenta
WHERE t.fecha_hora >= TIMESTAMP '2026-07-01 00:00:00'
GROUP BY o.region, o.segmento
ORDER BY monto_total DESC;

-- 3. Evidencia de "sin copia": el plan muestra el scan remoto en Oracle (filtro empujado a la base) y el scan Iceberg
EXPLAIN
SELECT region, count(*) FROM oracle_core.sbcore.clientes WHERE segmento = 'PYME' GROUP BY region;

-- 4. Frescura: en SQL Developer como SBCORE ejecutar
--    UPDATE SBCORE.CLIENTES SET SEGMENTO = 'CORPORATIVO' WHERE ID_CLIENTE = 50; COMMIT;
--    y repetir: el cambio se ve de inmediato, sin pipeline de por medio.
SELECT id_cliente, segmento FROM oracle_core.sbcore.clientes WHERE id_cliente = 50;

-- 5. (Opcional, declarar) SQL Server via conector COMUNITARIO de Trino: sin soporte directo de Cloudera.
-- SELECT calificacion_riesgo, count(*) FROM sqlserver_creditos.dbo.creditos GROUP BY calificacion_riesgo;

-- Evidencia de auditoria: Ranger > Audit > Access, servicio cm_trino, usuario de la sesion.
-- Mensaje para la SB: Trino federa para exploracion y consultas puntuales; las cargas recurrentes se ingestan
-- (NiFi / CDC) al lakehouse. Ver c01_ae01_nifi_ingesta.md.
