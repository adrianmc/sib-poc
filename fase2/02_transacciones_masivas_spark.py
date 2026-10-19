"""
FASE 2 - Paso 02 (CDE, PySpark): genera el volumen masivo de transacciones directamente en S3,
evitando subir GBs desde un equipo local. Mismo esquema que la muestra multiformato.

Job CDE (UI o CLI):  archivo = 02_transacciones_masivas_spark.py
  args: --bucket CAMBIAR_BUCKET --millones 30 --cuentas 2000000
Salida: s3a://<bucket>/sb/landing/transacciones/parquet_masivo/  (tabla sb_raw.transacciones_masivo)
"""
import argparse
from pyspark.sql import SparkSession, functions as F

ap = argparse.ArgumentParser()
ap.add_argument("--bucket", required=True)
ap.add_argument("--millones", type=int, default=30)
ap.add_argument("--cuentas", type=int, default=2_000_000)
a = ap.parse_args()

spark = SparkSession.builder.appName("sb-fase2-transacciones-masivas").getOrCreate()
n = a.millones * 1_000_000
inicio = 1767225600   # 2026-01-01 00:00:00 UTC
rango = 18_316_800    # hasta 2026-07-31

def elegir(col_rand, valores):
    expr = F.lit(valores[-1])
    for i in reversed(range(len(valores) - 1)):
        expr = F.when(col_rand < (i + 1) / len(valores), F.lit(valores[i])).otherwise(expr)
    return expr

df = (spark.range(0, n, numPartitions=max(64, a.millones * 4))
      .withColumn("r1", F.rand(1)).withColumn("r2", F.rand(2)).withColumn("r3", F.rand(3))
      .select(
          F.format_string("TXM%012d", F.col("id")).alias("id_transaccion"),
          (F.floor(F.rand(4) * a.cuentas) + 1).cast("bigint").alias("id_cuenta"),
          F.from_unixtime(F.lit(inicio) + F.floor(F.rand(5) * rango)).alias("fecha_hora"),
          elegir(F.col("r1"), ["DEPOSITO", "RETIRO", "TRANSFERENCIA", "PAGO"]).alias("tipo"),
          elegir(F.col("r2"), ["APP", "WEB", "ATM", "SUCURSAL"]).alias("canal"),
          F.round(F.exp(F.randn(6) * 1.3 + 4.5), 2).alias("monto"),
          F.when(F.col("r3") < 0.8, "LOCAL").otherwise("USD").alias("moneda"),
          (F.floor(F.rand(7) * 50) + 1).cast("bigint").alias("id_entidad_destino"),
          elegir(F.col("r3"), ["pago servicios", "transferencia propia", "compra comercio",
                               "retiro efectivo", "deposito planilla"]).alias("descripcion")))

(df.write.mode("overwrite").option("compression", "zstd")
   .parquet(f"s3a://{a.bucket}/sb/landing/transacciones/parquet_masivo/"))
print(f"Generadas {n} transacciones")
