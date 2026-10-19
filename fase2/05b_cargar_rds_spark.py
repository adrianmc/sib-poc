"""
FASE 2 - Paso 05 (opcion recomendada, CDE): carga RDS desde S3 con Spark JDBC en paralelo.
Lee salida/rds/*.csv subidos a s3a://<bucket>/sb/landing/rds/ y escribe en RDS Oracle (clientes, cuentas)
y RDS SQL Server (creditos). Las tablas destino ya existen (03_rds_oracle.sql y 04_rds_sqlserver.sql).

Job CDE "sb-cargar-rds" (Spark 3), VC vc-depto-a. Recurso sb-drivers con ojdbc8.jar y mssql-jdbc.jar.
  jars: ojdbc8.jar, mssql-jdbc.jar
  args: --bucket CAMBIAR_BUCKET
        --ora-url jdbc:oracle:thin:@//CAMBIAR_RDS_ORACLE:1521/ORCL --ora-user SBCORE --ora-password CAMBIAR
        --sql-url "jdbc:sqlserver://CAMBIAR_RDS_SQLSERVER:1433;databaseName=sbcreditos;encrypt=false"
        --sql-user CAMBIAR --sql-password CAMBIAR
Red: el security group de RDS debe permitir 1521 y 1433 desde las subnets privadas del ambiente (EKS).
"""
import argparse
from pyspark.sql import SparkSession, functions as F

ap = argparse.ArgumentParser()
for a_ in ["--bucket", "--ora-url", "--ora-user", "--ora-password", "--sql-url", "--sql-user", "--sql-password"]:
    ap.add_argument(a_, required=True)
ap.add_argument("--solo", choices=["oracle", "sqlserver"])
a = ap.parse_args()

spark = SparkSession.builder.appName("sb-cargar-rds").config("spark.sql.session.timeZone", "UTC").getOrCreate()
BASE = f"s3a://{a.bucket}/sb/landing/rds"


def leer(nombre):
    return spark.read.option("header", True).csv(f"{BASE}/{nombre}.csv")


def escribir(df, url, usuario, password, tabla, driver, particiones=8):
    (df.repartition(particiones).write.format("jdbc").mode("append")
       .option("url", url).option("dbtable", tabla).option("user", usuario).option("password", password)
       .option("driver", driver).option("batchsize", 10000).option("isolationLevel", "READ_COMMITTED").save())
    print(f"{tabla}: {df.count()} filas cargadas")


def mayusculas(df):
    """Oracle: el dialecto JDBC de Spark entrecomilla nombres; las columnas deben ir en mayusculas."""
    return df.toDF(*[c.upper() for c in df.columns])


if a.solo in (None, "oracle"):
    ORA = "oracle.jdbc.OracleDriver"
    cli = leer("clientes").select(
        F.col("id_cliente").cast("long"), "identificacion", "nombre", "email", "telefono",
        F.to_date("fecha_nacimiento").alias("fecha_nacimiento"), "region", "segmento",
        F.col("ingreso_mensual").cast("decimal(14,2)"), F.to_date("fecha_alta").alias("fecha_alta"),
        F.to_timestamp("fecha_actualizacion").alias("fecha_actualizacion"))
    escribir(mayusculas(cli), a.ora_url, a.ora_user, a.ora_password, "SBCORE.CLIENTES", ORA)
    cta = leer("cuentas").select(
        F.col("id_cuenta").cast("long"), F.col("id_cliente").cast("long"), "tipo_cuenta", "moneda",
        F.col("saldo").cast("decimal(16,2)"), "estado", F.to_date("fecha_apertura").alias("fecha_apertura"),
        F.col("id_entidad").cast("int"))
    escribir(mayusculas(cta), a.ora_url, a.ora_user, a.ora_password, "SBCORE.CUENTAS", ORA)

if a.solo in (None, "sqlserver"):
    cre = leer("creditos").select(
        F.col("id_credito").cast("long"), "identificacion_cliente", F.col("id_producto").cast("int"),
        F.col("monto_original").cast("decimal(16,2)"), F.col("saldo_pendiente").cast("decimal(16,2)"),
        F.col("tasa_interes").cast("decimal(6,2)"), F.col("plazo_meses").cast("int"), F.col("dias_mora").cast("int"),
        "calificacion_riesgo", F.to_date("fecha_desembolso").alias("fecha_desembolso"),
        F.col("default_12m").cast("int"))
    escribir(cre, a.sql_url, a.sql_user, a.sql_password, "dbo.creditos",
             "com.microsoft.sqlserver.jdbc.SQLServerDriver")
