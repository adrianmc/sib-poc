-- C01-AE-02 (parte SQL). Herramienta: Hue -> Impala, usuario user006.
-- La MISMA consulta se ejecuta luego en Cloudera AI (c01_ae02_notebook.py) sobre la misma tabla fisica.
-- Se usan funciones exactas (COUNT DISTINCT, no NDV) para que los resultados coincidan entre motores.
SELECT c.region,
       t.canal,
       COUNT(*)                                    AS transacciones,
       CAST(SUM(t.monto) AS DECIMAL(20,2))         AS monto_total,
       COUNT(DISTINCT t.id_cuenta)                 AS cuentas_distintas,
       ROW_NUMBER() OVER (PARTITION BY c.region ORDER BY SUM(t.monto) DESC) AS ranking_canal
FROM sb_curated.transacciones t
JOIN sb_curated.cuentas  cu ON cu.id_cuenta = t.id_cuenta
JOIN sb_curated.clientes c  ON c.id_cliente = cu.id_cliente
WHERE t.fecha_hora >= '2026-06-01' AND t.fecha_hora < '2026-07-01'
GROUP BY c.region, t.canal
ORDER BY c.region, ranking_canal;

-- Evidencia de no duplicacion: una sola ubicacion fisica para todos los consumidores
DESCRIBE FORMATTED sb_curated.transacciones;
