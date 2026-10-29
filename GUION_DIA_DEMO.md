# Guion operativo de la demo SIB: 3 sesiones de 1.5 h

Estado: VERSION FINAL 28-oct. Orden definido por el equipo Cloudera.
Fechas: sesion 1 lun 2-nov, sesion 2 mie 4-nov, sesion 3 vie 6-nov. Dry-run sesiones 1 y 2: vie 30-oct; dry-run sesion 3: jue 5-nov.
Convenciones: [OK] validado en vivo, [PEND] por validar en el dry-run, [DECL] se declara sin demostrar.
Usuarios: user001 admin, user002 ingeniero, user003 cientifico, user005 analista CENTRAL sin confidencial,
user006 analista NORTE con confidencial, user008 MCP restringido.

| Sesion | Tema | Bloques | Hilo narrativo |
|---|---|---|---|
| 1 (2-nov) | Plataforma y datos | C01, C03, C02, C04, C01-AE-05 CDC | Del origen SQL Server al tablero |
| 2 (4-nov) | Seguridad, gobierno y DevOps | C07, C08, C05 | Quien ve que, como se audita y como se despliega |
| 3 (6-nov) | IA y operacion | C06, C09 | Del dato gobernado al modelo en produccion, y lo que cuesta operarlo |

---

## Checklist general (antes de CADA sesion)
- [ ] Encender ambiente, Data Lake y Data Hubs al menos 1 h antes (arranque medido: >= 1 h)
- [ ] EC2 Windows (SQL Server + Power BI + runner) encendida ANTES que el Data Hub sibrd-kafka
- [ ] Data Lake, FreeIPA y Data Hubs en Running/Healthy; VW `impala-sib-a` encendido (no usar sibrd-impala: catalogd danado)
- [ ] IP de salida de CAI (`curl -s https://checkip.amazonaws.com` en la Terminal) y las 3 IP de los NAT en el security group de Knox (443).
      Sintoma si falta: timeout hacia `...dl-gateway...` (Ranger/Atlas por API)
- [ ] Sesion de Cloudera AI con Terminal; `cd /home/cdsw`; variable `B=$(python -c "from lib.sbpoc import cfg; print(cfg()['s3']['bucket'])")`
- [ ] Applications `sib-despachador` y `sib-accesos` en Running
- [ ] VW impala-sib-waa encendido (C02 aislamiento, C09); ambos VW (impala-sib-a e impala-sib-waa) con `default_query_options` = `ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true`
      (prueba: user006 `SELECT COUNT(*) FROM sb_curated.clientes` debe dar 150.464, no 1.000.000)
- [ ] Hue desde `impala-sib-a`; una ventana de incognito por usuario de la sesion
- [ ] Plan B de cada bloque: capturas en `evidencias/<codigo>/`

---

# SESION 1: Plataforma y datos (90 min)

Preparacion especifica:
- [ ] SMM > Connect: conector `sb-cdc-sqlserver-core` y su TAREA en Running. Si esta FAILED ("No route to host" a
      10.10.2.235:1433, quedo asi mientras la EC2 estaba apagada): Restart de la TAREA (Connect no reintenta solo)
- [ ] Driver JDBC presente en `/var/lib/kafka_connect_jdbc/` de cada host de Connect (se pierde si un nodo se repara)
- [ ] SQL Server Agent corriendo en la EC2
- [ ] Repetibilidad del CDC: en SSMS `DELETE FROM sbcore.dbo.clientes WHERE id_cliente = 9000001;` (si existe)
- [ ] Job `sib-pipeline` con argumentos `--version v1 --reintentos 3 --espera 180`; `hdfs dfs -ls s3a://$B/sb/control/` vacio
- [ ] Power BI: .pbix abierto, conexion al host de `impala-sib-a`, usuario user006, pagina "AE-01" con Page refresh 5 s
- [ ] Hue (user001): UPDATE +1000 y -1000 del id_credito ya escritos
- [ ] C03: `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache` corrido antes de la sesion

