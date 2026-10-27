# Guion operativo del dia de la demo (se completa a medida que cada bloque se valida en vivo)

Estado: borrador. Version final el 28-oct; dry-run el 29-oct.

## Checklist general antes de cada sesion
- [ ] Encender ambiente, Data Lake y Data Hubs al menos 1 h antes (arranque medido: >= 1 h)
- [ ] Data Lake, FreeIPA y Data Hubs en Running/Healthy
- [ ] Impala VW `impala-sib-a` encendido (el VW anterior quedo con el catalogd danado: no usar)
- [ ] Sesion de Cloudera AI abierta con Terminal; `cd /home/cdsw`
- [ ] Variable lista: `B=$(python -c "from lib.sbpoc import cfg; print(cfg()['s3']['bucket'])")`
- [ ] Las 3 IP de los NAT en el security group de Knox (y de CDW si aplica)
- [ ] Hue abierto desde el VW correcto; una ventana de incognito por usuario de demo
- [ ] EC2 SQL Server encendida ANTES que el Data Hub sibrd-kafka; despues en SMM > Connect revisar la tarea del conector sbcore: si esta FAILED ("No route to host" a 10.10.2.235:1433, quedo asi mientras la EC2 estaba apagada) -> Restart de la TAREA. Connect no reintenta solo
- [ ] Si se muestra C05: API key nueva (vence en 1 dia) en el secret CONFIG_YAML de GitHub

## C02 Procesamiento (validado 22/23-oct) - ~8 min

Preparacion (antes de la sesion):
1. Job `sib-pipeline`, argumentos: `--version v1 --reintentos 3 --espera 180` (3 min entre intentos para poder explicar).
2. Marcador ausente: `hdfs dfs -ls s3a://$B/sb/control/` debe estar vacio.
3. Tener escritos en un bloc de notas:
   - crear marcador: `echo x > /tmp/m && hdfs dfs -put -f /tmp/m s3a://$B/sb/control/fallar_paso_3`
   - borrar marcador: `hdfs dfs -rm s3a://$B/sb/control/fallar_paso_3`

Secuencia:
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Jobs: mostrar grafo `sib-pipeline -> sib-calidad` y una corrida en Success (2m47s, 25.75M filas) | Inicio, fin, estado, log de 4 pasos | C02-PRE-03, AE-01 |
| 2 | Log de `sib-calidad` | 5 reglas en [OK], 0 duplicados | AE-06 (integridad) |
| 3 | Crear marcador y Run de `sib-pipeline` | Tras ~1.5 min: `Paso 3 intento 1: FALLIDO ... FALLO CONTROLADO ... Accion: eliminar el marcador` | AE-05 |
| 4 | **Apenas aparezca el FALLIDO**, borrar el marcador | `Paso 3 intento 2: EXITOSO`, Job en Success, calidad corre sola | AE-06 (recuperacion) |
| 5 | Hue: `SELECT paso, intento, estado, mensaje FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC LIMIT 6;` | Paso 3 dos veces: FALLIDO y EXITOSO | AE-05, AE-06 |

Lecciones del ensayo (23-oct):
- Con `--espera 60` no hubo tiempo de borrar el marcador: los 3 intentos fallaron. Usar 180.
- Los pasos 1 y 2 tardan ~1.5 min antes de llegar al paso 3: mantener el comando `rm` ya escrito en la Terminal.
- La carpeta `sb/control` debe existir (`hdfs dfs -mkdir -p s3a://$B/sb/control`); `put` no la crea.
- Pendiente para el dry-run: completar el paso 4 (recuperacion) de punta a punta.

Plan B: capturas en `evidencias/C02/` (grafo de jobs, log de 4 pasos, log de calidad, log del fallo).
Cierre: confirmar marcador borrado.

