# Sesion 1 (lunes 2-nov): Plataforma y datos. Paso a paso

Del origen SQL Server al tablero. Duracion: 90 min. Cada paso dice DONDE, QUE hacer y QUE debe verse.
Ningun paso depende de algo que no este escrito antes en este documento.

Usuarios: user001 admin, user002 ingeniero, user005 analista CENTRAL, user006 analista NORTE.
Contrasenas: las de workload de cada usuario (las mismas de `config/config.yaml`).

---

## PARTE A. Preparacion (empezar 90 min antes)

### A1. Encender la EC2 de SQL Server y Power BI (T-90)
1. Consola de AWS > arriba a la derecha, region **US East (Ohio) us-east-2**.
2. Servicio **EC2** > **Instances**.
3. Marcar la instancia Windows cuya IP privada es **10.10.2.235** > **Instance state** > **Start instance**.
4. Esperar: Instance state = **Running** y Status check = **2/2 checks passed** (~3 min).
5. Conectarse por RDP como siempre.

### A2. SQL Server Agent (T-85)
1. En la EC2, abrir **SQL Server Management Studio** > **Connect** al servidor local.
2. En **Object Explorer**, mirar el ultimo nodo, **SQL Server Agent**.
3. Debe tener una flecha verde. Si tiene un cuadro rojo: clic derecho > **Start** > **Yes**.

### A3. Encender el ambiente de CDP (T-85, si esta apagado)
1. Consola de CDP > **Management Console** > **Environments** > `sibrd-cdp-env`.
2. Si el estado no es Available/Running: boton **Actions** (arriba a la derecha) > **Start Environment** > confirmar.
3. Esperar a que el ambiente y la pestana **Data Lake** queden en Running (40 a 60 min).

### A4. Encender el Data Hub de Kafka (T-30, con el ambiente ya arriba y la EC2 encendida)
1. Environments > `sibrd-cdp-env` > pestana **Data Hubs** > clic en `sibrd-kafka`.
2. Si esta Stopped: **Actions** > **Start**. Esperar **Running** (10 a 15 min).

### A5. Encender los dos Virtual Warehouses (T-25)
1. Selector de aplicaciones (cuadricula arriba a la izquierda) > **Data Warehouse** > **Virtual Warehouses**.
2. Filas `impala-sib-a` e `impala-sib-waa`: si alguna dice Stopped, clic en su boton de encendido. Esperar **Running**.

### A6. Sesion de Cloudera AI con Terminal (T-20)
1. Selector de aplicaciones > **AI Workbench** > workspace de la PoC > **Projects** > `sib-poc`.
2. **New Session**: Kernel **Python 3.10**, Resource Profile **2 vCPU / 4 GiB** > **Start Session**.
3. Cuando la sesion este lista, boton **Terminal Access** (se abre una pestana con la Terminal).
4. En la Terminal, pegar:
   ```
   cd /home/cdsw && git pull && pip install -q kafka-python
   ```
   Debe terminar sin error.

### A7. Conectividad a Ranger y Atlas y ensayo de C03 (T-18)
1. En la Terminal:
   ```
   python fase3/c03/c03_ae01_apis_plataforma.py
   ```
2. Debe decir **"6/6 superficies respondieron OK"**.
3. Si Atlas y Ranger dicen ERROR con timeout: falta la IP de CAI en el security group de Knox:
   1. En la Terminal: `curl -s https://checkip.amazonaws.com` (anotar la IP).
   2. AWS > **EC2** > **Instances** > buscar la instancia del gateway del Data Lake (nombre con `sibrd-aw-dl` y `gateway`).
   3. Pestana **Security** > clic en el security group > **Inbound rules** > **Edit inbound rules** > **Add rule**:
      Type **HTTPS**, Source **Custom** `<IP>/32` > **Save rules**.
   4. Repetir el paso 1.

### A8. Filtro de fila correcto en COUNT(*) (T-15)
1. En la Terminal:
   ```
   python -c "from lib.sbpoc import consulta; print(consulta('SELECT COUNT(*) FROM sb_curated.clientes', rol='analista2')[1])"
   ```
2. Debe imprimir **[(150464,)]**.
3. Si imprime [(1000000,)]: Data Warehouse > fila `impala-sib-a` > menu de tres puntos > **Edit** > pestana **Configurations** >
   componente **Impala Coordinator** > archivo **flagfile** > `default_query_options` debe contener
   `ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true` > **Apply Changes** (el VW se reinicia) > repetir el paso 1.

