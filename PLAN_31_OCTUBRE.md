# Plan comprimido: listo el 31 de octubre

Reemplaza el calendario de 5 semanas de `PLAN_VALIDACION.md` (los criterios de salida de cada paso siguen valiendo).

## Supuestos (actualizado lun 19 oct: ambiente listo)
- Quedan 9.5 dias habiles: lun 19 (tarde) a vie 30, 8 h/dia. Sabado 31 = colchon.
- 2 personas: **A** = Adrian (SE), **B** = apoyo. Capacidad: ~152 h (antes 208 h).
- Para absorber los 5 dias perdidos: el Nivel 2 pasa por defecto a "mostrar" y solo se construye si sobra tiempo,
  y queda **un solo dry-run** (jue 29). Pasos referidos a `RUNBOOK_IMPLEMENTACION.md` (E0..E14).

## Triage de alcance

**Nivel 1 - En vivo, se construye si o si** (nativo, alto puntaje, bajo riesgo)
C01-AE-02/03/04/05/07/08 · C02-AE-01/02/04/05/06/07/08/09/10/11/12 · C04-AE-01/02/03/05(parcial)/06 · C05-AE-01..06 ·
C06-AE-01/03/04/05/07/08/09 · C07-AE-01..05 · C08-AE-02/03/04/05/06/08 · C03-AE-01/02 · C09-AE-01/02/04 (C09-AE-05 se explica en sesion)

**Nivel 2 - Por defecto se MUESTRA; se construye solo si sobra tiempo** (dias 28-31). Excepcion: CDC, que es Nivel 1 con timebox
| Item | Limite | Si no sale |
|---|---|---|
| C01-AE-05 CDC SQL Server (Debezium) - **se construye** | 1 dia tras montar la EC2 (sab 24) | Se muestra la captura nativa de SQL Server (tablas cdc.*) y el conector; MERGE documentado |
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
| 1 | lun 19 tarde | E1: Keycloak, primer login de los 9 usuarios, workload passwords, roles, sync FreeIPA | E0: proyecto en Cloudera AI, config.yaml, certificado Kafka, CLI y recursos CDE | |
| 2 | mar 20 | E2.1 DDL en RDS (WIN). Tarde: E3.1 DDL lakehouse, E3.2 tags, E3.3 politicas | E2.2 generar datos, E2.3 subir a S3, E2.4 carga RDS, E2.5 masivo 30M | **Gate 1** (E4 al cierre) |
| 3 | mie 21 | E5.2 carga puente clientes/cuentas. E6.1-E6.3 pipeline, Airflow, fallo y recuperacion | E5.1 CDC (timebox inicia) | |
| 4 | jue 22 | E7 seguridad. E8 capa semantica y glosario | E5.1 CDC. E5.3 operaciones lakehouse. E6.5 streaming | |
| 5 | vie 23 | E8 Power BI completo. E5.4 misma consulta en dos interfaces | E6.6 pruebas de carga (corren solas) + E6.4 trigger SQS | **Gate 2** |
| 6 | lun 26 | E10 CI/CD GitHub completo | E9 pasos 1-5 (enmascarado, Python, R, registro, endpoint) | |
| 7 | mar 27 | E11 gobernanza (linaje, impacto, corrupcion, WORM, solicitud de acceso) | E9 pasos 6-9 (drift, RAG, MCP) | |
| 8 | mie 28 | E12 Alpha Vantage y APIs. E13 cuello de botella y costos. E5.6 Data Sharing (timebox 3 h) | Correcciones pendientes. Inicio de capturas de evidencia | **Gate 3** |
| 9 | jue 29 | **Dry-run unico** completo, cronometrado | (juntos) | |
| 10 | vie 30 | Correcciones. Excel (puntaje propio y Comentario). Deck PG-01 | PPT de carga C02-AE-10, ficha PG-03, evidencia PG-13, documentos Nivel 3 | **Gate 4** |
| - | sab 31 | Colchon: repaso parcial o Nivel 2 (NiFi flujo A, Trino) si todo lo demas esta en verde | | |

Regla de corte: al cierre de cada dia se revisa el avance. Si un bloque se atrasa mas de medio dia, ese item pasa a
"mostrar" y se sigue. El dry-run del jueves no se mueve.

Clave de dependencias: el pipeline (dia 3) ya no espera al CDC; usa la carga puente E5.2 y el CDC la reemplaza cuando funcione.

## Respuestas ya definidas (14 oct)
Volumen: 30M Parquet/Iceberg + muestras. Power BI: solo Desktop. Dev/test/prod: fisico o logico, declarado.
Trino: GA. C09-AE-05: explicado en sesion. Runtime 7.3.2: REST Catalog y Data Sharing disponibles. Sin pendientes.

## Con una sola persona
76 h (9.5 dias) no alcanzan para el Nivel 1 completo. Pasan a "mostrar" o documental: C02-AE-03, C02-AE-04 (trigger),
C06-AE-05/06, C08-AE-07/08 y C09-AE-04; el RAG se monta con el AMP de RAG Studio en vez de `rag/app.py`; CDC con
timebox de medio dia. Cobertura en vivo estimada: ~60% de las acciones esperadas.