## C07 Seguridad (validado 22-oct) - ~6 min
Ventanas de incognito: user005, user006, user001. En cada una (Hue, Impala):
`SELECT identificacion, nombre, region FROM sb_curated.clientes LIMIT 3;` y `SELECT id_credito, saldo_pendiente FROM sb_curated.creditos LIMIT 3;`
| Usuario | Esperado | Prueba |
|---|---|---|
| user005 | hash, solo CENTRAL; creditos: error de autorizacion | AE-02, AE-05 |
| user006 | hash, solo NORTE; creditos: OK | AE-01, AE-05 |
| user001 | todo en claro | AE-05 |
Luego Ranger > Audit > Access filtrando user005: Allowed y Denied (C07-AE-01, C08-AE-04).
Narrativa: permisos con roles de Ranger (independientes del IdP), atributos como roles, PII/CONFIDENCIAL por tags de Atlas.
Pendiente: capturas de evidencia (se cerro la sesion sin guardarlas).

## C04 Power BI (AE-01 validado 24-oct) - ~6 min
Preparacion: EC2 Windows encendida, Power BI con el driver Cloudera redirigido (guia c04, paso 0), conectado al host
de `impala-sib-a` (VW oficial; el AE-01 del 24-oct se valido contra sibrd-impala: reconectar), archivo .pbix
abierto con la pagina "AE-01" (tarjeta Suma dias_mora + tabla filtrada dias_mora > 900), conectado como user006.
Actualizacion de pagina cada 5 s. En Hue (user001) dejar escritos el UPDATE +1000 y el -1000 con el id_credito.
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | Mostrar conexion: conector Impala, DirectQuery, usuario user006 | Solo region NORTE (61.319 creditos), identificacion en hash | C04-PRE-01, AE-03 |
| 2 | Hue: UPDATE +1000 | Tarjeta sube 1000 y aparece la fila, sin tocar Power BI | AE-01 |
| 3 | Hue: UPDATE -1000 | Vuelve al valor original | AE-01 |
Lecciones (25-oct): con el host de sibrd-impala (VW viejo) Power BI dio 503 y luego ParseException en `select top`;
mismo archivo y driver con el host de impala-sib-a funciona. Todas las consultas del .pbix deben apuntar a impala-sib-a
(revisar en Editor avanzado, linea Source).
Lecciones (24-oct): el conector Impala de fabrica no habla HTTP (error "Unexpected response"); Hive LLAP ya no existe
en Power BI. Si Power BI se actualiza, rehacer el paso 0 de la guia. C04 completo 25-oct: AE-02 Import, AE-03 user005/user006 (Refresh tras cambiar usuario), AE-05, AE-06. AE-01 con actualizacion automatica de pagina (Format page > Page refresh).

