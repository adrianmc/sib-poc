# Plan de validacion y tiempos de entrega - PoC SIB

> **Calendario vigente: `PLAN_31_OCTUBRE.md`** (entrega 31 de octubre). Este archivo conserva el detalle de pasos y criterios de salida de cada bloque.

Objetivo: validar cada demostrable contra su criterio de exito **antes** de comprometer fechas con la SIB.
Equipo supuesto: Adrian (SE) + 1 ingeniero de apoyo, con Claude corrigiendo scripts sobre los errores reportados.
Duraciones en **dias habiles**. Cada bloque tiene criterio de salida (gate): no se avanza al siguiente sin cumplirlo.

## Supuesto vigente (2026-10-07)
El ambiente Cloudera (Data Lake, Data Hubs Streams Messaging y Flow Management, CDW con Impala/Hive/Trino, CDE,
Cloudera AI con GPU, AI Inference) se crea en **4 horas** con todos los recursos. Lo que queda es configuracion,
construccion y validacion. Equipo: 2 personas (SE + apoyo); con 1 persona los tiempos casi se duplican.

## Estimacion de esfuerzo

| Bloque | Contenido | Esfuerzo (persona-dias) | Calendario con 2 personas |
|---|---|---|---|
| B0 | Complementos AWS fuera de CDP: RDS Oracle y SQL Server, EC2 Windows con software, SQS, bucket WORM + replicacion; pedir cuota GPU el dia 0 si no viene incluida | 1 | Dia 1 (en paralelo con B1) |
| B1 | Configuracion post-ambiente: Keycloak y primeros logins, workload passwords, roles; Trino VW y conector Oracle; drivers en Kafka Connect y NiFi; recursos CDE; proyecto Cloudera AI, perfiles, SMTP; modelos en AI Inference; Hue AI Assistant; GitHub y runner | 2 | Dias 1-2 |
| B2 | Smoke tests (10 pruebas binarias) | 0.5 | Dia 3 - **Gate 1** |
| B3 | Fase 2: datos (1M/2M/500K + 30M), RDS, DDL, tags, politicas | 3 | Dias 3-5 |
| B4 | C01 ingesta: CDC, NiFi, Trino, operaciones Iceberg | 3 | Dias 6-7 - **Gate 2** |
| B5 | C02 pipelines, streaming, trigger, carga 50-500, GPU | 4 | Dias 8-10 |
| B6 | C07 seguridad + C04 Power BI | 3 | Dias 8-10 (en paralelo) |
| B7 | C06 Python/R, endpoint, drift, RAG, MCP | 4 | Dias 11-13 |
| B8 | C05 GitHub Actions | 1.5 | Dias 11-12 (en paralelo) |
| B9 | C08 gobierno, C03 integraciones, C09 operacion | 4 | Dias 13-15 - **Gate 3** |
| B10 | Dry-run 1 | 2 | Dias 16-17 |
| B11 | Correcciones, dry-run 2, Excel de evidencias, deck, PPT de carga | 5 | Dias 18-20 - **Gate 4** |
| | **Total** | **~33 persona-dias** | **~20 dias habiles (4 semanas)** |

**Compromiso recomendado con la SIB: 5 semanas** desde que el ambiente esta listo (4 de trabajo + 1 de holgura del 25%).
Minimo defendible: 4 semanas, aceptando mover C01-AE-06 o C09-AE-05 a 2DA PARTE si fallan en el primer intento.
Con una sola persona: 7 semanas.

Factores que pueden alargarlo (fuera del control del equipo):
- Respuestas de la SIB a las preguntas abiertas (segregacion dev/test/prod, Power BI Desktop/Service, volumen por formato).
- Primer contacto con Debezium sobre RDS Oracle (LogMiner): es el paso con mas probabilidad de ajustes (reservado 1 dia en B4).

**Dependencias del cliente** (pedirlas por escrito la primera semana):
| Pregunta | Necesaria antes de | Si no llega |
|---|---|---|
| Segregacion dev/test/prod | B8 (dia 11) | Logica en un ambiente y se declara |
| Power BI Desktop/Service y licencias | B6 (dia 8) | Solo Desktop; C04-AE-05 parcial |
| Volumen por formato | B3 (dia 3) | 30M Parquet + muestras |

---