| Min | Bloque | Contenido |
|---|---|---|
| 0-10 | Apertura | Arquitectura: SQL Server -> Kafka/CDC -> Lakehouse Iceberg (raw, curada, consumible) -> CDW/Power BI; SDX (Ranger, Atlas) transversal |
| 10-25 | C01 Lakehouse | AE-02, AE-03, AE-04, AE-07 |
| 25-35 | C03 Integraciones | AE-01, AE-02 |
| 35-50 | C02 Pipelines | PRE-03, PRE-06, AE-01, AE-05, AE-06, AE-09, AE-10 |
| 50-65 | C04 Power BI | PRE-01, AE-01, AE-03 |
| 65-80 | C01-AE-05 CDC | SIEMPRE despues de C02 (ver nota) |
| 80-90 | Preguntas | |

## C01 Lakehouse [OK 25-oct] ~15 min
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Misma consulta en Hue (user006) y en Python impyla en CAI | mismo resultado, dos motores | AE-02 |
| 2 | Hue (user002): `c01_ae03_operaciones_transaccionales.sql` (CTAS, INSERT, UPDATE, DELETE, MERGE) + `DESCRIBE HISTORY` | snapshot por operacion | AE-03 |
| 3 | Hue (user002): `c01_ae04_evolucion_esquema.sql` (ADD COLUMNS, rename) | sin reescritura de datos | AE-04 |
| 4 | Hue (user001): DESCRIBE FORMATTED / HISTORY / SHOW FILES / COLUMN STATS | metadatos tecnicos | AE-07 |
Leccion: `config.yaml impala.host_depto_a` debe ser el host de impala-sib-a (404 con el viejo).
C01-AE-06 (motor externo sin exportar) se muestra en la sesion 2 con C08-AE-07.

## C03 Integraciones [AE-01/02 OK 29-oct] ~10 min
Validado 29-oct: 7/7 superficies OK; Alpha Vantage accion_ibm 100, fx_usd_eur 100, tesoro_10a 882, tasa_fed 867 filas
(2.7 a 4 s por fuente). En la demo usar --desde-cache (no gasta cuota: 25 solicitudes/dia, 4 por corrida).
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Terminal CAI: `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache` + Hue: `SELECT serie, COUNT(*), MAX(fecha) FROM sb_curated.mercado_series GROUP BY serie;` | 4 series (accion, FX, tesoro, tasa Fed) con filas; JSON crudo en sb_raw.api_alphavantage | AE-02 |
| 1b | `--sin-clave` | la API rechaza y el script falla con mensaje accionable | AE-02 (manejo de errores) |
| 2 | Terminal CAI: `python fase3/c03/c03_ae01_apis_plataforma.py --ejecutar-job sib-calidad` | Atlas, Ranger, CAI API v2 y SQL con estado y ms; Job lanzado por API | AE-01, PRE-02 |
| 3 | Diagramas Entra, SharePoint, D365, IDMC, CipherTrust | documental | AE-03..07 [DECL] |

## C02 Pipelines [OK 22/23-oct; recuperacion PEND dry-run] ~15 min
Bloc de notas:
- crear marcador: `echo x > /tmp/m && hdfs dfs -put -f /tmp/m s3a://$B/sb/control/fallar_paso_3`
- borrar marcador: `hdfs dfs -rm s3a://$B/sb/control/fallar_paso_3`

| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Jobs: grafo `sib-pipeline -> sib-calidad` y una corrida en Success (2m47s, 25.75M filas) | inicio, fin, estado, log de 4 pasos | PRE-03, AE-01 |
| 2 | Log de `sib-calidad` | 5 reglas [OK], 0 duplicados | AE-06 (integridad) |
| 3 | Crear marcador y Run de `sib-pipeline` | a ~1.5 min: `Paso 3 intento 1: FALLIDO ... FALLO CONTROLADO` | AE-05 |
| 4 | Apenas aparezca el FALLIDO, borrar el marcador | `Paso 3 intento 2: EXITOSO`, calidad corre sola | AE-06 (recuperacion) |
| 5 | Hue: `SELECT paso, intento, estado, mensaje FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC LIMIT 6;` | paso 3 FALLIDO y EXITOSO | AE-05, AE-06 |
Rendimiento 50 -> 500 usuarios (C02-PRE-06, AE-10), corrido el 29-oct; en la sesion se muestra la tabla y no se re-ejecuta (11 min):
| Usuarios | Exitosas/s fijo | Exitosas/s WAA | Errores fijo | Errores WAA | p95 fijo | p95 WAA |
|---|---|---|---|---|---|---|
| 50 | 114 | 120 | 0 | 0 | 541 ms | 551 ms |
| 200 | 60 | 135 | 0 | 0 | 4.1 s | 1.8 s |
| 300 | 46 | 138 | 1.720 | 0 | 7.6 s | 2.5 s |
| 500 | 71 | 118 | 2.595 | 0 | 8.2 s | 4.9 s |
Fijo = impala-sib-a; WAA = impala-sib-waa (2 ejecutores en reposo, 4 en el pico). Detalle en sb_consumption.metricas_rendimiento.
Aislamiento (C02-AE-09) EN VIVO [PEND]: carga en impala-sib-waa (sesion CAI 8 vCPU) y sonda en impala-sib-a desde OTRA sesion:
  sesion 1: `python fase3/c02/c02_prueba_carga.py --prueba aislamiento --depto b --niveles 500 --segundos 300 --sin-registro`
  sesion 2 (30 s despues): `python fase3/c02/c02_prueba_carga.py --prueba sonda_carga --depto a --niveles 1 --segundos 240 --sin-registro`
  Linea base de la sonda sin carga: p50 123 ms, p95 280 ms. RIESGO: con la sonda en el MISMO proceso que la carga, la sonda subio
  a 3.3 s (probable cuello de botella del cliente: el rendimiento se estanca en ~135 consultas/s). No validado en dos sesiones.
