# Plan comprimido: listo el 31 de octubre

Reemplaza el calendario de 5 semanas de `PLAN_VALIDACION.md` (los criterios de salida de cada paso siguen valiendo).

## Supuestos
- 13 dias habiles: mie 14 a vie 30 de octubre, 8 h/dia. Sabado 31 = colchon.
- 2 personas: **A** = Adrian (SE), **B** = apoyo. Capacidad: ~208 h.
- El ambiente Cloudera se lanza el **mie 14 a primera hora** y queda listo en 4 h.
- El trabajo pendiente estimado era ~33 persona-dias (~264 h). Para caber en 208 h se recorta alcance (abajo),
  se reduce la holgura a cero y el dry-run pasa de 2 rondas largas a 1 completa + 1 de repaso.

## Triage de alcance

**Nivel 1 - En vivo, se construye si o si** (nativo, alto puntaje, bajo riesgo)
C01-AE-02/03/04/05/07/08 · C02-AE-01/02/04/05/06/07/08/09/10/11/12 · C04-AE-01/02/03/05(parcial)/06 · C05-AE-01..06 ·
C06-AE-01/03/04/05/07/08/09 · C07-AE-01..05 · C08-AE-02/03/04/05/06/08 · C03-AE-01/02 · C09-AE-01/02/04 (C09-AE-05 se explica en sesion)

**Nivel 2 - En vivo con tiempo limite** (si se excede, pasa a documental o 2DA PARTE sin discutir)
| Item | Limite | Si no sale |
|---|---|---|
| C01-AE-05 CDC Oracle (Debezium/LogMiner) | 1.5 dias | CDC sobre SQL Server (Debezium SQL Server es mas simple; se adapta el job) |
| C01-AE-01 flujo NiFi A | 4 h | Carga a S3 + tablas externas (cumple "sin conversion propietaria") |
| C01-AE-06 / C08-AE-07 REST Catalog + Data Sharing (Data Catalog) | 3 h | Plan B: DuckDB/PyIceberg leyendo metadatos Iceberg en S3 (AE-06); externo via JDBC con politica temporal (AE-07) |
| C02-AE-03 streaming bajo carga | 3 h | Se muestra SQL y batch; streaming documental |
| C06-AE-06 drift con correo | 2 h | Drift visible en el job (sin correo) |
| Trino federado (plus PG-10) y flujo NiFi B | 3 h c/u | Se omiten: PG-10 ya cumple con RDS + PBI + notebooks |

**Nivel 3 - Documental desde el inicio** (cero construccion, solo el documento/diagrama)
C03-AE-03..07 · C07-AE-06 · C09-AE-03 (AE), AE-06, AE-07 · brechas declaradas C04-AE-04 y C06-AE-02 ·
C08-AE-01 (sincronizacion hacia IDMC).

## Modo de evidencia: mostrar vs ejecutar
La plantilla acepta como evidencia la demostracion de la funcionalidad o configuracion. Solo se **ejecuta** cuando el
criterio exige observar un resultado (dato cambiado, acceso negado, latencia medida). Lo demas se **muestra** en la consola.

| Mostrar (consola o documento, sin scripts) | Ejecutar (el criterio exige resultado observado) |
|---|---|
| C01-AE-07 metadatos, AE-08 APIs | C01-AE-02/03/04/05 |
| C02-AE-08 GPU: perfil GPU, grupo 0->N, detener sesion, costo por tags (sin entrenamiento) | C02-AE-01/02/04/05/06/07/09 y prueba de carga (insumo de AE-10) |
| C02-AE-11 APIs, AE-12 IA (Hue AI Assistant) | C04-AE-01/02/03/05/06 |
| C06-AE-02 proyecto compartido + Git (brecha declarada) | C05-AE-01..06 |
| C07-AE-06 diagrama | C06-AE-01/03/04/05/06/07/08/09 |
| C08-AE-01 activo en Atlas con metadata, AE-04 Ranger Audit | C07-AE-01..05 |
| C03-AE-03..07 escenarios | C08-AE-02/03/05/06/07/08 |
| C09-AE-01 consumo, AE-03/05/06/07 | C03-AE-01/02 · C09-AE-02/04 |

