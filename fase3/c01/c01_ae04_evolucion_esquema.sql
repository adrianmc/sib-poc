-- C01-AE-04: evolucion de esquema sin reescribir datos ni romper consultas. Hue -> Impala, sb_ing01.
SELECT COUNT(*) FROM sb_sandbox_depto_a.transacciones_demo;

ALTER TABLE sb_sandbox_depto_a.transacciones_demo
  ADD COLUMNS (score_fraude DOUBLE COMMENT 'Score de fraude agregado en la demo');

-- Filas historicas devuelven NULL en la columna nueva, sin error
SELECT id_transaccion, monto, score_fraude FROM sb_sandbox_depto_a.transacciones_demo LIMIT 5;

INSERT INTO sb_sandbox_depto_a.transacciones_demo
VALUES ('TXDEMO000001', 1, now(), 'PAGO', 'WEB', 150.00, 'LOCAL', 0.87);

SELECT id_transaccion, score_fraude FROM sb_sandbox_depto_a.transacciones_demo WHERE score_fraude IS NOT NULL;

-- Rename de columna (operacion de metadata en Iceberg)
ALTER TABLE sb_sandbox_depto_a.transacciones_demo CHANGE COLUMN score_fraude score_riesgo_fraude DOUBLE;
DESCRIBE sb_sandbox_depto_a.transacciones_demo;

-- Tambien visible desde Spark/CML y Hive sin cambios adicionales (mismo metastore)
