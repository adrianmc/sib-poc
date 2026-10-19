-- =====================================================================
-- FASE 2 - Paso 04: RDS SQL Server (sistema de creditos ficticio) + CDC nativo
-- Herramienta: SSMS / Azure Data Studio como usuario MASTER de RDS.
-- Requiere edicion Standard o Enterprise (CDC usa SQL Server Agent).
-- =====================================================================
CREATE DATABASE sbcreditos;
GO
EXEC msdb.dbo.rds_cdc_enable_db 'sbcreditos';
GO
USE sbcreditos;
GO
CREATE TABLE dbo.creditos (
  id_credito            BIGINT        NOT NULL PRIMARY KEY,
  identificacion_cliente VARCHAR(20)  NOT NULL,
  id_producto           INT,
  monto_original        DECIMAL(16,2),
  saldo_pendiente       DECIMAL(16,2),
  tasa_interes          DECIMAL(6,2),
  plazo_meses           INT,
  dias_mora             INT,
  calificacion_riesgo   CHAR(1),
  fecha_desembolso      DATE,
  default_12m           TINYINT
);
GO
EXEC sys.sp_cdc_enable_table @source_schema = N'dbo', @source_name = N'creditos',
     @role_name = NULL, @supports_net_changes = 0;
GO
-- Validacion
SELECT name, is_cdc_enabled FROM sys.databases WHERE name = 'sbcreditos';
SELECT name, is_tracked_by_cdc FROM sys.tables;
