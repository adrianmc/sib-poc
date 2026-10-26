# C05 - CI/CD: preparacion en GitHub Actions

Sin acceso a Azure DevOps, la PoC usa **GitHub Actions**. Todo el trabajo real esta en scripts Python
(`validar_esquema.py`, `validar_calidad.py`, `desplegar_cde.py`) que hablan con Cloudera por SQL y REST;
el orquestador solo los llama. Por eso el mismo flujo corre en Azure Pipelines sin cambios de logica
(`referencia_azure-pipelines.yml`). Declarar a la SIB: integracion con Azure DevOps = mismo patron, demostrado aqui con GitHub.

## Preparacion (1 vez, ~2 horas)
1. Crear repositorio **publico** `sb-poc` en GitHub (plan Free). Motivo: en Free/Pro/Team los required reviewers
   de un environment solo funcionan en repos publicos; en privados requiere GitHub Enterprise.
   El repo no lleva secretos (config.yaml en .gitignore) ni datos (todos sinteticos y fuera del repo).
2. Subir el kit: `git init`, `git add .`, commit, `git branch -M main`, `git push`. Crear tag estable: `git tag v1.0.0 && git push --tags`.
3. Settings > Secrets and variables > Actions > New repository secret `CONFIG_YAML` (pegar config/config.yaml completo).
4. Settings > Environments: crear `sb-dev`, `sb-test`, `sb-prod`. En `sb-prod`: Required reviewers = usuario aprobador,
   activar **Prevent self-review**.
5. Settings > Branches > regla para `main`: Require a pull request + Require status checks (`CI: validacion de esquema y calidad`).
6. Runner self-hosted en el EC2 Windows (dentro de la VPC): Settings > Actions > Runners > New self-hosted runner (Windows),
   seguir los comandos que muestra GitHub, agregar la etiqueta `sb-poc` e instalarlo como servicio. Requiere Python 3.10+ y git en el PATH.
7. Dos usuarios GitHub: ejecutor (abre PR y hace merge) y aprobador (aprueba sb-prod). Ambos colaboradores del repo.
8. Red del runner: sale a internet por el NAT de la VPC. Agregar la IP publica (Elastic IP) del NAT a la allowlist de
   los endpoints de CDW y CDE, y permitir salida HTTPS a github.com (el runner se conecta hacia GitHub, no al reves).
9. Sin CDE: crear los Jobs `sib-pipeline-dev/test/prod` en Cloudera AI y poner `cai.*` en CONFIG_YAML (ver `fase3/c02/LEEME_JOBS_CAI.md`).
10. Prueba en seco antes de la demo: abrir un PR de prueba y verificar que los 4 jobs aparecen y que el runner los toma.

## Lecciones de la instalacion (26-oct)
- Runner en `C:\actions-runner`. En `C:\Users\Administrator\...` el servicio queda Offline:
  "Access to the path 'C:\Users\Administrator' is denied" (NETWORK SERVICE no lee perfiles).
- Comandos de Windows: `.\config.cmd` (GitHub a veces muestra `./config.sh`).
- `Invoke-WebRequest` lento: antes ejecutar `$ProgressPreference = 'SilentlyContinue'` (o usar `curl.exe -L -o`).
- Python 3.11 o 3.12 "Install for all users" (3.15 es muy nueva: faltan wheels).
- Una sola cuenta GitHub: ruleset con Required approvals = 0 y bypass para Repository admin; en sb-prod reviewer = uno mismo
  y SIN "Prevent self-review". Declarar: en operacion real el aprobador es otra persona.
- Secret CONFIG_YAML = config/config.cicd.ejemplo.yaml lleno (minimo), no el config.yaml completo. api_key vence en 1 dia.
- El workflow borra config/config.yaml del runner al terminar cada job (paso "Limpieza", if: always()).

## Despliegue via cola (26-oct)
El balanceador del workspace de Cloudera AI no acepto la IP del runner (ping si, TCP 443 no, aun con la regla en su SG:
el balanceador lo administra Kubernetes). Solucion sin depender de esa red:
1. Runner (GitHub) -> `desplegar_cai.py --via cola`: INSERT en `sb_gov.solicitudes_despliegue` (PENDIENTE) por Impala y espera.
2. Cloudera AI > Applications > **sib-despachador** (`fase3/c05/despachador_cai.py`): toma la solicitud, apunta el Job
   `sib-pipeline-<amb>` a la version, registra en `sb_gov.despliegues`, ejecuta y marca EXITOSO/FALLIDO.
3. El runner lee el estado: check verde o rojo en el PR. La URL de la Application muestra la cola (pantalla para la demo).
Ventaja para la SIB: el CI/CD externo nunca tiene credenciales de Cloudera AI; solo deja una solicitud auditable.
Prerrequisito: la Application `sib-despachador` en Running antes de abrir el PR.

## Verificacion de la preparacion (checklist)
- [ ] Runner `sb-poc` en estado Idle en Settings > Actions > Runners
- [ ] `python --version` y `git --version` en el EC2 Windows
- [ ] Desde el EC2: `python fase3/c05/validar_calidad.py` con config.yaml local funciona (descarta red y credenciales)
- [ ] PR de prueba: `validar` y `desplegar_dev` en verde; `sb_gov.despliegues` con fila dev
- [ ] Merge de prueba: `desplegar_prod` queda en Waiting for review y el ejecutor NO puede aprobar
- [ ] Rollback de prueba a `v1.0.0` termina en verde

Nota sobre segregacion: dev/test/prod despliegan jobs distintos (`sb-pipeline-batch-<amb>`) pero hoy escriben las mismas
tablas. Si la SIB pide segregacion de datos (Pregunta 3), se parametriza la base destino por ambiente.

## Demo (mapeo a la plantilla)
| Item | Accion |
|---|---|
| AE-01 | Rama `feature/ajuste-pipeline`: cambiar `c02_pipeline_batch.py`, `esquemas/contrato_datos.yaml` y `c04_capa_semantica.sql`; commit y push. Mostrar autor, fecha, diff |
| AE-02 | PR a main: corre validacion, empaquetado (artefacto `codigo_pipeline`), despliegue a DEV y verificacion; check verde/rojo en el PR. Para rojo: `monto: double` en el contrato |
| AE-03 | Merge: TEST se despliega; PROD queda "Waiting for review" hasta que apruebe el segundo usuario |
| AE-04 | Aprobado: Job `sib-pipeline-prod` apunta a la version `<commit>` (worktree inmutable); fila en `sb_gov.despliegues` |
| AE-05 | Actions > sb-cicd > Run workflow con `rollback_ref = v1.0.0`: el Job vuelve a esa version inmutable; `sb_gov.despliegues` conserva ambas |
| AE-06 | `c05_versionado_datos.sql` |
