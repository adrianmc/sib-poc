-- C02-AE-02: latencia registrada por medicion extremo a extremo (productor --medir)
SELECT * FROM sb_consumption.latencia_streaming ORDER BY enviado_ts DESC;

-- Latencia por evento dentro del pipeline (Kafka -> Iceberg). Si Impala no ve lo nuevo: REFRESH sb_curated.transacciones_rt;
SELECT COUNT(*) eventos,
       AVG(unix_timestamp(ingesta_ts) - unix_timestamp(evento_ts)) latencia_prom_s,
       MAX(unix_timestamp(ingesta_ts) - unix_timestamp(evento_ts)) latencia_max_s
FROM sb_consumption.v_transacciones_rt
WHERE evento_ts > now() - INTERVAL 15 MINUTES;

-- C02-AE-07: consulta ad-hoc sobre datos gobernados SIN copiar ni materializar.
-- Mostrar en el Query Profile que solo hay SCAN sobre la tabla Iceberg (sin CTAS ni tabla temporal).
SELECT canal, tipo, COUNT(*) n, CAST(SUM(monto) AS DECIMAL(20,2)) total
FROM sb_curated.transacciones
WHERE fecha_hora >= '2026-07-01'
GROUP BY canal, tipo ORDER BY total DESC;
-- Luego: Hue > Query History > Query Profile / Plan (bytes leidos, particiones podadas).