## C01-AE-05 CDC SQL Server (COMPLETO 27-oct: SQL Server -> Debezium -> Kafka -> MERGE Iceberg)
Preparacion: SQL Server Agent corriendo en la EC2; conector `sb-cdc-sqlserver-core` y su Task 0 en Running (SMM > Connect).
Antes de la demo: confirmar que el driver sigue en `/var/lib/kafka_connect_jdbc/` de cada host de Connect (se pierde si un nodo se repara).
Lecciones (25-oct): faltaba el driver JDBC (NoClassDefFoundError); JAAS PLAIN obligatorio por conector (producer.override.*);
el historial de esquema no hereda la seguridad (schema.history.internal.producer/consumer.*); Kerberos via cm-agent keytab
no funciono, se usa PLAIN (en MAYUSCULAS); politicas Ranger en el servicio Kafka del Data Hub; tras corregir, reiniciar la TAREA;
topicos creados a mano (sin autocreacion); snapshot.isolation.mode=snapshot para no bloquear UPDATEs en SQL Server.
Snapshot validado 17:05: 1M clientes en Kafka. UPDATE en vivo capturado con op=u (17:13).
VALIDADO 27-oct: consumidor `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py` (Terminal CAI, `pip install kafka-python`,
CA de FreeIPA en config/datahub-ca.pem). c01_ae05_generar_cambios.sql en SSMS -> log
"sb_curated.clientes: 5 eventos -> MERGE {'u': 3, 'c': 1, 'd': 1} en 5.6 s"; en Hue 10/20/30 PYME y 9000001 con cdc_ts nuevo, 40 eliminado.
| # | Accion | Se ve |
|---|---|---|
| 1 | Terminal CAI: arrancar el consumidor ANTES de tocar SQL Server | "Consumidor CDC activo" |
| 2 | SSMS: ejecutar c01_ae05_generar_cambios.sql | 3 UPDATE, 1 INSERT, 1 DELETE en origen |
| 3 | Terminal: esperar la linea MERGE (15-30 s) | MERGE {'u': 3, 'c': 1, 'd': 1} |
| 4 | Hue: SELECT de ids 10,20,30,40,9000001 + DESCRIBE HISTORY | cdc_ts de hoy, 40 ausente, snapshot nuevo |
Lecciones (27-oct): si la EC2 estuvo apagada, la tarea de Debezium queda FAILED ("No route to host") y Connect no reintenta:
Restart de la TAREA; retoma desde su offset y publica lo pendiente (CDC de SQL Server retiene 3 dias). La EC2 en UTC es normal.
OJO ORDEN: cualquier corrida de sib-pipeline (C02, C05, C08-AE-06) recarga sb_curated.clientes desde sb_raw (TRUNCATE + INSERT)
y borra lo aplicado por CDC: mostrar CDC DESPUES de esas demos. Declarar: en produccion el paso 1 seria MERGE incremental.
Para repetir la demo: el INSERT de 9000001 falla si ya existe; antes borrar 9000001 en SSMS (o cambiar el id) y usar otros ids en el UPDATE.

## C01 Lakehouse (validado 25-oct)
AE-02 misma consulta Hue (user006) y Python impyla en CAI; AE-03 CTAS/INSERT/UPDATE/DELETE/MERGE + DESCRIBE HISTORY (user002);
AE-04 ADD COLUMNS/rename sin reescritura (user002); AE-07 DESCRIBE FORMATTED/HISTORY/SHOW FILES/COLUMN STATS (user001).
Leccion: config.yaml impala.host_depto_a debe ser el host de impala-sib-a (404 con el viejo).

