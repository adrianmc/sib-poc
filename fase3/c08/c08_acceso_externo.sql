-- =====================================================================
-- C08-AE-07: acceso gobernado y temporal para un ente externo SIN acceso a la plataforma.
-- Hue -> Impala como sb_admin01. Se comparte una copia ENMASCARADA fisicamente (el motor externo lee
-- archivos Parquet via REST Catalog y el masking dinamico de Ranger no aplica en ese camino).
-- =====================================================================
CREATE TABLE IF NOT EXISTS sb_share.clientes_externo
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')
AS SELECT id_cliente,
          mask_hash(identificacion) AS identificacion_hash,
          region, segmento,
          CAST(ROUND(ingreso_mensual, -2) AS DECIMAL(14,2)) AS ingreso_aproximado,
          fecha_alta
   FROM sb_curated.clientes;

-- Opcion 1 (recomendada, nativa en 7.3.2): Data Catalog > Data Sharing: crear el share de esta tabla para el consumidor
--   externo; el consumidor lee con Python (fase3/c01/c01_ae06_lectura_externa.py) sin cuenta en la plataforma.
--   Revocacion: eliminar el share/acceso en Data Catalog o dejar que venza el token (vigencia del share).
-- Opcion 2 (Power BI externo): usuario sb_externo01 con politica Ranger temporal (c08_politica_externo_temporal.json)
-- Revocacion: eliminar la politica / el share, o dejar que expire el validitySchedule, y repetir la consulta -> denegado.
SELECT COUNT(*) FROM sb_share.clientes_externo;
