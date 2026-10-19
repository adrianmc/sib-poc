-- C05-AE-05 (rollback de datos) y AE-06 (versionado de datos, no solo codigo). Hue -> Impala, sb_ing01.
DESCRIBE HISTORY sb_curated.transacciones;                          -- cada ejecucion = snapshot con fecha

-- Time travel por fecha y por snapshot (usar valores reales de DESCRIBE HISTORY)
SELECT COUNT(*) FROM sb_curated.transacciones FOR SYSTEM_TIME AS OF '2026-08-20 10:00:00';
SELECT COUNT(*) FROM sb_curated.transacciones FOR SYSTEM_VERSION AS OF CAMBIAR_SNAPSHOT_ID;

-- Simular una carga erronea y revertirla con rollback atomico (sin copiar datos)
DELETE FROM sb_curated.transacciones WHERE canal = 'ATM';
SELECT COUNT(*) FROM sb_curated.transacciones WHERE canal = 'ATM';   -- 0
ALTER TABLE sb_curated.transacciones EXECUTE ROLLBACK(CAMBIAR_SNAPSHOT_ID_PREVIO);
SELECT COUNT(*) FROM sb_curated.transacciones WHERE canal = 'ATM';   -- restaurado
DESCRIBE HISTORY sb_curated.transacciones;                           -- el historial conserva ambas versiones

-- Historial de despliegues de codigo (trazabilidad version <-> ambiente <-> autor)
SELECT * FROM sb_gov.despliegues ORDER BY fecha DESC;
