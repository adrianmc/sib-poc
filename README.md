# SIB PoC - Kit de Fase 2 (datos y seguridad base) y Fase 3 (casos C01-C09)

**Orden de lectura**
1. `PLAN_31_OCTUBRE.md` (seccion Calendario): que toca hoy y quien lo hace.
2. `RUNBOOK_IMPLEMENTACION.md`: como hacerlo, paso a paso, empezando por E0.1. Es el unico que se sigue al ejecutar.
3. Solo de consulta: `VALIDACION_ENTREGABLES.md` (estado y brechas por item) y `GUION_DEMO.md` (para el dry-run del 29).
El resto de archivos son los scripts que el runbook manda ejecutar.

Kit para la Plantilla de Escenarios de Demostracion de la Superintendencia de Bancos sobre Cloudera on cloud (AWS).
Todos los datos son **sinteticos**. Nada de este repositorio contiene datos reales.

## 1. Lo que necesito de las Fases 0 y 1 (checklist)
- [ ] Buckets de datos, logs y backup del ambiente
- [ ] Ambiente CDP con runtime **7.3.2** (incluye Iceberg REST Catalog y Data Sharing en Data Catalog) y tags `proyecto`, `ambiente`, `centro_costo`
- [ ] Keycloak (IdP SAML del ambiente demo) con usuarios y grupos de `fase2/10_usuarios_y_grupos.md`; sincronizacion de grupos al login activa en CDP
- [ ] Data Hub **Streams Messaging** (Kafka + Kafka Connect/Debezium + SMM) y Data Hub **Flow Management** (NiFi)
- [ ] CDW (ultima version): Database Catalog, VW Impala `impala-depto-a` y `impala-depto-b` con autoscaling (ver seccion 6), **VW Hive** (tabla JSON), Hue
- [ ] CDW: **Trino VW `trino-sb`** (auto-suspend OFF, minimo 1 worker), secreto registrado en el ambiente y Federation Connector certificado Oracle `oracle_core` asociado al VW
- [ ] NiFi (Flow Management): `mssql-jdbc.jar` copiado a todos los nodos; bucket con prefijo `sb/entrada/` para el buzon
- [ ] CDE: VC `vc-depto-a` y `vc-depto-b` con Airflow; recurso con `datahub-truststore.jks`
- [ ] CML workspace con grupo CPU y grupo **GPU (min 0)**; AI Inference Service con un LLM open source y un modelo de embeddings
- [ ] RDS Oracle (backups automaticos ON) y RDS SQL Server Standard/Enterprise, accesibles desde la VPC
- [ ] Cola SQS `sb-bronce-eventos` + notificacion S3 ObjectCreated del prefijo `sb/landing/transacciones/`
- [ ] EC2 Windows con Power BI Desktop, on-premises data gateway, SQL Developer/DBeaver y SSMS (scripts 03 y 04)
- [ ] Security group de RDS: 1521 y 1433 abiertos desde las subnets privadas del ambiente (CDE y Cloudera AI)
- [ ] Cloudera AI: perfil de recursos de 8 vCPU / 16 GB (prueba de 500 usuarios); recurso CDE `sb-drivers` con `ojdbc8.jar` y `mssql-jdbc.jar`
- [ ] GitHub: repo publico, secret CONFIG_YAML, environments sb-dev/test/prod (aprobador en prod), 2 usuarios y runner self-hosted en el EC2 Windows (`fase3/c05/LEEME_CICD.md`)
- [ ] Hue: SQL AI Assistant habilitado y apuntando a un modelo (C02-AE-12, PG-16)
- [ ] Cloudera AI: SMTP configurado en el workspace (notificaciones de Jobs para la alerta de drift, C06-AE-06)
- [ ] CDE: envio de linaje a Atlas activo (C08-AE-02); CDW: acceso kubeconfig al cluster (C09-AE-05)
- [ ] Cuota de instancias GPU (G and VT) aprobada en la region; runtime de Cloudera AI con CUDA
- [ ] Bucket de logs con versionado + bucket WORM con Object Lock y replicacion del prefijo `ranger/audit/` (ver c08)

## 2. Configuracion
1. Copiar `config/config.ejemplo.yaml` a `config/config.yaml` y completar todos los `CAMBIAR_*`. `config.yaml` no se versiona (`.gitignore`); en CML crearlo dentro del proyecto.
2. En SQL y Markdown, reemplazar `CAMBIAR_BUCKET` y demas marcadores con buscar y reemplazar de VS Code.
3. `pip install -r requirements.txt` en el proyecto de Cloudera AI (todos los scripts Python cliente corren ahi). En CML: crear el proyecto desde el repositorio Git;
   `lib/sbpoc.py` asume la raiz del proyecto en `/home/cdsw`.

