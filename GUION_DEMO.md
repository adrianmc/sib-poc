# Guion de demo por item (Fase 3)

Estado de cumplimiento por item y preguntas abiertas: ver `VALIDACION_ENTREGABLES.md`. Calendario: `PLAN_31_OCTUBRE.md`; pasos y criterios de salida: `PLAN_VALIDACION.md`.

Convencion: **Herramienta** indica donde se ejecuta. "Evidencia" es lo que se anota en la columna Comentario del Excel
(tipo de evidencia, origen nativo/workaround/tercero, licencia/SKU y madurez).

## Precondiciones generales (PG)
| Codigo | Como se cubre |
|---|---|
| PG-02/03/17 | Ambiente `sb-poc` + slide de capacidades (region, Data Lake, VW depto A/B con WAA, VC A/B, workspace CPU/GPU) |
| PG-04/05/06/07 | Fase 2 completa: RDS, S3 multiformato, 20-50M transacciones (Delta: declarar no nativo) |
| PG-08/09 | `fase2/10_usuarios_y_grupos.md`, tags Atlas + politicas Ranger |
| PG-10 | Power BI Desktop + DBeaver + CML sobre el mismo VW |
| PG-12 | Este repositorio en GitHub |
| PG-14 | `sb_consumption.pipeline_runs`, `metricas_rendimiento`, query profiles |
| PG-15/16 | Tabla de APIs (`c03_apis_y_diagramas.md`) + funciones de IA (Hue SQL AI Assistant, Copilot CML, RAG, MCP) |

## C01 Lakehouse
| Codigo | Herramienta | Accion | Artefacto | Evidencia |
|---|---|---|---|---|
| AE-01 | NiFi + Hue | Copiar CSV, JSON, XLSX y PDF al buzon; NiFi los aterriza en la capa cruda (Provenance); consultar `sb_raw.*` | `c01_ae01_nifi_ingesta.md` (flujo A) | Nativo |
| AE-02 | Hue + CML | Misma consulta en Impala y en notebook (impyla y Spark) | `c01_ae02_*` | Nativo; una sola ubicacion fisica |
| PG-10 / plus | Hue (Trino) | Oracle vivo + Iceberg en una consulta; ETL NiFi SQL Server -> `sb_raw.creditos_nifi` | `c01_federacion_trino.sql`, flujo B NiFi | Nativo (Trino: confirmar madurez) |
| AE-03 | Hue | INSERT/UPDATE/DELETE/MERGE desde CSV, Avro, Parquet | `c01_ae03_*.sql` | Nativo (Iceberg V2) |
| AE-04 | Hue | ADD COLUMNS + rename, consultas sin error | `c01_ae04_*.sql` | Nativo |
| AE-05 | SQL Developer + Hue | Cambios en Oracle -> solo esos registros en curada | `cdc/*` | Componentes nativos, ensamblaje con desarrollo |
| AE-06 | Laptop externa | PyIceberg via REST Catalog (plan B: DuckDB directo a S3) | `c01_ae06_*.py` | Nativo (runtime 7.3.2) |
| AE-07 | Hue + Atlas | DESCRIBE HISTORY/FILES/PARTITIONS, Atlas | `c01_ae07_*.sql` | Nativo |
| AE-08 | Terminal | CDP CLI + CDE API + Atlas/Ranger REST | `c03_apis_y_diagramas.md` | Nativo |

## C02 Procesamiento
| Codigo | Herramienta | Accion | Artefacto |
|---|---|---|---|
| AE-01 | CDE + Airflow | Ejecutar `sb_orquestacion`; mostrar inicio/fin/estado y `pipeline_runs` | `c02_pipeline_batch.py`, `c02_dag_airflow.py` |
| AE-02 | Terminal + Hue | `c02_streaming_productor.py --medir` y consulta de latencia | `c02_streaming_*`, `c02_latencia_y_adhoc.sql` |
| AE-03 | Terminal + Grafana + CDE | SQL, batch y streaming antes/despues | `c02_ae03_carga_batch_streaming.md` |
| AE-04 | S3 + CML App | Subir un archivo a `landing/transacciones/csv/` -> se dispara el DAG | `c02_trigger_bronce.py` |
| AE-05 | Terminal + CDE | `aws s3 cp` de un archivo vacio a `s3://CAMBIAR_BUCKET/sb/control/fallar_paso_3` -> fallo con mensaje accionable | `c02_pipeline_batch.py` |
| AE-06 | Terminal + Airflow | Borrar el marcador; el reintento de Airflow termina OK; conteos sin duplicados (`validar_calidad.py`) | idem |
| AE-07 | Hue | Consulta ad-hoc + Query Profile (sin materializacion) | `c02_latencia_y_adhoc.sql` |
| AE-08 | Cloudera AI | Sesion con perfil GPU (grupo min 0): `c06_gpu_entrenamiento.py --dispositivo cuda` vs `cpu`; detener sesion y ver el grupo volver a 0; costo por tags AWS | `c06_gpu_entrenamiento.py` |
| AE-09 | Terminal + Grafana | Linea base de la sonda (`--niveles 1 --sonda-depto b`) y luego 500 usuarios en A con sonda en B | `c02_prueba_carga.py --sonda-depto b` |
| AE-10 | PPT | Curva 50->500 usuarios con recursos fijos (desde `metricas_rendimiento`) | resultados CSV |
| AE-11/12 | Terminal + Hue | APIs; SQL AI Assistant en Hue (texto a SQL, explicar, optimizar) | - |

