"""
C02-PRE-03 / AE-01 / AE-05 / AE-06 (version Cloudera AI, sin CDE):
pipeline batch de 4 pasos verificables ejecutado en CDW (Impala) y orquestado como Job de Cloudera AI.

Fuentes (3+): transacciones multiformato en S3 (CSV, Avro, Parquet, Parquet masivo), clientes/cuentas (core Oracle)
y creditos (SQL Server), estos dos aterrizados en la capa cruda; mas la maestra de entidades.
Pasos:
  1 limpieza y tipado de clientes, cuentas y creditos
  2 union de 4 formatos + deduplicacion con ROW_NUMBER (staging)
  3 enriquecimiento con la maestra de entidades (curada)
  4 conciliacion FULL OUTER JOIN + agregacion con COUNT DISTINCT y ranking (consumible)
Recuperacion: cada paso es idempotente (TRUNCATE + INSERT) y se reintenta automaticamente.
Fallo controlado (AE-05): si existe s3a://<bucket>/sb/control/fallar_paso_<N>, el paso N falla con mensaje accionable;
al borrar el marcador durante los reintentos, la corrida se recupera sola (AE-06).
Trazabilidad: sb_consumption.pipeline_runs (corrida) y sb_consumption.pipeline_pasos (paso a paso, filas, duracion).

Job de Cloudera AI "sib-pipeline": script fase3/c02/c02_pipeline_sql.py, argumentos opcionales:
  --version v1 --ambiente dev --reintentos 3 --espera 60
"""
import argparse
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.sbpoc import cfg, impala  # noqa: E402

TABLAS_CONTROL = [
    """CREATE TABLE IF NOT EXISTS sb_consumption.pipeline_pasos (
         run_id STRING, paso INT, descripcion STRING, inicio TIMESTAMP, fin TIMESTAMP, duracion_s DOUBLE,
         filas BIGINT, intento INT, estado STRING, mensaje STRING)
       STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')""",
    """CREATE TABLE IF NOT EXISTS sb_curated.transacciones_stg (
         id_transaccion STRING, id_cuenta BIGINT, fecha_hora TIMESTAMP, tipo STRING, canal STRING,
         monto DECIMAL(18,2), moneda STRING, id_entidad_destino INT, formato_origen STRING)
       STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')""",
]