### A9. Sin marcadores de fallo pendientes (T-13)
1. En la Terminal:
   ```
   python fase3/c02/c02_marcador.py ver
   ```
2. Debe decir **"vacia (sin marcadores)"**. Si muestra `fallar_paso_3`: `python fase3/c02/c02_marcador.py borrar`.

### A10. Argumentos del Job del pipeline (T-12)
1. Proyecto `sib-poc` > menu izquierdo **Jobs** > clic en `sib-pipeline` > pestana **Settings**.
2. Campo **Arguments**: `--version v1 --reintentos 3 --espera 180` > **Update Job**.

### A11. Datos de mercado de C03 (T-10)
1. En la Terminal:
   ```
   python fase3/c03/c03_ingesta_alphavantage.py --desde-cache
   ```
2. Deben salir 4 lineas (accion_ibm, fx_usd_eur, tesoro_10a, tasa_fed) con filas.

### A12. Conector CDC en RUNNING (T-8)
1. Environments > `sibrd-cdp-env` > **Data Hubs** > `sibrd-kafka` > en la pagina del cluster, enlace **Streams Messaging Manager**.
2. En SMM, menu izquierdo **Connect** > clic en el conector de SQL Server (el que lee la base `sbcore`).
3. El conector y la fila **Task 0** deben decir **RUNNING**.
4. Si la tarea dice **FAILED** (normal si la EC2 estuvo apagada: "No route to host"): **Restart** en la fila de la tarea
   y esperar RUNNING. Connect no reintenta solo.

### A13. Power BI (T-6)
1. En la EC2: Power BI Desktop > **File** > **Open** > el archivo .pbix de la demo.
2. **Home** > **Transform data** > **Data source settings**: el servidor debe ser el host de `impala-sib-a`.
   **Edit Permissions** > **Edit**: usuario **user006**.
3. Ir a la pagina **AE-01** (pestanas abajo) > panel **Visualizations** > **Format page** (pincel) > **Page refresh** = On, 5 seconds.
4. Deben verse la tarjeta y la tabla con datos solo de NORTE.

### A14. Ventanas de Hue (T-4)
1. Data Warehouse > **Virtual Warehouses** > fila `impala-sib-a` > boton **Data Explorer**.
2. Abrir 3 ventanas de incognito con esa misma URL, cada una con su login: **user001**, **user002**, **user006**.
3. En cada ventana: menu izquierdo **Editor** > **Impala**.
4. En la ventana de **user001**, dejar escritas (SIN ejecutar) estas dos sentencias, con el `id_credito` de la primera fila
   de la tabla de la pagina AE-01 de Power BI:
   ```
   UPDATE sb_curated.creditos SET dias_mora = dias_mora + 1000 WHERE id_credito = <id_credito>;
   UPDATE sb_curated.creditos SET dias_mora = dias_mora - 1000 WHERE id_credito = <id_credito>;
   ```

### A15. Material abierto (T-2)
- GitHub abierto en `fase3/c01/cdc/c01_ae05_generar_cambios.sql` (boton **Raw**) para copiarlo a SSMS en el bloque 5.
- `fase3/c03/c03_apis_y_diagramas.md` abierto para los diagramas de C03.
- La tabla de rendimiento del bloque 3 a la vista.

---

## PARTE B. La sesion (90 min)

### Bloque 0. Apertura (0-10 min)
Pantalla: arquitectura. Mensaje: un solo origen (SQL Server) entra por CDC y por extraccion al lakehouse Iceberg
(raw, curada, consumible), se consulta con CDW y llega a Power BI. SDX (Ranger y Atlas) gobierna todo el recorrido.

### Bloque 1. C01 Lakehouse (10-25 min)
| # | Donde | Que hacer | Que debe verse | Prueba |
|---|---|---|---|---|
| 1 | Hue user006 | Pegar y ejecutar la primera consulta de `fase3/c01/c01_ae02_misma_consulta.sql` | Tabla region / canal / transacciones / monto | C01-AE-02 |
| 2 | Terminal | `python fase3/c01/c01_ae02_notebook.py` | Los mismos numeros, desde Python | C01-AE-02 |
| 3 | Hue user002 | Pegar `fase3/c01/c01_ae03_operaciones_transaccionales.sql` y ejecutar todo (empieza con DROP IF EXISTS de su propia tabla de sandbox: "partimos de cero") | CTAS, INSERT, UPDATE, DELETE y MERGE sin error; DESCRIBE HISTORY con un snapshot por operacion | C01-AE-03 |
| 4 | Hue user002 | Pegar `fase3/c01/c01_ae04_evolucion_esquema.sql` y ejecutar todo | Columna nueva con NULL en filas historicas; rename sin reescribir datos | C01-AE-04 |
| 5 | Hue user001 | Pegar `fase3/c01/c01_ae07_metadatos.sql` y ejecutar todo | Ubicacion, formato, snapshots, archivos y estadisticas | C01-AE-07 |