## 3. Orden de ejecucion
**Fase 2** (ver pie de `fase2/10_usuarios_y_grupos.md`): 01 generar datos (Cloudera AI) -> 03/04 RDS -> 06 subir S3 ->
02 y 05b en CDE -> 07 DDL (Hue) -> 10 usuarios -> 08 tags Atlas -> 09 politicas Ranger.

**Fase 3** (orden de construccion por dependencias):
1. C01 CDC (conectores Debezium + job `c01_ae05_cdc_spark.py`) -> puebla `sb_curated.clientes` y `cuentas`
2. C02 pipeline batch + DAG + streaming + trigger + prueba de carga
3. C07 pruebas de acceso (valida las politicas de Fase 2)
4. C04 capa semantica + glosario + Power BI
5. C06 entrenamiento, endpoint, drift, RAG, MCP
6. C05 CI/CD con GitHub Actions (usa el pipeline de C02)
7. C08 linaje BI, impacto, acceso externo, solicitudes
8. C03 ingesta API + diagramas; C09 runbooks
9. Dry-run completo con `GUION_DEMO.md`

## 4. Honestidad tecnica incorporada en el kit
Cada script declara en su encabezado si la capacidad es nativa, workaround o integracion. Brechas no nativas:
metadata semantica heredada por Power BI (C04-AE-04), co-edicion en tiempo real de notebooks (C06-AE-02) y
flujo de solicitud de acceso en catalogo (C08-AE-08). Matices: herencia de identidad en Power BI Service (C04-AE-03),
masking en Spark directo sobre S3 (C07-AE-03), reintento (no continuacion) de consultas Impala ante perdida de nodo (C09-AE-05).

## 5. Lo que NO fue probado contra un ambiente real
El codigo se escribio contra las APIs y sintaxis documentadas, pero solo el generador de datos se ejecuto aqui.
Puntos con mayor probabilidad de ajuste en el primer intento: nombres de servicio Ranger (`cm_hive`/`cm_tag`),
propiedades Debezium segun version (1.x vs 2.x), paquete Kafka/Avro de Spark en CDE, URIs del REST Catalog,
y conexion HTTP/TLS del servidor MCP. Reporta el error exacto y se corrige.

## 6. Decisiones de arquitectura (por que cada servicio)

**Identidad: Keycloak.** Es el IdP de los ambientes demo de Cloudera. El patron (SAML con grupos en la asercion) es el
mismo que con Entra ID, que se presenta como escenario en C03-AE-03.

**Impala VW con autoscaling (WAA).** No es un tipo distinto de VW: es el modo de autoscaling del Impala VW normal.
Se usa porque la plantilla pide elasticidad (C02-PRE-04, C02-AE-03, C09-AE-02). Para la prueba de "recursos fijos"
(C02-PRE-06/AE-10) se fija minimo = maximo de ejecutores en el mismo VW, y luego se libera el maximo. Si la version
desplegada ofrece el autoscaling clasico en lugar de WAA, tambien cumple; WAA solo escala de forma mas fina por consulta.

**NiFi en Data Hub Flow Management (no Cloudera DataFlow).** Por simplicidad y costo: un cluster fijo pequeno, sin
habilitar otro data service. DataFlow sumaria despliegues por flujo con autoscaling y KPIs (reforzaria C02-AE-03 para
ingesta), pero exige habilitar el servicio y su consumo. Si el ambiente demo ya lo tiene, conviene usarlo.

**CI/CD: GitHub Actions** (sin acceso a Azure DevOps). Mismos scripts; `referencia_azure-pipelines.yml` muestra el equivalente.

**CDE: donde es necesario y donde solo se reutiliza**
| Uso | Por que CDE | Alternativa sin CDE |
|---|---|---|
| C02 pipeline batch (`c02_pipeline_batch.py`) + DAG Airflow | **Necesario**: Spark administrado con autoscaling de ejecutores/nodos, consola de ejecuciones con estado y logs (AE-05), reintentos de Airflow (AE-06), API para disparar (AE-04) y aislamiento por Virtual Cluster (PG-17) | Spark en Cloudera AI cubre el computo, pero no la orquestacion ni la consola de jobs que piden AE-01/05/06 |
| C05 destino de despliegue (`desplegar_cde.py`) | **Necesario**: el artefacto desplegado y versionado es el job de C02 | - |
| C01 CDC (`c01_ae05_cdc_spark.py`) y streaming (`c02_streaming_consumidor.py`) | Reutiliza: Spark Structured Streaming de larga duracion con monitoreo | NiFi (ConsumeKafka -> PutIceberg) o SQL Stream Builder (Flink); el MERGE de CDC es mas simple en Spark |
| Fase 2 masivo (`02`) y carga RDS (`05b`) | Reutiliza: ya existe el VC; carga paralela de 30M y 3.5M filas | Spark en una sesion de Cloudera AI, o NiFi (PutDatabaseRecord) para RDS |
