# C02 y C05 con Jobs de Cloudera AI (mientras CDE no este disponible)

Declarar a la SIB: "CDE con Airflow es el orquestador recomendado; por un defecto conocido del ambiente demo,
el flujo se muestra con Jobs de Cloudera AI. Mismo pipeline, mismos controles". CDE queda como 2DA PARTE.

## Preparacion (una vez, ~30 min)
1. **API key**: Cloudera AI > User Settings > API Keys > Create API Key. En `config.yaml`:
   `cai.url` (URL del workspace), `cai.api_key`, `cai.project_id` (Terminal: `echo $CDSW_PROJECT_ID`).
2. **Prueba**: `python -c "from lib.sbpoc import cai_api; s,u,p=cai_api(); print(s.get(f'{u}/projects/{p}/jobs').status_code)"` -> 200.
3. **Jobs** (proyecto sib-poc > Jobs > New Job; runtime Python 3.10, 2 vCPU / 4 GB):

| Job | Script | Argumentos | Programacion |
|---|---|---|---|
| sib-pipeline | fase3/c02/c02_pipeline_sql.py | `--version v1 --reintentos 3 --espera 60` | Manual (o diaria) |
| sib-calidad | fase3/c05/validar_calidad.py | - | **Dependent** de sib-pipeline (cadena) |
| sib-pipeline-dev | fase3/c05/ejecutar_version.py | `--ref v1.0.0 --ambiente dev` | Manual |
| sib-pipeline-test | fase3/c05/ejecutar_version.py | `--ref v1.0.0 --ambiente test` | Manual |
| sib-pipeline-prod | fase3/c05/ejecutar_version.py | `--ref v1.0.0 --ambiente prod` | Manual |

   En sib-pipeline: Notifications > on failure > tu correo (si el workspace tiene SMTP).
4. **Trigger por capa bronce**: Applications > New: `fase3/c02/c02_trigger_bronce.py` (requiere SQS de E6.4).

## Demo C02
| Item | Accion | Evidencia |
|---|---|---|
| AE-01 | Run de sib-pipeline; al terminar corre sib-calidad (dependencia) | Job History: inicio, fin, estado; `SELECT * FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC` |
| AE-05 | `echo x > /tmp/m && hdfs dfs -put -f /tmp/m s3a://<bucket>/sb/control/fallar_paso_3` y run | Log del job: "FALLO CONTROLADO en paso 3 ... Accion: eliminar el marcador" |
| AE-06 | Durante la espera del reintento: `hdfs dfs -rm s3a://<bucket>/sb/control/fallar_paso_3` | Intento 2 EXITOSO; sib-calidad sin duplicados; pasos 1-2 no se repiten de mas (idempotentes) |
| AE-04 | Subir un archivo a `sb/landing/transacciones/csv/` | Log de la Application: "job sib-pipeline lanzado" + nuevo run |

## Demo C05
`fase3/c05/LEEME_CICD.md`: el workflow llama a `desplegar_cai.py` (apunta el job del ambiente a la version,
lo ejecuta, verifica y registra en `sb_gov.despliegues`). Rollback: `rollback_ref = v1.0.0`.
Red: el runner (EC2 Windows) debe alcanzar la URL del workspace de Cloudera AI (allowlist si aplica).
