# Runbook de implementacion paso a paso (SIB PoC)

Un solo recorrido, en orden, desde el ambiente vacio hasta tener cada item listo para la demo.
Cada paso indica: **donde** se ejecuta, **que** se ejecuta (literal), **valida** (lo que debe verse para darlo por bueno)
y **cubre** (items de la plantilla). Si un paso falla, copiar el error exacto y corregir antes de seguir.

Convenciones
- `<...>` = valor del ambiente. Se toma de `config/config.yaml`.
- **(V)** = depende de la version o configuracion del ambiente; confirmar en el primer intento.
- Estaciones de trabajo:
  - **AI** = Terminal de una sesion de Cloudera AI dentro del proyecto `sib-poc` (raiz `/home/cdsw`).
  - **WIN** = EC2 Windows (Power BI Desktop, SQL Server 2022 + SSMS, runner de GitHub).
  - **HUE** = Hue del VW indicado. **CDE** = CLI de CDE (desde AI) o UI del Virtual Cluster.
  - **LAP** = laptop fuera de la plataforma (solo para lectura externa y MCP).

Indice de etapas
| Etapa | Contenido | Tiempo estimado |
|---|---|---|
| E0 | Preparar estaciones y configuracion | 3 h |
| E1 | Identidad y accesos | 3 h |
| E2 | Fuente SQL Server y datos | 6 h |
| E3 | Lakehouse, tags y politicas | 4 h |
| E4 | Smoke tests (Gate 1) | 2 h |
| E5 | C01 Lakehouse e ingesta | 12 h |
| E6 | C02 Procesamiento | 16 h |
| E7 | C07 Seguridad | 3 h |
| E8 | C04 Power BI y capa semantica | 8 h |
| E9 | C06 Ciencia de datos e IA | 14 h |
| E10 | C05 CI/CD | 6 h |
| E11 | C08 Gobernanza | 10 h |
| E12 | C03 Integraciones | 3 h |
| E13 | C09 Operacion y FinOps | 5 h |
| E14 | Evidencias y dry-run | 16 h |

---

## E0 - Preparar estaciones y configuracion

**E0.1 Subir el kit a GitHub** (laptop, una sola vez)
1. GitHub > New repository: nombre `sib-poc`, **Public**, sin README > Create.
   (Publico: el gate de aprobacion de C05 lo exige en plan Free. El repo no lleva secretos: `config.yaml` esta en .gitignore.)
2. En la laptop, donde descargaste el zip:
```
unzip sb-poc-kit-fase2-fase3.zip
cd sb-poc
git init
git add .
git status                      # verificar que NO aparece config/config.yaml
git commit -m "SIB PoC kit v1"
git branch -M main
git remote add origin https://github.com/adrianmc/sib-poc.git
git push -u origin main
git tag v1.0.0
git push --tags
```
No subir el zip como archivo: se suben los archivos descomprimidos (los scripts deben verse en el repo).

**E0.1b Proyecto en Cloudera AI desde Git** (consola web de Cloudera AI)
Projects > New Project > nombre `sib-poc` > Initial Setup: **Git** > `https://github.com/adrianmc/sib-poc.git` > Create.
New Session > Runtime Python 3.10+ (JupyterLab), perfil 4 vCPU / 16 GB > Start > Terminal: `ls`
Valida: aparecen `README.md`, `config`, `fase2`, `fase3`, `lib` en `/home/cdsw`.
Para traer cambios posteriores del repo: `git pull` en la Terminal.

**E0.2 Dependencias** (AI, Terminal; primera sesion del proyecto recien creado)
```
cd /home/cdsw
chmod +x instalar.sh
./instalar.sh
```
Valida: termina con "Instalacion OK" y muestra la version de mlflow del runtime. Si pip responde con un conflicto,
no forzar nada: copiar el error y corregir el archivo de requisitos.
(El script guarda las versiones del runtime y las usa como restriccion: nunca actualiza paquetes de Cloudera.)