Lecciones: con `--espera 60` no hubo tiempo de borrar el marcador (usar 180); la carpeta `sb/control` debe existir
(`hdfs dfs -mkdir -p s3a://$B/sb/control`). Cierre: confirmar el marcador borrado.

## C04 Power BI [OK 24/25-oct] ~15 min
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Conexion: conector Impala, DirectQuery, user006 | solo NORTE (61.319 creditos), identificacion en hash | PRE-01, AE-03 |
| 2 | Hue (user001): UPDATE +1000 | la tarjeta sube 1000 sin tocar Power BI | AE-01 |
| 3 | Hue: UPDATE -1000 | vuelve al valor original | AE-01 |
| 4 | Cambiar credencial a user005 + Refresh | solo CENTRAL | AE-03 |
Lecciones: el conector Impala de fabrica no habla HTTP; se redirige al driver Cloudera 2.7+ (guia c04, paso 0; rehacer si
Power BI se actualiza). Hive LLAP ya no existe en Power BI. Todas las consultas del .pbix deben apuntar a impala-sib-a
(Editor avanzado, linea Source). Tras cambiar de usuario: Refresh. Vistas con INNER JOIN a clientes (el LEFT JOIN filtro
348.433 creditos sin region). AE-02 Import, AE-05 y AE-06 validados el 25-oct.

## C01-AE-05 CDC SQL Server -> Kafka -> MERGE Iceberg [OK 27-oct] ~15 min
NOTA DE ORDEN: cualquier corrida de sib-pipeline (C02, C05, C08-AE-06) recarga sb_curated.clientes desde sb_raw
(TRUNCATE + INSERT) y borra lo aplicado por CDC. Por eso el CDC cierra la sesion 1. Declarar: en produccion el paso 1
del pipeline seria un MERGE incremental.
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Terminal CAI: `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py` ANTES de tocar SQL Server | "Consumidor CDC activo" | |
| 2 | SSMS: `c01_ae05_generar_cambios.sql` | 3 UPDATE, 1 INSERT, 1 DELETE en origen | AE-05 |
| 3 | Terminal: esperar la linea MERGE (15-30 s) | `MERGE {'u': 3, 'c': 1, 'd': 1}` | AE-05 |
| 4 | Hue: `SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,40,9000001);` + `DESCRIBE HISTORY` | cdc_ts de hoy, 40 ausente, snapshot nuevo | AE-05 |
Resultado del 27-oct: 5 eventos -> MERGE en 5.6 s.
Lecciones: driver JDBC copiado a mano; JAAS PLAIN por conector (producer.override.*) y en schema.history.internal.*;
PLAIN en MAYUSCULAS; politicas Ranger en el servicio Kafka del Data Hub (sb_12, sb_13); topicos creados a mano;
snapshot.isolation.mode=snapshot; tras corregir, reiniciar la TAREA. Requisitos del consumidor: `pip install kafka-python`,
CA de FreeIPA en `config/datahub-ca.pem`. Detener con Ctrl+C al terminar.

---

# SESION 2: Seguridad, gobierno y DevOps (90 min)

