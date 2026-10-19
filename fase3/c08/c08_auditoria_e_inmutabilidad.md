# C08-AE-04 / AE-05 / PRE-05: auditoria e inmutabilidad

## AE-04: logs de acceso y actividad de un usuario
Ranger Admin (Data Lake > Ranger) > **Audit > Access**. Filtros: `User = sb_analista01`, rango = hora de la demo.
Columnas visibles: usuario, servicio, recurso (db/tabla/columna), tipo de acceso, **resultado Allowed/Denied**,
politica que decidio, IP cliente, fecha/hora. Mostrar un Allowed (consumo) y un Denied (columna CONFIDENCIAL, C07-AE-02).
Complementos: **Audit > Admin** (cambios a politicas, p. ej. la politica creada por la solicitud de acceso),
**Audit > Login Sessions**, auditoria del control plane (CDP Management Console > Audit) y AWS CloudTrail.

## PRE-05: politica de retencion (declarar en la demo)
- Consulta en linea: los audits de Ranger se indexan en Solr del Data Lake; la retencion es configurable (TTL en dias).
- Largo plazo: Ranger escribe los audits en el storage del ambiente (prefijo `ranger/audit/` del bucket de logs);
  la retencion la gobierna S3 (Lifecycle) y la inmutabilidad el bucket WORM descrito abajo.
- Propuesta para la SIB: 90 dias en linea, 5 anos en almacenamiento WORM. Validar el valor por defecto del TTL de Solr en el ambiente.

## AE-05: inmutabilidad (incluso ante usuarios privilegiados)
Mecanismo: control de AWS, no funcion nativa de Ranger. **No se activa Object Lock en el bucket de logs de CDP**
(ahi tambien se escriben logs de servicios y backups, y s3a hace renames); se replica el prefijo de auditoria a un bucket WORM dedicado.

Preparacion (Fase 0, cuenta AWS):
1. Bucket de logs de CDP (existente): habilitar versionado (requisito de la replicacion) y lifecycle que expire versiones no actuales a los 7 dias.
2. Bucket nuevo `CAMBIAR_BUCKET_WORM` creado con Object Lock y retencion por defecto (PoC: GOVERNANCE 1 dia; produccion: COMPLIANCE):
```
aws s3api create-bucket --bucket CAMBIAR_BUCKET_WORM --object-lock-enabled-for-bucket
aws s3api put-object-lock-configuration --bucket CAMBIAR_BUCKET_WORM --object-lock-configuration "{\"ObjectLockEnabled\":\"Enabled\",\"Rule\":{\"DefaultRetention\":{\"Mode\":\"GOVERNANCE\",\"Days\":1}}}"
```
   (fuera de us-east-1 agregar `--create-bucket-configuration LocationConstraint=<region>` al create-bucket)
3. S3 Replication (misma region) en el bucket de logs: regla con filtro de prefijo `ranger/audit/` hacia `CAMBIAR_BUCKET_WORM`
   (consola S3 > bucket de logs > Management > Replication rules; rol IAM que la consola crea).
4. Bucket policy del bucket WORM que niegue `s3:PutBucketObjectLockConfiguration`, `s3:BypassGovernanceRetention`
   y `s3:DeleteObjectVersion` a todo principal salvo un rol break-glass.

Demostracion:
```
aws s3api list-object-versions --bucket CAMBIAR_BUCKET_WORM --prefix ranger/audit/ --max-items 1
aws s3api delete-object --bucket CAMBIAR_BUCKET_WORM --key CAMBIAR_KEY --version-id CAMBIAR_VERSION_ID
```
Resultado esperado: AccessDenied por Object Lock y bucket policy, aun con un usuario administrador. CloudTrail registra el intento.
Mensaje para la SIB: en COMPLIANCE ni la cuenta root puede borrar antes del vencimiento; GOVERNANCE se usa en la PoC
para no dejar objetos imborrables en la cuenta de demo.
