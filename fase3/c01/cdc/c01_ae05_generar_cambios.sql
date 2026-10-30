-- C01-AE-05 (en vivo): cambios en el ORIGEN SQL Server. Herramienta: SSMS en la EC2 > New Query > pegar > Execute.
-- Repetible sin preparacion: el INSERT usa el siguiente id libre desde 9000001 y el DELETE el menor id entre 40 y 99
-- que todavia exista. Ambos ids se muestran en el resultado (anotarlos para la verificacion en Hue).
USE sbcore;
DECLARE @nuevo BIGINT = (SELECT ISNULL(MAX(id_cliente), 9000000) + 1 FROM dbo.clientes WHERE id_cliente >= 9000001);
UPDATE dbo.clientes SET segmento = 'PYME', fecha_actualizacion = SYSDATETIME() WHERE id_cliente IN (10, 20, 30);
INSERT INTO dbo.clientes
OUTPUT inserted.id_cliente AS id_insertado
VALUES (@nuevo, CONCAT('999', @nuevo), 'Cliente Demo CDC', 'demo.cdc@correo-ficticio.test',
  '80000001', '1990-05-10', 'CENTRAL', 'PERSONAL', 1500.00, CAST(GETDATE() AS DATE), SYSDATETIME());
DELETE FROM dbo.clientes
OUTPUT deleted.id_cliente AS id_borrado
WHERE id_cliente = (SELECT MIN(id_cliente) FROM dbo.clientes WHERE id_cliente BETWEEN 40 AND 99);

-- Verificacion en Hue (Impala), tras ver la linea MERGE en la Terminal del consumidor:
-- SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,<id_borrado>,<id_insertado>);
-- DESCRIBE HISTORY sb_curated.clientes;
