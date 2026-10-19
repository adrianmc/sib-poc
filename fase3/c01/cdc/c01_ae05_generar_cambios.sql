-- C01-AE-05 (en vivo): cambios en el ORIGEN Oracle. Herramienta: SQL Developer/DBeaver como SBCORE.
-- Luego en Hue/Impala verificar que SOLO estos registros cambiaron en sb_curated.clientes (ver cdc_ts).
UPDATE SBCORE.CLIENTES SET SEGMENTO = 'PYME', FECHA_ACTUALIZACION = SYSTIMESTAMP WHERE ID_CLIENTE IN (10, 20, 30);
INSERT INTO SBCORE.CLIENTES VALUES (9000001, '999000001', 'Cliente Demo CDC', 'demo.cdc@correo-ficticio.test',
  '80000001', DATE '1990-05-10', 'CENTRAL', 'PERSONAL', 1500.00, SYSDATE, SYSTIMESTAMP);
DELETE FROM SBCORE.CLIENTES WHERE ID_CLIENTE = 40;
COMMIT;

-- Verificacion en Hue (Impala), ~15-30 s despues:
-- REFRESH sb_curated.clientes;
-- SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,40,9000001);
-- SELECT id_cliente, cdc_ts FROM sb_curated.clientes ORDER BY cdc_ts DESC LIMIT 10;
-- DESCRIBE HISTORY sb_curated.clientes;
