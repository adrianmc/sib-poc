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

## Parte 0: como se hace cada cosa (navegacion)
Cada paso del guion cita estos codigos [N#]. Nombres que dependen del tenant van entre < >.

| Codigo | Que | Donde y como | Que debe verse / si falla |
|---|---|---|---|
| N1 | Consola de CDP | Navegador > URL del tenant > login SSO | Pagina de inicio con los servicios |
| N2 | Encender el ambiente | Management Console > Environments > `sibrd-cdp-env` > boton **Actions** (arriba a la derecha) > **Start Environment** | Ambiente y pestana **Data Lake** en Running/Available. Tarda 40-60 min |
| N3 | Encender el Data Hub de Kafka | Environments > `sibrd-cdp-env` > pestana **Data Hubs** > `sibrd-kafka` > **Actions** > **Start** | Running en 10-15 min. Encender DESPUES de la EC2 (N4) |
| N4 | EC2 Windows (SQL Server, Power BI, runner) | Consola AWS, region us-east-2 (Ohio) > **EC2** > **Instances** > la instancia Windows con IP privada 10.10.2.235 > **Instance state** > **Start**. Entrar por RDP como siempre | Instance state = Running y Status checks 2/2 (~3 min) |
| N5 | SQL Server Agent | En la EC2: **SSMS** > Object Explorer > conectar al servidor > nodo **SQL Server Agent** | Icono con flecha verde. Si tiene cuadro rojo: clic derecho > **Start** |
| N6 | Estado del conector CDC | Environments > `sibrd-cdp-env` > Data Hubs > `sibrd-kafka` > en la pagina del cluster, enlaces de servicios > **Streams Messaging Manager** > menu izquierdo **Connect** > clic en el conector de SQL Server (el que lee `sbcore`) | Conector y fila **Task 0** en RUNNING. Si la tarea esta FAILED: en la fila de la tarea, **Restart** (o menu de tres puntos > Restart) y esperar RUNNING |
| N7 | Encender un Virtual Warehouse | Selector de aplicaciones (cuadricula arriba a la izquierda) > **Data Warehouse** > **Virtual Warehouses** > fila del VW | Estado Running. Si dice Stopped: boton de encendido (play) en la fila; 2-5 min |
| N8 | Hue como un usuario | En N7, fila de `impala-sib-a` > boton **Data Explorer** > login con usuario y password de workload (ej. user006). Una ventana de incognito por usuario. Editor: menu izquierdo **Editor** > **Impala**, pegar el SQL, ejecutar con el triangulo o Ctrl+Enter | Los archivos .sql del kit se abren en CAI (N9, pestana **Files**) o en GitHub y se copian al editor |
| N9 | Sesion y Terminal de Cloudera AI | Selector de aplicaciones > **AI Workbench** > workspace de la PoC > **Projects** > `sib-poc` > **New Session**: Python 3.10, 2 vCPU / 4 GB (8 vCPU / 16 GB para la prueba de carga) > **Start Session** > cuando este lista, boton **Terminal Access** > `cd /home/cdsw` | Prompt `cdsw@...:~$` |
| N10 | Applications de CAI | Proyecto `sib-poc` > menu izquierdo **Applications** | `sib-despachador` y `sib-accesos` en Running. Si no: menu de tres puntos > **Restart**. Abrir: clic en el nombre |
| N11 | Jobs de CAI | Proyecto `sib-poc` > **Jobs** > clic en el job > pestana **Settings**: campo **Arguments** > **Update Job**. Ejecutar: boton **Run**. Ver corridas y logs: pestana **History** > clic en la corrida | Estado Success / Failed por corrida |
| N12 | Ranger | Environments > `sibrd-cdp-env` > pestana **Data Lake** > enlaces de servicios > **Ranger**. Auditoria: menu superior **Audit** > **Access** > filtro **User** | Filas con resultado Allowed / Denied |
| N13 | Atlas | Igual que N12 > **Atlas** > buscar por nombre de tabla | Entidad con pestanas Properties y Lineage |
| N14 | IP de CAI en el security group de Knox | 1) Terminal de CAI (N9): `curl -s https://checkip.amazonaws.com`. 2) Consola AWS > **EC2** > **Instances** > instancia gateway del Data Lake (nombre con `sibrd-aw-dl` y `gateway`) > pestana **Security** > clic en el security group > **Inbound rules** | Regla HTTPS 443 con la IP del paso 1 en /32 y las 3 IP de los NAT. Si falta: **Edit inbound rules** > **Add rule** > HTTPS > Source `<IP>/32` > **Save** |
| N15 | Power BI | En la EC2: Power BI Desktop > **File** > **Open** > el .pbix de la demo. Fuente: **Home** > **Transform data** > **Data source settings**: servidor = host de `impala-sib-a`. Credenciales: **Edit Permissions** > **Edit**. Auto refresh: clic en la pagina > panel Visualizations > **Format page** (pincel) > **Page refresh** On, 5 seconds | Visuales cargan sin error |
| N16 | GitHub | Repo `adrianmc/sib-poc` > **Actions** (corridas) / **Pull requests** / **Settings** > **Actions** > **Runners** | Runner `sb-poc` en Idle (requiere la EC2 encendida) |
| N17 | AWS CloudShell | Consola AWS (us-east-2) > icono `>_` en la barra superior | Prompt de CloudShell |
| N18 | Ejecutar un script del kit | Terminal de CAI (N9), desde `/home/cdsw`: `python <ruta del script>` | Salida en la Terminal |

