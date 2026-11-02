# Prueba de concepto Cloudera para la Superintendencia de Bancos

Codigo y configuracion de la prueba de concepto sobre Cloudera on cloud (AWS), runtime 7.3.2.
Todos los datos son **sinteticos**: el repositorio no contiene datos reales ni credenciales.

## Arquitectura del ambiente
| Capa | Componente |
|---|---|
| Origen | SQL Server 2022 (base `sbcore`) con CDC nativo, en una EC2 de la VPC del ambiente |
| Ingesta | Data Hub Streams Messaging: Kafka, Kafka Connect con Debezium y Streams Messaging Manager |
| Lakehouse | Apache Iceberg v2 en S3, capas `sb_raw`, `sb_curated` y `sb_consumption` |
| SQL y BI | Cloudera Data Warehouse: Virtual Warehouses Impala `impala-sib-a` (recursos fijos) e `impala-sib-waa` (autoescalado por carga), Hue (Cloudera Data Explorer) y Power BI Desktop |
| Procesamiento, IA y operacion | Cloudera AI: sesiones, Jobs (pipeline y calidad), Applications (`sib-despachador`, `sib-accesos`), MLflow, AI Registry y endpoints de modelos |
| Seguridad y gobierno | SDX: Ranger (roles, atributos, enmascaramiento, filtros por fila, auditoria), Atlas (clasificacion y linaje), RAZ para S3 |
| CI/CD | GitHub Actions con runner en la VPC; despliegue por cola auditable hacia Cloudera AI |

## Estructura
| Carpeta | Contenido |
|---|---|
| `config/` | `config.ejemplo.yaml`: plantilla de configuracion |
| `lib/` | `sbpoc.py`: utilidades comunes (configuracion, Impala, Ranger y Atlas por Knox, API de Cloudera AI) |
| `fase2/` | Generacion de datos, base origen SQL Server, DDL del lakehouse, tags de Atlas y politicas de Ranger |
| `fase3/c01` | Lakehouse: misma tabla para varios motores, operaciones transaccionales, evolucion de esquema, metadatos y CDC |
| `fase3/c02` | Pipelines: pipeline orquestado con fallo controlado y recuperacion, calidad, prueba de carga |
| `fase3/c03` | Integraciones: APIs de la plataforma, API externa autenticada, escenarios de integracion |
| `fase3/c04` | Capa semantica, glosario en Atlas y guia de conexion de Power BI |
| `fase3/c05` | CI/CD: validacion de esquema y calidad, despliegue versionado, despachador y versionado de datos |
| `fase3/c06` | Ciencia de datos e IA: entrenamiento trazable, registro, endpoint, drift, RAG y MCP |
| `fase3/c07` | Seguridad: pruebas de acceso por rol y atributo, diagrama de red |
| `fase3/c08` | Gobierno: linaje de punta a punta, impacto, auditoria inmutable, acceso externo y solicitudes de acceso |
| `fase3/c09` | Administracion y FinOps: costos, picos, diagnostico y continuidad |
| `.github/workflows/` | Workflow `sb-cicd` (PR, TEST, PROD con aprobacion y rollback) |

## Configuracion
1. Copiar `config/config.ejemplo.yaml` a `config/config.yaml` y completar los valores `CAMBIAR_*`.
   `config.yaml` y los certificados no se versionan (`.gitignore`); el CI/CD recibe su configuracion por un secret.
2. En el proyecto de Cloudera AI: `pip install -r requirements.txt`. Los scripts asumen la raiz del proyecto en `/home/cdsw`.
3. Cada script indica en su encabezado que demuestra, como se ejecuta y su alcance.