**E0.3 Configuracion** (AI)
```
cp config/config.ejemplo.yaml config/config.yaml
```
Editar `config/config.yaml` y reemplazar todos los `CAMBIAR`. Donde se obtiene cada valor:
| Clave | Donde |
|---|---|
| `s3.bucket` | Management Console > Environment > Summary > Storage (bucket de datos) |
| `impala.host_depto_a/b` | CDW > VW > menu ⋮ > Copy JDBC URL (tomar solo el host) |
| `impala.host_trino` | CDW > Trino VW > Copy JDBC URL |
| `datalake.knox_api` | Management Console > Data Lake > Endpoints > (base de cdp-proxy-api) |
| `cde.token_url`, `jobs_api_depto_a/b` | CDE > Virtual Cluster > Cluster Details > JOBS API URL; token: host del servicio + `/gateway/authtkn/knoxtoken/api/v1/token` |
| `kafka.brokers` | Data Hub Streams Messaging > Hardware (hosts broker, puerto 9093) |
| `inferencia.*` | AI Inference > Model Endpoints > Endpoint URL e ID del modelo |
| `usuarios.*.password` | workload password de cada usuario (E1) |

Buscar marcadores restantes en SQL y Markdown:
```
grep -rn "CAMBIAR" --include=*.sql --include=*.md --include=*.json . | wc -l
```
Reemplazar al menos `CAMBIAR_BUCKET` y la IP privada de la EC2 con SQL Server:
```
grep -rl "CAMBIAR_BUCKET" . | xargs sed -i 's/CAMBIAR_BUCKET/<bucket>/g'
grep -rl "CAMBIAR_SQLSERVER_IP_PRIVADA" . | xargs sed -i 's/CAMBIAR_SQLSERVER_IP_PRIVADA/<ip-privada-ec2>/g'
```

**E0.4 Certificado de Kafka (PEM)** (AI)
```
openssl s_client -showcerts -connect <broker1>:9093 </dev/null 2>/dev/null \
 | awk '/BEGIN CERT/,/END CERT/' > config/datahub-ca.pem
```
Para los jobs Spark se necesita el truststore JKS:
```
keytool -importcert -noprompt -alias datahub -file config/datahub-ca.pem \
 -keystore config/datahub-truststore.jks -storepass changeit
```
Valida: ambos archivos existen y no estan vacios. **(V)** si el PEM trae solo el certificado del broker y no la CA,
pedir el certificado de la CA del ambiente (Management Console > Environment > FreeIPA).

**E0.5 CLI de CDE** (AI)
Descargar el binario Linux desde CDE > Virtual Cluster > Cluster Details > CLI TOOL. Luego:
```
chmod +x cde && sudo mv cde /usr/local/bin/ 2>/dev/null || mv cde ~/.local/bin/
mkdir -p ~/.cde && cat > ~/.cde/config.yaml <<EOF
user: sb_ing01
vcluster-endpoint: <jobs_api_depto_a>
EOF
cde job list
```
Valida: pide la workload password y lista (vacio). Repetir con un segundo archivo de config para `vc-depto-b` si se usa.

**E0.6 Recursos CDE** (AI)
```
cde resource create --name sib-codigo
cde resource upload --name sib-codigo --local-path fase2/02_transacciones_masivas_spark.py \
  --local-path fase3/c02/c02_pipeline_batch.py \
  --local-path fase3/c01/cdc/c01_ae05_cdc_spark.py --local-path fase3/c02/c02_streaming_consumidor.py \
  --local-path config/datahub-truststore.jks
cde resource create --name sb-drivers
cde resource upload --name sb-drivers --local-path <ruta>/mssql-jdbc.jar
cde resource create --name sib-airflow
cde resource upload --name sib-airflow --local-path fase3/c02/c02_dag_airflow.py
```
Drivers: descargar `mssql-jdbc` (Microsoft) a la sesion. Si `--local-path` no acepta varios
valores en tu version **(V)**, subir uno por comando.
Valida: `cde resource describe --name sib-codigo` lista los archivos.

---

## E1 - Identidad y accesos

