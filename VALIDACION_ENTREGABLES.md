# Validacion de entregables contra la plantilla de la SIB

Fecha de revision: 2026-10-05. Base: criterios de exito de la plantilla (PG, C01-C09) contra el kit `sb-poc`.

**Veredictos**
- **OK**: el demostrable responde el criterio tal como esta redactado (indica nativo o workaround).
- **PARCIAL**: responde una parte; la brecha se declara en el Comentario.
- **NO SE PUEDE**: la plataforma no lo cumple de forma nativa; se declara y se muestra el workaround si existe.
- **PENDIENTE**: falta un entregable que no es codigo (PPT, documento, .pbix) o una decision.
- **2DA PARTE**: propuesto para sesion evaluable posterior (requiere decision de Adrian/AE).

"Validar en ensayo" = escrito contra la documentacion; solo se confirma ejecutandolo en el ambiente.

## Precondiciones generales
| Codigo | Criterio (resumen) | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|---|
| PG-01 | PPT introductoria | - | PENDIENTE | Construir deck |
| PG-02 | Sandbox exclusivo con workspace | Fase 0/1 | OK | - |
| PG-03 | Declarar capacidades de la instancia | - | PENDIENTE | Ficha tecnica del ambiente (region, runtime, VW/VC/workspace, autoscaling, limites). Se arma al cerrar Fase 1 |
| PG-04 | Conectores preconfigurados | Debezium, JDBC, Graph/Dataverse | OK | - |
| PG-05 | Datos sinteticos | fase2/01, 02 | OK | - |
| PG-06 | 10M-50M "segun tipo de archivo" | 30M Parquet (cruda) e Iceberg (curada); muestras en otros formatos | OK | Justificacion: formatos columnares recomendados para analitica |
| PG-07 | CSV/Excel/JSON/Parquet/PDF/PNG/Iceberg/Delta/Avro | fase2/01, 07 | PARCIAL | Delta: NO SE PUEDE nativo. Todo lo demas OK |
| PG-08 | Usuarios por rol (admin, ingeniero, cientifico, analista, auditor) | fase2/10 | OK | - |
| PG-09 | Permisos por rol y atributo | politicas 01-08 | OK | - |
| PG-10 | Clientes SQL Server, Oracle, Power BI y notebook al mismo entorno | RDS (CDC/JDBC/NiFi) + Trino federado + PBI + Cloudera AI | OK | Definido: son bases origen. Plus: consulta federada Oracle + Iceberg (`c01_federacion_trino.sql`). Oracle con conector certificado; SQL Server via Trino solo comunitario (declarar) |
| PG-11 | Definicion dev/test/prod y dominios/equipos | diagrama + jobs y politicas por ambiente | OK | Fisica o logica, declarado; demo logica |
| PG-12 | Directorio de scripts | repositorio | OK | - |
| PG-13 | Evidencia documental oficial | - | PENDIENTE | Lista de enlaces oficiales (docs, SLA, casos). No se inventan URLs: armar con fuentes vigentes |
| PG-14 | Logs de rendimiento, latencia y consumo | pipeline_runs, metricas_rendimiento, latencia_streaming | PARCIAL | Consumo de recursos (CPU/memoria) queda en Grafana/Spark UI, no persistido en tabla. Validar si el VW expone `sys.impala_query_log` |
| PG-15 | Funcionalidades APIficadas | c03_apis_y_diagramas.md | OK | - |
| PG-16 | Funcionalidades con IA | GUION | PARCIAL | Falta lista formal; Hue AI Assistant requiere configuracion en Fase 1 |
| PG-17 | 2 tenants | VW/VC depto A y B | OK | - |

