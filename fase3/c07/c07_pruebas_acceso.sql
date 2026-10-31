-- =====================================================================
-- C07: pruebas de control de acceso. Hue -> Impala. Iniciar sesion con cada usuario indicado.
-- Evidencia de cada prueba: Ranger > Audit > Access (usuario, recurso, politica, Allowed/Denied).
-- =====================================================================

-- Se prueba sobre la TABLA (tag asignado directo en la columna). La prueba sobre la vista depende de la
-- propagacion de tags por linaje de Atlas: validarla en el ensayo antes de mostrarla.

-- C07-AE-01 (rol + atributo correctos): user006 (sb_analista + attr_acceso_confidencial + attr_region_norte)
SELECT id_credito, calificacion_riesgo, saldo_pendiente FROM sb_curated.creditos LIMIT 10;
-- Esperado: acceso concedido y saldo/calificacion visibles. Ranger > Audit: usuario user006, Allowed.

-- C07-AE-02 (rol correcto, SIN atributo): user005 (sb_analista, sin attr_acceso_confidencial)
SELECT id_credito, calificacion_riesgo, saldo_pendiente FROM sb_curated.creditos LIMIT 10;
-- Esperado: AuthorizationException sobre columnas CONFIDENCIAL (politica tag-based sb_04). Mismo rol que
-- user006: la diferencia es solo el atributo. Ranger > Audit: Denied, politica sb_04.
SELECT id_credito, dias_mora FROM sb_curated.creditos LIMIT 10;
-- Esperado: funciona (columnas no confidenciales): el rol (RBAC) si da acceso a la tabla.

-- C07-AE-05 (campo sensible con y sin permiso)
SELECT id_cliente, identificacion, nombre, email FROM sb_curated.clientes LIMIT 5;
-- user005: hash en PII + solo region CENTRAL.  user001: datos en claro, todas las regiones.

-- C07-AE-04 (segregacion de ambientes): user005 intenta escribir en la capa de "produccion"
INSERT INTO sb_consumption.resumen_cliente_mensual SELECT * FROM sb_consumption.resumen_cliente_mensual LIMIT 1;
-- Esperado: AuthorizationException. En la arquitectura objetivo dev/test/prod son ambientes CDP separados
-- (Data Lake, IAM, buckets distintos): un usuario de dev no tiene identidad ni rol en prod. Ver diagrama.

-- C07-AE-03 (misma politica en SQL, BI y notebook): ejecutar esta misma consulta con user005 en
--   (1) Hue, (2) Power BI Desktop, (3) CML con fase3/c07/c07_ae03_notebook.py -> mismo resultado enmascarado.
SELECT identificacion, region FROM sb_curated.clientes ORDER BY id_cliente LIMIT 3;

-- Control 29-oct (hallazgo Iceberg COUNT(*) + filtro de fila): como user006 debe dar 150.464 (solo NORTE), no 1.000.000.
-- Si da 1.000.000, falta ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true en default_query_options del VW.
SELECT COUNT(*) FROM sb_curated.clientes;
EXPLAIN SELECT COUNT(*) FROM sb_curated.clientes;   -- con la mitigacion debe aparecer un SCAN de la tabla
