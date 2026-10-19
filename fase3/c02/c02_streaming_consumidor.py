"""
C02-AE-02: Kafka -> Spark Structured Streaming -> Iceberg (sb_curated.transacciones_rt).
Job CDE streaming "sb-streaming-rt", mismas conf/recursos que c01_ae05_cdc_spark.py.
  args: --brokers CAMBIAR_BROKERS --usuario sb_ing01 --password CAMBIAR --bucket CAMBIAR_BUCKET --topico sb.transacciones.rt
Latencia esperada: segundos (trigger de 5 s + commit Iceberg). Para sub-segundo: Kudu (Real-Time Data Mart).
"""
import argparse
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType

ap = argparse.ArgumentParser()
for arg in ["--brokers", "--usuario", "--password", "--bucket", "--topico"]:
    ap.add_argument(arg, required=True)
ap.add_argument("--truststore", default="/app/mount/datahub-truststore.jks")
ap.add_argument("--truststore-password", default="changeit")
a = ap.parse_args()

spark = SparkSession.builder.appName("sb-streaming-rt").getOrCreate()
esquema = StructType([StructField("id_transaccion", StringType()), StructField("id_cuenta", LongType()),
                      StructField("tipo", StringType()), StructField("canal", StringType()),
                      StructField("monto", DoubleType()), StructField("evento_ts", StringType())])

eventos = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", a.brokers)
           .option("kafka.security.protocol", "SASL_SSL").option("kafka.sasl.mechanism", "PLAIN")
           .option("kafka.sasl.jaas.config", "org.apache.kafka.common.security.plain.PlainLoginModule required "
                   f'username="{a.usuario}" password="{a.password}";')
           .option("kafka.ssl.truststore.location", a.truststore)
           .option("kafka.ssl.truststore.password", a.truststore_password)
           .option("subscribe", a.topico).option("startingOffsets", "latest").load()
           .select(F.from_json(F.col("value").cast("string"), esquema).alias("e")).select("e.*")
           .select("id_transaccion", "id_cuenta", "tipo", "canal", F.col("monto").cast("decimal(18,2)").alias("monto"),
                   F.to_timestamp("evento_ts").alias("evento_ts"), F.current_timestamp().alias("ingesta_ts")))

(eventos.writeStream.format("iceberg").outputMode("append")
 .option("checkpointLocation", f"s3a://{a.bucket}/sb/checkpoints/streaming_rt")
 .trigger(processingTime="5 seconds")
 .toTable("sb_curated.transacciones_rt")
 .awaitTermination())