**E1.1 Usuarios y grupos en Keycloak** (Keycloak admin)
Crear grupos y usuarios de `fase2/10_usuarios_y_grupos.md`. Verificar el mapper de grupos en el cliente SAML de CDP.

**E1.2 Primer login** (navegador, cada usuario)
Cada uno de los 9 usuarios entra una vez a la consola de CDP y define su workload password (Profile > Set Workload Password).
Registrar las passwords en `config/config.yaml`.

**E1.3 Roles y sincronizacion** (Management Console)
Environment > Actions > Manage Access: roles por grupo segun la tabla de `fase2/10`. Luego Actions > Synchronize Users to FreeIPA.
Valida: Ranger > Settings > Users/Groups muestra los 9 usuarios y los grupos `sb_*` y `attr_*` (~5 min).

---

## E2 - Fuente SQL Server y datos

**E2.1 Base origen en SQL Server** (WIN: EC2 Windows Server con SQL Server 2022 Developer, en la VPC del ambiente)
- SSMS como sysadmin: ejecutar `fase2/03_sqlserver_origen.sql` (cambiar las 2 contrasenas antes).
  Valida: `is_cdc_enabled = 1` en `sbcore` y `is_tracked_by_cdc = 1` en clientes, cuentas y creditos.
- Prerrequisitos: autenticacion mixta, TCP 1433, SQL Server Agent en ejecucion, firewall de Windows y security group
  con 1433 abiertos al CIDR de la VPC.

**E2.2 Generar datos** (AI, perfil 4 vCPU / 16 GB, ~15 min)
```
python fase2/01_generar_datos.py --salida /home/cdsw/salida
cat /home/cdsw/salida/manifiesto.json
```
Valida: 1.000.000 clientes, 2.000.000 cuentas, 500.000 creditos, 1.000.000 transacciones en muestra.

**E2.3 Subir a S3** (AI; credenciales via IDBroker)
```
B=s3a://<bucket>/sb
hdfs dfs -mkdir -p $B/landing/rds $B/landing/transacciones/{csv,json,avro,parquet} $B/landing/maestras/{entidades,productos,excel} $B/landing/documentos
hdfs dfs -put -f /home/cdsw/salida/rds/*.csv $B/landing/rds/
for f in csv json avro parquet; do hdfs dfs -put -f /home/cdsw/salida/landing/transacciones/$f/* $B/landing/transacciones/$f/; done
hdfs dfs -put -f /home/cdsw/salida/landing/maestras/entidades_financieras.csv $B/landing/maestras/entidades/
hdfs dfs -put -f /home/cdsw/salida/landing/maestras/catalogo_productos.csv $B/landing/maestras/productos/
hdfs dfs -put -f /home/cdsw/salida/landing/maestras/catalogo_productos.xlsx $B/landing/maestras/excel/
hdfs dfs -put -f /home/cdsw/salida/landing/documentos/* $B/landing/documentos/
hdfs dfs -ls -R $B/landing | wc -l
```
Valida: ~20 archivos listados.

**E2.4 Cargar SQL Server** (AI Terminal, ~15-20 min: 3.5M filas)
```
python fase2/05_cargar_sqlserver.py
```
Valida: `clientes`, `cuentas` y `creditos` con los mismos conteos del manifiesto (SSMS: `SELECT COUNT(*) FROM dbo.<tabla>`).
Si se cuelga al conectar: revisar security group y firewall de Windows en 1433.

**E2.5 Volumen masivo** (CDE, ~10-20 min)
```
cde job create --name sib-masivo --type spark --application-file 02_transacciones_masivas_spark.py \
  --mount-1-resource sib-codigo --arg --bucket --arg <bucket> --arg --millones --arg 30
cde job run --name sib-masivo
```
Valida: termina en succeeded. Cubre: **PG-05, PG-06**.

---

## E3 - Lakehouse, tags y politicas

**E3.1 DDL** (HUE Impala `impala-depto-a`, sb_admin01)
Abrir `fase2/07_ddl_lakehouse.sql`, ejecutar todo. Luego en el editor **Hive** ejecutar el bloque comentado de `sb_raw.transacciones_json`.
Valida: la consulta final devuelve 250.000 por formato y 30.000.000 en `masivo`. Cubre: **C01-PRE-01/02, PG-07**.