## B0 - Complementos AWS (lo que no crea el ambiente Cloudera) - 1 dia - Adrian
| Paso | Accion | Criterio de salida |
|---|---|---|
| 0.1 | **Dia 1:** solicitar cuota G and VT (GPU) y vCPU On-Demand en la region | Ticket abierto (aprobacion 2-5 dias, corre en paralelo) |
| 0.2 | VPC /16, 3 subnets privadas /19 y publicas con NAT | Subnets en 3 AZ |
| 0.3 | Buckets: datos, logs (versionado + lifecycle), backup; bucket WORM con Object Lock + replicacion `ranger/audit/` | `aws s3api get-object-lock-configuration` OK en WORM |
| 0.4 | IAM (rol cross-account, IDBroker, roles de Data Lake) y CMK en KMS | Politicas generadas desde la consola CDP |
| 0.5 | RDS Oracle (backups ON) y SQL Server Standard; SG con 1521/1433 desde subnets privadas | Conexion desde EC2 Windows |
| 0.6 | EC2 Windows (Power BI Desktop, gateway, SQL Developer, SSMS) | RDP OK |
| 0.7 | Keycloak: usuarios y grupos de `fase2/10`; mapper de grupos al cliente SAML de CDP | Login SSO de un usuario de prueba con sus grupos visibles en CDP |
| 0.8 | SQS `sb-bronce-eventos` + notificacion S3 | Mensaje de prueba recibido |

## B1 - Configuracion post-ambiente - 2 dias - Adrian + apoyo
Si el ambiente ya viene creado, este bloque es solo la configuracion. Referencia del orden completo: credencial + IdP -> ambiente/Data Lake (runtime con REST Catalog) -> Data Hubs Streams Messaging y Flow Management ->
CDW (ultima version: Impala A/B con WAA, Hive VW, **Trino VW**) -> CDE (VC A/B con Airflow) -> Cloudera AI (CPU + GPU min 0)
-> AI Inference (LLM + embeddings) -> GitHub (repo, secret, environments, runner self-hosted: `fase3/c05/LEEME_CICD.md`).
Criterio de salida: todos los servicios en estado Running y la ficha tecnica del ambiente (PG-03) llenada con valores reales.

## B2 - Smoke tests de plataforma - medio dia - Adrian (Gate 1)
Cada prueba es binaria. Si una falla, se corrige antes de cargar datos.
| # | Prueba | Como | OK si |
|---|---|---|---|
| 2.1 | Impala por HTTP/LDAP | `python -c "from lib.sbpoc import consulta; print(consulta('SELECT 1'))"` en Cloudera AI | Devuelve `[(1,)]` |
| 2.2 | Knox -> Ranger y Atlas | curl de `c03_apis_y_diagramas.md` (listar politicas, buscar entidades) | HTTP 200 |
| 2.3 | NiFi | Flujo minimo GenerateFlowFile -> PutS3Object al bucket | Archivo en S3 |
| 2.4 | Trino | En Hue/Trino: `SHOW CATALOGS` y `SELECT 1 FROM oracle_core...` tras crear el conector | Catalogo visible y consulta OK |
| 2.5 | CDE | Token + `GET /jobs` | HTTP 200 |
| 2.6 | Red a RDS desde EKS | Job CDE minimo con `spark.read.jdbc` a Oracle y SQL Server | Cuenta filas sin timeout |
| 2.7 | Kafka | Productor de prueba desde Cloudera AI con el CA PEM | Mensaje visible en SMM |
| 2.8 | GPU | Sesion con perfil GPU: `nvidia-smi` | GPU listada (si la cuota no llego, registrar riesgo) |
| 2.9b | Salida a internet desde Cloudera AI | `curl -s https://www.alphavantage.co` en la Terminal de la sesion | Responde (si no: revisar NAT/proxy) |
| 2.9 | MCP | Claude Desktop con `sb-lakehouse-admin` y `get_schema` | Lista tablas |
| 2.10 | Nombres de servicios Ranger | Ranger UI: cm_hive, cm_tag, cm_trino | Coinciden con config o se corrige config |