## Preparacion comun (antes de CADA sesion, empezar 90 min antes)
| Hora | Paso | Como | Verificacion |
|---|---|---|---|
| T-90 | 1. Encender la EC2 | N4 | Running, 2/2 checks |
| T-85 | 2. Encender el ambiente (si esta apagado) | N2 | Ambiente y Data Lake Running (~40-60 min) |
| T-85 | 3. SQL Server Agent | N5 | Flecha verde |
| T-30 | 4. Encender el Data Hub de Kafka (solo sesion 1) | N3 | Running |
| T-25 | 5. Encender `impala-sib-a` y `impala-sib-waa` | N7 | Ambos Running |
| T-20 | 6. Sesion de CAI con Terminal | N9 | Prompt en `/home/cdsw` |
| T-18 | 7. IP de CAI en el security group de Knox | N14 | Regla presente. Sintoma si falta: timeout hacia `...dl-gateway...` en scripts que usan Ranger o Atlas |
| T-15 | 8. Applications | N10 | `sib-despachador` y `sib-accesos` Running |
| T-12 | 9. Correccion del COUNT(*) | N8 como user006: `SELECT COUNT(*) FROM sb_curated.clientes;` | **150.464**. Si da 1.000.000: CDW > VW > **Edit** > **Configurations** > Impala Coordinator > flagfile > `default_query_options` debe tener `ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true` |
| T-10 | 10. Variable del bucket en la Terminal | N9: `B=$(python -c "from lib.sbpoc import cfg; print(cfg()['s3']['bucket'])")` | `echo $B` imprime el bucket |
| T-5 | 11. Plan B a mano | Carpeta de capturas por codigo | Abierta |

---

# SESION 1: Plataforma y datos (90 min)

