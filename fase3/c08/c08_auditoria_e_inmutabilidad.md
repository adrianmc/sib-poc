# C08-AE-04 / AE-05 / PRE-05: auditoria e inmutabilidad

## AE-04: logs de acceso y actividad de un usuario
Ranger Admin (Data Lake > Ranger) > **Audit > Access**. Filtros: `User = sb_analista01`, rango = hora de la demo.
Columnas visibles: usuario, servicio, recurso (db/tabla/columna), tipo de acceso, **resultado Allowed/Denied**,
politica que decidio, IP cliente, fecha/hora. Mostrar un Allowed (consumo) y un Denied (columna CONFIDENCIAL, C07-AE-02).
Complementos: **Audit > Admin** (cambios a politicas, p. ej. la politica creada por la solicitud de acceso),
**Audit > Login Sessions**, auditoria del control plane (CDP Management Console > Audit) y AWS CloudTrail.

## PRE-05: politica de retencion (declarar en la demo)
- Consulta en linea: los audits de Ranger se indexan en Solr del Data Lake; la retencion es configurable (TTL en dias).
- Largo plazo: Ranger escribe los audits en el storage del ambiente (`<storage location base>/ranger/audit/`, ruta de datos);
  la retencion la gobierna S3 (Lifecycle) y la inmutabilidad el bucket WORM descrito abajo.
- Propuesta para la SIB: 90 dias en linea, 5 anos en almacenamiento WORM. Validar el valor por defecto del TTL de Solr en el ambiente.

## AE-05: inmutabilidad (incluso ante usuarios privilegiados)
Mecanismo: control de AWS (S3 Object Lock), no funcion nativa de Ranger. **No se activa Object Lock en el bucket de CDP**
(ahi se escriben datos, logs de servicios y backups, y s3a hace renames); el prefijo de auditoria se copia o replica a un
bucket WORM dedicado. Region del ambiente: us-east-2. Herramienta: consola de AWS + CloudShell.

Preparacion (validada el 28-oct):
1. Ruta de auditoria: Management Console > Environments > sibrd-cdp-env > Summary > Logs Storage and Audits >
   **Storage Location Base** (la ruta de datos, termina en /data; NO el Logs location base). Los audits de Ranger quedan en
   `<storage location base>/ranger/audit/<servicio>/<fecha>/` (los escribe el Ranger Audit Role). Validado 28-oct.
2. Bucket WORM: S3 > Create bucket `CAMBIAR_BUCKET_WORM` (us-east-2) > Advanced settings > **Object Lock: Enable**
   (activa versionado). Properties > Object Lock > Default retention: **Governance, 1 dia** (produccion: Compliance, 5 anos).
3. Permissions > Bucket policy: `fase3/c08/c08_politica_bucket_worm.json` (cuenta y bucket reemplazados). Niega bypass de
   governance, borrado de versiones, cambio de retencion y de configuracion de Object Lock a todo principal salvo el rol
   break-glass `sb-breakglass` (no se crea en la PoC: nadie puede, que es lo que se demuestra).
4. Carga de los audits (CloudShell): `aws s3 sync s3://<bucket>/<prefijo-data>/ranger/audit/ s3://CAMBIAR_BUCKET_WORM/ranger/audit/`
5. Continuo (declarar; opcional en la PoC): S3 Replication del prefijo `<prefijo-data>/ranger/audit/` hacia el bucket WORM.
   Requiere versionado en el bucket de CDP + lifecycle que expire versiones no actuales a los 7 dias.

Demostracion (CloudShell):
```
aws s3api list-object-versions --bucket CAMBIAR_BUCKET_WORM --prefix ranger/audit/ --max-items 1 --query "Versions[0].[Key,VersionId]"
aws s3api delete-object --bucket CAMBIAR_BUCKET_WORM --key <KEY> --version-id <VERSION_ID>
aws s3api delete-object --bucket CAMBIAR_BUCKET_WORM --key <KEY> --version-id <VERSION_ID> --bypass-governance-retention
```
Resultado esperado: los dos borrados de version dan **AccessDenied**, aun con un usuario administrador de la cuenta.
Matiz para explicar: `aws s3 rm` o "Delete" en la consola SIN version solo agrega un delete marker; la version original
sigue intacta (list-object-versions la muestra). CloudTrail registra cada intento.
Mensaje para la SIB: en COMPLIANCE ni la cuenta root puede borrar antes del vencimiento; GOVERNANCE + bucket policy se usa
en la PoC para no dejar objetos imborrables en la cuenta de demo. Honestidad: en GOVERNANCE un administrador podria
quitar la bucket policy y luego borrar con bypass (queda en CloudTrail); por eso en produccion se usa COMPLIANCE. Limpieza post-PoC: quitar la bucket policy y esperar
el vencimiento de 1 dia.
