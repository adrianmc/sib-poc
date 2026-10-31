# Sesion 1 (lunes 2-nov): Plataforma y datos. Paso a paso

Hilo de la sesion: del origen SQL Server al tablero de Power BI. Duracion: 90 min.
Version: dry-run del 30-oct aplicado. Todo lo de este documento se valido en ese ensayo.

Como leer cada paso:
- **Para que**: que demuestra ante la SIB o por que hace falta.
- **Donde / Que hacer**: la pantalla exacta y lo que se escribe o se pulsa.
- **Debe verse**: el resultado correcto.
- **Si falla**: que hacer.

Ningun paso depende de algo que no este escrito antes en este documento.

Usuarios (contrasenas de workload, las mismas de `config/config.yaml`):
user001 admin, user002 ingeniero, user005 analista region CENTRAL sin acceso confidencial,
user006 analista region NORTE con acceso confidencial.

---

## PARTE A. Preparacion (empezar 90 min antes)

### A1. Encender la EC2 (T-90)
**Para que:** en esa maquina Windows estan SQL Server (el origen de datos del cliente), Power BI y el runner de GitHub.
**Donde / Que hacer:**
1. Consola de AWS > region **US East (Ohio) us-east-2** (arriba a la derecha).
2. **EC2** > **Instances** > marcar la instancia Windows con IP privada **10.10.2.235** > **Instance state** > **Start instance**.
3. Conectarse por RDP como siempre.
**Debe verse:** Instance state **Running** y Status check **2/2 checks passed** (unos 3 min).

### A2. SQL Server Agent (T-85)
**Para que:** el Agent es el que publica los cambios en las tablas de CDC de SQL Server. Sin el, el CDC del bloque 5 no ve nada.
**Donde / Que hacer:** en la EC2, **SQL Server Management Studio (SSMS)** > **Connect** al servidor local > en **Object Explorer**,
el ultimo nodo, **SQL Server Agent**.
**Debe verse:** icono con flecha verde.
**Si falla:** cuadro rojo > clic derecho > **Start** > **Yes**.

### A3. Encender el ambiente de CDP (T-85, solo si esta apagado)
**Para que:** el ambiente incluye el Data Lake (Ranger, Atlas, metastore). Todo lo demas depende de el.
**Donde / Que hacer:** consola de CDP > **Management Console** > **Environments** > `sibrd-cdp-env`. Si no esta Running:
boton **Actions** (arriba a la derecha) > **Start Environment** > confirmar.
**Debe verse:** el ambiente y la pestana **Data Lake** en Running. Tarda de 40 a 60 min.

### A4. Encender el Data Hub de Kafka (T-30)
**Para que:** Kafka y Kafka Connect (Debezium) transportan los cambios de SQL Server para el CDC.
Encenderlo DESPUES de la EC2: si arranca con la EC2 apagada, la tarea de Debezium falla (ver A12).
**Donde / Que hacer:** Environments > `sibrd-cdp-env` > pestana **Data Hubs** > `sibrd-kafka` > **Actions** > **Start**.
**Debe verse:** **Running** en 10 a 15 min.

### A5. Encender los dos Virtual Warehouses (T-25)
**Para que:** `impala-sib-a` es el motor SQL de toda la sesion (Hue, Power BI, scripts). `impala-sib-waa` es el VW con
autoescalado, usado en la prueba de aislamiento del bloque 3.
**Donde / Que hacer:** selector de aplicaciones (cuadricula arriba a la izquierda) > **Data Warehouse** > **Virtual Warehouses**.
En las filas `impala-sib-a` e `impala-sib-waa`, si alguna dice Stopped, clic en su boton de encendido.
**Debe verse:** ambos **Running**.

### A6. Sesion de Cloudera AI con Terminal (T-20)
**Para que:** desde esta Terminal se corren todos los scripts de la sesion. La sesion es nueva cada dia, por eso se
reinstala `kafka-python` (lo usa el consumidor del CDC).
**Donde / Que hacer:**
1. Selector de aplicaciones > **AI Workbench** > workspace de la PoC > **Projects** > `sib-poc`.
2. **New Session**: Kernel **Python 3.10**, Resource Profile **2 vCPU / 4 GiB** > **Start Session**.
3. Cuando este lista, boton **Terminal Access** (abre una pestana con la Terminal). En ella:
   ```
   cd /home/cdsw && git pull && pip install -q kafka-python
   ```