Preparacion especifica de la sesion 1 (despues de la comun). Los scripts de demo son repetibles por si mismos
(C01-AE-03 empieza con DROP IF EXISTS de su tabla de sandbox; el CDC calcula sus ids): no hay limpieza previa.
| Paso | Como | Verificacion |
|---|---|---|
| 1. Conector CDC | N6 | Conector y Task 0 RUNNING (si la EC2 estuvo apagada, la tarea queda FAILED: Restart) |
| 2. Carpeta de control de C02 vacia | Terminal (N9): `hdfs dfs -mkdir -p s3a://$B/sb/control && hdfs dfs -ls s3a://$B/sb/control/` | Sin archivos listados |
| 3. Argumentos del Job | N11: job `sib-pipeline` > Settings > Arguments = `--version v1 --reintentos 3 --espera 180` | Guardado |
| 4. Datos de C03 desde cache | N18: `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache` | 4 series con filas |
| 5. Power BI | N15: fuente = host de `impala-sib-a`, credencial user006, pagina **AE-01** con Page refresh 5 s | Tarjeta y tabla cargadas, solo NORTE |
| 6. SQL de C04 listo | N8 como user001: dejar escritos (sin ejecutar) el UPDATE +1000 y el -1000 del `id_credito` de la tabla AE-01 | Editor con las dos sentencias |
| 7. Bloc de notas de C02 | Copiar los comandos de crear y borrar el marcador (bloque C02) | Listos para pegar |

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
| # | Como | Accion | Se ve | Prueba |
|---|---|---|---|---|
| 1a | N8 user006 | Pegar y ejecutar `fase3/c01/c01_ae02_misma_consulta.sql` (la primera consulta) | Tabla region / canal / transacciones / monto | AE-02 |
| 1b | N18 | `python fase3/c01/c01_ae02_notebook.py` | Los mismos numeros que en Hue, desde Python | AE-02 |
| 2 | N8 user002 | Pegar y ejecutar `fase3/c01/c01_ae03_operaciones_transaccionales.sql` completo (Ctrl+Enter sentencia por sentencia o "ejecutar todo") | CTAS, INSERT, UPDATE, DELETE y MERGE sin error; `DESCRIBE HISTORY` con un snapshot por operacion | AE-03 |
| 3 | N8 user002 | Pegar y ejecutar `fase3/c01/c01_ae04_evolucion_esquema.sql` | Columna nueva con NULL en filas viejas, rename sin reescritura | AE-04 |
| 4 | N8 user001 | Pegar y ejecutar `fase3/c01/c01_ae07_metadatos.sql` | DESCRIBE FORMATTED, HISTORY, SHOW FILES, COLUMN STATS | AE-07 |
Leccion: `config.yaml impala.host_depto_a` debe ser el host de impala-sib-a (404 con el viejo).
C01-AE-06 (motor externo sin exportar) se muestra en la sesion 2 con C08-AE-07.

## C03 Integraciones [AE-01/02 OK 29-oct, incluido --sin-clave] ~10 min
Validado 29-oct: 7/7 superficies OK; Alpha Vantage accion_ibm 100, fx_usd_eur 100, tesoro_10a 882, tasa_fed 867 filas
(2.7 a 4 s por fuente). En la demo usar --desde-cache (no gasta cuota: 25 solicitudes/dia, 4 por corrida).
| # | Como | Accion | Se ve | Prueba |
|---|---|---|---|---|
| 1 | N18 | `python fase3/c03/c03_ae01_apis_plataforma.py --ejecutar-job sib-calidad` | 7 lineas [200]/[201] con ms; "7/7 superficies respondieron OK"; en N11 aparece una corrida nueva de sib-calidad | AE-01, PRE-02 |
| 2 | N18 | `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache` | 4 series con filas | AE-02 |
| 3 | N8 user002 | `SELECT serie, COUNT(*), MAX(fecha) FROM sb_curated.mercado_series GROUP BY serie;` y `SELECT fuente, ingesta_ts FROM sb_raw.api_alphavantage LIMIT 4;` | Curada y JSON crudo | AE-02 |
| 4 | N18 | `python fase3/c03/c03_ingesta_alphavantage.py --sin-clave --solo accion_ibm` | Falla con "la API respondio 'Error Message'... revisar clave" | AE-02 (errores) |
| 5 | Pantalla | Diagramas de `fase3/c03/c03_apis_y_diagramas.md` (Entra, SharePoint, D365, IDMC, CipherTrust) | documental | AE-03..07 [DECL] |

## C02 Pipelines [OK 22/23-oct; recuperacion PEND dry-run] ~15 min
Bloc de notas:
- crear marcador: `echo x > /tmp/m && hdfs dfs -put -f /tmp/m s3a://$B/sb/control/fallar_paso_3`
- borrar marcador: `hdfs dfs -rm s3a://$B/sb/control/fallar_paso_3`