## B3 - Datos y seguridad base (Fase 2) - 3 dias - Adrian + apoyo
| Paso | Accion | Criterio de salida |
|---|---|---|
| 3.1 | `01_generar_datos.py` (escala 1) en Cloudera AI; subir a S3 (`06`) | Manifiesto con 1M/2M/500K |
| 3.2 | `03`/`04` en RDS; `05b_cargar_rds_spark.py` en CDE | Conteos en Oracle y SQL Server = CSV |
| 3.3 | `02_transacciones_masivas_spark.py --millones 30` | `COUNT(*)` de `sb_raw.transacciones_masivo` = 30M |
| 3.4 | `07_ddl_lakehouse.sql` (Impala) + tabla JSON en Hive | Consulta de validacion final del script OK |
| 3.5 | Usuarios en Keycloak (`10`), primer login de cada uno en CDP, Sync FreeIPA, workload passwords | Login en Hue con los 9 usuarios |
| 3.6 | `08_tags_atlas.py` y `09_politicas_ranger.py` (incluye 10 y 11 de Trino) | Todas las politicas creadas (HTTP 200) |
| 3.7 | Prueba rapida: `SELECT identificacion FROM sb_curated.clientes` con sb_analista01 vs sb_admin01 (tras cargar clientes en B4) | Hash vs claro |

## B4 - Ingesta y lakehouse (C01, PG-10) - 3 dias - apoyo
| Paso | Artefacto | Criterio de salida (= criterio SIB) |
|---|---|---|
| 4.1 | Debezium Oracle/SQL Server + `c01_ae05_cdc_spark.py` | Snapshot inicial puebla `sb_curated.clientes/cuentas`; `c01_ae05_generar_cambios.sql` cambia solo 5 filas (ver `cdc_ts`) |
| 4.2 | NiFi flujo A | 4 tipos de archivo aterrizan en la capa cruda sin intervencion |
| 4.3 | NiFi flujo B | Segunda ejecucion ingesta solo los 5 creditos nuevos |
| 4.4 | `c01_federacion_trino.sql` | Consulta federada OK; masking en Oracle para sb_analista02; cambio en Oracle visible al instante |
| 4.5 | `c01_ae02`, `ae03`, `ae04`, `ae07` | Mismos resultados Hue vs notebook; MERGE con filas actualizadas e insertadas; ADD COLUMNS sin error |
| 4.6 | `c01_ae06_lectura_externa.py` desde laptop | Lee `sb_share.clientes_externo` via REST Catalog (si falla: riesgo a 2DA PARTE) |
Gate 2: 4.1, 4.2 y 4.5 en verde.

## B5 - Pipelines y carga (C02) - 4 dias - apoyo
| Paso | Artefacto | Criterio de salida |
|---|---|---|
| 5.1 | `c02_pipeline_batch.py` + DAG | Fila EXITOSO en `pipeline_runs`; salida en `resumen_cliente_mensual` |
| 5.2 | Fallo y recuperacion | Marcador paso 3 -> FALLIDO con mensaje; sin marcador -> retry OK; `validar_calidad.py` sin duplicados |
| 5.3 | Trigger bronce | Archivo nuevo en landing dispara `sb-orquestacion` en < 1 min |
| 5.4 | Streaming + `--medir` | Fila en `latencia_streaming`; anotar valor real (umbral a proponer a la SIB) |
| 5.5 | `c02_prueba_carga.py --niveles 50,100,...,500` (recursos fijos) | CSV completo; insumo de la PPT C02-AE-10 |
| 5.6 | Autoscaling y aislamiento (`--sonda-depto b`) | Grafana muestra escalado; sonda B sin degradacion relevante |
| 5.7 | `c02_ae03_carga_batch_streaming.md` | Antes/despues batch y streaming medidos |
| 5.8 | GPU (`c06_gpu_entrenamiento.py` cuda vs cpu) | Tiempos comparados; grupo GPU vuelve a 0 al detener |

## B6 - Seguridad y Power BI (C07, C04) - 3 dias - Adrian
| Paso | Artefacto | Criterio de salida |
|---|---|---|
| 6.1 | `c07_pruebas_acceso.sql` con 3 usuarios | Allowed/Denied esperados visibles en Ranger Audit |
| 6.2 | `c04_capa_semantica.sql` + `c04_glosario_atlas.py` | Vistas y terminos de glosario asignados |
| 6.3 | Validar propagacion de tags a vistas | Si no propaga: politicas por recurso sobre las vistas (se ajusta script) |
| 6.4 | Power BI: .pbix DirectQuery + Import, actualizacion automatica de pagina | Cambio en Hue visible solo; refresh Import con tiempos |
| 6.5 | Mismo dato en SQL, PBI y notebook (C07-AE-03) | Mismo hash en los 3 canales |

