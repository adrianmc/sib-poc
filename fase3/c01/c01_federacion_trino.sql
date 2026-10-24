-- =====================================================================
-- PG-10 / C02-AE-07 / C03-PRE-01: consulta federada con Trino Virtual Warehouse (CDW, ultima version).
-- La base SQL Server origen del cliente (EC2) se consulta EN VIVO junto con el lakehouse Iceberg, sin copiar datos.
-- Herramienta: Hue (Data Explorer) -> editor Trino del VW trino-sb. Usuarios: user006 (analista2) y user001 (admin).
-- DECLARAR: el conector SQL Server de Trino es COMUNITARIO (Cloudera certifica Oracle, no SQL Server).
-- Prerrequisitos (Fase 1):
--   * Trino VW "trino-sb" (auto-suspend desactivado, minimo 1 worker: problema conocido de metadata en Hue).
--   * Catalogo "sqlserver_core": connector.name=sqlserver,
--     connection-url=jdbc:sqlserver://CAMBIAR_SQLSERVER_IP_PRIVADA:1433;databaseName=sbcore;encrypt=false,
--     usuario sbcore_app (contrasena como secreto del ambiente), asociado al VW.
--   * Politicas Ranger cm_trino: fase2/politicas_ranger/10 y 11 (endurecer la postura por defecto de cm_trino).
-- Validar en el primer ensayo con SHOW CATALOGS: nombre real del catalogo del lakehouse (asumido "iceberg").
-- =====================================================================

SHOW CATALOGS;
SHOW SCHEMAS FROM sqlserver_core;
SHOW TABLES FROM sqlserver_core.dbo;

-- 1. Lectura en vivo de la base origen. user006: identificacion en hash (politica sb_11). user001: en claro.
SELECT id_cliente, identificacion, region, segmento FROM sqlserver_core.dbo.clientes LIMIT 10;

-- 2. Consulta federada: clientes vivos en SQL Server + transacciones historicas en Iceberg, una sola sentencia
SELECT o.region,
       o.segmento,
       count(*)                     AS transacciones,
       sum(t.monto)                 AS monto_total,
       count(DISTINCT o.id_cliente) AS clientes
FROM sqlserver_core.dbo.clientes o
JOIN iceberg.sb_curated.cuentas c       ON c.id_cliente = o.id_cliente
JOIN iceberg.sb_curated.transacciones t ON t.id_cuenta = c.id_cuenta
WHERE t.fecha_hora >= TIMESTAMP '2026-07-01 00:00:00'
GROUP BY o.region, o.segmento
ORDER BY monto_total DESC;

-- 3. Evidencia de "sin copia": el plan muestra el scan remoto en SQL Server (filtro empujado a la base) y el scan Iceberg
EXPLAIN
SELECT region, count(*) FROM sqlserver_core.dbo.clientes WHERE segmento = 'PYME' GROUP BY region;

-- 4. Frescura: en SSMS (base sbcore) ejecutar
--    UPDATE dbo.clientes SET segmento = 'CORPORATIVO' WHERE id_cliente = 50;
--    y repetir: el cambio se ve de inmediato, sin pipeline de por medio.
SELECT id_cliente, segmento FROM sqlserver_core.dbo.clientes WHERE id_cliente = 50;

-- Evidencia de auditoria: Ranger > Audit > Access, servicio cm_trino, usuario de la sesion.
-- Mensaje para la SB: Trino federa para exploracion y consultas puntuales; las cargas recurrentes se ingestan
-- (NiFi / CDC) al lakehouse. Ver c01_ae01_nifi_ingesta.md.
