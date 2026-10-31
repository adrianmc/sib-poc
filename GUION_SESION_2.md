# Sesion 2 (miercoles 4-nov): Seguridad, gobierno y DevOps. Paso a paso

Hilo de la sesion: quien ve que, como se audita y como se despliega. Duracion: 90 min.
Version: preparada el 30-oct, PENDIENTE de dry-run (31-oct). Cada bloque ya se valido por separado entre el 22 y el 28-oct.

Como leer cada paso:
- **Para que**: que demuestra ante la SIB o por que hace falta.
- **Donde / Que hacer**: la pantalla exacta y lo que se escribe o se pulsa.
- **Debe verse**: el resultado correcto.
- **Si falla**: que hacer.

Usuarios (contrasenas de workload, las mismas de `config/config.yaml`):
user001 admin; user002 ingeniero; user005 analista CENTRAL sin acceso confidencial; user006 analista NORTE con acceso
confidencial; user011 ente externo, sin roles en la plataforma.

Regla de orden de esta sesion: el pipeline (`sib-pipeline` y los despliegues de C05) recarga tablas curadas con
TRUNCATE + INSERT. Nunca debe correr al mismo tiempo que otro bloque que consulta esas tablas. Por eso:
el PR de C05 se abre ANTES de la sesion (A12), las dos corridas del pipeline de C08 van seguidas y C05 va al final.

---

## PARTE A. Preparacion (empezar 90 min antes)

### A1. Encender la EC2 (T-90)
**Para que:** en esa maquina estan Power BI (C08) y el runner de GitHub Actions (C05).
**Donde / Que hacer:** AWS > region **us-east-2** > **EC2** > **Instances** > instancia Windows con IP privada **10.10.2.235** >
**Instance state** > **Start instance**. Conectarse por RDP.
**Debe verse:** Running y **2/2 checks passed**.

### A2. Encender el ambiente de CDP (T-85, solo si esta apagado)
**Para que:** Ranger, Atlas y el metastore viven en el Data Lake del ambiente. El Data Hub de Kafka NO hace falta hoy.
**Donde / Que hacer:** Management Console > **Environments** > `sibrd-cdp-env` > **Actions** > **Start Environment**.
**Debe verse:** ambiente y pestana **Data Lake** en Running (40 a 60 min).

### A3. Encender los Virtual Warehouses (T-25)
**Para que:** `impala-sib-a` es el motor SQL de la sesion. `impala-sib-waa` lo usa el ente externo (C08-AE-07): al ser otro
servidor, Power BI le guarda una credencial propia y no pisa la de los otros usuarios.
**Donde / Que hacer:** **Data Warehouse** > **Virtual Warehouses** > encender `impala-sib-a` e `impala-sib-waa` si estan Stopped.
**Debe verse:** ambos Running.

### A4. Sesion de Cloudera AI con Terminal (T-20)
**Donde / Que hacer:** **AI Workbench** > workspace de la PoC > **Projects** > `sib-poc` > **New Session** (Python 3.10,
2 vCPU / 4 GiB) > **Start Session** > **Terminal Access**. En la Terminal:
```
cd /home/cdsw && git pull
```

### A5. Conectividad y API key de Cloudera AI (T-18)
**Para que:** comprueba en un solo comando que Ranger y Atlas responden por Knox, y que la API key de Cloudera AI sigue
vigente (la usan `sib-despachador` en C05 y el portal en C08).
**Donde / Que hacer:** en la Terminal:
```
python fase3/c03/c03_ae01_apis_plataforma.py
```
**Debe verse:** "6/6 superficies respondieron OK".
**Si falla:**
- Atlas y Ranger con timeout: falta la IP de Cloudera AI en el security group de Knox. En la Terminal
  `curl -s https://checkip.amazonaws.com`; luego AWS > EC2 > instancia gateway del Data Lake (nombre con `sibrd-aw-dl` y
  `gateway`) > **Security** > security group > **Edit inbound rules** > **Add rule** HTTPS, `<IP>/32` > **Save rules**.
- Cloudera AI API v2 con 401: la API key vencio. Cloudera AI > avatar > **User Settings** > **API Keys** > **Create API Key**;
  pegarla en `config/config.yaml`, seccion `cai`, campo `api_key`; reiniciar `sib-despachador` (A8).

