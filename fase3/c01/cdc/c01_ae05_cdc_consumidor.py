"""
C01-AE-05: aplica los cambios CDC (SQL Server -> Debezium -> Kafka) a las tablas Iceberg curadas con MERGE en Impala.
Version sin Spark ni CDE (CDE bloqueado): consumidor Python en Cloudera AI, micro-lotes cada --intervalo segundos.

Por cada micro-lote y tabla:
  1. Lee los eventos Debezium (JSON sin schema: before / after / op / ts_ms) desde Kafka (SASL_SSL PLAIN, user002).
  2. Se queda con el ULTIMO cambio por llave dentro del lote.
  3. Los escribe en una tabla de staging Iceberg y aplica un MERGE: u/c -> UPDATE o INSERT, d -> DELETE.
  4. Confirma el offset en Kafka SOLO despues del MERGE (si falla, el lote se reprocesa: MERGE es idempotente).
Los eventos 'r' (snapshot inicial) se omiten por defecto: la curada ya se cargo con la extraccion inicial (07b).

  python fase3/c01/cdc/c01_ae05_cdc_consumidor.py                 # desde el final (cambios nuevos)
  python fase3/c01/cdc/c01_ae05_cdc_consumidor.py --desde inicio  # reprocesa todo el topico (lento con 1M)
  python fase3/c01/cdc/c01_ae05_cdc_consumidor.py --una-vez       # un solo lote y termina (pruebas)

Requiere: config kafka.brokers y kafka.ca_pem (CA de FreeIPA del ambiente en PEM), usuario 'ingeniero' (user002)
con las politicas Ranger sb_12/sb_13 en el servicio Kafka del Data Hub.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import RAIZ, cfg, impala, leer_argumentos  # noqa: E402

TABLAS = {
    "clientes": {
        "destino": "sb_curated.clientes", "llave": "id_cliente",
        "cols": {"id_cliente": "BIGINT", "identificacion": "STRING", "nombre": "STRING", "email": "STRING",
                 "telefono": "STRING", "fecha_nacimiento": "DATE", "region": "STRING", "segmento": "STRING",
                 "ingreso_mensual": "DECIMAL(14,2)", "fecha_alta": "DATE", "fecha_actualizacion": "TIMESTAMP"}},
    "cuentas": {
        "destino": "sb_curated.cuentas", "llave": "id_cuenta",
        "cols": {"id_cuenta": "BIGINT", "id_cliente": "BIGINT", "tipo_cuenta": "STRING", "moneda": "STRING",
                 "saldo": "DECIMAL(16,2)", "estado": "STRING", "fecha_apertura": "DATE", "id_entidad": "INT"}},
}


def topico(tabla):
    return f"sbcore.sbcore.dbo.{tabla}"


def valor_sql(v, tipo):
    """Convierte el valor Debezium (time.precision.mode=connect, decimal=string) a literal SQL de Impala."""
    if v is None:
        return "NULL"
    if tipo == "DATE":                     # dias desde 1970-01-01
        return f"DATE '{(dt.date(1970, 1, 1) + dt.timedelta(days=int(v))).isoformat()}'"
    if tipo == "TIMESTAMP":                # epoch en milisegundos
        return f"CAST('{dt.datetime.utcfromtimestamp(int(v) / 1000):%Y-%m-%d %H:%M:%S.%f}' AS TIMESTAMP)"
    if tipo == "STRING":
        return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"
    return f"CAST('{v}' AS {tipo})"


def consumidor(a):
    from kafka import KafkaConsumer
    c = cfg()
    u = c["usuarios"]["ingeniero"]
    cons = KafkaConsumer(
        *[topico(t) for t in TABLAS],
        bootstrap_servers=c["kafka"]["brokers"].split(","), group_id=a.grupo,
        security_protocol="SASL_SSL", sasl_mechanism="PLAIN",
        sasl_plain_username=u["user"], sasl_plain_password=u["password"],
        ssl_cafile=str(RAIZ / c["kafka"]["ca_pem"]),
        enable_auto_commit=False, auto_offset_reset="earliest" if a.desde == "inicio" else "latest",
        value_deserializer=lambda b: json.loads(b) if b else None, max_poll_records=5000)
    if a.desde == "fin":                   # posicionarse al final de cada particion (solo cambios nuevos)
        cons.poll(timeout_ms=5000)
        cons.seek_to_end()
        for p in cons.assignment():
            cons.position(p)
        cons.commit()
    return cons


def aplicar(cur, tabla, eventos):
    meta = TABLAS[tabla]
    cols, llave = meta["cols"], meta["llave"]
    ultimo = {}
    for e in eventos:                      # ultimo cambio por llave dentro del lote
        fila = e["before"] if e["op"] == "d" else e["after"]
        ultimo[fila[llave]] = (e["op"], e["ts_ms"], fila)
    stg = f"sb_curated.cdc_stg_{tabla}"
    defs = ", ".join(f"{k} {t}" for k, t in cols.items())
    cur.execute(f"CREATE TABLE IF NOT EXISTS {stg} ({defs}, op STRING, cdc_ts TIMESTAMP) "
                "STORED AS ICEBERG TBLPROPERTIES ('format-version'='2')")
    cur.execute(f"TRUNCATE TABLE {stg}")
    filas = []
    for op, ts, f in ultimo.values():
        vals = [valor_sql(f.get(k), t) for k, t in cols.items()]
        vals += [f"'{op}'", valor_sql(ts, "TIMESTAMP")]
        filas.append("(" + ", ".join(vals) + ")")
    for i in range(0, len(filas), 500):
        cur.execute(f"INSERT INTO {stg} VALUES " + ", ".join(filas[i:i + 500]))
    nombres = list(cols) + ["cdc_ts"]
    sets = ", ".join(f"{k} = s.{k}" for k in nombres if k != llave)
    cur.execute(f"""
        MERGE INTO {meta['destino']} t USING {stg} s ON t.{llave} = s.{llave}
        WHEN MATCHED AND s.op = 'd' THEN DELETE
        WHEN MATCHED THEN UPDATE SET {sets}
        WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT ({', '.join(nombres)}) VALUES ({', '.join('s.' + k for k in nombres)})""")
    ops = {}
    for op, _, _ in ultimo.values():
        ops[op] = ops.get(op, 0) + 1
    return ops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", choices=["fin", "inicio"], default="fin")
    ap.add_argument("--grupo", default="sb-cdc-merge")
    ap.add_argument("--intervalo", type=int, default=15)
    ap.add_argument("--incluir-snapshot", action="store_true", help="aplicar tambien los eventos op=r")
    ap.add_argument("--una-vez", action="store_true")
    a = leer_argumentos(ap)
    cons = consumidor(a)
    print(f"Consumidor CDC activo (grupo {a.grupo}, desde {a.desde}); micro-lotes cada {a.intervalo} s", flush=True)
    while True:
        lote = cons.poll(timeout_ms=a.intervalo * 1000, max_records=20000)
        por_tabla = {}
        for tp, msgs in lote.items():
            tabla = tp.topic.rsplit(".", 1)[-1]
            for m in msgs:
                e = m.value
                if not e or not e.get("op"):
                    continue                 # tombstones de deletes
                if e["op"] == "r" and not a.incluir_snapshot:
                    continue
                por_tabla.setdefault(tabla, []).append(e)
        if por_tabla:
            con = impala("ingeniero")
            cur = con.cursor()
            for tabla, eventos in por_tabla.items():
                t0 = time.time()
                ops = aplicar(cur, tabla, eventos)
                print(f"[{time.strftime('%H:%M:%S')}] {TABLAS[tabla]['destino']}: {len(eventos)} eventos -> "
                      f"MERGE {ops} en {time.time() - t0:.1f} s", flush=True)
            con.close()
        cons.commit()                        # offsets confirmados solo despues del MERGE
        if a.una_vez:
            break


if __name__ == "__main__":
    main()
