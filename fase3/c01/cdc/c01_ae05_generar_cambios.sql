-- C01-AE-05 (en vivo): cambios en el ORIGEN SQL Server. Herramienta: SSMS en la EC2 > New Query > pegar > Execute.
-- Repetible: el DELETE toma el menor id entre 40 y 99 que todavia exista (cada ensayo borra uno distinto) y lo muestra.
-- Antes: el cliente 9000001 no debe existir (preparacion de la sesion 1, paso 2).
USE sbcore;
UPDATE dbo.clientes SET segmento = 'PYME', fecha_actualizacion = SYSDATETIME() WHERE id_cliente IN (10, 20, 30);
INSERT INTO dbo.clientes VALUES (9000001, '999000001', 'Cliente Demo CDC', 'demo.cdc@correo-ficticio.test',
  '80000001', '1990-05-10', 'CENTRAL', 'PERSONAL', 1500.00, CAST(GETDATE() AS DATE), SYSDATETIME());
DELETE FROM dbo.clientes
OUTPUT deleted.id_cliente AS id_borrado
WHERE id_cliente = (SELECT MIN(id_cliente) FROM dbo.clientes WHERE id_cliente BETWEEN 40 AND 99);

-- Verificacion en Hue (Impala), ~15-30 s despues de ver la linea MERGE en la Terminal del consumidor
-- (reemplazar <id_borrado> por el valor que mostro el DELETE):
-- SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,<id_borrado>,9000001);
-- DESCRIBE HISTORY sb_curated.clientes;