**E3.2 Tags en Atlas** (AI) - esperar ~5 min tras E3.1 para que Atlas registre las tablas
```
python fase2/08_tags_atlas.py
```
Valida: cada columna con "OK". Si alguna da 404, esperar y repetir.

**E3.3 Politicas Ranger** (AI)
Antes: en Ranger UI confirmar los nombres de servicio (Hadoop SQL, TAG, Trino) y ajustarlos en config.
```
python fase2/09_politicas_ranger.py
```
Valida: todas "creada -> 200". Cubre: **PG-08, PG-09, C07-PRE-01..03**.
Hardening Trino: en Ranger > cm_trino, desactivar las politicas por defecto que dan acceso amplio a `{USER}`/`public` **(V)**.

---

## E4 - Smoke tests (Gate 1)

| # | Donde | Comando | Valida |
|---|---|---|---|
| 1 | AI | `python -c "from lib.sbpoc import consulta; print(consulta('SELECT COUNT(*) FROM sb_raw.transacciones_masivo'))"` | 30000000 |
| 2 | AI | `python -c "from lib.sbpoc import knox; s,u=knox('ranger'); print(s.get(u+'/service/public/v2/api/policy?policyNamePartial=sb_').status_code)"` | 200 |
| 3 | AI | `python -c "from lib.sbpoc import cde_token; print(len(cde_token('ingeniero'))>0)"` | True |
| 4 | AI | `python -c "from lib.sbpoc import consulta; print(consulta('SELECT 1', rol='analista', depto='b'))"` | VW depto B responde |
| 5 | AI | `curl -s -o /dev/null -w '%{http_code}' https://www.alphavantage.co` | 200 (salida a internet) |
| 6 | AI | `python -c "from lib.sbpoc import consulta; print(consulta('SELECT id_transaccion FROM sb_raw.transacciones_csv LIMIT 1'))"` | sin error |
| 7 | HUE Trino | `SHOW CATALOGS` | catalogo del lakehouse visible |
| 8 | WIN | Power BI Desktop > Obtener datos > Impala > host depto A | ve las bases `sb_*` |
| 9 | LAP | Claude Desktop con `fase3/c06/mcp/claude_desktop_config.json` (admin) > "lista las tablas" | responde con tablas |
| 10 | AI | sesion con perfil GPU: `nvidia-smi` | GPU listada |

Gate 1 = las 10 en verde.

---

## E5 - C01 Lakehouse e ingesta

**E5.1 CDC SQL Server** (Debezium SQL Server)
1. Topico de historia: SMM > Topics > Add New: `sbcore.historia.esquema` (1 particion). **(V)** el resto se autocrea.
2. SMM > Connect > New Connector > Debezium SQL Server: pegar el `config` de `fase3/c01/cdc/debezium_sqlserver.json`
   (sin la clave `_notas`; dejar solo el juego 1.x o 2.x que aplique). Estado esperado: RUNNING.
3. SMM > Topics: aparecen los topicos de `dbo.clientes`, `dbo.cuentas` y `dbo.creditos` con mensajes del snapshot inicial.
4. Consumidor (sin Spark/CDE): Terminal de CAI `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py` (micro-lotes + MERGE
   en Impala; requiere `kafka.brokers` y `kafka.ca_pem` = CA de FreeIPA). `c01_ae05_cdc_spark.py` queda como referencia CDE.
5. Esperar el snapshot (HUE): `REFRESH sb_curated.clientes; SELECT COUNT(*) FROM sb_curated.clientes;` = 1.000.000.
6. Prueba (WIN SSMS, base sbcore): `fase3/c01/cdc/c01_ae05_generar_cambios.sql`. Luego en HUE las consultas comentadas del mismo archivo.
Valida: solo cambian los ids 10, 20, 30, 40 y 9000001 (ver `cdc_ts`). Cubre: **C01-AE-05, PG-04**.