Preparacion especifica:
- [ ] GitHub: API key nueva (vence en 1 dia) en el secret CONFIG_YAML; runner en Idle; tag v1.0.0 con el pipeline
      (en CAI: `git fetch origin --tags --force && git cat-file -e v1.0.0:fase3/c02/c02_pipeline_sql.py && echo OK`)
- [ ] Rama `feature/demo-sesion2` con un cambio menor lista para abrir el PR
- [ ] Repetibilidad C08-AE-03: `DROP VIEW IF EXISTS sb_sandbox_depto_a.v_tx_por_entidad; DROP TABLE IF EXISTS sb_sandbox_depto_a.entidades_copia;`
- [ ] Power BI: pagina con la tabla `nombre_entidad` filtrada por `id_entidad_destino = 7`
- [ ] AWS CloudShell abierto con las variables B/K/V de la guia `c08_auditoria_e_inmutabilidad.md`
- [ ] Power BI en la EC2: conexion a sb_share.clientes_externo con user011 (credencial guardada aparte de user006)
- [ ] Portal sib-accesos sin solicitudes pendientes de ensayos

| Min | Bloque | Contenido |
|---|---|---|
| 0-5 | Apertura | SDX: Ranger (permisos, masking, filtros, auditoria), Atlas (tags, linaje), roles independientes del IdP |
| 5-20 | C07 Seguridad | AE-01, AE-02, AE-05. Al inicio, abrir el PR de C05 para que CI y DEV corran en paralelo |
| 20-60 | C08 Gobierno | PRE-01/02, AE-01..08 |
| 60-80 | C05 CI/CD | AE-01..05 |
| 80-90 | Preguntas | |

## C07 Seguridad [OK 22-oct; capturas PEND] ~15 min
En cada ventana (Hue, Impala): `SELECT identificacion, nombre, region FROM sb_curated.clientes LIMIT 3;` y
`SELECT id_credito, saldo_pendiente FROM sb_curated.creditos LIMIT 3;`
| Usuario | Esperado | Prueba |
|---|---|---|
| user005 | hash, solo CENTRAL; creditos: error de autorizacion | AE-02, AE-05 |
| user006 | hash, solo NORTE; creditos: OK | AE-01, AE-05 |
| user001 | todo en claro | AE-05 |
Luego Ranger > Audit > Access filtrando user005: Allowed y Denied (C07-AE-01 y C08-AE-04).
Narrativa: permisos con roles de Ranger, atributos como roles, PII/CONFIDENCIAL por tags de Atlas.
Hallazgo 29-oct (corregido en la configuracion de los VW): en Iceberg, Impala responde `COUNT(*)` sin predicado desde los
metadatos del snapshot (EXPLAIN: `00:UNION constant-operands=1`, sin SCAN) y NO aplica el filtro de fila de Ranger: user006
obtenia 1.000.000 en vez de 150.464. Los datos nunca se expusieron (cualquier lectura real filtra bien); el riesgo era la
cardinalidad total y conteos incorrectos en BI. Mitigacion: `ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true` como opcion por
defecto del VW. Si la SIB pregunta: se declara como hallazgo de la PoC, mitigado y reportado a ingenieria de Cloudera.

