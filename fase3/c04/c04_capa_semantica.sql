-- =====================================================================
-- C04: capa semantica gobernada basada en vistas (Hue -> Impala, sb_admin01)
-- Honestidad: Cloudera no tiene capa de metricas nativa. La "definicion oficial" es una vista gobernada,
-- documentada con comentarios y glosario Atlas, protegida con Ranger y reutilizable por cualquier consumidor.
-- =====================================================================

-- C04-PRE-06: vista con nombres de negocio y descripcion por campo (Power BI ve los nombres de columna;
-- las descripciones NO se heredan en Power BI - brecha declarada en C04-AE-04)
CREATE VIEW IF NOT EXISTS sb_consumption.v_cartera_crediticia (
  Identificacion_Deudor COMMENT 'Documento del deudor (PII, enmascarado segun rol)',
  Producto              COMMENT 'Nombre del producto crediticio',
  Tipo_Producto         COMMENT 'Hipotecario, personal, vehiculo, tarjeta, pyme',
  Region                COMMENT 'Region del cliente',
  Monto_Original        COMMENT 'Monto desembolsado',
  Saldo_Pendiente       COMMENT 'Saldo pendiente (CONFIDENCIAL)',
  Dias_Mora             COMMENT 'Dias de atraso',
  Calificacion          COMMENT 'Categoria de riesgo A-E (CONFIDENCIAL)',
  Fecha_Desembolso      COMMENT 'Fecha de desembolso')
AS SELECT cr.identificacion_cliente, p.nombre_producto, p.tipo_producto, c.region,
          cr.monto_original, cr.saldo_pendiente, cr.dias_mora, cr.calificacion_riesgo, cr.fecha_desembolso
   FROM sb_curated.creditos cr
   LEFT JOIN sb_curated.catalogo_productos p ON p.id_producto = cr.id_producto
   LEFT JOIN sb_curated.clientes c ON c.identificacion = cr.identificacion_cliente;

-- C04-PRE-03 / AE-06: metricas semanticas oficiales (una sola definicion reutilizable)
CREATE VIEW IF NOT EXISTS sb_consumption.m_indice_morosidad_oficial (
  Region COMMENT 'Region', Tipo_Producto COMMENT 'Tipo de producto',
  Saldo_Total COMMENT 'Saldo total de la cartera',
  Saldo_En_Mora COMMENT 'Saldo con mas de 90 dias de atraso (definicion oficial)',
  Indice_Morosidad COMMENT 'Saldo en mora > 90 dias / saldo total. METRICA OFICIAL certificada en glosario')
AS SELECT c.region, p.tipo_producto,
          SUM(cr.saldo_pendiente),
          SUM(CASE WHEN cr.dias_mora > 90 THEN cr.saldo_pendiente ELSE 0 END),
          CAST(SUM(CASE WHEN cr.dias_mora > 90 THEN cr.saldo_pendiente ELSE 0 END) / SUM(cr.saldo_pendiente) AS DECIMAL(9,6))
   FROM sb_curated.creditos cr
   JOIN sb_curated.clientes c ON c.identificacion = cr.identificacion_cliente
   LEFT JOIN sb_curated.catalogo_productos p ON p.id_producto = cr.id_producto
   GROUP BY c.region, p.tipo_producto;

CREATE VIEW IF NOT EXISTS sb_consumption.m_transaccionalidad_mensual (
  Mes COMMENT 'Mes', Region COMMENT 'Region', Clientes_Activos COMMENT 'Clientes con al menos una transaccion',
  Monto_Total COMMENT 'Monto transado', Ticket_Promedio COMMENT 'Monto total / transacciones. METRICA OFICIAL')
AS SELECT mes, region, COUNT(DISTINCT id_cliente), SUM(monto_total),
          CAST(SUM(monto_total) / SUM(num_transacciones) AS DECIMAL(18,2))
   FROM sb_consumption.resumen_cliente_mensual GROUP BY mes, region;

-- C04-PRE-04: metrica con definicion EN CONFLICTO (morosidad > 30 dias) preparada por un "equipo B"
CREATE VIEW IF NOT EXISTS sb_sandbox_depto_b.m_indice_morosidad_equipo_b (
  Region COMMENT 'Region', Indice_Morosidad COMMENT 'NO OFICIAL: usa > 30 dias')
AS SELECT c.region,
          CAST(SUM(CASE WHEN cr.dias_mora > 30 THEN cr.saldo_pendiente ELSE 0 END) / SUM(cr.saldo_pendiente) AS DECIMAL(9,6))
   FROM sb_curated.creditos cr JOIN sb_curated.clientes c ON c.identificacion = cr.identificacion_cliente
   GROUP BY c.region;

-- C04-AE-06: reutilizacion de la metrica oficial en OTRO proceso (sin recrear la logica)
SELECT o.Region, SUM(o.Saldo_En_Mora) / SUM(o.Saldo_Total) AS morosidad_oficial, b.Indice_Morosidad AS morosidad_equipo_b
FROM sb_consumption.m_indice_morosidad_oficial o
JOIN sb_sandbox_depto_b.m_indice_morosidad_equipo_b b ON b.Region = o.Region
GROUP BY o.Region, b.Indice_Morosidad;
-- Mensaje: el conflicto se hace visible y el glosario (c04_glosario_atlas.py) identifica cual es la oficial.
-- Control automatico de duplicidad NO es nativo: se gobierna por certificacion en glosario + Ranger
-- (solo sb_admin crea objetos en sb_consumption).
