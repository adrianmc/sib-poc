# C04 - Guia Power BI Desktop (EC2 Windows, VW Impala)

Metodo VALIDADO (24 oct): conector **Impala** nativo de Power BI con su driver interno redirigido al
**Cloudera ODBC Driver for Impala 2.7+** en modo HTTP. Se mantiene DirectQuery.
- El conector Impala con su driver interno falla contra CDW ("Unexpected response received from server"): usa protocolo
  binario y CDW expone solo HTTP/443.
- El conector Hive LLAP (metodo de la doc de Cloudera) esta en retiro por Microsoft desde abril 2026: ya no aparece.
- Power BI debe estar instalado con el .exe (no Microsoft Store). Declarar: configuracion no certificada, documentada
  por la comunidad de Cloudera. Para Power BI Service con gateway se repite la misma configuracion en el gateway.
Fuente: https://community.cloudera.com/t5/Community-Articles/How-to-Connect-to-CDW-Impala-VW-Using-the-Power-BI-Desktop/ta-p/393013

Usuarios (contrasena = workload password de cada uno, no la de Keycloak):
- user006 (analista2: region NORTE, acceso confidencial) -> AE-01, AE-02, AE-06
- user005 (analista: region CENTRAL, sin confidencial) -> AE-03
- user001 (admin) -> UPDATE en Hue para AE-01

## 0. Preparacion (una vez, PowerShell como administrador, Power BI cerrado)
1. Instalar Cloudera ODBC Driver for Impala 64 bits, version 2.7 o superior. Verificar:
   `(Get-Item "C:\Program Files\Cloudera ODBC Driver for Impala\lib\ClouderaImpalaODBC64.dll").VersionInfo.FileVersion`
2. Copiar el driver dentro de Power BI:
   `Copy-Item "C:\Program Files\Cloudera ODBC Driver for Impala" "C:\Program Files\Microsoft Power BI Desktop\bin\ODBC Drivers\" -Recurse`
3. `notepad "C:\Program Files\Microsoft Power BI Desktop\bin\ODBC Drivers\Simba Impala ODBC Driver.ini"`:
   comentar con `;` la linea `Driver=...` original y agregar `Driver=Cloudera ODBC Driver for Impala\lib\ClouderaImpalaODBC64.dll`.
4. Crear la configuracion del driver (no viene; el .did de lib es la licencia):
   `Set-Content "C:\Program Files\Microsoft Power BI Desktop\bin\ODBC Drivers\Cloudera ODBC Driver for Impala\lib\cloudera.impalaodbc.ini" "[Driver]`r`nTransportMode=http`r`nAuthMech=3`r`nSSL=1`r`nAllowHostNameCNMismatch=0`r`nCheckCertRevocation=0" -Encoding ASCII`
5. Host: CDW > Virtual Warehouses > VW Impala > Copy JDBC URL; el host es el texto entre `jdbc:impala://` y `:443`.

## 1. Conexion (C04-PRE-01)
Obtener datos > **Impala** > Servidor `<host>:443` > Opciones avanzadas: Implementation `1.0` > Modo **DirectQuery** > OK.
Credenciales: **Base de datos**, user006 + workload password. Navegador: `sb_consumption` > `v_cartera_crediticia`
y `m_indice_morosidad_oficial` > Cargar.
Cambiar de usuario: Archivo > Opciones y configuracion > Configuracion de origen de datos > el servidor > Borrar permisos.

## 2. C04-AE-01 cambio inmediato y automatico (DirectQuery) - VALIDADO 24 oct
1. Visual **Tarjeta**: Suma de `dias_mora` (v_cartera_crediticia). Anotar el valor.
2. Visual **Tabla**: identificacion_deudor, dias_mora; filtro del visual `dias_mora` mayor que 900 (queda vacia).
3. Formato de pagina > **Actualizacion de pagina** = Activado, cada 5 segundos (en Desktop no hay minimo).
4. Hue (user001), credito NORTE:
   `SELECT cr.id_credito, cr.dias_mora FROM sb_curated.creditos cr JOIN sb_curated.clientes c ON c.identificacion = cr.identificacion_cliente WHERE c.region = 'NORTE' LIMIT 1;`
5. Hue (user001): `UPDATE sb_curated.creditos SET dias_mora = dias_mora + 1000 WHERE id_credito = <id>;`
6. En <= 5 s, sin tocar Power BI: la tarjeta sube 1000 y la fila aparece en la tabla (hash + mora alta).
7. Revertir: `UPDATE sb_curated.creditos SET dias_mora = dias_mora - 1000 WHERE id_credito = <id>;`
Nota Service: el intervalo minimo lo define la capacidad del tenant (fuera de alcance: solo Desktop).
Hallazgo 24 oct: con LEFT JOIN a clientes la vista mostraba 348.433 creditos de otras regiones con region en blanco
para user006. Corregido con INNER JOIN (c04_capa_semantica.sql). Leccion: el filtro por fila vive en la tabla que
tiene el atributo; toda vista o tabla derivada debe heredarlo (JOIN) o tener su propia politica (sb_05b).

## 3. C04-AE-02 carga masiva (Import)
Archivo nuevo > Impala mismo servidor (Implementation 1.0), Modo **Import**, tabla `resumen_cliente_mensual` > Cargar.
Inicio > Actualizar y cronometrar. Evidencia: duracion del refresh + filas cargadas + consulta en Hue > Query History
(o Query Profile del VW: filas y bytes escaneados).

## 4. C04-AE-03 herencia de permisos por identidad
1. Archivo > Opciones y configuracion > **Configuracion de origen de datos** > el origen > **Borrar permisos**.
2. Actualizar > credenciales de user005.
3. Resultado: Identificacion_Deudor en hash, solo region CENTRAL; incluir Saldo_Pendiente da error de autorizacion.
4. Repetir con user006: hash igual (PII aplica a todos salvo admin, auditor e ingeniero), solo region NORTE, Saldo_Pendiente visible.
5. Opcional con user001: identificacion en claro, todas las regiones.
Matiz a declarar: en Power BI Service con gateway todos los visores usan la credencial almacenada (no es herencia por visor).

## 5. C04-AE-05 consumo vs desarrollo (parcial, solo Desktop)
- Consumidor user005: Hue `CREATE TABLE sb_consumption.x (a INT);` -> AuthorizationException.
- Desarrollador user002: conecta Power BI a `sb_sandbox_depto_a` (tiene ALL ahi). Roles de workspace de Service: solo mostrar.

## 6. C04-AE-06 metrica reutilizada
Visual de `m_indice_morosidad_oficial` (Indice_Morosidad por Region) + misma vista en Hue (`c04_capa_semantica.sql`)
+ Atlas > Glossary > SB_Glosario (termino asignado). Una definicion, varios consumidores.

## C04-AE-04 (brecha declarada)
Los COMMENT de las vistas y las relaciones no llegan a Power BI; los nombres de columna llegan en minusculas.
Se ajustan en el modelo de Power BI.

## Plan B
Si el driver redirigido falla tras una actualizacion de Power BI: repetir los pasos 0.2 a 0.4 (la actualizacion
reescribe la carpeta bin). Ultimo recurso: DSN ODBC con el mismo driver (solo Import; AE-01 pasa a mostrarse con Hue).