## B7 - Ciencia de datos e IA (C06) - 4 dias - apoyo
| Paso | Criterio de salida |
|---|---|
| 7.1 Python + R + registro | Experimento con 2 corridas (Python y R); modelo Python versionado en Registry con snapshot y commit |
| 7.2 Endpoint + prueba de carga | p50/p95, errores y throughput medidos |
| 7.3 Drift `--simular` | Job falla con alerta y llega el correo |
| 7.4 RAG (indexar + app) | Pregunta valida con cita; fuera de alcance y sensible rechazadas; calibrar `UMBRAL_SIMILITUD` |
| 7.5 MCP dos instancias | Agente responde sin SQL manual; restringido ve hash, admin ve claro; Ranger Audit con sb_mcp01 |

## B8 - DevOps (C05, GitHub Actions) - 1.5 dias - Adrian (Gate 3 al cerrar B7 y B8)
| Paso | Criterio de salida |
|---|---|
| 8.1 | Repo con ramas main/feature y tag `v1.0.0` desplegado en prod |
| 8.2 | PR con contrato roto -> rojo; PR correcto -> verde con deploy a DEV verificado |
| 8.3 | Merge -> TEST -> pausa en sb-prod hasta que apruebe el segundo usuario |
| 8.4 | Rollback con `rollbackRef=v1.0.0` -> job apunta al recurso previo; `sb_gov.despliegues` con ambas versiones |
| 8.5 | `c05_versionado_datos.sql` | Time travel y EXECUTE ROLLBACK restauran conteos |

## B9 - Gobierno, integraciones y operacion (C08, C03, C09) - 4 dias - Adrian + apoyo
| Paso | Criterio de salida |
|---|---|
| 9.1 `c08_registro_activos_y_linaje_bi.py` | Linaje Oracle -> curada -> consumo -> dashboard visible en Atlas |
| 9.2 `c08_impacto_y_corrupcion.sql` | Vista dependiente falla y aparece downstream; dato corrupto llega a PBI; audit de sb_ing01; rollback OK |
| 9.3 Auditoria e inmutabilidad | Borrado en bucket WORM -> AccessDenied |
| 9.4 Acceso externo + revocacion | Externo lee tabla enmascarada; tras eliminar politica, denegado |
| 9.5 Solicitud de acceso (workaround) | Solicitar -> aprobar -> acceso valido |
| 9.6 C03: `c03_ingesta_alphavantage.py` (y `--sin-clave` para mostrar el error accionable) + curl de APIs + diagramas Entra/SharePoint/D365/IDMC/CipherTrust | Tabla `sb_raw.api_*` poblada; diagramas revisados |
| 9.7 C09 cuello de botella y perdida de nodo | Profile antes/despues; consulta reintentada y nodo reemplazado |
| 9.8 C09 costos | Reporte de consumo por VW/VC y tags; costo base vs pico con la calculadora (AE) |

## B10 - Dry-run 1 - 2 dias - todo el equipo
Ejecutar `GUION_DEMO.md` completo en tiempo real (20-22 h repartidas). Registrar por item: OK / fallo / tiempo real.
Salida: lista de defectos priorizada.

## B11 - Correcciones, dry-run 2 y evidencias - 5 persona-dias, 3 dias de calendario (Gate 4)
- Corregir defectos (Claude ajusta scripts sobre el error exacto).
- Dry-run 2 sin interrupciones.
- Llenar la columna Comentario del Excel (tipo de evidencia, origen, SKU, madurez) con valores observados.
- Deck PG-01, PPT C02-AE-10, ficha PG-03, evidencia documental PG-13, lista de conectores C03-PRE-01.
Salida: aprobacion interna (SE + AE) y confirmacion de fecha a la SIB.

## Reglas para no correr
1. No se da fecha firme a la SIB hasta pasar **Gate 1** (dia 3). Antes solo se comparte el plan de 5 semanas.
2. Si un bloque se atrasa > 2 dias, se decide en el momento: recortar alcance (2DA PARTE) o mover fecha. No se comprime el dry-run.
3. Items candidatos a 2DA PARTE si aprieta el tiempo: C01-AE-06 (REST Catalog), C09-AE-05 (perdida de nodo).
4. Apagar VWs, VCs y grupo GPU fuera de horario para no consumir creditos entre ensayos.
