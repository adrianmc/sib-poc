-- =====================================================================
-- FASE 2 - Paso 03: RDS Oracle (core bancario ficticio) + prerrequisitos CDC (Debezium/LogMiner)
-- Herramienta: SQL Developer / DBeaver conectado como usuario MASTER de RDS.
-- Prerrequisito Fase 0: backups automaticos habilitados en RDS (ARCHIVELOG activo).
-- Validar grants contra la documentacion de Debezium de la version incluida en Streams Messaging.
-- =====================================================================

-- 1. Esquema de negocio
CREATE USER SBCORE IDENTIFIED BY "CAMBIAR_PASSWORD" QUOTA UNLIMITED ON USERS;
GRANT CREATE SESSION, CREATE TABLE TO SBCORE;

CREATE TABLE SBCORE.CLIENTES (
  ID_CLIENTE          NUMBER(12)    PRIMARY KEY,
  IDENTIFICACION      VARCHAR2(20)  NOT NULL,
  NOMBRE              VARCHAR2(120),
  EMAIL               VARCHAR2(120),
  TELEFONO            VARCHAR2(20),
  FECHA_NACIMIENTO    DATE,
  REGION              VARCHAR2(20),
  SEGMENTO            VARCHAR2(20),
  INGRESO_MENSUAL     NUMBER(14,2),
  FECHA_ALTA          DATE,
  FECHA_ACTUALIZACION TIMESTAMP
);

CREATE TABLE SBCORE.CUENTAS (
  ID_CUENTA      NUMBER(12)   PRIMARY KEY,
  ID_CLIENTE     NUMBER(12)   NOT NULL,
  TIPO_CUENTA    VARCHAR2(20),
  MONEDA         VARCHAR2(10),
  SALDO          NUMBER(16,2),
  ESTADO         VARCHAR2(20),
  FECHA_APERTURA DATE,
  ID_ENTIDAD     NUMBER(6)
);

-- 2. Logging suplementario (requerido por LogMiner)
EXEC rdsadmin.rdsadmin_util.alter_supplemental_logging('ADD');
EXEC rdsadmin.rdsadmin_util.alter_supplemental_logging('ADD','ALL');
ALTER TABLE SBCORE.CLIENTES ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;
ALTER TABLE SBCORE.CUENTAS  ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;
EXEC rdsadmin.rdsadmin_util.set_configuration('archivelog retention hours', 24);

-- 3. Usuario Debezium
CREATE USER DBZUSER IDENTIFIED BY "CAMBIAR_PASSWORD" QUOTA UNLIMITED ON USERS;
GRANT CREATE SESSION TO DBZUSER;
GRANT CREATE TABLE TO DBZUSER;
GRANT SELECT ANY TRANSACTION TO DBZUSER;
GRANT LOGMINING TO DBZUSER;
GRANT FLASHBACK ANY TABLE TO DBZUSER;
GRANT SELECT ON SBCORE.CLIENTES TO DBZUSER;
GRANT SELECT ON SBCORE.CUENTAS TO DBZUSER;
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$DATABASE','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$LOG','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$LOGFILE','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$ARCHIVED_LOG','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$ARCHIVE_DEST_STATUS','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$LOGMNR_LOGS','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$LOGMNR_CONTENTS','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$TRANSACTION','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$MYSTAT','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('V_$STATNAME','DBZUSER','SELECT');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('DBMS_LOGMNR','DBZUSER','EXECUTE');
EXEC rdsadmin.rdsadmin_util.grant_sys_object('DBMS_LOGMNR_D','DBZUSER','EXECUTE');

-- 4. Validacion
SELECT SUPPLEMENTAL_LOG_DATA_MIN, SUPPLEMENTAL_LOG_DATA_ALL, LOG_MODE FROM V$DATABASE;