**E5.2 Cuentas para los pipelines** (si E5.1 se retrasa)
El pipeline necesita `sb_curated.clientes` y `cuentas`. Carga puente (HUE Impala), se reemplaza cuando el CDC funcione:
```sql
-- Solo si el CDC aun no corre: leer de los CSV crudos extraidos del origen
CREATE EXTERNAL TABLE IF NOT EXISTS sb_raw.clientes_csv (id_cliente BIGINT, identificacion STRING, nombre STRING, email STRING,
  telefono STRING, fecha_nacimiento STRING, region STRING, segmento STRING, ingreso_mensual DOUBLE, fecha_alta STRING,
  fecha_actualizacion STRING) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE
  LOCATION 's3a://<bucket>/sb/landing/rds/clientes_dir/' TBLPROPERTIES ('skip.header.line.count'='1');
```
(mover `clientes.csv` y `cuentas.csv` a subcarpetas propias en S3 antes de crear las tablas). Insertar a curada con CAST.

**E5.3 Operaciones del lakehouse** (HUE Impala, sb_ing01)
| Archivo | Valida | Cubre |
|---|---|---|
| `c01_ae03_operaciones_transaccionales.sql` | MERGE actualiza 5.000 e inserta 20.000; DESCRIBE HISTORY con un snapshot por operacion | C01-AE-03 |
| `c01_ae04_evolucion_esquema.sql` | SELECT tras ADD COLUMNS sin error, NULL en filas viejas | C01-AE-04 |
| `c01_ae07_metadatos.sql` | historial, archivos, particiones | C01-AE-07 |

**E5.4 Misma consulta en dos interfaces** (requiere E6.1 ejecutado)
HUE con sb_analista02: `c01_ae02_misma_consulta.sql`. AI: abrir `c01_ae02_notebook.py` en JupyterLab, poner el nombre de la
conexion Spark del proyecto (Project > Data) y ejecutar. Valida: mismas filas y valores. Cubre: **C01-AE-02**.

**E5.5 Ingesta NiFi a capa cruda** (timebox 4 h) - seguir `fase3/c01/c01_ae01_nifi_ingesta.md`, flujo A.
Prueba: `hdfs dfs -put` de un csv, json, xlsx y pdf a `s3a://<bucket>/sb/entrada/`. Valida: aparecen en `sb/landing/...`
y en Data Provenance. Cubre: **C01-AE-01**.

**E5.6 Lectura externa** (timebox 3 h, LAP)
1. HUE: ejecutar `fase3/c08/c08_acceso_externo.sql` (crea `sb_share.clientes_externo`).
2. Data Catalog > Data Sharing: crear share con esa tabla para `sb_externo01`; copiar URI y credenciales OAuth **(V)**.
3. LAP: `pip install "pyiceberg[pyarrow]"`, completar URI y credenciales en `fase3/c01/c01_ae06_lectura_externa.py` y ejecutar.
Valida: imprime esquema y 20 filas. Plan B: `c01_ae06_lectura_externa_duckdb.py`. Cubre: **C01-PRE-04, C01-AE-06**.

**E5.7 Federacion Trino** (opcional, 3 h)
Catalogo `sqlserver_core` (conector SQL Server de Trino, comunitario: declararlo) asociado al Trino VW. HUE Trino: `c01_federacion_trino.sql`.

---

## E6 - C02 Procesamiento

**E6.1 Pipeline batch** (AI)
```
cde job create --name sb-pipeline-batch --type spark --application-file c02_pipeline_batch.py \
  --mount-1-resource sib-codigo --mount-2-resource sb-drivers --conf spark.jars=/app/mount/mssql-jdbc.jar \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog \
  --conf spark.sql.catalog.spark_catalog.type=hive --conf spark.sql.iceberg.handle-timestamp-without-timezone=true \
  --arg --bucket --arg <bucket> --arg --jdbc-url --arg "jdbc:sqlserver://<ip-privada-ec2>:1433;databaseName=sbcore;encrypt=false" \
  --arg --jdbc-user --arg <usr> --arg --jdbc-password --arg <pwd> --arg --version --arg v1
cde job run --name sb-pipeline-batch
```
**(V)** si falla al leer Avro: agregar `--conf spark.jars.packages=org.apache.spark:spark-avro_2.12:<version_spark_vc>`.
Valida (HUE): `SELECT * FROM sb_consumption.pipeline_runs ORDER BY inicio DESC;` estado EXITOSO y
`SELECT COUNT(*) FROM sb_consumption.resumen_cliente_mensual;` > 0. Cubre: **C02-PRE-02/03, C02-AE-01**.

