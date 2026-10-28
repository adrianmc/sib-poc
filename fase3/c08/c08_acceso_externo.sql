-- =====================================================================
-- C08-AE-07: acceso gobernado y temporal para un ente externo SIN acceso a la plataforma.
-- Hue -> Impala como user001 (admin). Se comparte una copia ENMASCARADA fisicamente (el motor externo lee
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

-- Tenant de la PoC (28-oct): SIN Data Sharing (falta el entitlement CDP_DATA_SHARE_ADMIN). Se usa el plan B:
--   fase3/c08/c08_ae07_lectura_externo.py + usuario IAM sib-externo con c08_politica_iam_externo.json (vence sola, revocable).
-- Opcion 1 (nativa en 7.3.2, con entitlement): Data Catalog > Data Sharing: crear el share de esta tabla para el consumidor
--   externo; el consumidor lee con Python (fase3/c01/c01_ae06_lectura_externa.py) sin cuenta en la plataforma.
--   Revocacion: eliminar el share/acceso en Data Catalog o dejar que venza el token (vigencia del share).
-- Opcion 2 (Power BI externo): usuario sb_externo01 con politica Ranger temporal (c08_politica_externo_temporal.json)
-- Revocacion: eliminar la politica / el share, o dejar que expire el validitySchedule, y repetir la consulta -> denegado.
SELECT COUNT(*) FROM sb_share.clientes_externo;
DESCRIBE FORMATTED sb_share.clientes_externo;   -- copiar Location (ruta de la tabla) y metadata_location
