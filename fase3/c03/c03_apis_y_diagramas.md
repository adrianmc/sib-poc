# C03 - Integraciones: APIs de la plataforma y escenarios de conexion

## C03-PRE-02 / AE-01: APIs y endpoints disponibles (prueba en vivo)

| Superficie | Endpoint / herramienta | Prueba en vivo sugerida |
|---|---|---|
| Control plane CDP | CDP CLI / REST (`cdp environments`, `cdp dw`, `cdp de`, `cdp ml`, `cdp datalake`) | `cdp dw list-vws --cluster-id <id>` |
| Jobs de ingenieria | CDE Jobs API `https://<vc>/dex/api/v1` | ver curl abajo |
| Gobierno | Atlas REST v2 via Knox `.../cdp-proxy-api/atlas/api/atlas/v2` | buscar entidad `sb_curated.clientes` |
| Seguridad | Ranger REST via Knox `.../cdp-proxy-api/ranger/service/public/v2/api` | listar politicas `sb_*` |
| SQL | JDBC/ODBC Impala y Hive (HTTP 443, LDAP o Browser SSO SAML) | Power BI, DBeaver |
| ML | CML API v2, endpoints de modelos, AI Inference (compatible OpenAI) | prediccion `curl` |
| Lakehouse abierto | Iceberg REST Catalog | PyIceberg (C01-AE-06) |

Prueba en vivo (Terminal de CAI), sin valores a mano: `python fase3/c03/c03_ae01_apis_plataforma.py`
(Atlas, Ranger, Cloudera AI API v2 jobs/applications/models y SQL de CDW, con estado y tiempo por superficie).
Con `--ejecutar-job sib-calidad` ademas lanza un Job por API. CDE no esta en el tenant: su API se declara.
Control plane: `cdp environments list-environments` si la CLI de CDP esta configurada en la laptop.

## C03-AE-03: Entra ID (escenario; en la demo el IdP es Keycloak con el mismo patron SAML)
```mermaid
flowchart LR
  U[Usuario SIB] -->|SSO SAML + MFA| E[Entra ID]
  E -->|SAML assertion| CP[CDP Control Plane]
  E -->|SCIM usuarios y grupos| CP
  CP -->|sync| IPA[FreeIPA del ambiente]
  IPA --> R[Ranger: politicas por grupo]
  PBI[Power BI / DBeaver] -->|ODBC Browser SSO SAML| IMP[Impala VW]
  IMP --> R
```

## C03-AE-04 / AE-05: SharePoint y Dynamics 365 (integracion via API)
```mermaid
flowchart LR
  SP[SharePoint Online] -->|Microsoft Graph| G[OAuth2 client credentials - App Registration Entra]
  D365[Dynamics 365 / Dataverse] -->|Web API OData v9.2| G
  G --> N[NiFi InvokeHTTP o script CML]
  N --> RAW[(sb_raw.api_* Iceberg)]
  RAW --> CUR[(sb_curated)]
  D365 -.->|alternativa: Synapse Link export| S3[(Storage)] -.-> N
```
Demo funcional: `c03_ingesta_api_autenticada.py --fuente sharepoint|dataverse`.

## C03-AE-06: Informatica IDMC (integracion de terceros)
```mermaid
flowchart LR
  IDMC_CDI[IDMC Cloud Data Integration] -->|conector Hive/Impala JDBC| CDW[CDW Impala/Hive]
  IDMC_CDGC[IDMC Data Governance & Catalog] -->|escaner de metadata| HMS[Metastore / Atlas]
  CDGC_MP[IDMC Data Marketplace] -.->|solicitud de acceso aprobada| RAPI[Ranger REST API]
```
Declarar: la integracion se configura del lado de Informatica (conectores y escaneres de IDMC); Cloudera expone JDBC, HMS y APIs de Atlas/Ranger. Validar version de escaner con Informatica.

## C03-AE-07: Thales CipherTrust Manager (integracion en la capa de llaves de AWS)
```mermaid
flowchart LR
  CTM[CipherTrust Manager] -->|CCKM: BYOK o XKS| KMS[AWS KMS CMK]
  KMS -->|SSE-KMS| S3[(S3 lakehouse)]
  KMS -->|cifrado EBS| EBS[(Volumenes EKS/EC2)]
  CDP[CDP ambiente sb-poc] -->|usa CMK configurada al crear el ambiente| KMS
```
Declarar: CDP consume la CMK de AWS KMS; CipherTrust gestiona el ciclo de vida de esa llave. No es una integracion certificada directamente por Cloudera; es una arquitectura de responsabilidad en la capa de nube. Tokenizacion con preservacion de formato requeriria el producto de tokenizacion de Thales o Protegrity (UDFs).
