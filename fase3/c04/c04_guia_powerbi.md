# C04 - Guia Power BI (Desktop en EC2 Windows + Service con gateway)

**Conexion (C04-PRE-01, AE-01).** Power BI Desktop > Obtener datos > **Impala**.
Servidor: `CAMBIAR_HOST_IMPALA_DEPTO_A:443`. Modo: **DirectQuery**.
Autenticacion: usuario y contraseña (workload password) o, con el driver ODBC de Cloudera, Browser SSO (SAML/Entra).
Si el conector nativo pide transporte HTTP, usar el driver ODBC de Cloudera Impala con: `SSL=1; TransportMode=http; HTTPPath=cliservice; AuthMech=3`.

**AE-01 (cambio inmediato y automatico).** Reporte sobre `sb_consumption.v_cartera_crediticia` en DirectQuery, conectado con
`sb_analista02` (tiene atributo confidencial; con `sb_analista01` la vista falla por las columnas CONFIDENCIAL).
Activar **Actualizacion automatica de pagina** (Formato de pagina > Actualizacion de pagina, cada 5 s; disponible para DirectQuery).
En Hue ejecutar `UPDATE sb_curated.creditos SET dias_mora = 120 WHERE id_credito = 1;` y el visual cambia solo, sin recarga manual.
En Power BI Service la frecuencia minima de actualizacion automatica la define la capacidad (validar con el administrador del tenant).

**Visual adicional para C08-AE-06:** "Transacciones por entidad" (DirectQuery sobre `sb_curated.transacciones`, campo `nombre_entidad`).

**AE-02 (carga masiva).** Segundo reporte en modo **Import** sobre `sb_consumption.resumen_cliente_mensual`.
Refrescar y mostrar: duracion del refresh (Power BI) + consultas y bytes escaneados en Hue > Query History / CDW Grafana.

**AE-03 (herencia de permisos) - declarar el matiz.**
- Desktop con `sb_analista01`: `Identificacion_Deudor` sale como hash (tag PII) y `Saldo_Pendiente`/`Calificacion` son denegadas (tag CONFIDENCIAL). Con `sb_analista02` se ven. Ranger aplica por identidad sin configuracion en Power BI.
- Service: la conexion via on-premises data gateway usa una credencial almacenada; todos los visores heredan la identidad de esa credencial. Para seguridad por visor: RLS en Power BI o un modelo semantico por rol. No es herencia automatica.

**AE-04 (descripciones/relaciones) - brecha.** Los nombres de negocio llegan como nombres de columna de las vistas, pero el metastore los normaliza a minusculas (`saldo_pendiente`); mayusculas o espacios se ajustan en Power BI. Las descripciones (COMMENT) y relaciones no se importan: se definen en el modelo de Power BI. Mostrarlo con transparencia.

**AE-05 (consumo vs desarrollo).**
- Consumidor (`sb_analista01`): rol Viewer en el workspace de Power BI; solo SELECT en sb_consumption.
- Desarrollador (`sb_ing01`): conecta un dashboard nuevo a `sb_sandbox_depto_a` (tiene ALL ahi por la politica sb_06). Mostrar que `sb_analista01` recibe AuthorizationException al intentar crear una tabla en sb_consumption.

**AE-06.** Visual de `m_indice_morosidad_oficial` en Power BI y la misma vista reutilizada en SQL (c04_capa_semantica.sql) y en CML: una definicion, varios consumidores. Mostrar el termino en Atlas > Glossary > SB_Glosario.

**Nota de seguridad en vistas.** Las tags PII/CONFIDENCIAL se asignan en columnas base y Atlas las propaga por linaje
(propagate=true) a las columnas de las vistas; Ranger aplica las politicas tag-based sobre la vista. Verificar en Atlas
(columna de la vista > Classifications) antes de la demo; la propagacion tarda unos minutos.