## C03 Integraciones
| Codigo | Accion | Artefacto |
|---|---|---|
| AE-01 | Tabla de APIs + curl en vivo (token CDE, lista de jobs, run) | `c03_apis_y_diagramas.md` |
| AE-02 | Ingesta de 4 endpoints de Alpha Vantage (API key) a `sb_raw.api_alphavantage` y `sb_curated.mercado_series`; luego consulta en Hue | `c03_ingesta_alphavantage.py` |
| AE-04 / AE-05 | Escenario de conexion SharePoint (Graph) y D365 (Dataverse) - documental | `c03_apis_y_diagramas.md` |
| AE-03 | Login SSO SAML con Keycloak (grupos visibles en CDP y Ranger) + diagrama del escenario Entra ID | `c03_apis_y_diagramas.md` |
| AE-06 / AE-07 | Arquitectura IDMC y CipherTrust (documental) | diagramas |

## C04 Analitica y Power BI
Ver `fase3/c04/c04_guia_powerbi.md` (AE-01 a AE-06) y `c04_capa_semantica.sql`, `c04_glosario_atlas.py`.

## C05 DevOps
Ver `fase3/c05/LEEME_CICD.md` (GitHub Actions, AE-01 a AE-06).

## C06 Ciencia de datos e IA
| Codigo | Herramienta | Accion | Artefacto |
|---|---|---|---|
| AE-01 | Hue (sb_cient01) | JOIN/GROUP BY sobre PII enmascarada | `c06_ae01_*.sql` |
| AE-02 | CML | **Brecha declarada:** no hay co-edicion en tiempo real. Mostrar proyecto compartido: sb_cient01 hace commit, sb_cient02 hace pull y ejecuta en su sesion | Git |
| AE-03 | Cloudera AI (runtime R) | `c06_ae03_entrenar_r.R` y luego `c06_ae03_registrar_r.py` (corrida R en el mismo experimento) | - |
| AE-04 | CML | `c06_ae04_entrenar_python.py` -> Experiments + Model Registry (snapshot Iceberg + commit en tags) | - |
| AE-05 | CML Models | Desplegar `predecir`, correr `c06_ae05_prueba_endpoint.py`, mostrar metricas del modelo | - |
| AE-06 | CML Jobs | Job `c06_ae06_drift.py --simular` con notificacion por fallo | - |
| AE-07 | CML App | `rag/indexar.py` + `rag/app.py`: pregunta valida, fuera de alcance y sensible | - |
| AE-08/09 | Claude Desktop | Dos servidores MCP (restringido/admin) | `mcp/LEEME_MCP.md` |

## C07 Seguridad
`c07_pruebas_acceso.sql` (AE-01, 02, 04, 05), `c07_ae03_notebook.py` + Power BI (AE-03), `c07_ae06_diagrama_red_seguridad.md` (AE-06).

## C08 Gobernanza
| Codigo | Artefacto |
|---|---|
| AE-01 / PRE-01/02 | `c08_registro_activos_y_linaje_bi.py` + tags (fase2/08) + glosario (c04) |
| AE-02 / AE-06 | Atlas Lineage + `c08_impacto_y_corrupcion.sql` |
| AE-03 | `c08_impacto_y_corrupcion.sql` (parte AE-03) |
| AE-04 / AE-05 / PRE-05 | `c08_auditoria_e_inmutabilidad.md` |
| AE-07 | `c08_acceso_externo.sql` + `fase2/09_politicas_ranger.py fase3/c08/c08_politica_externo_temporal.json` + `c01_ae06_lectura_externa.py` |
| AE-08 | `c08_solicitud_acceso.py` (workaround declarado) |

## C09 Administracion y FinOps
Ver `fase3/c09/c09_runbooks.md` (AE-01 a AE-07). AE-03 lo presenta el AE.
