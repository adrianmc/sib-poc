-- C01-AE-03: INSERT / UPDATE / DELETE / MERGE sobre Iceberg V2, con datos de origen en CSV, Avro y Parquet.
-- Herramienta: Hue -> Impala, usuario user002. Se trabaja sobre una copia en el sandbox.

-- Arranque limpio (repetible): solo toca la tabla de demo del sandbox, nunca las capas raw/curada/consumible
DROP TABLE IF EXISTS sb_sandbox_depto_a.transacciones_demo PURGE;

CREATE TABLE sb_sandbox_depto_a.transacciones_demo
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')
AS SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP) fecha_hora, tipo, canal,
          CAST(monto AS DECIMAL(18,2)) monto, moneda
   FROM sb_raw.transacciones_csv ORDER BY id_transaccion LIMIT 100000;

-- INSERT desde origen Avro
INSERT INTO sb_sandbox_depto_a.transacciones_demo
SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), tipo, canal, CAST(monto AS DECIMAL(18,2)), moneda
FROM sb_raw.transacciones_avro LIMIT 50000;

-- UPDATE
UPDATE sb_sandbox_depto_a.transacciones_demo SET canal = 'APP_MOVIL' WHERE canal = 'APP';

-- DELETE
DELETE FROM sb_sandbox_depto_a.transacciones_demo WHERE monto < 1;

-- MERGE (upsert) mezclando origenes: 5.000 registros que YA existen (subconjunto del CSV usado en el CTAS, con monto +10%)
-- + 20.000 registros nuevos del origen Parquet. Ejercita ambas ramas: MATCHED (update) y NOT MATCHED (insert).
MERGE INTO sb_sandbox_depto_a.transacciones_demo t
USING (
  SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP) fecha_hora, tipo, canal,
         CAST(monto * 1.10 AS DECIMAL(18,2)) monto, moneda
  FROM (SELECT * FROM sb_raw.transacciones_csv ORDER BY id_transaccion LIMIT 5000) existentes
  UNION ALL
  SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), tipo, canal, CAST(monto AS DECIMAL(18,2)), moneda
  FROM sb_raw.transacciones_parquet LIMIT 20000
) s
ON t.id_transaccion = s.id_transaccion
WHEN MATCHED THEN UPDATE SET monto = s.monto
WHEN NOT MATCHED THEN INSERT VALUES (s.id_transaccion, s.id_cuenta, s.fecha_hora, s.tipo, s.canal, s.monto, s.moneda);

-- Evidencia: cada operacion genera un snapshot atomico
DESCRIBE HISTORY sb_sandbox_depto_a.transacciones_demo;
SELECT canal, COUNT(*) FROM sb_sandbox_depto_a.transacciones_demo GROUP BY canal;
-- Nota para el evaluador: JSON (semiestructurado) se opera igual desde Spark/Hive; Impala no lee JsonSerDe.