| # | Como | Accion | Se ve | Prueba |
|---|---|---|---|---|
| 1 | N11 | Lista de Jobs: `sib-calidad` depende de `sib-pipeline`. Abrir `sib-pipeline` > History > la ultima corrida Success > log | Inicio, fin, estado y log de los 4 pasos con filas | PRE-03, AE-01 |
| 2 | N11 | `sib-calidad` > History > ultima corrida > log | 5 reglas [OK], 0 duplicados | AE-06 (integridad) |
| 3 | N9 | Pegar el comando "crear marcador" del bloc de notas | Sin error | AE-05 |
| 4 | N11 | `sib-pipeline` > **Run** > abrir la corrida en curso y mirar el log | A ~1.5 min: `Paso 3 intento 1: FALLIDO ... FALLO CONTROLADO ... Accion: eliminar el marcador` | AE-05 |
| 5 | N9 | APENAS aparezca el FALLIDO, pegar el comando "borrar marcador" | En el log: `Paso 3 intento 2: EXITOSO`; job en Success; sib-calidad corre sola | AE-06 (recuperacion) |
| 6 | N8 user001 | `SELECT paso, intento, estado, mensaje FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC LIMIT 6;` | Paso 3 FALLIDO y EXITOSO | AE-05, AE-06 |
| 7 | Pantalla | Tabla de rendimiento fijo vs WAA (abajo) | 0 errores con WAA a 500 usuarios | PRE-06, AE-10 |
| 8 | N9 x2 | Aislamiento en vivo (abajo) | Sonda en impala-sib-a cerca de su linea base | AE-09 [PEND] |
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
| # | Como | Accion | Se ve | Prueba |
|---|---|---|---|---|
| 1 | N15 | Mostrar Data source settings: conector Impala, servidor impala-sib-a, DirectQuery, credencial user006 | Solo region NORTE (61.319 creditos), identificacion en hash | PRE-01, AE-03 |
| 2 | N8 user001 | Ejecutar el UPDATE +1000 preparado | En ~5 s la tarjeta sube 1000 y aparece la fila, sin tocar Power BI | AE-01 |
| 3 | N8 user001 | Ejecutar el UPDATE -1000 | Vuelve al valor original | AE-01 |
| 4 | N15 | Data source settings > Edit Permissions > Edit > user005 > OK > **Refresh** | Solo CENTRAL | AE-03 |
| 5 | N15 | Volver a user006 > Refresh (deja Power BI listo) | NORTE | |
Lecciones: el conector Impala de fabrica no habla HTTP; se redirige al driver Cloudera 2.7+ (guia c04, paso 0; rehacer si
Power BI se actualiza). Hive LLAP ya no existe en Power BI. Todas las consultas del .pbix deben apuntar a impala-sib-a
(Editor avanzado, linea Source). Tras cambiar de usuario: Refresh. Vistas con INNER JOIN a clientes (el LEFT JOIN filtro
348.433 creditos sin region). AE-02 Import, AE-05 y AE-06 validados el 25-oct.