### A6. Filtro de fila correcto en COUNT(*) en los dos VW (T-16)
**Para que:** control del hallazgo del 29-oct (COUNT(*) de Iceberg sin filtro de fila). En esta sesion se habla de seguridad:
no puede fallar.
**Donde / Que hacer:** en la Terminal:
```
python -c "from lib.sbpoc import consulta; [print(d, consulta('SELECT COUNT(*) FROM sb_curated.clientes', rol='analista2', depto=d)[1]) for d in 'ab']"
```
**Debe verse:** `a [(150464,)]` y `b [(150464,)]`.
**Si falla:** el VW que da 1000000 > **Edit** > **Configurations** > **Impala Coordinator** > **flagfile** >
`default_query_options` con `ICEBERG_DISABLE_COUNT_STAR_OPTIMIZATION=true` > **Apply Changes**.

### A7. Sin marcadores de fallo (T-15)
**Para que:** C08 corre el pipeline dos veces; un marcador olvidado de un ensayo lo haria fallar.
**Donde / Que hacer:** `python fase3/c02/c02_marcador.py ver`
**Debe verse:** "vacia (sin marcadores)". Si no: `python fase3/c02/c02_marcador.py borrar`.

### A8. Applications de Cloudera AI (T-14)
**Para que:** `sib-despachador` ejecuta los despliegues de C05; `sib-accesos` es el portal de solicitudes de C08.
**Donde / Que hacer:** proyecto `sib-poc` > menu izquierdo **Applications**.
**Debe verse:** las dos en **Running**. Abrir cada una (clic en el nombre): el despachador muestra "ultima revision" de hace
menos de 1 min y sin aviso de error; el portal muestra **Pendientes de aprobacion (0)**.
**Si falla:** menu de tres puntos > **Restart**. Si el portal tiene pendientes de ensayos: **Rechazar**. Si el historial tiene
alguna **APROBADA** de ensayos (user005 o user011): **Revocar**.

### A9. Runner de GitHub y version estable (T-13)
**Para que:** el runner (en la EC2) ejecuta el CI/CD; `v1.0.0` es la version a la que se hace rollback.
**Donde / Que hacer:**
1. GitHub > repo `adrianmc/sib-poc` > **Settings** > **Actions** > **Runners**: `sb-poc` debe estar **Idle**.
2. En la Terminal:
   ```
   git fetch origin --tags --force && git cat-file -e v1.0.0:fase3/c02/c02_pipeline_sql.py && echo OK
   ```
**Debe verse:** runner Idle e imprime OK.
**Si falla:** runner Offline = la EC2 esta apagada o el servicio del runner detenido (en la EC2: **Services** >
"GitHub Actions Runner" > **Start**).

### A10. Copia fresca de los audits al bucket inmutable (T-12)
**Para que:** el bucket WORM retiene cada objeto 1 dia (modo Governance de la PoC). Los audits copiados el 28-oct ya
vencieron su retencion; se copian los de hoy para que el bloqueo que se muestre sea el de Object Lock vigente.
**Donde / Que hacer:** consola de AWS (us-east-2) > icono **CloudShell** (`>_`). Pegar, cambiando `<bucket-worm>` por el nombre
del bucket creado el 28-oct:
```
B=<bucket-worm>
aws s3 sync s3://sibrd-buk-e8bc75b5/data/ranger/audit/ s3://$B/ranger/audit/
K=$(aws s3api list-object-versions --bucket $B --prefix ranger/audit/ --query "sort_by(Versions,&LastModified)[-1].Key" --output text)
V=$(aws s3api list-object-versions --bucket $B --prefix "$K" --query "Versions[0].VersionId" --output text)
echo $K $V
```
**Debe verse:** la ruta de un archivo de audit de hoy y su version. Dejar CloudShell abierto (las variables viven ahi).

### A11. Power BI (T-10)
**Para que:** C08-AE-06 muestra el dato corrupto llegando al tablero; C08-AE-07 muestra al ente externo con su propia herramienta.
**Donde / Que hacer** (EC2, Power BI Desktop):
1. Abrir `C04-AE-01.pbix` > pagina **Sb_Curated** (la de la tabla `nombre_entidad` + conteo filtrada por
   `id_entidad_destino = 7`). Si dice "Visuals are paused": **Resume visual queries**. Page refresh On, 5 s.
2. Abrir una segunda ventana de Power BI con un archivo en blanco: **Get data** > **Impala** > servidor = host de
   **`impala-sib-waa`** > **DirectQuery** > credencial **user011**. En el **Navigator**, abrir las bases: no debe verse
   ninguna tabla. Dejar el Navigator abierto.