**Debe verse:** termina sin error.

### A7. Conectividad a Ranger y Atlas (T-18)
**Para que:** los scripts que consultan Ranger y Atlas pasan por el gateway Knox del Data Lake, que solo acepta IP
autorizadas. Este script ademas es el ensayo del bloque 2.
**Donde / Que hacer:** en la Terminal:
```
python fase3/c03/c03_ae01_apis_plataforma.py
```
**Debe verse:** 6 lineas `[200]` y al final **"6/6 superficies respondieron OK"**.
**Si falla** (Atlas y Ranger con ERROR por timeout): la IP de salida de Cloudera AI no esta en el security group de Knox.
1. En la Terminal: `curl -s https://checkip.amazonaws.com` y anotar la IP.
2. AWS > **EC2** > **Instances** > instancia del gateway del Data Lake (nombre con `sibrd-aw-dl` y `gateway`) >
   pestana **Security** > clic en el security group > **Inbound rules** > **Edit inbound rules** > **Add rule**:
   Type **HTTPS**, Source **Custom** `<IP>/32` > **Save rules**.
3. Repetir el comando.

### A8. Filtro de fila correcto en COUNT(*) (T-15)
**Para que:** control del hallazgo del 29-oct. En tablas Iceberg, Impala podia responder `COUNT(*)` desde metadatos sin
aplicar el filtro de fila de Ranger. Los dos VW tienen la correccion; esto confirma que sigue puesta.
**Donde / Que hacer:** en la Terminal:
```
python -c "from lib.sbpoc import consulta; print(consulta('SELECT COUNT(*) FROM sb_curated.clientes', rol='analista2')[1])"
```
**Debe verse:** **[(150464,)]** (los clientes de NORTE que user006 puede ver).
**Si falla** (imprime [(1000000,)]): Data Warehouse > fila `impala-sib-a` > menu de tres puntos > **Edit** > pestana
**Configurations** > componente **Impala Coordinator** > archivo **flagfile** > `default_query_options` debe contener
`ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true` > **Apply Changes** (el VW se reinicia) > repetir el comando.

### A9. Sin marcadores de fallo pendientes (T-13)
**Para que:** en el bloque 3 se provoca un fallo controlado del pipeline con un archivo "marcador". Si quedo uno de un
ensayo, el pipeline fallaria cuando no toca.
**Donde / Que hacer:** en la Terminal:
```
python fase3/c02/c02_marcador.py ver
```
**Debe verse:** `...sb/control: vacia (sin marcadores)`.
**Si falla** (muestra `fallar_paso_3`): `python fase3/c02/c02_marcador.py borrar`.

### A10. Argumentos del Job del pipeline (T-12)
**Para que:** `--espera 180` son los segundos entre un intento fallido y el siguiente. Dan 3 min para mostrar el error,
explicarlo y borrar el marcador antes del reintento (con 60 s no alcanzo en el ensayo del 23-oct). Solo cuenta cuando un
paso falla: no alarga las corridas normales.
**Donde / Que hacer:** proyecto `sib-poc` > menu izquierdo **Jobs** > clic en `sib-pipeline` > pestana **Settings** >
campo **Arguments**:
```
--version v1 --reintentos 3 --espera 180
```
> **Update Job**.

### A11. Plan B de la API externa (T-10)
**Para que:** en el bloque 2 se llama en vivo a Alpha Vantage. `--desde-cache` NO llama a la API: reutiliza las respuestas
guardadas de la ultima llamada real (`data/cache_api/`) y hace el resto igual (JSON crudo a la capa raw y tabla curada).
Sirve si en vivo falla internet o la API, y no gasta cuota (plan gratuito: 25 llamadas por dia, 4 por corrida).
**Donde / Que hacer:** en la Terminal:
```
python fase3/c03/c03_ingesta_alphavantage.py --desde-cache
```
**Debe verse:** 4 lineas (accion_ibm, fx_usd_eur, tesoro_10a, tasa_fed) con filas.

### A12. Conector CDC en RUNNING (T-8)
**Para que:** Debezium (en Kafka Connect) lee los cambios de SQL Server. Si la EC2 estuvo apagada cuando arranco Kafka,
la tarea queda en FAILED ("No route to host") y Kafka Connect no reintenta solo.
**Donde / Que hacer:** Environments > `sibrd-cdp-env` > **Data Hubs** > `sibrd-kafka` > en la pagina del cluster, enlace
**Streams Messaging Manager** > menu izquierdo **Connect** > clic en el conector de SQL Server (el que lee la base `sbcore`).
**Debe verse:** el conector y la fila **Task 0** en **RUNNING**.
**Si falla:** en la fila de la tarea, **Restart**, y esperar RUNNING. Los cambios no se pierden: SQL Server los retiene 3 dias.

