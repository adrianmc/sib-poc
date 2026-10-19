# C01-AE-01 y ETL con NiFi (Data Hub Flow Management)

Objetivo: que la llegada a la capa cruda la haga la **plataforma** (no `aws s3 cp`) para los 3 tipos de dato,
y mostrar un ETL desde una base origen del cliente (SQL Server) hacia el lakehouse.
Herramienta: NiFi UI del Data Hub (Knox SSO), usuario sb_ing01. Crear el Process Group `SIB-PoC`.
**(V)** = propiedad que depende del Data Hub desplegado; se confirma en el ensayo de NiFi (paso 2.3 del plan).
Si ya tienes un flujo NiFi -> PostgreSQL funcionando, se reutiliza cambiando solo el DBCPConnectionPool.

## Servicios de controlador (Process Group > Configure > Controller Services)
| Servicio | Tipo | Propiedades clave |
|---|---|---|
| sb-kerberos | KerberosPasswordUserService | Principal `sb_ing01@<REALM del ambiente>` (V); password = workload password |
| sb-aws | AWSCredentialsProviderControllerService | Credenciales segun el mecanismo del Data Hub (IDBroker) (V) |
| sb-hive-catalog | HiveCatalogService | Metastore URI y `hive-site.xml`/`core-site.xml` del Data Hub (V) |
| sb-sqlserver | DBCPConnectionPool | URL `jdbc:sqlserver://CAMBIAR_RDS_SQLSERVER:1433;databaseName=sbcreditos;encrypt=false`; driver `com.microsoft.sqlserver.jdbc.SQLServerDriver`; Driver Location: `mssql-jdbc.jar` copiado a todos los nodos NiFi (V) |
| sb-csv-reader / sb-json-reader | CSVReader / JsonTreeReader | Inferir esquema; CSV con cabecera |
| sb-avro-reader / sb-avro-writer | AvroReader / AvroRecordSetWriter | Esquema embebido |

## Flujo A - Archivos a la capa cruda (estructurado, semiestructurado, no estructurado)
Simula la entrega de archivos de un tercero en el buzon `s3a://CAMBIAR_BUCKET/sb/entrada/`.
1. **ListS3**: bucket CAMBIAR_BUCKET, prefijo `sb/entrada/`, credenciales sb-aws.
2. **FetchS3Object**.
3. **RouteOnAttribute** (Routing Strategy: Route to Property name):
   `csv = ${filename:endsWith('.csv')}`, `json = ${filename:endsWith('.json')}`,
   `excel = ${filename:endsWith('.xlsx')}`, `nodoc = ${filename:endsWith('.pdf'):or(${filename:endsWith('.png')})}`.
4. Rama excel: **ConvertExcelToCSVProcessor** -> UpdateAttribute `filename = ${filename:substringBeforeLast('.')}.csv` -> rama csv.
5. Cada rama: **UpdateAttribute** `s3.destino` =
   csv -> `sb/landing/transacciones/csv/${filename}` (o `sb/landing/maestras/productos/` para el Excel),
   json -> `sb/landing/transacciones/json/${filename}`, nodoc -> `sb/landing/documentos/${filename}`;
   luego **PutS3Object** (Object Key `${s3.destino}`).
6. Evidencia en vivo: copiar al buzon un `.csv`, un `.json`, un `.xlsx` y un `.pdf`; mostrar Data Provenance en NiFi;
   en Hue: `REFRESH sb_raw.transacciones_csv; SELECT COUNT(*) ...` (JSON en el editor Hive). PDF/PNG visibles como
   activos en Atlas (c08, tipo documento_normativo).

## Flujo B - ETL incremental SQL Server -> lakehouse
Tabla destino (Hue/Impala, una vez):
```sql
CREATE TABLE IF NOT EXISTS sb_raw.creditos_nifi (
  id_credito BIGINT, identificacion_cliente STRING, id_producto INT, monto_original DECIMAL(16,2),
  saldo_pendiente DECIMAL(16,2), tasa_interes DECIMAL(6,2), plazo_meses INT, dias_mora INT,
  calificacion_riesgo STRING, fecha_desembolso DATE, default_12m INT, banda_mora STRING)
STORED AS ICEBERG TBLPROPERTIES ('format-version'='2');
```
1. **QueryDatabaseTableRecord**: pool sb-sqlserver, tabla `dbo.creditos`, Maximum-value Columns `id_credito`,
   Record Writer sb-avro-writer, Fetch Size 10000. Lee solo filas nuevas en cada ejecucion.
2. **QueryRecord** (transformacion visible), relacion `transformado`:
   `SELECT *, CASE WHEN dias_mora = 0 THEN 'AL_DIA' WHEN dias_mora <= 90 THEN 'ATRASO' ELSE 'MORA' END AS banda_mora FROM FLOWFILE`
3. **PutIceberg**: Catalog Service sb-hive-catalog, Kerberos sb-kerberos, Catalog Namespace `sb_raw`, Table Name `creditos_nifi`,
   Record Reader sb-avro-reader. Si los tipos DECIMAL/DATE no coinciden, ajustar con un esquema explicito en el writer (V).
4. Evidencia: primera ejecucion = carga completa. Insertar 5 creditos nuevos en SQL Server
   (`INSERT INTO dbo.creditos VALUES (900001, ...)`), ejecutar de nuevo: entran solo esos 5
   (`SELECT COUNT(*)` antes/despues y `DESCRIBE HISTORY sb_raw.creditos_nifi`). Linaje NiFi -> Atlas si el reporting task esta activo (V).

Declarar: QueryDatabaseTable es incremental por columna de valor maximo; **no captura UPDATE ni DELETE**.
Eso lo cubre el CDC con Debezium (C01-AE-05). Son patrones complementarios.
