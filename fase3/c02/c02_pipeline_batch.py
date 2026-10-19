"""
C02-AE-01/05/06: pipeline batch con 3 fuentes y 4 pasos de transformacion verificables.

Fuentes: (1) clientes/cuentas curados por CDC desde Oracle, (2) creditos por JDBC desde SQL Server,
         (3) transacciones crudas multiformato en S3 (csv, json, avro, parquet, masivo).
Pasos:   1 limpieza y tipado | 2 deduplicacion (ROW_NUMBER) | 3 enriquecimiento con maestras
         4 conciliacion FULL OUTER JOIN + agregacion mensual con ranking.
Recuperacion: escrituras idempotentes (overwritePartitions), commits atomicos Iceberg, reintentos Airflow.
Fallo controlado (C02-AE-05): si existe s3a://<bucket>/sb/control/fallar_paso_<N>, el paso N falla.

Job CDE "sb-pipeline-batch" (Spark 3, Iceberg activado). Recursos: este archivo + mssql-jdbc.jar
(Si el VC no incluye spark-avro: agregar spark.jars.packages=org.apache.spark:spark-avro_2.12:<version Spark>)
  args: --bucket CAMBIAR_BUCKET --jdbc-url "jdbc:sqlserver://CAMBIAR_RDS_SQLSERVER:1433;databaseName=sbcreditos;encrypt=false"
        --jdbc-user CAMBIAR --jdbc-password CAMBIAR --version v1
"""
import argparse
import uuid
from datetime import datetime

from pyspark.sql import SparkSession, functions as F, Window

ap = argparse.ArgumentParser()
ap.add_argument("--bucket", required=True)
ap.add_argument("--jdbc-url", required=True)
ap.add_argument("--jdbc-user", required=True)
ap.add_argument("--jdbc-password", required=True)
ap.add_argument("--version", default="dev")
a = ap.parse_args()

