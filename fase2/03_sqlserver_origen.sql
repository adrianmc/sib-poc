-- =====================================================================
-- FASE 2 - Paso 03: base origen del cliente en SQL Server (core bancario y creditos ficticios) + CDC nativo
-- Donde: SQL Server 2022 Developer en la EC2 Windows. Herramienta: SSMS conectado como sysadmin.
-- Prerrequisitos: autenticacion mixta (SQL + Windows), TCP 1433 habilitado, servicio SQL Server Agent en
-- ejecucion (CDC lo necesita), firewall de Windows y security group con 1433 abierto al CIDR de la VPC.
-- Developer incluye CDC (igual que Enterprise); no es para produccion, suficiente para la PoC.
-- =====================================================================
USE master;
GO
CREATE LOGIN sbcore_app WITH PASSWORD = 'CAMBIAR_PASSWORD', CHECK_POLICY = OFF;
CREATE LOGIN sbcore_dbz WITH PASSWORD = 'CAMBIAR_PASSWORD', CHECK_POLICY = OFF;
GO
CREATE DATABASE sbcore;
GO
USE sbcore;
GO
CREATE TABLE dbo.clientes (
  id_cliente          BIGINT        NOT NULL PRIMARY KEY,
  identificacion      VARCHAR(20)   NOT NULL,
  nombre              VARCHAR(120),
  email               VARCHAR(120),
  telefono            VARCHAR(20),
  fecha_nacimiento    DATE,
  region              VARCHAR(20),
  segmento            VARCHAR(20),
  ingreso_mensual     DECIMAL(14,2),
  fecha_alta          DATE,
  fecha_actualizacion DATETIME2(3)
);
CREATE TABLE dbo.cuentas (
  id_cuenta      BIGINT       NOT NULL PRIMARY KEY,
  id_cliente     BIGINT       NOT NULL,
  tipo_cuenta    VARCHAR(20),
  moneda         VARCHAR(10),
  saldo          DECIMAL(16,2),
  estado         VARCHAR(20),
  fecha_apertura DATE,
  id_entidad     INT
);
CREATE TABLE dbo.creditos (
  id_credito             BIGINT        NOT NULL PRIMARY KEY,
  identificacion_cliente VARCHAR(20)   NOT NULL,
  id_producto            INT,
  monto_original         DECIMAL(16,2),
  saldo_pendiente        DECIMAL(16,2),
  tasa_interes           DECIMAL(6,2),
  plazo_meses            INT,
  dias_mora              INT,
  calificacion_riesgo    CHAR(1),
  fecha_desembolso       DATE,
  default_12m            TINYINT
);
GO
-- Usuarios: la app carga datos; Debezium lee tablas y el esquema cdc (db_owner simplifica la PoC: declararlo)
CREATE USER sbcore_app FOR LOGIN sbcore_app;
ALTER ROLE db_datareader ADD MEMBER sbcore_app;
ALTER ROLE db_datawriter ADD MEMBER sbcore_app;
CREATE USER sbcore_dbz FOR LOGIN sbcore_dbz;
ALTER ROLE db_owner ADD MEMBER sbcore_dbz;
GO
-- CDC nativo (base y tablas). Se habilita ANTES de cargar datos: el snapshot inicial de Debezium toma lo cargado
EXEC sys.sp_cdc_enable_db;
GO
EXEC sys.sp_cdc_enable_table @source_schema = N'dbo', @source_name = N'clientes', @role_name = NULL, @supports_net_changes = 0;
EXEC sys.sp_cdc_enable_table @source_schema = N'dbo', @source_name = N'cuentas',  @role_name = NULL, @supports_net_changes = 0;
EXEC sys.sp_cdc_enable_table @source_schema = N'dbo', @source_name = N'creditos', @role_name = NULL, @supports_net_changes = 0;
GO
-- Snapshot de Debezium sin bloquear escrituras (conector con snapshot.isolation.mode=snapshot)
ALTER DATABASE sbcore SET ALLOW_SNAPSHOT_ISOLATION ON;
GO
-- Validacion: is_cdc_enabled = 1 y las 3 tablas con is_tracked_by_cdc = 1
SELECT name, is_cdc_enabled FROM sys.databases WHERE name = 'sbcore';
SELECT name, is_tracked_by_cdc FROM sys.tables;