`fase3/c06/c06_gpu_entrenamiento.py` queda opcional.

## Calendario

| Dia | Fecha | A (Adrian) | B (apoyo) | Gate |
|---|---|---|---|---|
| 1 | mie 14 | 7:00 lanzar ambiente (cuota GPU ya aprobada). Keycloak (usuarios/grupos). GitHub (repo, secret, environments). Tarde: config post-ambiente (Trino VW opcional, recursos CDE, proyecto Cloudera AI, perfiles, AI Inference) | RDS Oracle + SQL Server, scripts 03/04. EC2 Windows (PBI, gateway, SQL Developer, SSMS, runner GitHub). Generar datos escala 1 en laptop y subir a S3 | |
| 2 | jue 15 | Primer login de los 9 usuarios, workload passwords, roles. Smoke tests 2.1-2.10 | Job 05b (carga RDS), job 02 (30M), DDL 07 | **Gate 1** |
| 3 | vie 16 | Tags Atlas + politicas Ranger (08, 09). C07 completo | Debezium Oracle + job CDC (inicio timebox) | |
| 4 | lun 19 | C02 pipeline batch + DAG + fallo/recuperacion + validar_calidad | CDC (fin timebox) + C01 SQL (02, 03, 04, 07) | **Gate 2** |
| 5 | mar 20 | C04 capa semantica + glosario + Power BI (DirectQuery, Import) | Streaming + medicion de latencia + trigger SQS | |
| 6 | mie 21 | Power BI: permisos, consumo vs desarrollo, AE-03 tres canales | Prueba de carga 50-500, autoscaling, aislamiento tenant B. Preparar perfil GPU para mostrar | |
| 7 | jue 22 | C05 GitHub Actions completo (PR rojo/verde, gate, rollback) | C06 Python + R + registro + endpoint + prueba de carga | |
| 8 | vie 23 | C08 registro Atlas, linaje, impacto, corrupcion, auditoria, WORM | C06 drift + RAG (indexar, app, calibrar umbral) | |
| 9 | lun 26 | C08 acceso externo + solicitud de acceso. C03 APIs + Alpha Vantage | MCP (2 instancias). C09 cuello de botella, costos, perdida de nodo | **Gate 3** |
| 10 | mar 27 | **Dry-run 1** completo con `GUION_DEMO.md`, cronometrado | (juntos) | |
| 11 | mie 28 | Correcciones de defectos | Correcciones + Nivel 2 pendientes (NiFi A, Trino) | |
| 12 | jue 29 | Dry-run 2 (repaso) + captura de evidencias | Ficha PG-03, PPT de carga C02-AE-10, lista de conectores | |
| 13 | vie 30 | Excel: puntaje propio y columna Comentario. Deck PG-01 | Evidencia documental PG-13, documentos Nivel 3 | **Gate 4** |
| - | sab 31 | Colchon | | |

Regla de corte: al final de cada dia se revisa el avance. Si un bloque Nivel 1 se atrasa mas de medio dia,
se toma tiempo de un item Nivel 2 (nunca del dry-run).

## Respuestas ya definidas (14 oct)
Volumen: 30M Parquet/Iceberg + muestras. Power BI: solo Desktop. Dev/test/prod: fisico o logico, declarado.
Trino: GA. C09-AE-05: explicado en sesion. Runtime 7.3.2: REST Catalog y Data Sharing disponibles. Sin pendientes.

## Con una sola persona
104 h no alcanzan para el Nivel 1 completo. Se pasan a documental tambien: C02-AE-03 completo, C06-AE-05/06,
C08-AE-07/08 y C09-AE-04; el dry-run queda en una sola ronda. Cobertura en vivo estimada: ~70% de las acciones esperadas.