PASOS = [
    (1, "Limpieza y tipado de clientes, cuentas y creditos", [
        "TRUNCATE TABLE sb_curated.clientes",
        """INSERT INTO sb_curated.clientes
           SELECT id_cliente, identificacion, nombre, email, telefono, CAST(fecha_nacimiento AS DATE),
                  upper(trim(region)), upper(trim(segmento)), CAST(ingreso_mensual AS DECIMAL(14,2)),
                  CAST(fecha_alta AS DATE), CAST(fecha_actualizacion AS TIMESTAMP), now()
           FROM sb_raw.clientes_rds WHERE id_cliente IS NOT NULL""",
        "TRUNCATE TABLE sb_curated.cuentas",
        """INSERT INTO sb_curated.cuentas
           SELECT id_cuenta, id_cliente, tipo_cuenta, moneda, CAST(saldo AS DECIMAL(16,2)), estado,
                  CAST(fecha_apertura AS DATE), id_entidad, now()
           FROM sb_raw.cuentas_rds WHERE id_cuenta IS NOT NULL""",
        "TRUNCATE TABLE sb_curated.creditos",
        """INSERT INTO sb_curated.creditos
           SELECT id_credito, identificacion_cliente, id_producto, CAST(monto_original AS DECIMAL(16,2)),
                  CAST(saldo_pendiente AS DECIMAL(16,2)), CAST(tasa_interes AS DECIMAL(6,2)), plazo_meses,
                  dias_mora, calificacion_riesgo, CAST(fecha_desembolso AS DATE), default_12m, now()
           FROM sb_raw.creditos_rds WHERE id_credito IS NOT NULL""",
    ], "SELECT COUNT(*) FROM sb_curated.clientes"),
    (2, "Union de 4 formatos y deduplicacion con ROW_NUMBER", [
        "TRUNCATE TABLE sb_curated.transacciones_stg",
        """INSERT INTO sb_curated.transacciones_stg
           SELECT id_transaccion, id_cuenta, fecha_hora, tipo, canal, monto, moneda, id_entidad_destino, formato_origen
           FROM (
             SELECT u.*, ROW_NUMBER() OVER (PARTITION BY u.id_transaccion ORDER BY u.fecha_hora DESC) rn
             FROM (
               SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP) fecha_hora, upper(trim(tipo)) tipo,
                      upper(trim(canal)) canal, CAST(monto AS DECIMAL(18,2)) monto, moneda,
                      CAST(id_entidad_destino AS INT) id_entidad_destino, 'csv' formato_origen
               FROM sb_raw.transacciones_csv
               UNION ALL
               SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
                      CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'avro'
               FROM sb_raw.transacciones_avro
               UNION ALL
               SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
                      CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'parquet'
               FROM sb_raw.transacciones_parquet
               UNION ALL
               SELECT id_transaccion, id_cuenta, CAST(fecha_hora AS TIMESTAMP), upper(trim(tipo)), upper(trim(canal)),
                      CAST(monto AS DECIMAL(18,2)), moneda, CAST(id_entidad_destino AS INT), 'parquet'
               FROM sb_raw.transacciones_masivo
             ) u
             WHERE u.monto > 0 AND u.fecha_hora IS NOT NULL AND u.id_cuenta IS NOT NULL
           ) d
           WHERE d.rn = 1""",
    ], "SELECT COUNT(*) FROM sb_curated.transacciones_stg"),
    (3, "Enriquecimiento con la maestra de entidades", [
        "TRUNCATE TABLE sb_curated.transacciones",
        """INSERT INTO sb_curated.transacciones
           SELECT s.id_transaccion, s.id_cuenta, s.fecha_hora, s.tipo, s.canal, s.monto, s.moneda,
                  s.id_entidad_destino, e.nombre, s.formato_origen, now()
           FROM sb_curated.transacciones_stg s
           LEFT JOIN sb_curated.entidades_financieras e ON e.id_entidad = s.id_entidad_destino""",
    ], "SELECT COUNT(*) FROM sb_curated.transacciones"),
    (4, "Conciliacion FULL OUTER JOIN y agregacion mensual con ranking", [
        "TRUNCATE TABLE sb_consumption.conciliacion_cliente_credito",
        """INSERT INTO sb_consumption.conciliacion_cliente_credito
           SELECT coalesce(c.identificacion, cr.identificacion), c.id_cliente, CAST(coalesce(cr.num_creditos, 0) AS BIGINT),
                  CASE WHEN c.id_cliente IS NULL THEN 'CREDITO_SIN_CLIENTE'
                       WHEN cr.num_creditos IS NULL THEN 'CLIENTE_SIN_CREDITO' ELSE 'OK' END, now()
           FROM (SELECT identificacion, id_cliente FROM sb_curated.clientes) c
           FULL OUTER JOIN (SELECT identificacion_cliente identificacion, COUNT(*) num_creditos
                            FROM sb_curated.creditos GROUP BY identificacion_cliente) cr
             ON c.identificacion = cr.identificacion""",
        "TRUNCATE TABLE sb_consumption.resumen_cliente_mensual",
        """INSERT INTO sb_consumption.resumen_cliente_mensual
           SELECT a.id_cliente, a.region, a.segmento, a.mes, a.num_transacciones, a.monto_total, a.canales_distintos,
                  CAST(ROW_NUMBER() OVER (PARTITION BY a.region, a.mes ORDER BY a.monto_total DESC) AS INT), now()
           FROM (
             SELECT cl.id_cliente, cl.region, cl.segmento, CAST(trunc(t.fecha_hora, 'MM') AS DATE) mes,
                    COUNT(*) num_transacciones, CAST(SUM(t.monto) AS DECIMAL(20,2)) monto_total,
                    COUNT(DISTINCT t.canal) canales_distintos
             FROM sb_curated.transacciones t
             JOIN sb_curated.cuentas cu ON cu.id_cuenta = t.id_cuenta
             JOIN sb_curated.clientes cl ON cl.id_cliente = cu.id_cliente
             GROUP BY cl.id_cliente, cl.region, cl.segmento, CAST(trunc(t.fecha_hora, 'MM') AS DATE)
           ) a""",
    ], "SELECT COUNT(*) FROM sb_consumption.resumen_cliente_mensual"),
]