### A13. Power BI: dos reportes (T-6)
**Para que:** el bloque 4 muestra el mismo tablero con dos usuarios distintos. Se usan dos archivos para no cambiar
credenciales en vivo: `C04-AE-01.pbix` (user006, NORTE) y `C04-AE-03-user005.pbix` (user005, CENTRAL, sin columnas
confidenciales). El segundo apunta al servidor con `:443` al final para que Power BI le guarde su propia credencial.
**Donde / Que hacer** (en la EC2, Power BI Desktop):
1. **File** > **Open** > `C04-AE-01.pbix`. Si aparece la barra amarilla "Visuals are paused", clic en **Resume visual queries**.
2. El panel **Data** (derecha) debe listar `m_indice_morosidad...`, `transacciones` y `v_cartera_crediticia`. Si dice
   "You haven't loaded any data yet": **File** > **Save**, cerrar Power BI y volver a abrir el archivo.
3. Pagina **AE-01** (pestanas de abajo). Debe tener:
   - Tarjeta **Dias en Mora** = Sum of dias_mora con el numero completo (Display units = None). Anotar el valor.
   - Tabla con `identificacion_deudor`, `region`, `Sum of saldo_pendiente`, `Sum of dias_mora`, ordenada por dias_mora
     de mayor a menor.
   - **Format page** > **Page refresh** = On, 5 seconds.
   - Interacciones: la tabla NO filtra la tarjeta (Format > Edit interactions > sobre la tarjeta, icono "None").
4. **File** > **Open** > `C04-AE-03-user005.pbix` > Refresh.
**Debe verse:** el primero solo NORTE; el segundo solo CENTRAL. Sin errores en ninguno.

### A14. Ventanas de Hue (T-4)
**Para que:** Hue es la interfaz SQL. Cada usuario va en su propia ventana de incognito para mostrar que la misma consulta
devuelve cosas distintas segun quien la hace.
**Donde / Que hacer:**
1. Data Warehouse > **Virtual Warehouses** > fila `impala-sib-a` > boton **Data Explorer**.
2. Abrir 3 ventanas de incognito con esa URL y entrar con **user001**, **user002** y **user006**. En cada una:
   menu izquierdo **Editor** > **Impala**.
3. En la ventana de **user001**, dejar escritas SIN ejecutar las dos sentencias del bloque 4 (credito demo `id_credito = 8`,
   de NORTE, con dias_mora 0):
   ```
   UPDATE sb_curated.creditos SET dias_mora = dias_mora + 100000 WHERE id_credito = 8;
   UPDATE sb_curated.creditos SET dias_mora = dias_mora - 100000 WHERE id_credito = 8;
   ```

### A15. Material abierto (T-2)
- Navegador con `https://github.com/adrianmc/sib-poc/blob/main/fase3/c01/cdc/c01_ae05_generar_cambios.sql` (boton **Raw**).
- `fase3/c03/c03_apis_y_diagramas.md` para los diagramas del bloque 2.

---

## PARTE B. La sesion (90 min)

### Bloque 0. Apertura (0-10 min)
Mensaje: un solo origen (SQL Server, el core bancario ficticio) entra al lakehouse Iceberg por dos caminos (extraccion y CDC),
se organiza en capas raw, curada y consumible, se consulta con CDW y llega a Power BI. Ranger y Atlas (SDX) gobiernan
todo el recorrido: permisos, enmascaramiento, filtros, auditoria y linaje.

### Bloque 1. C01 Lakehouse (10-25 min)

**1.1 Misma tabla, dos motores (C01-AE-02).**
Para que: una sola copia fisica de los datos sirve a la interfaz SQL y a Python, con los mismos resultados.
- Hue **user006**: pegar y ejecutar la primera consulta de `fase3/c01/c01_ae02_misma_consulta.sql`.
- Terminal: `python fase3/c01/c01_ae02_notebook.py`
- Debe verse: los mismos numeros en ambos (region, canal, transacciones, monto). user006 solo ve NORTE.