**Debe verse:** la entidad 7 con su nombre real; el Navigator de user011 sin tablas.

### A12. Abrir el PR de la demo (T-10)
**Para que:** CI y despliegue a DEV tardan ~6 min y corren el pipeline. Se abren ANTES para que en la sesion los checks ya
esten en verde y el pipeline no corra mientras se consulta.
**Donde / Que hacer:**
1. En la laptop, carpeta `sb-poc` (SIN `[skip ci]`):
   ```
   git checkout main && git pull && git checkout -b feature/demo-sesion2 && echo "demo $(date +%F)" >> fase3/c02/LEEME_JOBS_CAI.md && git commit -am "Demo sesion 2: ajuste de documentacion del pipeline" && git push -u origin feature/demo-sesion2 && git checkout main
   ```
2. GitHub > **Pull requests** > **New pull request** > base `main`, compare `feature/demo-sesion2` > **Create pull request**.
**Debe verse:** a los ~6 min, los checks del PR en verde ("CI: validacion de esquema y calidad" y
"PR: despliegue a DEV y verificacion").
**Si falla:** abrir el check en rojo > log; si es "Sin respuesta del despachador", ver A8.

### A13. Ventanas de Hue y consolas (T-5)
**Donde / Que hacer:**
1. **Data Warehouse** > fila `impala-sib-a` > **Data Explorer**. Cuatro ventanas de incognito: **user001**, **user002**,
   **user005**, **user006**. En cada una: **Editor** > **Impala**.
2. Environments > `sibrd-cdp-env` > pestana **Data Lake** > enlaces **Atlas** y **Ranger** en dos pestanas.
3. GitHub con el PR abierto.

---

## PARTE B. La sesion (90 min)

| Min | Bloque |
|---|---|
| 0-5 | Apertura |
| 5-20 | C07 Seguridad |
| 20-60 | C08 Gobierno |
| 60-80 | C05 CI/CD |
| 80-90 | Preguntas |

### Bloque 0. Apertura (0-5 min)
Mensaje: la seguridad y el gobierno no estan en cada herramienta sino en una capa comun (SDX). Ranger decide quien ve que
(roles, atributos, enmascaramiento, filtros por fila) y lo audita todo; Atlas clasifica los datos y traza su linaje.
La misma regla aplica en SQL, en Python y en Power BI. Los roles viven en Ranger, independientes del IdP.

### Bloque 1. C07 Seguridad (5-20 min)

**1.1 Datos personales y region segun el usuario (C07-AE-05, AE-01).**
Para que: la misma consulta devuelve datos distintos segun quien la ejecuta: PII enmascarada y filtro por region.
- En las ventanas de **user005**, **user006** y **user001**, la misma consulta:
  ```
  SELECT identificacion, nombre, region FROM sb_curated.clientes LIMIT 3;
  ```
- Debe verse: user005, identificacion y nombre en hash y solo CENTRAL; user006, hash y solo NORTE; user001, todo en claro.

**1.2 Mismo rol, distinto atributo (C07-AE-01, AE-02).**
Para que: user005 y user006 tienen el mismo rol (analista); solo user006 tiene el atributo de acceso confidencial.
- En **user006** y luego en **user005**:
  ```
  SELECT id_credito, calificacion_riesgo, saldo_pendiente FROM sb_curated.creditos LIMIT 5;
  ```
- Debe verse: user006 ve los datos; user005 recibe **AuthorizationException** (columnas con tag CONFIDENCIAL).
- En **user005**: `SELECT id_credito, dias_mora FROM sb_curated.creditos LIMIT 5;` -> funciona: el rol da acceso a la tabla,
  el atributo decide las columnas sensibles.

**1.3 La misma regla en Python (C07-AE-03).**
- Terminal: `python fase3/c07/c07_ae03_notebook.py`
- Debe verse: para `analista` la identificacion en hash y una sola region; para `admin` en claro. Mismo resultado que en Hue.
- Power BI: ya visto en la sesion 1 (user005 sin saldos, user006 con saldos).

**1.4 Un analista no escribe en la capa productiva (C07-AE-04).**
- En **user005**:
  ```
  INSERT INTO sb_consumption.resumen_cliente_mensual SELECT * FROM sb_consumption.resumen_cliente_mensual LIMIT 1;
  ```
- Debe verse: **AuthorizationException**.
- Declarar: en la PoC la segregacion es logica (bases, jobs y politicas por ambiente); en produccion, un ambiente CDP por
  dev/test/prod (Data Lake, IAM y buckets separados).