## C08 Gobierno [OK 27/28-oct, AE-07 plan C validado 28-oct] ~40 min
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Atlas: `sb_curated.clientes` > Properties y Lineage; `Tablero Cartera Crediticia` > Lineage; `Asistente normativo RAG` > Lineage | Gobierno_SB (dominio, propietario, custodio user002, criticidad); linaje SQL Server -> curada -> vistas -> tablero; documentos -> agente | PRE-01/02, AE-01/02 |
| 2 | Hue (user002): CREATE entidades_copia + vista; Atlas muestra la vista aguas abajo; rename de columna; SELECT de la vista | `Could not resolve column/field reference: 'e.nombre'` | AE-03 |
| 3 | Hue (user002): DESCRIBE HISTORY (anotar snapshot) + UPDATE entidad 7 a 'ENTIDAD CORRUPTA - DEMO' + Job sib-pipeline (~4 min: explicar mientras corre) | el valor corrupto en Hue y en Power BI | AE-06 |
| 4 | Ranger > Audit > Access: user002, entidades_financieras | el UPDATE con usuario, fecha y recurso | AE-04, AE-06 |
| 5 | `ALTER TABLE sb_curated.entidades_financieras EXECUTE ROLLBACK(<snapshot>)` + sib-pipeline + SELECT | nombre original de vuelta | AE-06 |
| 6 | CloudShell: delete-object de una version del bucket WORM, sin y con `--bypass-governance-retention` | AccessDenied en ambos | AE-05, PRE-05 |
| 7 | Power BI (EC2) con user011: navegador sin tablas. Portal sib-accesos: user011 pide sb_share.clientes_externo, Aprobar 7 dias; Power BI ve solo esa tabla, enmascarada; Revocar; Refresh -> error | acceso SQL temporal a una sola tabla, auditado | AE-07 |
| 8 | Portal sib-accesos: user005 solicita sb_raw.entidades_financieras; Aprobar 7 dias; Hue user005 lee; Revocar; denegado | bandeja, historial, aprobador real (Remote-User); Ranger > Audit > Admin | AE-08 |
Declaraciones:
- AE-01: Atlas es el mecanismo compatible; la sincronizacion hacia IDMC la hace el escaner de Informatica.
- AE-02: los tramos de origen (SQL Server) y de consumo (Power BI, RAG) se registran por API; el intermedio es automatico.
- AE-05: inmutabilidad por S3 Object Lock (AWS), no por Ranger. En la PoC GOVERNANCE + bucket policy; en produccion
  COMPLIANCE (ni root borra). Matiz: un "Delete" sin version solo agrega un delete marker.
- AE-07: el tenant no tiene el entitlement CDP_DATA_SHARE_ADMIN (Data Catalog sin menu Data Sharing; solicitado 28-oct) y la
  cuenta AWS no permite crear usuarios IAM. Plan C: user011 como ente externo, sin roles en la plataforma (no entra a Hue,
  CAI ni Data Catalog), solo SQL desde su herramienta sobre la tabla enmascarada, con politica Ranger temporal y revocable
  (mismo portal de AE-08). Declarar: el externo tiene una identidad CDP limitada; "sin cuenta" estricto = Data Sharing nativo.
  C01-AE-06 (motor externo sin exportar) queda [DECL] hasta el entitlement (fase3/c08/c08_ae07_lectura_externo.py listo).
- AE-08: workaround (el catalogo no trae flujo de solicitud); en produccion ServiceNow, Power Automate o IDMC Marketplace.
Lecciones: el contenedor de CAI corre en UTC (la vigencia de Ranger se envia en hora de Costa Rica); los audits de Ranger
estan en `<storage location base>/ranger/audit/` (ruta data, no logs); el paso 3 y el 5 corren el pipeline dos veces (~8 min).

## C05 CI/CD [OK 26/27-oct] ~20 min
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | PR abierto al inicio de la sesion: checks CI (esquema + calidad) y DEV via cola | checks verdes en el PR | AE-01, AE-02 |
| 2 | Pagina de `sib-despachador` | cola con estados, ambiente y version | AE-02 |
| 3 | Merge del PR: TEST automatico y PROD en "Waiting for review" | gate de aprobacion | AE-03, AE-04 |
| 4 | Review deployments > Approve and deploy | PROD verde | AE-03 |
| 5 | Actions > sb-cicd > Run workflow, rollback_ref = v1.0.0 (TEST, luego aprobar PROD) | version inmutable redesplegada | AE-05 |
| 6 | Hue: `SELECT * FROM sb_gov.despliegues ORDER BY 6 DESC LIMIT 8;` | historial completo | AE-05 |
Narrativa: el CI/CD externo no tiene credenciales de Cloudera AI; deja una solicitud auditable que la plataforma ejecuta
(la EC2 no llega al balanceador de CAI). Cada version se materializa por commit en `despliegues/<ambiente>/<commit>`.
Lecciones: el workflow hace checkout SIEMPRE de main y pasa el tag como --version (kit v19); `[skip ci]` en commits de kit;
Python del runner en `C:\actions-runner\.path` (una sola linea) y en el PATH de maquina; sb-prod con Required reviewers.
Tiempos: PR completo ~5 min; rollback TEST ~4 min + PROD ~5 min. Si el tiempo aprieta: rollback solo hasta TEST y mostrar
el run #16 del 27-oct como evidencia de PROD.

---

# SESION 3: IA y operacion (90 min)