**1.2 Operaciones transaccionales (C01-AE-03).**
Para que: el lakehouse acepta INSERT, UPDATE, DELETE y MERGE como una base de datos, y guarda cada cambio como snapshot.
- Hue **user002**: pegar `fase3/c01/c01_ae03_operaciones_transaccionales.sql` y ejecutar todo. Empieza con
  `DROP TABLE IF EXISTS` de su propia tabla de sandbox ("partimos de cero"); nunca toca las capas raw, curada ni consumible.
- Debe verse: todas las sentencias sin error y, al final, `DESCRIBE HISTORY` con un snapshot por operacion.

**1.3 Evolucion de esquema (C01-AE-04).**
Para que: se agregan y renombran columnas sin reescribir datos ni romper consultas.
- Hue **user002**: pegar `fase3/c01/c01_ae04_evolucion_esquema.sql` y ejecutar todo.
- Debe verse: la columna nueva con NULL en las filas historicas y el rename aplicado.

**1.4 Metadatos tecnicos (C01-AE-07).**
- Hue **user001**: pegar `fase3/c01/c01_ae07_metadatos.sql` y ejecutar todo.
- Debe verse: ubicacion, formato, snapshots, archivos y estadisticas de la tabla.

### Bloque 2. C03 Integraciones (25-35 min)

**2.1 APIs de la plataforma (C03-AE-01, PRE-02).**
Para que: Atlas, Ranger, Cloudera AI y CDW se operan por API, y un Job se puede lanzar desde fuera.
- Terminal: `python fase3/c03/c03_ae01_apis_plataforma.py --ejecutar-job sib-calidad`
- Debe verse: 7 lineas `[200]`/`[201]` con milisegundos, Atlas con "10 tablas de sb_curated catalogadas", y
  "7/7 superficies respondieron OK".
- Cloudera AI > **Jobs** > `sib-calidad` > **History**: la corrida recien lanzada por API.

**2.2 API externa autenticada (C03-AE-02).**
Para que: se consume una API financiera externa con API key y se guarda en el lakehouse (JSON crudo + tabla).
- Terminal: `python fase3/c03/c03_ingesta_alphavantage.py` (llamada REAL; usa 4 de las 25 llamadas del dia).
- Debe verse: 4 series con filas. La fecha maxima de accion_ibm y fx_usd_eur es el ultimo dia habil: prueba de que es en vivo.
- Si falla internet o la API: repetir con `--desde-cache` y decirlo en voz alta.
- Hue **user002**: `SELECT serie, COUNT(*), MAX(fecha) FROM sb_curated.mercado_series GROUP BY serie;`

**2.3 Manejo de errores de la API (C03-AE-02).**
- Terminal: `python fase3/c03/c03_ingesta_alphavantage.py --sin-clave --solo accion_ibm`
- Debe verse: falla con "la API respondio 'Error Message'... revisar clave, simbolo o cuota".

**2.4 Integraciones declaradas (C03-AE-03 a 07).** Diagramas de `c03_apis_y_diagramas.md`: Entra ID, SharePoint,
Dynamics 365, Informatica IDMC, Thales CipherTrust.

### Bloque 3. C02 Pipelines (35-50 min)

**3.1 Pipeline orquestado (C02-PRE-03, AE-01).**
- Cloudera AI > **Jobs**: `sib-calidad` depende de `sib-pipeline`. Abrir `sib-pipeline` > **History** > la ultima corrida
  Success > log: inicio, fin, estado y los 4 pasos con filas.
- `sib-calidad` > **History** > ultima corrida > log: 5 reglas [OK], 0 duplicados (C02-AE-06, integridad).

**3.2 Fallo controlado con mensaje accionable (C02-AE-05).**
Para que: cuando algo falla, el error dice que paso fallo y que hacer.
- Terminal: `python fase3/c02/c02_marcador.py crear` (crea un archivo que hace fallar el paso 3 a proposito).
- Jobs > `sib-pipeline` > **Run** > abrir la corrida en curso y mirar el log.
- Debe verse, a ~1.5 min: `Paso 3 intento 1: FALLIDO ... FALLO CONTROLADO ... Accion: eliminar el marcador ...`