**1.5 Todo queda auditado (C07-AE-01 trazable, C08-AE-04).**
- Pestana **Ranger** > **Audit** > **Access** > filtro **User** = `user005`.
- Debe verse: las consultas de hace un momento, con fecha, recurso, politica que decidio y resultado **Allowed** / **Denied**.

**1.6 Red y seguridad del ambiente (C07-AE-06).** Diagrama de `fase3/c07/c07_ae06_diagrama_red_seguridad.md`.

Si preguntan por COUNT(*) y filtros: hallazgo del 29-oct. En Iceberg, Impala respondia COUNT(*) desde metadatos sin aplicar
el filtro de fila (nunca expuso filas, si el total). Se corrigio en la configuracion de los VW y se reporto a ingenieria.

### Bloque 2. C08 Gobierno (20-60 min)

**2.1 Activos con duenos y linaje de punta a punta (C08-PRE-01/02, AE-01/02).**
Para que: cada activo tiene dueno, dominio y criticidad, y se ve de donde viene y a donde llega.
- Pestana **Atlas** > buscar `clientes` > `sb_curated.clientes`:
  - **Properties**: owner y la seccion **Gobierno_SB** (dominio, propietario, custodio user002, criticidad ALTA).
  - **Lineage**: `dbo.clientes` (SQL Server) > ingesta > `sb_curated.clientes` > consumidores.
- Buscar `Tablero Cartera Crediticia` > **Lineage**: vistas > refresh > tablero de Power BI.
- Buscar `Asistente normativo RAG` > **Lineage**: 5 documentos > indexacion > agente.
- Declarar: los tramos de SQL Server y de Power BI/RAG se registran por API; el intermedio lo captura Atlas solo.
  La sincronizacion hacia un catalogo institucional (IDMC) la hace el escaner de Informatica.

**2.2 Impacto de un cambio en la fuente (C08-AE-03).**
Para que: antes de cambiar algo, Atlas dice que se rompe.
1. Hue **user002**: pegar la parte AE-03 de `fase3/c08/c08_impacto_y_corrupcion.sql` hasta la creacion de la vista
   (empieza con DROP IF EXISTS de su propio sandbox):
   ```
   DROP VIEW IF EXISTS sb_sandbox_depto_a.v_tx_por_entidad;
   DROP TABLE IF EXISTS sb_sandbox_depto_a.entidades_copia PURGE;
   CREATE TABLE sb_sandbox_depto_a.entidades_copia STORED AS ICEBERG AS SELECT * FROM sb_curated.entidades_financieras;
   CREATE VIEW sb_sandbox_depto_a.v_tx_por_entidad AS SELECT e.nombre, COUNT(*) n FROM sb_curated.transacciones t JOIN sb_sandbox_depto_a.entidades_copia e ON e.id_entidad = t.id_entidad_destino GROUP BY e.nombre;
   ```
2. **Atlas** > buscar `entidades_copia` > **Lineage** (esperar ~1 min si aun no aparece): `v_tx_por_entidad` aguas abajo.
3. Hue **user002**:
   ```
   ALTER TABLE sb_sandbox_depto_a.entidades_copia CHANGE COLUMN nombre nombre_entidad STRING;
   SELECT * FROM sb_sandbox_depto_a.v_tx_por_entidad LIMIT 5;
   ```
- Debe verse: `Could not resolve column/field reference: 'e.nombre'`: la vista que Atlas habia senalado quedo rota.

**2.3 Un dato maestro corrupto llega al tablero, se detecta y se revierte (C08-AE-06).**
Para que: se ve el recorrido del error por el linaje, quien lo hizo y como se deshace sin restaurar backups.
1. Hue **user002**: `DESCRIBE HISTORY sb_curated.entidades_financieras;` -> anotar el `snapshot_id` de la ultima fila.
2. Hue **user002**:
   ```
   UPDATE sb_curated.entidades_financieras SET nombre = 'ENTIDAD CORRUPTA - DEMO' WHERE id_entidad = 7;
   ```
3. Cloudera AI > **Jobs** > `sib-pipeline` > **Run** (~4 min; mientras corre, explicar el linaje en Atlas:
   `entidades_financieras` > `transacciones` > vistas > tablero).
4. Al terminar, Hue **user002**:
   ```
   SELECT nombre_entidad, COUNT(*) FROM sb_curated.transacciones WHERE id_entidad_destino = 7 GROUP BY nombre_entidad;
   ```
   Debe verse 'ENTIDAD CORRUPTA - DEMO'. En Power BI, pagina **Sb_Curated**, el mismo nombre corrupto.