### Bloque 2. C03 Integraciones (25-35 min)
| # | Donde | Que hacer | Que debe verse | Prueba |
|---|---|---|---|---|
| 1 | Terminal | `python fase3/c03/c03_ae01_apis_plataforma.py --ejecutar-job sib-calidad` | 7 lineas [200]/[201] con milisegundos; "7/7 superficies respondieron OK" | C03-AE-01, PRE-02 |
| 2 | CAI > Jobs > `sib-calidad` > History | Mostrar la corrida recien lanzada por API | Corrida nueva | C03-AE-01 |
| 3 | Terminal | `python fase3/c03/c03_ingesta_alphavantage.py --desde-cache` | 4 series con filas | C03-AE-02 |
| 4 | Hue user002 | `SELECT serie, COUNT(*), MAX(fecha) FROM sb_curated.mercado_series GROUP BY serie;` | 4 series | C03-AE-02 |
| 5 | Terminal | `python fase3/c03/c03_ingesta_alphavantage.py --sin-clave --solo accion_ibm` | Falla con "la API respondio 'Error Message'... revisar clave" | C03-AE-02 (errores) |
| 6 | Pantalla | Diagramas de `c03_apis_y_diagramas.md` | Entra, SharePoint, D365, IDMC, CipherTrust | C03-AE-03..07 (declarado) |

### Bloque 3. C02 Pipelines (35-50 min)
| # | Donde | Que hacer | Que debe verse | Prueba |
|---|---|---|---|---|
| 1 | CAI > Jobs | Mostrar que `sib-calidad` depende de `sib-pipeline`. Abrir `sib-pipeline` > History > ultima corrida Success > log | Inicio, fin, estado y log de los 4 pasos con filas | C02-PRE-03, AE-01 |
| 2 | CAI > Jobs > `sib-calidad` > History > ultima corrida | Abrir el log | 5 reglas [OK], 0 duplicados | C02-AE-06 |
| 3 | Terminal | `python fase3/c02/c02_marcador.py crear` | "Marcador creado" | C02-AE-05 |
| 4 | CAI > Jobs > `sib-pipeline` | **Run** > abrir la corrida en curso > ver el log | A ~1.5 min: `Paso 3 intento 1: FALLIDO ... FALLO CONTROLADO ... Accion: eliminar el marcador` | C02-AE-05 |
| 5 | Terminal | APENAS aparezca el FALLIDO: `python fase3/c02/c02_marcador.py borrar` | En el log, a los 3 min: `Paso 3 intento 2: EXITOSO`; job en Success; `sib-calidad` corre sola | C02-AE-06 |
| 6 | Hue user001 | `SELECT paso, intento, estado, mensaje FROM sb_consumption.pipeline_pasos ORDER BY inicio DESC LIMIT 6;` | Paso 3 FALLIDO y luego EXITOSO | C02-AE-05, AE-06 |
| 7 | Pantalla | Tabla de rendimiento (abajo) | Recursos fijos vs WAA | C02-PRE-06, AE-10 |
| 8 | Dos Terminales (opcional, ver abajo) | Aislamiento en vivo | Sonda cerca de su linea base | C02-AE-09 |

Mientras el pipeline espera entre intentos (paso 4 a 5) se explica la tabla de rendimiento:

| Usuarios | Exitosas/s fijo | Exitosas/s WAA | Errores fijo | Errores WAA | p95 fijo | p95 WAA |
|---|---|---|---|---|---|---|
| 50 | 114 | 120 | 0 | 0 | 541 ms | 551 ms |
| 200 | 60 | 135 | 0 | 0 | 4.1 s | 1.8 s |
| 300 | 46 | 138 | 1.720 | 0 | 7.6 s | 2.5 s |
| 500 | 71 | 118 | 2.595 | 0 | 8.2 s | 4.9 s |
Fijo = `impala-sib-a`. WAA = `impala-sib-waa`, 2 ejecutores en reposo y 4 en el pico.

