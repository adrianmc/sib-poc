# Fase 2 - Paso 10: usuarios, grupos y roles (IdP Keycloak del ambiente demo)

El ambiente demo de Cloudera usa **Keycloak** como IdP SAML. Los usuarios y grupos se crean en Keycloak;
CDP crea el usuario en su primer inicio de sesion y toma los grupos del atributo SAML de grupos
(con la sincronizacion de grupos al iniciar sesion habilitada en el proveedor de identidad de CDP; validar en
Management Console > User Management > Identity Providers).

Pasos:
1. Keycloak (realm del ambiente demo): crear los grupos y usuarios de las tablas; asignar membresias; definir contrasena.
2. Verificar que el cliente SAML de CDP en Keycloak envia el mapper de grupos (Group list) hacia el atributo de grupos de CDP.
3. **Cada usuario inicia sesion una vez** en la consola CDP (si no, no existe para Ranger y las politicas por usuario fallan).
4. En CDP: cada usuario define su **workload password** (Profile > Set Workload Password) y se registra en `config/config.yaml`.
5. Asignar roles de ambiente (tabla de abajo) y Actions > **Synchronize Users to FreeIPA**. Esperar ~5 min al usersync de Ranger.

| Usuario | Grupos | Proposito en la demo |
|---|---|---|
| sb_admin01 | sb_admin | Administrador de plataforma, ve todo |
| sb_ing01 | sb_ingeniero | Ingeniero de datos (pipelines, CDE) |
| sb_cient01 | sb_cientifico | Cientifico de datos, ve PII enmascarada |
| sb_cient02 | sb_cientifico | Segundo cientifico (colaboracion C06-AE-02) |
| sb_analista01 | sb_analista, attr_region_central | Analista con rol correcto pero SIN atributo confidencial (C07-AE-02) |
| sb_analista02 | sb_analista, attr_region_norte, attr_acceso_confidencial | Analista con rol y atributo (C07-AE-01) |
| sb_auditor01 | sb_auditor | Auditor: lectura y auditoria |
| sb_mcp01 | (ninguno) | Identidad tecnica del servidor MCP restringido |
| sb_externo01 | (ninguno) | Usuario externo temporal (C08-AE-07) |

Roles de ambiente (Management Console > Environments > sb-poc > Actions > Manage Access):

| Grupo | Roles |
|---|---|
| sb_admin | EnvironmentAdmin, DWAdmin, DEAdmin, MLAdmin |
| sb_ingeniero | EnvironmentUser, DWUser, DEUser |
| sb_cientifico | EnvironmentUser, DWUser, MLUser |
| sb_analista, sb_auditor | EnvironmentUser, DWUser |
| sb_mcp01, sb_externo01 (usuarios) | EnvironmentUser, DWUser |

Nota C03-AE-03 (Entra ID): el mecanismo con Entra es el mismo (SAML + grupos en la asercion; Entra agrega SCIM).
En la demo se muestra el login SSO con Keycloak como evidencia del patron y el diagrama de Entra como escenario.

Orden de ejecucion de la Fase 2: 01 (Cloudera AI) -> 03/04 (SQL Developer/SSMS en EC2 Windows) -> 06 (subir a S3) -> 05b y 02 (CDE) -> 07 (Hue) -> 10 -> 08 -> 09.