5. **Ranger** > **Audit** > **Access** > User `user002`, recurso `entidades_financieras`: el UPDATE con fecha y hora.
6. Hue **user002**, con el snapshot del paso 1:
   ```
   ALTER TABLE sb_curated.entidades_financieras EXECUTE ROLLBACK(<snapshot_id>);
   SELECT id_entidad, nombre FROM sb_curated.entidades_financieras WHERE id_entidad = 7;
   ```
   Debe verse el nombre original.
7. **Jobs** > `sib-pipeline` > **Run** otra vez (~4 min; mientras corre, hacer 2.4). Al terminar, repetir la consulta del
   paso 4 y **Refresh** en Power BI: el nombre original de vuelta.

**2.4 Logs de auditoria inmutables (C08-AE-05, PRE-05).**
Para que: ni un administrador puede borrar la evidencia de auditoria.
- En CloudShell (variables de A10):
  ```
  aws s3api get-object-retention --bucket $B --key "$K" --version-id "$V"
  ```
  Debe verse: `"Mode": "GOVERNANCE"` y la fecha `RetainUntilDate`.
  ```
  aws s3api delete-object --bucket $B --key "$K" --version-id "$V"
  ```
  Debe verse: **AccessDenied**.
  ```
  aws s3api delete-object --bucket $B --key "$K" --version-id "$V" --bypass-governance-retention
  ```
  Debe verse: **AccessDenied** (la bucket policy prohibe saltar la retencion a todos salvo un rol de emergencia).
- Declarar: es S3 Object Lock de AWS, no Ranger. Ranger escribe los audits; el almacenamiento los hace inmutables. En
  produccion, modo COMPLIANCE: ni la cuenta root puede borrar antes del vencimiento. Un "Delete" sin version solo agrega
  una marca de borrado; la version original sigue intacta.

**2.5 Un ente externo con acceso temporal a datos enmascarados (C08-AE-07).**
Para que: un tercero sin roles en la plataforma recibe, solo con aprobacion, acceso a una tabla enmascarada, por tiempo
limitado y revocable.
1. Power BI de **user011** (A11): el Navigator sin tablas. "Hoy no tiene acceso a nada."
2. Portal **sib-accesos** > **Nueva solicitud**: Usuario `user011`, Tabla `sb_share.clientes_externo`,
   Motivo `Ente externo: auditoria` > **Enviar solicitud**.
3. En **Pendientes de aprobacion**: dias `7` > **Aprobar**. El aviso verde dice la politica creada y el aprobador
   (tu usuario de Cloudera AI).
4. Esperar 30 s. Power BI de user011: en el Navigator, boton de refrescar (icono de hoja con flechas) > aparece solo
   `sb_share` > `clientes_externo` > marcarla > **Load**.
5. Debe verse: identificacion en hash (`identificacion_hash`), sin nombre, email ni telefono, e ingreso redondeado.
6. Portal > **Historial** > la solicitud de user011 > **Revocar**. Esperar 30 s > **Refresh** en Power BI > error de acceso.
- Declarar: el tenant no tiene Data Sharing (entitlement `CDP_DATA_SHARE_ADMIN`, solicitado); user011 tiene una identidad
  sin roles. Con Data Sharing, el externo no tendria cuenta y leeria por REST Catalog de Iceberg.

**2.6 Solicitud de acceso con aprobacion (C08-AE-08).**
Para que: el acceso se pide, se aprueba, queda registrado y se retira, con trazabilidad.
1. Hue **user005**: `SELECT * FROM sb_raw.entidades_financieras LIMIT 5;` -> **AuthorizationException** (la capa raw no es
   para analistas).
2. Portal > **Nueva solicitud**: `user005`, `sb_raw.entidades_financieras`, motivo `Conciliacion de maestra` > **Enviar** >
   **Aprobar** con 7 dias.
3. Esperar 30 s. Hue **user005**: repetir la consulta -> devuelve filas.
4. **Ranger** > **Audit** > **Admin**: la politica `sb_solicitud_<id>` creada, con su usuario y fecha.
5. Portal > **Historial** > **Revocar**. Esperar 30 s > repetir la consulta -> **AuthorizationException** de nuevo.
- Declarar: el catalogo de Cloudera no trae este flujo; es un workaround minimo. En produccion: ServiceNow, Power Automate o
  IDMC Data Marketplace llamando la misma API de Ranger.