**E6.2 Orquestacion Airflow** (AI)
```
cde job create --name sb-orquestacion --type airflow --dag-file c02_dag_airflow.py --mount-1-resource sib-airflow
cde job run --name sb-orquestacion
```
Valida: Airflow UI del VC muestra el DAG `sb_orquestacion` en verde.

**E6.3 Fallo y recuperacion** (AI)
```
echo x > /tmp/m && hdfs dfs -put -f /tmp/m s3a://<bucket>/sb/control/fallar_paso_3
cde job run --name sb-orquestacion
```
Valida: run FALLIDO con mensaje "FALLO CONTROLADO en paso 3" en logs y en `pipeline_runs`. Luego:
```
hdfs dfs -rm s3a://<bucket>/sb/control/fallar_paso_3
python fase3/c05/validar_calidad.py
```
Valida: el reintento de Airflow termina OK y las 5 reglas de calidad en OK (sin duplicados). Cubre: **C02-PRE-05, C02-AE-05/06**.

**E6.4 Trigger por capa bronce** (AWS + AI)
1. AWS: S3 > bucket > Properties > Event notifications: ObjectCreated, prefijo `sb/landing/transacciones/`, destino SQS `sb-bronce-eventos`.
2. AI: Applications > New: script `fase3/c02/c02_trigger_bronce.py`, perfil 1 vCPU. **(V)** el rol del workspace necesita
   `sqs:ReceiveMessage` y `sqs:DeleteMessage`.
3. Prueba: `hdfs dfs -put -f /home/cdsw/salida/landing/transacciones/csv/*.csv s3a://<bucket>/sb/landing/transacciones/csv/nuevo.csv`
Valida: el log de la Application muestra "run sb-orquestacion: 200" y Airflow arranca un run. Cubre: **C02-AE-04**.

**E6.5 Streaming** (SMM + CDE + AI)
1. SMM > Topics > Add: `sb.transacciones.rt` (3 particiones).
2. CDE: igual que E5.1 paso 5 pero `--name sib-streaming-rt --application-file c02_streaming_consumidor.py`
   y args `--brokers <brokers> --usuario sb_ing01 --password <pwd> --bucket <bucket> --topico sb.transacciones.rt`.
3. AI:
```
python fase3/c02/c02_streaming_productor.py --eventos 2000 --por-segundo 20 &
python fase3/c02/c02_streaming_productor.py --medir --tasa-fondo 20
```
Valida: imprime "LATENCIA EXTREMO A EXTREMO: N s" y queda en `sb_consumption.latencia_streaming`.
Si no ve el evento en 60 s, repetir con `--refresh`. Cubre: **C02-PRE-01, C02-AE-02**.

**E6.6 Carga, recursos fijos y aislamiento** (CDW + AI, perfil 8 vCPU / 16 GB)
1. CDW > impala-depto-a > Edit: min = max ejecutores (recursos fijos).
2. `python fase3/c02/c02_prueba_carga.py --prueba recursos_fijos --niveles 50,100,150,200,250,300,350,400,450,500 --segundos 120`
3. CDW: liberar el maximo (autoscaling). `python fase3/c02/c02_prueba_carga.py --prueba autoscaling --niveles 50,500 --segundos 180`
4. Linea base sonda: `python fase3/c02/c02_prueba_carga.py --prueba sonda_base --niveles 1 --depto b --segundos 60`
5. Aislamiento: `python fase3/c02/c02_prueba_carga.py --prueba aislamiento --niveles 500 --segundos 300 --sonda-depto b`
Valida: CSV de cada prueba y filas en `sb_consumption.metricas_rendimiento`; Grafana del VW muestra el escalado;
p50 de la sonda B similar a su linea base. Cubre: **C02-PRE-04/06, C02-AE-03 (SQL), C02-AE-09, insumo de C02-AE-10, PG-14**.
Batch y streaming bajo carga: `fase3/c02/c02_ae03_carga_batch_streaming.md`.

