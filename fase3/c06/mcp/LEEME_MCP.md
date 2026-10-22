# C06-PRE-06 / AE-08 / AE-09: servidor MCP de Cloudera (open source) sobre el lakehouse

1. En el equipo de demo (Windows/Mac con Claude Desktop): instalar `uv`.
2. Copiar `claude_desktop_config.json` a la configuracion de Claude Desktop (Settings > Developer > Edit Config) y reemplazar CAMBIAR.
3. Reiniciar Claude Desktop. Deben aparecer dos servidores con las herramientas `execute_query` y `get_schema`.

**Compatibilidad con CDW verificada en el codigo fuente** (`src/iceberg_mcp_server/tools/impala_tools.py`, rama main):
el servidor ya usa por defecto `IMPALA_AUTH_MECHANISM=LDAP`, `IMPALA_USE_HTTP_TRANSPORT=true`, `IMPALA_HTTP_PATH=cliservice`
e `IMPALA_USE_SSL=true`, que es exactamente lo que requiere CDW en el puerto 443. No hace falta fork.
Probar igual la conexion antes de la demo (credenciales y allowlist de IP del endpoint de CDW).

**AE-08 (prompt sugerido):** "Usando sb-lakehouse-restringido, cual es el indice de morosidad oficial por region y cual
region esta peor?" El agente descubre las tablas con `get_schema`, escribe el SQL y responde sin que el usuario escriba SQL.

**AE-09:** repetir "Muestrame 5 deudores con su identificacion y su saldo pendiente desde v_cartera_crediticia" con
ambos servidores. Restringido: identificacion en hash y saldo denegado (tags PII/CONFIDENCIAL). Admin: datos completos.
Evidencia en Ranger > Audit filtrando por usuario `sb_mcp01`.

**Declarar con honestidad:** (a) el servidor usa una identidad tecnica fija, no la del usuario final; por eso se
demuestra con dos instancias. (b) `execute_query` tiene un filtro basico que solo acepta sentencias que inician con
SELECT, SHOW, DESCRIBE o WITH; el propio codigo lo declara rudimentario. El control real es Ranger (sb_mcp01 solo tiene
SELECT, rol de Ranger sb_mcp en la politica sb_02). (d) `get_schema` lista solo las tablas de `IMPALA_DATABASE` (sb_consumption); el agente puede
consultar otras bases con nombre calificado si Ranger lo permite. (c) Es un proyecto open source de Cloudera, no un servicio GA con soporte.