## C05 CI/CD (en construccion 26-oct)
Chequeo previo (laptop, en el repo): `git ls-remote --tags origin v1.0.0` y `git show v1.0.0:fase3/c02/c02_pipeline_sql.py | head -1`
(si el segundo falla, el tag apunta a un commit viejo: `git tag -f v1.0.0 HEAD && git push -f origin v1.0.0`).
Leccion (26-oct): v1.0.0 se creo antes del pipeline; el job fallo con SystemExit 2. ejecutar_version.py ahora hace fetch
con --force, materializa por commit (no por tag) y valida que la version tenga el pipeline, con mensaje accionable.
Red (26-oct): la EC2 no llega al balanceador de CAI (TCP 443) aun con regla en su SG. Despliegue via cola:
`sb_gov.solicitudes_despliegue` + Application `sib-despachador` en CAI. Antes de la demo: sib-despachador en Running.
Narrativa: el CI/CD externo no tiene credenciales de Cloudera AI; deja una solicitud auditable que la plataforma ejecuta.
PR validado 26-oct 15:25: CI (esquema + calidad) 42 s en verde; DEV via cola: sib-despachador EXITOSO, check verde (4m56s total).
Secuencia demo C05: PR (CI + DEV) -> merge (TEST automatico) -> PROD "Waiting for review" -> aprobar -> PROD -> rollback
(Actions > sb-cicd > Run workflow, rollback_ref = v1.0.0). Pantallas: PR checks, pagina sib-despachador, Jobs de CAI,
`SELECT * FROM sb_gov.despliegues ORDER BY fecha DESC`.
Runner: Python en C:\Program Files\Python\Python311 debe estar en C:\actions-runner\.path (UNA sola linea) y en el PATH de maquina.
Estado C05 (26-oct): PR -> CI -> DEV -> merge -> TEST -> PROD funcionando (prod dfd61f5 EXITOSO). sb-prod quedo SIN required
reviewers durante esa corrida (corregido despues: Required reviewers = adrianmc, sin Prevent self-review).
C05 COMPLETO 27-oct (run #16, workflow_dispatch rollback_ref=v1.0.0): CI verde, DEV omitido, TEST verde (4m 11s),
PROD retenido en "Waiting for review" (AE-03), aprobado por adrianmc y desplegado (AE-05). Evidencias capturadas.
Fix 27-oct (kit v19): el workflow hace checkout SIEMPRE de main y pasa el tag como --version (antes hacia checkout del
tag viejo y usaba un desplegar_cai.py sin --via cola). Un solo Run workflow con v1.0.0 cubre AE-05 en TEST y AE-03 + AE-05 en PROD.

## C06 IA/ML (26-oct)
- AE-01 JOIN sobre PII enmascarada (user003 vs user001, mismos totales): validado.
- AE-04 Python + MLflow: 500.000 filas desde snapshot Iceberg 4266263547230025387, AUC 0.8075; run con params, metricas,
  tags (snapshot, commit, autor) y artefacto. AI Registry desplegado (requirio Manage Access MLUser + Synchronize Users);
  el modelo se registra con metadata pero la version falla: "Failed to create model registry directory in storage"
  (permiso de almacenamiento del registro). PENDIENTE 27-oct.
- AE-03 R (glm): AUC 0.803, run glm-R en el mismo experimento.
- AE-05 endpoint Models: Deployed tras 2 ajustes: build script fase3/c06/cdsw-build.sh (el build no hereda paquetes de
  las sesiones: joblib/scikit-learn con la version EXACTA del entrenamiento) y artefacto en fase3/c06/modelo_riesgo.pkl
  (el build excluye lo que esta en .gitignore: data/, *.joblib). Antes de desplegar: cp data/modelo_riesgo.joblib fase3/c06/modelo_riesgo.pkl
- AE-05 VALIDADO 27-oct: Test en UI OK (prob 0.1994, APROBAR) con autenticacion activa. API key formato "x.y" (valor
  largo completo). Carga 500 req / 10 hilos: 0 errores, p50 113 ms, p95 3121 ms, 9.4 req/s con 1 replica de 1 vCPU.
  Narrativa: la cola p95 es por 1 sola replica; con 2-3 replicas baja (escalado horizontal desde Settings del modelo).
  Fix aplicado: track_metric esta en cml.metrics_v1 (no en models_v1).
- AE-04 COMPLETO 27-oct: version registrada en AI Registry tras dar acceso al machine user del registro en Ranger
  cm_s3 > "all - bucket, path" (ambiente con RAZ). Sin RAZ seria IDBroker mapping del Machine User CRN.

## C08 Gobernanza (en curso 27-oct)
| # | Accion | Se ve | Prueba |
|---|---|---|---|
| 1 | CAI Terminal: `python fase3/c08/c08_registro_activos_y_linaje_bi.py` | 200/409; Atlas: Business Metadata Gobierno_SB en clientes/creditos; linaje SQL Server -> curada -> vista -> dashboard | PRE-01/02, AE-01/02 |
| 2 | Hue (user002): parte AE-03 de c08_impacto_y_corrupcion.sql | vista dependiente falla tras el rename; Atlas la muestra downstream | AE-03 |
| 3 | Hue (user002): corrupcion de entidad 7 + Job sib-pipeline + SELECT | 'ENTIDAD CORRUPTA - DEMO' en transacciones y Power BI; Ranger audit del UPDATE; rollback | AE-06 |
| 4 | Ranger > Audit > Access (user005) | Allowed y Denied | AE-04 |
| 5 | AWS: bucket WORM + delete -> AccessDenied | inmutabilidad | AE-05, PRE-05 |
| 6 | Data Sharing de sb_share.clientes_externo + revocar | lee, luego denegado | AE-07 |
| 7 | c08_solicitud_acceso.py solicitar/listar/aprobar | usuario consulta tras ~30 s | AE-08 (workaround) |