## C01 Lakehouse
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01 capas | fase2/07 | OK | - |
| PRE-02 formatos y ubicacion | fase2/07 | OK | - |
| PRE-03 conectores | Debezium/JDBC | OK | - |
| PRE-04 segundo motor | PyIceberg via REST Catalog | OK | Runtime 7.3.2 |
| AE-01 estructurado + semi + no estructurado en cruda, sin conversion, reutilizables | `c01_ae01_nifi_ingesta.md` (flujo A) | OK | Ingesta por NiFi para CSV, JSON, Excel, PDF/PNG. PDF/PNG como activo via Atlas (c08). JSON consultable en Hive |
| AE-02 misma consulta en interfaces, sin duplicar | c01_ae02 | OK (corregido) | Se cambio NDV por COUNT(DISTINCT): NDV es aproximado y daria resultados distintos entre motores |
| AE-03 insert/update/upsert/merge desde distintos formatos | c01_ae03 | OK (corregido) | El MERGE original no tenia llaves coincidentes (solo insertaba). Ahora ejercita UPDATE e INSERT |
| AE-04 schema evolution | c01_ae04 | OK | - |
| AE-05 CDC automatico, solo cambios | cdc/* | OK workaround | Componentes nativos, ensamblaje con desarrollo. Validar en ensayo propiedades Debezium segun version |
| AE-06 lectura externa sin exportar | c01_ae06 (REST Catalog) / duckdb (plan B) | OK (validar en ensayo) | Nativo en runtime 7.3.2 |
| AE-07 metadatos tecnicos | c01_ae07 | OK | - |
| AE-08 APIs | c03 doc | OK | - |

## C02 Procesamiento
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01..05 | kit | OK | - |
| PRE-06 doc/PPT 50->500 recursos fijos | c02_prueba_carga | PENDIENTE | Se genera tras correr la prueba |
| PRE-07 workload GPU | c06_gpu_entrenamiento.py | OK (agregado) | No existia; ahora XGBoost CUDA vs CPU |
| AE-01 batch con inicio/fin/estado, full outer, row_number, distinct | c02_pipeline_batch | OK | - |
| AE-02 latencia hasta zona consumible | productor --medir | OK (corregido) | Antes media en curada y no persistia. Ahora vista en `sb_consumption` + tabla `latencia_streaming` |
| AE-03 carga batch y streaming antes/despues, sin intervencion | c02_ae03_carga_batch_streaming.md | PARCIAL | SQL y batch nativos; brokers Kafka no autoescalan |
| AE-04 trigger por capa bronce | c02_trigger_bronce | OK workaround | S3 event + SQS + API CDE |
| AE-05 fallo visible con mensaje accionable | marcador S3 | OK | - |
| AE-06 sin perdida ni duplicados | overwritePartitions + retries + validar_calidad | OK | - |
| AE-07 ad-hoc sin materializar | c02_latencia_y_adhoc + c01_federacion_trino | OK | Plus: consulta sobre Oracle vivo sin copia (EXPLAIN muestra scan remoto) |
| AE-08 GPU asignar/escalar/apagar, costo | c06_gpu + perfil GPU | OK | Costo por tags AWS, no dentro de Cloudera AI |
| AE-09 tenant A no impacta B | prueba_carga --sonda-depto | OK (agregado) | No existia la medicion en B |
| AE-10 PPT por cada 50 usuarios | resultados CSV | PENDIENTE | Niveles por defecto saltan de 50 a 100, 200...: para "cada 50" usar `--niveles 50,100,150,...,500` |
| AE-11 APIs | c03 doc | OK | - |
| AE-12 IA de la plataforma | Hue AI Assistant | PARCIAL | Asistente (texto a SQL, explicar, optimizar); no autonomo |

## C03 Integraciones
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01 lista de conectores | Trino (certificados/comunitarios) + NiFi + Kafka Connect | PARCIAL | Base disponible: lista oficial de conectores Trino. Falta consolidar documento con NiFi y Debezium |
| PRE-02..07 | c03_apis_y_diagramas | OK | - |
| AE-01 APIs + prueba | curl | OK | - |
| AE-02 API externa autenticada -> tabla | `c03_ingesta_alphavantage.py` | OK (validar en ensayo) | Alpha Vantage, API key; 4 endpoints (accion, FX, tesoro, tasa Fed) -> JSON crudo + tabla curada. Limite gratuito 25 solicitudes/dia: usar cache en ensayos. Requiere salida a internet del workspace |
| AE-03 Entra ID | login SSO SAML (Keycloak) en vivo + diagrama Entra | OK documental | El ambiente demo usa Keycloak; mismo patron SAML + grupos. Entra agrega SCIM. Declarar |
| AE-04 SharePoint | diagrama + patron Graph API (c03_apis_y_diagramas.md) | OK documental | El criterio pide "escenario de conexion o caso implementado": no requiere tenant. Origen: integracion via API (NiFi/Graph), no conector nativo |
| AE-05 Dynamics 365 | diagrama + patron Dataverse Web API | OK documental | Igual que AE-04. Demo en vivo solo si la SIB aporta su propio tenant |
| AE-06 IDMC | diagrama | PARCIAL | Criterio acepta "caso implementado anteriormente": **Pregunta 5** |
| AE-07 CipherTrust | diagrama | PARCIAL | Igual: **Pregunta 5** |

## C04 Analitica
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01 PBI con visuales | - | PENDIENTE | Construir .pbix (DirectQuery + Import) |
| PRE-02..05 | kit | OK | - |
| PRE-06 capa semantica con nombres, relaciones, descripciones | vistas + comentarios + glosario | PARCIAL | Relaciones no se declaran en el lakehouse; nombres llegan en minusculas |
| AE-01 cambio inmediato y automatico en PBI | guia (corregida) | OK | Se agrego actualizacion automatica de pagina; sin ella el refresh es manual |
| AE-02 carga masiva + rendimiento y consumo | guia | OK | - |
| AE-03 PBI hereda permisos sin configuracion | guia | OK (Desktop) | Se demuestra en Desktop. Si preguntan por Service: con gateway la credencial es fija (declarar) |
| AE-04 PBI hereda descripciones, nombres, relaciones | - | NO SE PUEDE | Workaround posible: script que lee COMMENT del metastore y genera el modelo (TMDL) con descripciones y relaciones. **Pregunta 8** |
| AE-05 consumo vs desarrollo | guia | PARCIAL | Sin Service no hay "reporte publicado": se muestra la diferencia de permisos en la plataforma (consumo solo lee; desarrollo crea en sandbox) |
| AE-06 metrica oficial reutilizable | c04_capa_semantica + glosario | OK workaround | Control automatico de duplicidad no nativo |

## C05 DevOps
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01..06 | `.github/workflows/sb-cicd.yml` | OK | GitHub Actions (sin acceso a Azure DevOps). Repo publico para required reviewers en plan Free; runner self-hosted en la VPC |
| AE-01 commit con autor, fecha, diff | GitHub | OK | - |
| AE-02 PR ejecuta validacion, empaquetado, despliegue y verificacion | sb-cicd.yml | OK | Despliega a DEV y verifica el estado final del job |
| AE-03 gate de aprobacion | Environment sb-prod (required reviewers, prevent self-review) | OK | - |
| AE-04 despliegue con trazabilidad | desplegar_cde | OK | - |
| AE-05 rollback real, historial con ambas versiones | rollbackRef + recursos inmutables | OK (corregido) | Antes el rollback sobreescribia archivos del recurso; ahora lo reutiliza intacto |
| AE-06 versionado de datos | c05_versionado_datos | OK | - |
| Riesgo transversal | - | - | dev/test/prod escriben las mismas tablas: **Pregunta 3** |

## C06 Ciencia de datos e IA
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01, 02, 04-07 | kit + Fase 1 | OK | - |
| PRE-03 R y Python: exploracion, entrenamiento, evaluacion, registro | c06_ae03/04 (corregidos) | PARCIAL | Se agrego exploracion y registro de la corrida R en MLflow. El Model Registry versiona solo el modelo Python |
| AE-01 join/group by sobre enmascarado | c06_ae01 | OK | - |
| AE-02 notebook colaborativo, dos usuarios editan | - | NO SE PUEDE | Sin co-edicion en tiempo real. Se muestra colaboracion por proyecto + Git |
| AE-03 R ejecuta con resultado verificable | c06_ae03 | OK | - |
| AE-04 registro con version, metricas, datos y codigo | c06_ae04 | OK | - |
| AE-05 endpoint: latencia, error, throughput | modelo + prueba_endpoint | OK | - |
| AE-06 drift con alerta | c06_ae06_drift | OK workaround | Requiere SMTP en el workspace |
| AE-07 RAG con citas y rechazo | rag/* | OK workaround | - |
| AE-08 agente via MCP sin SQL manual | mcp | OK | Codigo fuente verificado: compatible con CDW sin cambios |
| AE-09 MCP respeta controles | 2 instancias | PARCIAL | Identidad fija por instancia, no del usuario final |

## C07 Seguridad
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01..03 | kit | OK | - |
| AE-01 acceso por rol y atributo, trazable | c07 (corregido) | OK | Ahora sobre la tabla; la vista depende de propagacion de tags (validar en ensayo) |
| AE-02 rol sin atributo, bloqueado | c07 (corregido) | OK | ABAC por atributo del dato nativo; atributo del usuario modelado como grupo |
| AE-03 misma politica en SQL, BI y notebook | c07 + PBI | OK | Notebook via Impala; Spark directo a S3 no aplica masking |
| AE-04 dev no accede a prod | c07 + diagrama | OK | Segregacion logica demostrada; fisica declarada |
| AE-05 campo sensible con/sin permiso | c07 | OK | - |
| AE-06 diagrama de red especifico | c07_ae06 | PARCIAL | Completar con CIDR, subnets y endpoints reales al cerrar Fase 0 |

## C08 Gobernanza
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01 activo con propietario, dominio, clasificacion | c08_registro (corregido) | OK | Se agrego Business Metadata Gobierno_SB |
| PRE-02 variedad de activos | c08_registro | OK workaround | Dashboard, agente y documentos como entidades custom |
| PRE-03..05 | kit | OK | - |
| AE-01 sincronizar con catalogo institucional | Atlas | PARCIAL | Atlas es el "mecanismo compatible"; hacia IDMC lo hace el escaner de Informatica |
| AE-02 linaje fuente -> consumo | Atlas + c08 (corregido) | OK workaround | Se agrego el tramo Oracle/SQL Server -> curada. Tramo BI por registro API |
| AE-03 cambio en fuente e impacto | c08_impacto | PARCIAL | Atlas muestra downstream; sin reporte de impacto proactivo |
| AE-04 logs de acceso | Ranger Audit | OK | - |
| AE-05 inmutabilidad de logs | c08_auditoria (rediseñado) | OK via AWS | Replica a bucket WORM, sin tocar el bucket de CDP |
| AE-06 dato maestro corrupto hasta dashboard + logs | c08_impacto | OK workaround | - |
| AE-07 externo sin acceso a plataforma, enmascarado, revocado | Data Sharing (Data Catalog) + c08_acceso_externo | OK nativo (validar en ensayo) | Alta y revocacion desde la UI de Data Catalog (7.3.2); se comparte tabla ya enmascarada porque el share no aplica masking por columna |
| AE-08 solicitud de acceso via catalogo | c08_solicitud_acceso | NO SE PUEDE nativo | Workaround fuera del catalogo |

## C09 Administracion y FinOps
| Codigo | Artefacto | Veredicto | Brecha / accion |
|---|---|---|---|
| PRE-01, 02 | runbooks | OK | - |
| PRE-03 SLA y RTO/RPO | - | PENDIENTE | Valores oficiales (AE/soporte) |
| PRE-04 modelo de costos | - | PENDIENTE | AE |
| AE-01 costos por proyecto y ambiente | runbook | PARCIAL | Validar granularidad real de la vista de consumo en el ambiente |
| AE-02 costo base vs pico | runbook | PENDIENTE | Requiere numeros de la calculadora |
| AE-03 modelo comercial | - | PENDIENTE | AE |
| AE-04 cuello de botella y diagnostico | runbook | OK | - |
| AE-05 perdida de nodo sin detener consulta | runbook (explicacion en sesion) | PARCIAL documental | Se explica HA y reemplazo de nodos; precision: Impala reintenta la consulta, no la continua |
| AE-06 SLA, RTO, RPO | runbook | PENDIENTE | Valores oficiales |
| AE-07 DR | runbook | OK documental | Sin activo-activo multi-region |

## Preguntas resueltas (2026-10-14)
1. **PG-06**: 30M en Parquet (cruda) e Iceberg (curada, Parquet por debajo). Los demas formatos (CSV, JSON, Avro, Excel,
   PDF, PNG) se presentan en volumen de muestra para ingesta e interoperabilidad. Justificacion: en analitica los formatos
   columnares (Parquet/Iceberg) son los recomendados por rendimiento; el propio PG-06 dice "de acuerdo al tipo de archivo".
2. **PG-10**: bases origen del cliente (RDS Oracle y SQL Server).
3. **PG-11 / C05 / C07-AE-04**: se declara que la segregacion puede ser fisica (ambientes CDP separados) o logica
   (bases, jobs y politicas por ambiente). En la demo se muestra la logica; la fisica en diagrama.
4. **C03-AE-02**: Alpha Vantage. C03-AE-04/05 documental.
5. **C03-AE-06/07**: existen referencias de Cloudera; ademas, casos donde Cloudera sustituyo a Informatica.
6. **C04**: solo Power BI Desktop (capacidad de conexion). Sin licencias de Service.
7. **Trino**: GA en Cloudera on cloud.
8. **C04-AE-04**: sin workaround; brecha declarada.
9. **C09-AE-05**: no se ejecuta; se explica en sesion (ver c09_runbooks.md, redaccion precisa).

## Pendiente
- Ninguno de la SIB ni de Cloudera. Runtime confirmado: **7.3.2** (REST Catalog disponible; Data Sharing con UI en Data Catalog,
  vigencia del share por token de Knox). Validar en el ensayo: alta del consumidor, lectura externa y revocacion.
  Plan B si falla: DuckDB leyendo metadatos Iceberg en S3 (`c01_ae06_lectura_externa_duckdb.py`).

## Nuevos riesgos registrados (2026-10-07)
- **Trino**: madurez a confirmar en la version de CDW desplegada (columna Estado de madurez). Servicio Ranger `cm_trino`
  con postura por defecto permisiva: endurecer antes de la demo. Las tags de Atlas no aplican a catalogos federados:
  el masking sobre Oracle es por recurso (politica sb_11). Para tablas Iceberg via Trino se requieren politicas en
  cm_trino y en cm_hive (doble auditoria).
- **NiFi**: propiedades de Kerberos/IDBroker/HiveCatalog dependen del Data Hub; se confirman en el ensayo.
- **C05 (2026-10-07)**: la necesidad institucional menciona Azure DevOps. La demo usa GitHub Actions; declarar que la
  integracion con Cloudera es por scripts y APIs (agnostica del orquestador) y mostrar `referencia_azure-pipelines.yml`.
  Riesgo de puntaje: el evaluador podria exigir Azure DevOps literal; si la SIB ofrece una organizacion, se migra en ~1 dia.
