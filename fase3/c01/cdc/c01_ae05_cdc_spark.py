"""
C01-AE-05: CDC automatico Oracle -> Debezium -> Kafka -> Spark Structured Streaming -> MERGE en Iceberg.
Procesa UNICAMENTE los registros que cambiaron (eventos c/u/d) y es idempotente (MERGE por llave).

Job CDE (tipo Spark, streaming de larga duracion), VC vc-depto-a:
  archivo: c01_ae05_cdc_spark.py      recurso adicional: datahub-truststore.jks (montado en /app/mount/)
  args: --brokers CAMBIAR_BROKERS --usuario sb_ing01 --password CAMBIAR --bucket CAMBIAR_BUCKET
  conf: spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.12:<version de Spark del VC>
        spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
        spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog
        spark.sql.catalog.spark_catalog.type=hive
        spark.sql.iceberg.handle-timestamp-without-timezone=true
        spark.sql.session.timeZone=UTC
"""
import argparse
from pyspark.sql import SparkSession, functions as F, Window
from pyspark.sql.types import StructType, StructField, StringType, LongType

ap = argparse.ArgumentParser()
ap.add_argument("--brokers", required=True)
ap.add_argument("--usuario", required=True)
ap.add_argument("--password", required=True)
ap.add_argument("--bucket", required=True)
ap.add_argument("--truststore", default="/app/mount/datahub-truststore.jks")
ap.add_argument("--truststore-password", default="changeit")
a = ap.parse_args()

spark = SparkSession.builder.appName("sb-c01-cdc").getOrCreate()

TABLAS = {
    "sbcore.SBCORE.CLIENTES": {
        "destino": "sb_curated.clientes", "llave": "id_cliente",
        "cols": {"id_cliente": "bigint", "identificacion": "string", "nombre": "string", "email": "string",
                 "telefono": "string", "fecha_nacimiento": "fecha", "region": "string", "segmento": "string",
                 "ingreso_mensual": "decimal(14,2)", "fecha_alta": "fecha", "fecha_actualizacion": "ts"}},
    "sbcore.SBCORE.CUENTAS": {
        "destino": "sb_curated.cuentas", "llave": "id_cuenta",
        "cols": {"id_cuenta": "bigint", "id_cliente": "bigint", "tipo_cuenta": "string", "moneda": "string",
                 "saldo": "decimal(16,2)", "estado": "string", "fecha_apertura": "fecha", "id_entidad": "int"}},
}

KAFKA = {
    "kafka.bootstrap.servers": a.brokers,
    "kafka.security.protocol": "SASL_SSL",
    "kafka.sasl.mechanism": "PLAIN",
    "kafka.sasl.jaas.config": ("org.apache.kafka.common.security.plain.PlainLoginModule required "
                               f'username="{a.usuario}" password="{a.password}";'),
    "kafka.ssl.truststore.location": a.truststore,
    "kafka.ssl.truststore.password": a.truststore_password,
    "startingOffsets": "earliest",
    "failOnDataLoss": "false",
}


def convertir(col, tipo):
    """Oracle via Debezium: DATE/TIMESTAMP llegan como epoch en milisegundos; NUMBER como string."""
    c = F.col(f"a.{col.upper()}")
    if tipo == "fecha":
        return F.to_date(F.from_unixtime(c.cast("long") / 1000)).alias(col)
    if tipo == "ts":
        return F.from_unixtime(c.cast("long") / 1000).cast("timestamp").alias(col)
    return c.cast(tipo).alias(col)


def procesar(topico, meta):
    campos = StructType([StructField(k.upper(), StringType()) for k in meta["cols"]])
    esquema = StructType([StructField("before", campos), StructField("after", campos),
                          StructField("op", StringType()), StructField("ts_ms", LongType())])
    cols = list(meta["cols"])
    llave = meta["llave"]

    def merge_lote(df, batch_id):
        if df.rdd.isEmpty():
            return
        # Para deletes la fila viene en 'before'
        df = df.withColumn("a", F.when(F.col("op") == "d", F.col("before")).otherwise(F.col("after")))
        df = df.select(*[convertir(c, t) for c, t in meta["cols"].items()], "op",
                       (F.col("ts_ms") / 1000).cast("timestamp").alias("cdc_ts"))
        # Ultimo cambio por llave dentro del micro-lote
        w = Window.partitionBy(llave).orderBy(F.col("cdc_ts").desc())
        df = df.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
        df.createOrReplaceTempView("cambios")
        sets = ", ".join([f"t.{c} = s.{c}" for c in cols + ["cdc_ts"]])
        ins_cols = ", ".join(cols + ["cdc_ts"])
        ins_vals = ", ".join([f"s.{c}" for c in cols + ["cdc_ts"]])
        df.sparkSession.sql(f"""
            MERGE INTO {meta['destino']} t USING cambios s ON t.{llave} = s.{llave}
            WHEN MATCHED AND s.op = 'd' THEN DELETE
            WHEN MATCHED THEN UPDATE SET {sets}
            WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT ({ins_cols}) VALUES ({ins_vals})""")
        print(f"[{topico}] lote {batch_id}: {df.count()} cambios aplicados")

    stream = (spark.readStream.format("kafka").options(**KAFKA).option("subscribe", topico).load()
              .select(F.from_json(F.col("value").cast("string"), esquema).alias("e"))
              .select("e.*").filter(F.col("op").isNotNull()))
    return (stream.writeStream.foreachBatch(merge_lote)
            .option("checkpointLocation", f"s3a://{a.bucket}/sb/checkpoints/cdc/{meta['destino']}")
            .trigger(processingTime="15 seconds").start())


consultas = [procesar(t, m) for t, m in TABLAS.items()]
spark.streams.awaitAnyTermination()