def limpio(texto):
    return str(texto).replace("'", "").replace("\n", " ")[:480]


def marcador_presente(bucket, paso):
    ruta = f"s3a://{bucket}/sb/control/fallar_paso_{paso}"
    r = subprocess.run(["hdfs", "dfs", "-test", "-e", ruta], capture_output=True)
    return ruta if r.returncode == 0 else None


def ejecutar(cur, sql):
    cur.execute(sql)
    return cur.fetchall() if cur.description else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="dev")
    ap.add_argument("--ambiente", default="dev")
    ap.add_argument("--reintentos", type=int, default=3)
    ap.add_argument("--espera", type=int, default=60, help="segundos entre reintentos")
    ap.add_argument("--desde-paso", type=int, default=1)
    a = ap.parse_args()

    bucket = cfg()["s3"]["bucket"]
    run_id, inicio = str(uuid.uuid4()), datetime.utcnow()
    con = impala("ingeniero")
    cur = con.cursor()
    for ddl in TABLAS_CONTROL:
        cur.execute(ddl)
    print(f"RUN {run_id} | version {a.version} | ambiente {a.ambiente} | inicio {inicio:%Y-%m-%d %H:%M:%S} UTC")

    filas_final, estado_final, mensaje_final = 0, "EXITOSO", "Pipeline completo"
    for numero, descripcion, sentencias, conteo in PASOS:
        if numero < a.desde_paso:
            continue
        for intento in range(1, a.reintentos + 1):
            t0, ts0 = time.time(), datetime.utcnow()
            try:
                marcador = marcador_presente(bucket, numero)
                if marcador:
                    raise RuntimeError(f"FALLO CONTROLADO en paso {numero}: existe {marcador}. "
                                       f"Accion: eliminar el marcador (hdfs dfs -rm {marcador}); "
                                       f"el paso se reintenta solo y es idempotente.")
                for sql in sentencias:
                    ejecutar(cur, sql)
                filas = ejecutar(cur, conteo)[0][0]
                estado, mensaje = "EXITOSO", "OK"
            except Exception as e:  # noqa: BLE001
                filas, estado, mensaje = 0, "FALLIDO", str(e)
            dur = time.time() - t0
            cur.execute(f"""INSERT INTO sb_consumption.pipeline_pasos VALUES ('{run_id}', {numero}, '{limpio(descripcion)}',
                CAST('{ts0:%Y-%m-%d %H:%M:%S}' AS TIMESTAMP), now(), {dur:.1f}, {filas}, {intento}, '{estado}',
                '{limpio(mensaje)}')""")
            print(f"[{datetime.utcnow():%H:%M:%S}] Paso {numero} intento {intento}: {estado} | {filas} filas | {dur:.0f} s"
                  + ("" if estado == "EXITOSO" else f" | {mensaje}"))
            if estado == "EXITOSO":
                filas_final = filas
                break
            if intento < a.reintentos:
                print(f"   reintento en {a.espera} s ...")
                time.sleep(a.espera)
        else:
            estado_final, mensaje_final = "FALLIDO", f"Paso {numero}: {mensaje}"
            break

    cur.execute(f"""INSERT INTO sb_consumption.pipeline_runs VALUES ('{run_id}', 'sib-pipeline', '{limpio(a.version)}',
        CAST('{inicio:%Y-%m-%d %H:%M:%S}' AS TIMESTAMP), now(), '{estado_final}', {filas_final},
        '{limpio(a.ambiente + ": " + mensaje_final)}')""")
    con.close()
    print(f"RUN {run_id} {estado_final}: {mensaje_final}")
    if estado_final != "EXITOSO":
        sys.exit(1)   # el Job de Cloudera AI queda en Failed, visible en la consola


if __name__ == "__main__":
    main()
