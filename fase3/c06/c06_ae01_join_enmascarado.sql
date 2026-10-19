-- C06-AE-01: JOIN y GROUP BY sobre datos enmascarados SIN desenmascarar.
-- Hue -> Impala con sb_cient01 (tag PII -> MASK_HASH, deterministico: el mismo valor produce el mismo hash
-- en ambas tablas, por eso el JOIN funciona).
SELECT identificacion, nombre, email FROM sb_curated.clientes LIMIT 5;             -- se ven hashes

SELECT c.region, cr.calificacion_riesgo,
       COUNT(DISTINCT c.identificacion) deudores,
       CAST(SUM(cr.saldo_pendiente) AS DECIMAL(20,2)) saldo
FROM sb_curated.clientes c
JOIN sb_curated.creditos cr ON cr.identificacion_cliente = c.identificacion        -- JOIN sobre columna enmascarada
GROUP BY c.region, cr.calificacion_riesgo
ORDER BY c.region, cr.calificacion_riesgo;
-- Repetir con sb_admin01: mismos totales, identificaciones en claro. Evidencia: Ranger > Audit (politica sb_03_mask_pii).
-- Nota: tokenizacion con preservacion de formato no es nativa (requiere Protegrity/Thales).