Aislamiento en vivo (C02-AE-09). Requiere una segunda sesion de CAI de **8 vCPU / 16 GiB** abierta antes del bloque:
1. Terminal de la sesion de 8 vCPU:
   `python fase3/c02/c02_prueba_carga.py --prueba aislamiento --depto b --niveles 500 --segundos 300 --sin-registro`
2. 30 s despues, en la Terminal de la sesion normal:
   `python fase3/c02/c02_prueba_carga.py --prueba sonda_carga --depto a --niveles 1 --segundos 240 --sin-registro`
3. Esperado: p50 de la sonda cerca de **123 ms** (linea base sin carga). RIESGO: no validado en dos sesiones.

### Bloque 4. C04 Power BI (50-65 min)
| # | Donde | Que hacer | Que debe verse | Prueba |
|---|---|---|---|---|
| 1 | Power BI | **Transform data** > **Data source settings**: conector Impala, servidor impala-sib-a, DirectQuery, usuario user006 | Solo NORTE (61.319 creditos), identificacion en hash | C04-PRE-01, AE-03 |
| 2 | Hue user001 | Ejecutar el UPDATE +1000 preparado | En ~5 s la tarjeta sube 1000 sin tocar Power BI | C04-AE-01 |
| 3 | Hue user001 | Ejecutar el UPDATE -1000 | Vuelve al valor original | C04-AE-01 |
| 4 | Power BI | Data source settings > **Edit Permissions** > **Edit** > user005 > **OK** > **Refresh** | Solo CENTRAL | C04-AE-03 |
| 5 | Power BI | Volver a user006 > **Refresh** | NORTE otra vez | |

### Bloque 5. C01-AE-05 CDC (65-80 min). SIEMPRE despues del bloque 3
Motivo: el pipeline recarga `sb_curated.clientes` desde la capa raw y borraria lo aplicado por CDC.
| # | Donde | Que hacer | Que debe verse | Prueba |
|---|---|---|---|---|
| 1 | Terminal | `python fase3/c01/cdc/c01_ae05_cdc_consumidor.py` y dejarlo corriendo | "Consumidor CDC activo" | |
| 2 | SSMS en la EC2 > **New Query** | Pegar `c01_ae05_generar_cambios.sql` (desde GitHub Raw) > **Execute** | 3 filas actualizadas; en Results, `id_insertado` e `id_borrado` (anotarlos) | C01-AE-05 |
| 3 | Terminal del paso 1 | Esperar 15-30 s | `sb_curated.clientes: 5 eventos -> MERGE {'u': 3, 'c': 1, 'd': 1}` | C01-AE-05 |
| 4 | Hue user001 | `SELECT id_cliente, segmento, cdc_ts FROM sb_curated.clientes WHERE id_cliente IN (10,20,30,<id_borrado>,<id_insertado>);` | 10/20/30 en PYME con cdc_ts de hoy; el insertado presente; el borrado ausente | C01-AE-05 |
| 5 | Hue user001 | `DESCRIBE HISTORY sb_curated.clientes;` | Snapshot nuevo del MERGE | C01-AE-05 |
| 6 | Terminal del paso 1 | **Ctrl+C** | Consumidor detenido | |
Declarar: en produccion el paso 1 del pipeline seria un MERGE incremental, no una recarga.

### Bloque 6. Preguntas (80-90 min)

---

## PARTE C. Cierre
1. Terminal: `python fase3/c02/c02_marcador.py ver` -> vacia.
2. CAI: detener las sesiones (boton **Stop**).
3. Data Warehouse: suspender `impala-sib-a` e `impala-sib-waa`.
4. Data Hub `sibrd-kafka` > **Actions** > **Stop**; ambiente > **Actions** > **Stop Environment**; EC2 > **Stop instance**
   (la sesion 2 es el miercoles).

## Si algo falla en vivo
| Sintoma | Causa probable | Accion |
|---|---|---|
| Scripts que usan Ranger o Atlas dan timeout | IP de CAI fuera del security group de Knox | A7 paso 3 |
| `COUNT(*)` de user006 da 1.000.000 | Falta la opcion en el VW | A8 paso 3 |
| El consumidor CDC no imprime MERGE | Tarea del conector FAILED | A12 paso 4; los cambios no se pierden (SQL Server los retiene 3 dias) |
| Power BI da 503 o error de parseo | Fuente apuntando a otro VW | A13 paso 2 |
| El pipeline falla los 3 intentos | El marcador no se borro a tiempo | `python fase3/c02/c02_marcador.py borrar` y **Run** de nuevo |
| Cualquier otro | | Mostrar la captura de `evidencias/<codigo>/` y seguir |