**E6.7 Mostrar** (sin scripts): consulta ad-hoc y Query Profile (`c02_latencia_y_adhoc.sql`, **C02-AE-07**);
perfil GPU, escalado del grupo y detener sesion (**C02-AE-08**); APIs (**C02-AE-11**); Hue AI Assistant (**C02-AE-12**).

---

## E7 - C07 Seguridad (HUE, cambiando de usuario)
Ejecutar `fase3/c07/c07_pruebas_acceso.sql` con sb_analista02, sb_analista01 y sb_admin01 segun los comentarios.
Canal notebook (AI): `python fase3/c07/c07_ae03_notebook.py`.
Valida: Allowed/Denied esperados en Ranger > Audit > Access; mismo hash en Hue, notebook y Power BI (E8).
Cubre: **C07-AE-01..05**. C07-AE-06: completar `c07_ae06_diagrama_red_seguridad.md` con los CIDR reales.

---

## E8 - C04 Power BI y capa semantica
1. HUE (sb_admin01): `fase3/c04/c04_capa_semantica.sql`.
2. AI: `python fase3/c04/c04_glosario_atlas.py` (esperar ~5 min tras el paso 1).
3. Atlas: abrir la columna `saldo_pendiente` de `v_cartera_crediticia` > Classifications: debe heredar CONFIDENCIAL.
   Si no hereda, avisar: se agregan politicas por recurso sobre las vistas.
4. WIN: seguir `fase3/c04/c04_guia_powerbi.md` (DirectQuery con actualizacion automatica de pagina, Import, usuarios).
Valida: cambio en Hue visible solo en PBI; analista01 ve hash y no ve confidencial. Cubre: **C04-PRE-01..06, C04-AE-01/02/03/05/06**.

---

## E9 - C06 Ciencia de datos e IA (AI salvo indicacion)
| Paso | Comando / accion | Valida | Cubre |
|---|---|---|---|
| 1 | HUE con sb_cient01: `c06_ae01_join_enmascarado.sql` | JOIN con hashes y totales iguales a admin | AE-01 |
| 2 | `python fase3/c06/c06_ae04_entrenar_python.py` (como sb_cient01) | AUC impreso; Experiments > sb-riesgo-credito con run y tags de snapshot y commit; Model Registry version 1 | AE-04, PRE-03 |
| 3 | Sesion runtime R: `source("fase3/c06/c06_ae03_entrenar_r.R")`; luego Python: `python fase3/c06/c06_ae03_registrar_r.py` | AUC R impreso; segundo run "glm-R" | AE-03 |
| 4 | Models > New Model: archivo `fase3/c06/c06_ae05_modelo_endpoint.py`, funcion `predecir` | estado Deployed; prueba con el JSON de ejemplo | AE-05 |
| 5 | `python fase3/c06/c06_ae05_prueba_endpoint.py --url <url_modelo> --clave <access_key> --n 500 --hilos 10` | p50/p95, errores y throughput | AE-05 |
| 6 | Jobs > New Job: `fase3/c06/c06_ae06_drift.py`, argumentos `--simular`, notificacion por fallo al correo | job falla con "ALERTA DE DRIFT" y llega correo | AE-06 |
| 7 | Proyecto aparte `sib-poc-rag` desde el mismo Git; copiar `config/config.yaml`; Terminal: `./instalar.sh rag`, `mkdir -p /home/cdsw/data/documentos && hdfs dfs -get s3a://<bucket>/sb/landing/documentos/*.pdf /home/cdsw/data/documentos/` y `python fase3/c06/rag/indexar.py` | "Indice vectorial: N fragmentos" | PRE-05 |
| 8 | En `sib-poc-rag`: Applications > New: `fase3/c06/rag/app.py` | 4 preguntas de ejemplo: cita, fuera de alcance, rechazo | AE-07 |
| 9 | LAP: `fase3/c06/mcp/LEEME_MCP.md` | agente responde sin SQL; restringido ve hash | AE-08/09, PRE-06 |
Mostrar: proyecto compartido + Git para **C06-AE-02** (brecha declarada); modelo open source en AI Inference (**PRE-07**).

