-- =====================================================================
-- C08-AE-03: analisis de impacto ante cambio controlado en la fuente
-- C08-AE-06: dato maestro corrupto que viaja por el linaje hasta el dashboard
-- Herramientas: Hue (Impala) + Atlas (Lineage) + Ranger (Audit) + Power BI
-- =====================================================================

-- AE-03 (antes de ejecutar el cambio): Atlas > buscar sb_curated.entidades_financieras > Lineage.
-- Se ven los consumidores: sb_curated.transacciones (pipeline) -> resumen/vistas -> Tablero Cartera (entidad custom).
-- Cambio controlado (sandbox para no romper la demo):
CREATE TABLE sb_sandbox_depto_a.entidades_copia STORED AS ICEBERG AS SELECT * FROM sb_curated.entidades_financieras;
CREATE VIEW sb_sandbox_depto_a.v_tx_por_entidad AS
  SELECT e.nombre, COUNT(*) n FROM sb_curated.transacciones t
  JOIN sb_sandbox_depto_a.entidades_copia e ON e.id_entidad = t.id_entidad_destino GROUP BY e.nombre;
ALTER TABLE sb_sandbox_depto_a.entidades_copia CHANGE COLUMN nombre nombre_entidad STRING;
SELECT * FROM sb_sandbox_depto_a.v_tx_por_entidad LIMIT 5;      -- falla: la vista dependiente quedo afectada
-- Atlas muestra v_tx_por_entidad como dependiente de entidades_copia (downstream) = objeto impactado.

-- AE-06: corrupcion de dato maestro (en Hue como user002 'ingeniero': queda auditado con su nombre)
DESCRIBE HISTORY sb_curated.entidades_financieras;             -- anotar snapshot actual para revertir
UPDATE sb_curated.entidades_financieras SET nombre = 'ENTIDAD CORRUPTA - DEMO' WHERE id_entidad = 7;
-- Re-ejecutar el pipeline: Cloudera AI > Jobs > sib-pipeline > Run (~4 min; el paso 3 re-enriquece transacciones)
-- OJO: el paso 1 recarga sb_curated.clientes desde sb_raw (TRUNCATE + INSERT) y borra lo aplicado por CDC (C01-AE-05).
-- En la demo: hacer C08-AE-06 ANTES de la demo de CDC, o repetir el CDC despues. Y mostrar la propagacion:
SELECT nombre_entidad, COUNT(*) FROM sb_curated.transacciones WHERE id_entidad_destino = 7 GROUP BY nombre_entidad;
-- Power BI (DirectQuery, visual 'Transacciones por entidad' sobre sb_curated.transacciones) muestra 'ENTIDAD CORRUPTA - DEMO'. Atlas Lineage muestra el recorrido.
-- Ranger > Audit > Access: filtrar usuario user002, recurso sb_curated/entidades_financieras, accion update.

-- Remediacion: rollback del maestro y reproceso
ALTER TABLE sb_curated.entidades_financieras EXECUTE ROLLBACK(CAMBIAR_SNAPSHOT_ANTERIOR);
-- Re-ejecutar el Job sib-pipeline (idempotente) y validar que el nombre correcto regresa con el mismo SELECT.
