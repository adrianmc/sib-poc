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

## C01-AE-05 CDC SQL Server (conector validado 25-oct; consumidor MERGE pendiente)
Preparacion: SQL Server Agent corriendo en la EC2; conector `sb-cdc-sqlserver-core` y su Task 0 en Running (SMM > Connect).
Antes de la demo: confirmar que el driver sigue en `/var/lib/kafka_connect_jdbc/` de cada host de Connect (se pierde si un nodo se repara).
Lecciones (25-oct): faltaba el driver JDBC (NoClassDefFoundError); JAAS PLAIN obligatorio por conector (producer.override.*);
el historial de esquema no hereda la seguridad (schema.history.internal.producer/consumer.*); Kerberos via cm-agent keytab
no funciono, se usa PLAIN (en MAYUSCULAS); politicas Ranger en el servicio Kafka del Data Hub; tras corregir, reiniciar la TAREA;
topicos creados a mano (sin autocreacion); snapshot.isolation.mode=snapshot para no bloquear UPDATEs en SQL Server.
Snapshot validado 17:05: 1M clientes en Kafka. UPDATE en vivo capturado con op=u (17:13). Pendiente: consumidor MERGE a Iceberg.

## C01 Lakehouse (validado 25-oct)
AE-02 misma consulta Hue (user006) y Python impyla en CAI; AE-03 CTAS/INSERT/UPDATE/DELETE/MERGE + DESCRIBE HISTORY (user002);
AE-04 ADD COLUMNS/rename sin reescritura (user002); AE-07 DESCRIBE FORMATTED/HISTORY/SHOW FILES/COLUMN STATS (user001).
Leccion: config.yaml impala.host_depto_a debe ser el host de impala-sib-a (404 con el viejo).