spark = (SparkSession.builder.appName("sb-pipeline-batch")
         .config("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
         .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
         .getOrCreate())
RUN_ID, INICIO = str(uuid.uuid4()), datetime.utcnow()
LANDING = f"s3a://{a.bucket}/sb/landing/transacciones"
fs_path = spark._jvm.org.apache.hadoop.fs.Path


def punto_de_control(paso):
    """Inyeccion de fallo controlado: crear el archivo marcador en S3 para que el paso falle."""
    marcador = fs_path(f"s3a://{a.bucket}/sb/control/fallar_paso_{paso}")
    fs = marcador.getFileSystem(spark._jsc.hadoopConfiguration())
    if fs.exists(marcador):
        raise RuntimeError(f"FALLO CONTROLADO en paso {paso}: se encontro {marcador}. "
                           f"Accion: eliminar el marcador y reintentar (el pipeline es idempotente).")
    print(f"[{datetime.utcnow():%H:%M:%S}] Paso {paso} OK")


def registrar(estado, filas, mensaje):
    esc = mensaje.replace("'", "")[:500]
    spark.sql(f"""INSERT INTO sb_consumption.pipeline_runs VALUES ('{RUN_ID}', 'sb-pipeline-batch', '{a.version}',
                 TIMESTAMP '{INICIO:%Y-%m-%d %H:%M:%S}', current_timestamp(), '{estado}', {filas}, '{esc}')""")


try:
    # ---------- Paso 1: lectura de 3 fuentes + limpieza y tipado ----------
    columnas = ["id_transaccion", "id_cuenta", "fecha_hora", "tipo", "canal", "monto", "moneda",
                "id_entidad_destino", "descripcion"]
    csv = spark.read.option("header", True).option("inferSchema", True).csv(f"{LANDING}/csv/")
    js = spark.read.json(f"{LANDING}/json/")
    avro = spark.read.format("avro").load(f"{LANDING}/avro/")
    pq = spark.read.parquet(f"{LANDING}/parquet/")
    masivo = spark.read.parquet(f"{LANDING}/parquet_masivo/")
    tipos = {"id_transaccion": "string", "id_cuenta": "bigint", "fecha_hora": "string", "tipo": "string",
             "canal": "string", "monto": "double", "moneda": "string", "id_entidad_destino": "bigint",
             "descripcion": "string"}
    tx = None
    for nombre, df in [("csv", csv), ("json", js), ("avro", avro), ("parquet", pq), ("parquet", masivo)]:
        df = df.select(*[F.col(c).cast(tipos[c]).alias(c) for c in columnas]).withColumn("formato_origen", F.lit(nombre))
        tx = df if tx is None else tx.unionByName(df)
    tx = (tx.withColumn("fecha_hora", F.to_timestamp("fecha_hora"))
            .withColumn("monto", F.col("monto").cast("decimal(18,2)"))
            .withColumn("canal", F.upper(F.trim("canal")))
            .withColumn("id_entidad_destino", F.col("id_entidad_destino").cast("int"))
            .filter("monto > 0 AND fecha_hora IS NOT NULL AND id_cuenta IS NOT NULL"))
    creditos_src = (spark.read.format("jdbc").option("url", a.jdbc_url).option("dbtable", "dbo.creditos")
                    .option("user", a.jdbc_user).option("password", a.jdbc_password)
                    .option("numPartitions", 8).option("partitionColumn", "id_credito")
                    .option("lowerBound", 1).option("upperBound", 500000).load())
    cuentas = spark.table("sb_curated.cuentas")
    clientes = spark.table("sb_curated.clientes")
    punto_de_control(1)

    # ---------- Paso 2: deduplicacion con ROW_NUMBER ----------
    w = Window.partitionBy("id_transaccion").orderBy(F.col("fecha_hora").desc())
    tx = tx.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
    punto_de_control(2)

    # ---------- Paso 3: enriquecimiento con tablas maestras ----------
    entidades = spark.table("sb_curated.entidades_financieras").select(
        F.col("id_entidad").alias("id_entidad_destino"), F.col("nombre").alias("nombre_entidad"))
    tx = tx.join(F.broadcast(entidades), "id_entidad_destino", "left")
    tx_final = tx.select("id_transaccion", "id_cuenta", "fecha_hora", "tipo", "canal", "monto", "moneda",
                         "id_entidad_destino", "nombre_entidad", "formato_origen",
                         F.current_timestamp().alias("fecha_proceso"))
    tx_final.writeTo("sb_curated.transacciones").overwritePartitions()
    creditos = (creditos_src.select(
        F.col("id_credito").cast("bigint"), "identificacion_cliente", F.col("id_producto").cast("int"),
        F.col("monto_original").cast("decimal(16,2)"), F.col("saldo_pendiente").cast("decimal(16,2)"),
        F.col("tasa_interes").cast("decimal(6,2)"), F.col("plazo_meses").cast("int"),
        F.col("dias_mora").cast("int"), F.col("calificacion_riesgo").cast("string"),
        F.col("fecha_desembolso").cast("date"), F.col("default_12m").cast("int"),
        F.current_timestamp().alias("fecha_proceso")))
    creditos.writeTo("sb_curated.creditos").overwritePartitions()
    punto_de_control(3)

    # ---------- Paso 4a: conciliacion clientes vs creditos (FULL OUTER JOIN) ----------
    cred_por_id = creditos.groupBy(F.col("identificacion_cliente").alias("identificacion")).agg(
        F.count("*").alias("num_creditos"))
    conc = (clientes.select("identificacion", "id_cliente")
            .join(cred_por_id, "identificacion", "full_outer")
            .select("identificacion", "id_cliente", F.coalesce("num_creditos", F.lit(0)).cast("bigint").alias("num_creditos"),
                    F.when(F.col("id_cliente").isNull(), "CREDITO_SIN_CLIENTE")
                     .when(F.col("num_creditos").isNull(), "CLIENTE_SIN_CREDITO")
                     .otherwise("OK").alias("estado_conciliacion"),
                    F.current_timestamp().alias("fecha_proceso")))
    conc.writeTo("sb_consumption.conciliacion_cliente_credito").overwritePartitions()

    # ---------- Paso 4b: agregacion mensual con DISTINCT y ranking ----------
    resumen = (tx_final.join(cuentas.select("id_cuenta", "id_cliente"), "id_cuenta")
               .join(clientes.select("id_cliente", "region", "segmento"), "id_cliente")
               .withColumn("mes", F.trunc("fecha_hora", "month"))
               .groupBy("id_cliente", "region", "segmento", "mes")
               .agg(F.count("*").alias("num_transacciones"),
                    F.sum("monto").cast("decimal(20,2)").alias("monto_total"),
                    F.countDistinct("canal").alias("canales_distintos")))
    wr = Window.partitionBy("region", "mes").orderBy(F.col("monto_total").desc())
    resumen = resumen.withColumn("ranking_region", F.row_number().over(wr)).withColumn(
        "fecha_proceso", F.current_timestamp())
    resumen.writeTo("sb_consumption.resumen_cliente_mensual").overwritePartitions()
    punto_de_control(4)

    filas = spark.table("sb_consumption.resumen_cliente_mensual").count()
    registrar("EXITOSO", filas, "Pipeline completo")
    print(f"RUN {RUN_ID} EXITOSO - filas consumibles: {filas}")
except Exception as e:  # noqa: BLE001
    registrar("FALLIDO", 0, str(e))
    raise