### Bloque 3. C05 CI/CD (60-80 min)
Mensaje: el codigo de los datos pasa por control de versiones, validacion automatica, aprobacion y despliegue trazable, con
rollback a una version inmutable. El CI/CD externo (GitHub) no tiene credenciales de la plataforma: deja una solicitud
auditable que la plataforma ejecuta.

**3.1 El cambio y sus validaciones (C05-AE-01, AE-02).**
- GitHub > el PR abierto en A12:
  - **Files changed**: autor, fecha y diff del commit (AE-01).
  - **Checks** en verde: "CI: validacion de esquema y calidad" (contrato de datos y reglas de calidad) y
    "PR: despliegue a DEV y verificacion" (AE-02).
- Abrir **sib-despachador**: la solicitud de DEV de ese commit en **EXITOSO**.

**3.2 Merge, TEST automatico y aprobacion para PROD (C05-AE-03, AE-04).**
1. PR > **Merge pull request** > **Confirm merge** (con el bypass de administrador si lo pide).
2. **Actions** > la corrida nueva de `sb-cicd`: CI en verde y "CD: despliegue a TEST" corriendo (~4 min; mostrar el
   despachador: TEST en EN_EJECUCION y luego EXITOSO).
3. "CD: despliegue a PROD" queda en **Waiting for review** (AE-03): nadie despliega a produccion sin aprobacion.
4. **Review deployments** > marcar `sb-prod` > comentario `Aprobado en demo` > **Approve and deploy** (~5 min).
5. Mientras corre PROD, Hue **user001**:
   ```
   SELECT * FROM sb_gov.despliegues ORDER BY 6 DESC LIMIT 8;
   ```
   Debe verse: cada despliegue con ambiente, version, autor y fecha (AE-04).

**3.3 Rollback a una version estable (C05-AE-05).**
- Si quedan 10 min: **Actions** > **sb-cicd** > **Run workflow** > branch `main`, rollback_ref `v1.0.0` > **Run workflow**.
  TEST (~4 min) y luego aprobar PROD (~5 min).
- Si no hay tiempo: mostrar en **Actions** la corrida **#16** del 27-oct (rollback a v1.0.0 con TEST verde, PROD aprobado y
  desplegado) y en `sb_gov.despliegues` las filas con version `v1.0.0`.
- Declarar: cada version se materializa una sola vez por commit; el rollback reutiliza esa copia intacta.

**3.4 Versionado de datos (C05-AE-06).**
- Hue **user001**: `DESCRIBE HISTORY sb_curated.transacciones;` -> cada corrida del pipeline es un snapshot con fecha.
- Copiar el `snapshot_id` de la penultima fila:
  ```
  SELECT COUNT(*) FROM sb_curated.transacciones FOR SYSTEM_VERSION AS OF <snapshot_id>;
  ```
  Debe verse el conteo de esa version anterior: los datos se versionan igual que el codigo.

### Bloque 4. Preguntas (80-90 min)

---

## PARTE C. Cierre
1. Portal sib-accesos: sin pendientes y sin aprobaciones activas (revocar si quedo alguna).
2. GitHub: la rama `feature/demo-sesion2` se puede borrar desde el PR cerrado (**Delete branch**).
3. Cloudera AI: **Stop** en la sesion. Data Warehouse: suspender los dos VW.
4. Ambiente > **Stop Environment**; EC2 > **Stop instance** (la sesion 3 es el viernes).

## Si algo falla en vivo
| Sintoma | Causa probable | Accion |
|---|---|---|
| Ranger o Atlas con timeout desde scripts o el portal | IP de Cloudera AI fuera del security group de Knox | A5, "Si falla" |
| El portal aprueba pero el SELECT sigue denegado | Refresco de politicas de Ranger (~30 s) | Esperar 30 s y repetir |
| Lineage de `entidades_copia` vacio | Atlas aun no proceso la tabla nueva | Esperar 1 min y refrescar |
| El check de DEV o TEST queda esperando | `sib-despachador` detenido o API key vencida | A8 y A5 |
| PROD no pide aprobacion | Environment `sb-prod` sin Required reviewers | GitHub > Settings > Environments > sb-prod |
| delete-object no da AccessDenied | Se perdieron las variables o la retencion vencio | Repetir A10 completo |
| Power BI de user011 ve tablas antes de aprobar | Quedo una aprobacion de un ensayo | Portal > Historial > Revocar |
| Cualquier otro | | Mostrar la captura de `evidencias/<codigo>/` y seguir |