---

## E10 - C05 CI/CD (GitHub Actions)
El repo ya existe (E0.1). Seguir `fase3/c05/LEEME_CICD.md` desde el paso 3 (secret, environments, reglas de rama, runner) y su checklist.
Demo: rama `feature/ajuste-pipeline`, PR rojo (`monto: double` en el contrato) y verde, merge, aprobacion, rollback.
Datos: `fase3/c05/c05_versionado_datos.sql` en HUE. Cubre: **C05-PRE-01..06, C05-AE-01..06**.

---

## E11 - C08 Gobernanza
| Paso | Comando | Valida | Cubre |
|---|---|---|---|
| 1 | AI: `python fase3/c08/c08_registro_activos_y_linaje_bi.py` | 200/409 en tipos; Atlas muestra Gobierno_SB en clientes/creditos y linaje SQL Server -> curada -> vista -> dashboard | PRE-01/02, AE-01/02 |
| 2 | HUE: `c08_impacto_y_corrupcion.sql` (parte AE-03, luego AE-06 re-ejecutando `sb-pipeline-batch`) | vista dependiente falla; nombre corrupto en PBI; Ranger audit de sb_ing01; rollback restaura | AE-03/06 |
| 3 | AWS + `c08_auditoria_e_inmutabilidad.md` | delete en bucket WORM -> AccessDenied | AE-05, PRE-05 |
| 4 | Ranger > Audit > Access filtrando sb_analista01 | Allowed y Denied con fecha y recurso | AE-04 |
| 5 | Data Sharing (E5.6) + revocar el share y repetir la lectura | antes lee, despues denegado | AE-07 |
| 6 | AI: `python fase3/c08/c08_solicitud_acceso.py solicitar --usuario sb_analista01 --tabla sb_consumption.m_transaccionalidad_mensual --motivo "Informe"`, luego `listar` y `aprobar --id <id>` | sb_analista01 consulta la tabla tras ~30 s | AE-08 (workaround) |

---

## E12 - C03 Integraciones
1. AI: agregar `apis.alphavantage_key` en config y ejecutar `python fase3/c03/c03_ingesta_alphavantage.py`.
   Valida: 4 series con filas; `SELECT * FROM sb_curated.mercado_series LIMIT 10` en HUE. Para ensayos: `--desde-cache`.
2. AI: curl de `fase3/c03/c03_apis_y_diagramas.md` (token CDE, listar jobs, run). Cubre: **C03-AE-01/02, C03-PRE-02**.
3. Documental: diagramas Entra/SharePoint/D365/IDMC/CipherTrust del mismo archivo (**C03-AE-03..07**).

---

## E13 - C09 Operacion y FinOps
Seguir `fase3/c09/c09_runbooks.md`: costos y tags (AE-01), pico con `metricas_rendimiento` y la calculadora (AE-02),
cuello de botella con DROP STATS / COMPUTE STATS y Query Profile (AE-04). AE-05/06/07 se explican; AE-03 lo presenta el AE.

---

## E14 - Evidencias y dry-run
1. Dry-run completo con `GUION_DEMO.md`, cronometrando cada item y anotando fallos.
2. Capturas por item (pantalla + query profile o log) en una carpeta `evidencias/<codigo>/`.
3. Llenar la columna Comentario del Excel con: tipo de evidencia, origen (nativo/workaround/tercero), SKU, madurez y el valor observado.
4. Antes de cada sesion: `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache`, VWs y VCs encendidos, CDC y streaming corriendo.
5. Despues de cada sesion: suspender VWs, detener jobs streaming, apagar sesiones GPU.