**3.3 Recuperacion automatica (C02-AE-06).**
Para que: al corregir la causa, el pipeline se recupera solo, sin intervenir el job y sin perder ni duplicar datos.
- APENAS aparezca el FALLIDO, Terminal: `python fase3/c02/c02_marcador.py borrar`
- Debe verse, a los 3 min: `Paso 3 intento 2: EXITOSO`, el job en Success y `sib-calidad` corriendo sola despues.
- Mientras espera los 3 min: explicar la tabla de rendimiento (3.5).
- Hue **user001**, solo la ultima corrida y en orden:
  ```
  SELECT paso, intento, estado, mensaje FROM sb_consumption.pipeline_pasos WHERE run_id = (SELECT run_id FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC LIMIT 1) ORDER BY inicio;
  ```
  Debe verse: pasos 1 y 2 EXITOSO, paso 3 FALLIDO, paso 3 EXITOSO, paso 4 EXITOSO.

**3.4 Aislamiento entre departamentos (C02-AE-09). Validado el 30-oct.**
Para que: 500 usuarios cargando el VW de un departamento no afectan al VW del otro.
Requiere una segunda sesion de Cloudera AI de **8 vCPU / 16 GiB** abierta antes del bloque, con su Terminal.
1. Terminal de la sesion de 8 vCPU (carga en `impala-sib-waa`, 5 min):
   `python fase3/c02/c02_prueba_carga.py --prueba aislamiento --depto b --niveles 500 --segundos 300 --sin-registro`
2. 30 s despues, en la Terminal normal (sonda en `impala-sib-a`, 4 min):
   `python fase3/c02/c02_prueba_carga.py --prueba sonda_carga --depto a --niveles 1 --segundos 240 --sin-registro`
3. Ambas imprimen una linea cada 10 s. Debe verse: la carga con miles de consultas por intervalo y la sonda con p50
   cerca de **123 ms**, su valor sin carga.
Resultado del 30-oct: carga 34.176 consultas (114/s), 6 rechazos (0,02 %); sonda p50 123 ms, p95 173 ms.
Si preguntan por los rechazos: el control de admision de Impala rechaza cuando la cola se llena, para proteger el VW;
se ajusta con el maximo de grupos del autoescalado o el tiempo de cola (con costo: C09).

**3.5 Rendimiento de 50 a 500 usuarios (C02-PRE-06, AE-10).** Se muestra la tabla (la prueba completa dura 11 min):
| Usuarios | Exitosas/s fijo | Exitosas/s WAA | Errores fijo | Errores WAA | p95 fijo | p95 WAA |
|---|---|---|---|---|---|---|
| 50 | 114 | 120 | 0 | 0 | 541 ms | 551 ms |
| 200 | 60 | 135 | 0 | 0 | 4.1 s | 1.8 s |
| 300 | 46 | 138 | 1.720 | 0 | 7.6 s | 2.5 s |
| 500 | 71 | 118 | 2.595 | 0 | 8.2 s | 4.9 s |
Fijo = `impala-sib-a` (recursos fijos). WAA = `impala-sib-waa` (autoescalado por carga). Detalle en
`sb_consumption.metricas_rendimiento`.

### Bloque 4. C04 Power BI (50-65 min)

**4.1 Tiempo real en el tablero (C04-AE-01).**
Para que: un cambio en el lakehouse aparece en Power BI en segundos, sin refrescar a mano (DirectQuery + actualizacion
de pagina cada 5 s).
- Mostrar `C04-AE-01.pbix`, pagina **AE-01**: conector Impala, servidor `impala-sib-a`, DirectQuery, usuario user006.
- Hue **user001**: ejecutar `UPDATE ... + 100000 WHERE id_credito = 8;`
- Debe verse, en ~5 s: la tarjeta sube exactamente 100.000 y el deudor aparece primero en la tabla.
- Hue **user001**: ejecutar `UPDATE ... - 100000 WHERE id_credito = 8;` -> la tarjeta vuelve a su valor.

**4.2 Cada usuario ve lo suyo (C04-AE-03, PRE-01).**
Para que: el mismo tablero muestra datos distintos segun quien se conecta, porque Ranger filtra en la plataforma.
- Poner lado a lado `C04-AE-01.pbix` (user006: solo NORTE) y `C04-AE-03-user005.pbix` (user005: solo CENTRAL).
- Punto a favor: el reporte de user005 no tiene saldos porque Ranger le niega las columnas confidenciales
  (`saldo_pendiente` y el indice de morosidad). Si se intentan, Power BI muestra un error de sintaxis enganoso
  ("select top"): es la negacion de Ranger vista desde Power BI.