Preparacion especifica:
- [ ] Modelo `sib-riesgo-credito` en Deployed; API key de usuario (formato "x.y") a mano
- [ ] Experimento MLflow `sb-riesgo-credito` con los runs Python y R; version registrada en AI Registry
- [ ] Endpoint del LLM (RAG) y servidor MCP (user008) arriba [PEND]
- [ ] Vista de consumo y costos de la Management Console filtrada por la PoC

| Min | Bloque | Contenido |
|---|---|---|
| 0-5 | Apertura | Ciclo de vida: dato gobernado -> entrenamiento trazable -> registro -> endpoint -> monitoreo |
| 5-55 | C06 IA/ML | AE-01, 03, 04, 05, 06, RAG, MCP |
| 55-80 | C09 Administracion y FinOps | AE-01, 02, 04, 05, 07 |
| 80-90 | Preguntas y cierre de la PoC | |

## C06 IA/ML [AE-01/03/04/05 OK 26/27-oct; drift, RAG y MCP PEND]
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | JOIN sobre PII enmascarada (user003 vs user001) | mismos totales, PII protegida | AE-01 |
| 2 | MLflow: run Python (500.000 filas, snapshot Iceberg 4266263547230025387, AUC 0.8075) y run R glm (AUC 0.803) | params, metricas, tags (snapshot, commit, autor), artefacto | AE-03, AE-04 |
| 3 | AI Registry: version del modelo registrada | linaje modelo -> datos | AE-04 |
| 4 | Endpoint: Test en UI (prob 0.1994, APROBAR) y prueba de carga | 500 req, 0 errores, p50 113 ms, p95 3121 ms, 9.4 req/s con 1 replica | AE-05 |
| 5 | Drift: comparacion contra `data/referencia_drift.csv` | alerta de drift visible en el job | AE-06 [PEND] |
| 6 | Asistente RAG sobre documentos normativos | respuesta con fuentes | [PEND] |
| 7 | MCP con user008: el agente consulta solo lo permitido por Ranger | consulta permitida y denegada | [PEND] |
Narrativa del p95: una sola replica de 1 vCPU; con 2-3 replicas baja (escalado horizontal desde Settings del modelo).
Lecciones: el build del endpoint no hereda paquetes de las sesiones (cdsw-build.sh con versiones EXACTAS); el artefacto
va en `fase3/c06/modelo_riesgo.pkl` (el build excluye lo de .gitignore); `track_metric` esta en `cml.metrics_v1`;
AI Registry requirio MLUser + Synchronize Users y, con RAZ, el machine user del registro en Ranger cm_s3 "all - bucket, path".
Si RAG o MCP no quedan listos: se declaran parciales con la arquitectura.

## C09 Administracion y FinOps [AE-02 y AE-04 OK 29-oct; AE-01 capturas PEND]
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Costos por proyecto y ambiente (tags + vista de consumo) | granularidad real del ambiente | AE-01 |
| 2 | Corrida corta en vivo: `python fase3/c02/c02_prueba_carga.py --prueba waa_vivo --depto b --niveles 50,100,200,300 --segundos 30 --sin-registro` + consola del VW (ejecutores 2 -> 4) | 0 errores; costo base 2 ejecutores vs pico 4, tope por Max groups | AE-02 |
| 3 | Cuello de botella: DROP STATS, consulta lenta, Query Profile, COMPUTE STATS, consulta rapida (validado 29-oct, tiempos anotados por Adrian) | diagnostico con evidencia | AE-04 |
| 4 | HA y perdida de nodo; DR | explicacion con diagrama | AE-05, AE-07 [DECL] |
Grafana del VW pidio un login distinto (no entro con user001 ni con el workload propio): evidencia del autoescalado desde la consola de CDW.
Costo/hora por ejecutor (CCU + EC2): lo aporta el AE con la calculadora.
Precision AE-05: Impala reintenta la consulta, no la continua. AE-03 (modelo comercial), AE-06 y PRE-03/04 (SLA, RTO/RPO,
costos) los presenta el AE con valores oficiales.

---

## Despues de cada sesion
- Detener el consumidor CDC (Ctrl+C) y cerrar las sesiones de CAI
- Suspender el VW, apagar el ambiente y la EC2
- Al cierre de la PoC: rotar las contrasenas de user001, user002 y sbcore_dbz; quitar la bucket policy del bucket WORM;
  revocar las solicitudes abiertas del portal (user011); revisar que `config.yaml` nunca se haya subido al repo