## C01-AE-05 CDC SQL Server -> Kafka -> MERGE Iceberg [OK 27-oct] ~15 min
NOTA DE ORDEN: cualquier corrida de sib-pipeline (C02, C05, C08-AE-06) recarga sb_curated.clientes desde sb_raw
(TRUNCATE + INSERT) y borra lo aplicado por CDC. Por eso el CDC cierra la sesion 1. Declarar: en produccion el paso 1
del pipeline seria un MERGE incremental.
| # | Como | Accion | Se ve | Prueba |
|---|---|---|---|---|
| 0 | N9 | En la sesion del dia (es nueva cada dia): `pip install -q kafka-python` | Sin error | |
| 1 | N18 | `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py` y dejarlo corriendo, ANTES de tocar SQL Server | "Consumidor CDC activo" | |
| 2 | En la EC2: SSMS > New Query | Pegar `fase3/c01/cdc/c01_ae05_generar_cambios.sql` (desde GitHub > Raw) > **Execute** | 3 filas actualizadas, `id_insertado` e `id_borrado` en la grilla de resultados (anotarlos) | AE-05 |
| 3 | Terminal del paso 1 | Esperar 15-30 s | `sb_curated.clientes: 5 eventos -> MERGE {'u': 3, 'c': 1, 'd': 1}` | AE-05 |
| 4 | N8 user001 | `SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,<id_borrado>,<id_insertado>);` y `DESCRIBE HISTORY sb_curated.clientes;` | 10/20/30 en PYME con cdc_ts de hoy, el id insertado nuevo, el id borrado ausente, snapshot nuevo | AE-05 |
| 5 | Terminal del paso 1 | Ctrl+C | Consumidor detenido | |
Resultado del 27-oct: 5 eventos -> MERGE en 5.6 s.
Lecciones: driver JDBC copiado a mano; JAAS PLAIN por conector (producer.override.*) y en schema.history.internal.*;
PLAIN en MAYUSCULAS; politicas Ranger en el servicio Kafka del Data Hub (sb_12, sb_13); topicos creados a mano;
snapshot.isolation.mode=snapshot; tras corregir, reiniciar la TAREA. Requisitos del consumidor: `pip install kafka-python`,
CA de FreeIPA en `config/datahub-ca.pem`. Detener con Ctrl+C al terminar.

---

# SESION 2: Seguridad, gobierno y DevOps (90 min)

Preparacion especifica de la sesion 2 (despues de la comun; el Data Hub de Kafka no hace falta):
| Paso | Como | Verificacion |
|---|---|---|
| 1. Runner de GitHub | N16 > Settings > Actions > Runners | `sb-poc` en Idle (si Offline: la EC2 esta apagada o el servicio del runner detenido) |
| 2. API key de CAI vigente | CAI > avatar > **User Settings** > **API Keys**: si la usada en `config/config.yaml` (seccion `cai`) vencio, **Create API Key** (API v2), pegarla en `cai.api_key` y reiniciar `sib-despachador` (N10) | El despachador muestra "ultima revision" reciente y sin error |
| 3. Tag v1.0.0 con el pipeline | Terminal (N9): `git fetch origin --tags --force && git cat-file -e v1.0.0:fase3/c02/c02_pipeline_sql.py && echo OK` | Imprime OK |
| 4. Rama para el PR de la demo | En la laptop, carpeta `sb-poc`: `git checkout main && git pull && git checkout -b feature/demo-sesion2 && echo "demo" >> fase3/c02/LEEME_JOBS_CAI.md && git commit -am "Demo sesion 2" && git push -u origin feature/demo-sesion2 && git checkout main` (SIN `[skip ci]`) | La rama aparece en GitHub; el PR se abre en vivo |
| 5. Power BI de C08 | N15: pagina con la tabla `nombre_entidad` + conteo, filtrada por `id_entidad_destino = 7` (credencial user001) | Nombre original de la entidad 7 |
| 6. Power BI de C08-AE-07 | N15: segunda conexion con user011 (sin acceso todavia) | Navegador sin tablas |
| 7. CloudShell para C08-AE-05 | N17: `B=<bucket-worm>`, luego las lineas K y V de la guia `fase3/c08/c08_auditoria_e_inmutabilidad.md` | `echo $K $V` imprime ruta y version |
| 8. Portal limpio | N10 > abrir `sib-accesos` | Pendientes = 0; si quedo alguna de ensayos: **Rechazar** |

| Min | Bloque | Contenido |
|---|---|---|
| 0-5 | Apertura | SDX: Ranger (permisos, masking, filtros, auditoria), Atlas (tags, linaje), roles independientes del IdP |
| 5-20 | C07 Seguridad | AE-01, AE-02, AE-05. Al inicio, abrir el PR de C05 para que CI y DEV corran en paralelo |
| 20-60 | C08 Gobierno | PRE-01/02, AE-01..08 |
| 60-80 | C05 CI/CD | AE-01..05 |
| 80-90 | Preguntas | |

## C07 Seguridad [OK 22-oct; capturas 29-oct] ~15 min
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

## C09 Administracion y FinOps [AE-01 capturas, AE-02 y AE-04 OK 29-oct]
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