### Bloque 5. C01-AE-05 CDC (65-80 min). SIEMPRE despues del bloque 3
Por que al final: el pipeline del bloque 3 recarga `sb_curated.clientes` desde la capa raw y borraria lo aplicado por CDC.
En produccion ese paso seria un MERGE incremental (declararlo).

Para que: un cambio en el origen (SQL Server) llega solo a la tabla del lakehouse en segundos. Camino:
SQL Server registra el cambio > Debezium lo publica en Kafka > un consumidor en Cloudera AI lo toma > MERGE en Iceberg.

**5.1 Arrancar el consumidor (el que escucha).**
- Terminal: `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py`
- Debe verse: `Consumidor CDC activo (grupo sb-cdc-merge, desde fin); micro-lotes cada 15 s`. Dejarlo corriendo: solo toma
  los cambios que llegan despues de arrancar.

**5.2 Cambios en el origen.**
1. Navegador: `c01_ae05_generar_cambios.sql` en GitHub > **Raw** > copiar todo (Ctrl+A, Ctrl+C).
2. EC2 > SSMS > **New Query** > pegar > **Execute** (F5).
3. El script: pone en PYME a los clientes 10, 20 y 30 (UPDATE), crea un cliente nuevo (INSERT) y borra uno existente
   (DELETE). Calcula solo sus ids, por eso se puede repetir.
- Debe verse en **Results**: `id_insertado` (ej. 9000002) e `id_borrado` (ej. 41). Anotarlos.

**5.3 Llegada de los cambios.**
- Terminal del 5.1, sin escribir nada, 15 a 30 s.
- Debe verse: `sb_curated.clientes: 5 eventos -> MERGE {'u': 3, 'c': 1, 'd': 1}` (3 actualizaciones, 1 creacion, 1 borrado).

**5.4 Comprobacion en el lakehouse.**
- Hue **user001**, con los dos ids anotados:
  ```
  SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,<id_borrado>,<id_insertado>);
  ```
- Debe verse: 10, 20 y 30 en PYME con `cdc_ts` de hoy (en UTC: 19:47 de Costa Rica = 01:47 UTC del dia siguiente), el
  insertado presente y el borrado ausente.
- `DESCRIBE HISTORY sb_curated.clientes;` -> la ultima fila es el snapshot del MERGE.
- Terminal del 5.1: **Ctrl+C**.

### Bloque 6. Preguntas (80-90 min)

---

## PARTE C. Cierre
1. Terminal: `python fase3/c02/c02_marcador.py ver` -> vacia.
2. Cloudera AI: **Stop** en las sesiones abiertas.
3. Data Warehouse: suspender `impala-sib-a` e `impala-sib-waa`.
4. Data Hub `sibrd-kafka` > **Actions** > **Stop**; ambiente > **Actions** > **Stop Environment**; EC2 > **Stop instance**
   (la sesion 2 es el miercoles).

## Si algo falla en vivo
| Sintoma | Causa probable | Accion |
|---|---|---|
| Scripts de Ranger o Atlas con timeout | IP de Cloudera AI fuera del security group de Knox | A7, "Si falla" |
| `COUNT(*)` de user006 da 1.000.000 | Falta la opcion en el VW | A8, "Si falla" |
| El consumidor CDC no imprime MERGE | Tarea de Debezium en FAILED | A12; los cambios no se pierden |
| Power BI: "Visuals are paused" | Pausa de consultas activada | **Resume visual queries** |
| Power BI: panel Data vacio | Estado del archivo | Guardar, cerrar y reabrir el .pbix |
| Power BI: tarjeta fija en un valor raro | Una fila seleccionada filtra la tarjeta | Clic de nuevo en la fila; A13 paso 3 (interacciones) |
| Power BI: "select top 1000001" | El usuario no tiene acceso a una columna confidencial | Usar el reporte sin esas columnas (A13) |
| Power BI: 503 | Fuente apuntando a otro VW | Data source settings: host de `impala-sib-a` |
| El pipeline falla los 3 intentos | El marcador no se borro a tiempo | `python fase3/c02/c02_marcador.py borrar` y **Run** de nuevo |
| Cualquier otro | | Mostrar la captura de `evidencias/<codigo>/` y seguir |

## Pendiente fuera de esta sesion
- En la carga del 30-oct, `impala-sib-waa` no escalo (el 29-oct si: 2 -> 4 ejecutores). Afecta C09-AE-02 (sesion 3).
  Diagnostico: eventos de escalado del VW, mensaje completo de una consulta rechazada, parametros de Sizing and Scaling.
