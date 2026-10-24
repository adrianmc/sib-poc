-- C01-AE-05 (en vivo): cambios en el ORIGEN SQL Server. Herramienta: SSMS en la EC2, base sbcore (sbcore_app o sysadmin).
-- Luego en Hue/Impala verificar que SOLO estos registros cambiaron en sb_curated.clientes (ver cdc_ts).
USE sbcore;
UPDATE dbo.clientes SET segmento = 'PYME', fecha_actualizacion = SYSDATETIME() WHERE id_cliente IN (10, 20, 30);
INSERT INTO dbo.clientes VALUES (9000001, '999000001', 'Cliente Demo CDC', 'demo.cdc@correo-ficticio.test',
  '80000001', '1990-05-10', 'CENTRAL', 'PERSONAL', 1500.00, CAST(GETDATE() AS DATE), SYSDATETIME());
DELETE FROM dbo.clientes WHERE id_cliente = 40;

-- Verificacion en Hue (Impala), ~15-30 s despues (el Agent de SQL Server publica los cambios en cdc.* en segundos):
-- REFRESH sb_curated.clientes;
-- SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,40,9000001);
-- SELECT id_cliente, cdc_ts FROM sb_curated.clientes ORDER BY cdc_ts DESC LIMIT 10;
-- DESCRIBE HISTORY sb_curated.clientes;
