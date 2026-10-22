"""
C02-AE-02: productor de eventos + medicion de latencia extremo a extremo.
  python fase3/c02/c02_streaming_productor.py --eventos 1000 --por-segundo 50   # carga continua
  python fase3/c02/c02_streaming_productor.py --medir                           # 1 evento y mide hasta verlo en la zona consumible
  python fase3/c02/c02_streaming_productor.py --medir --tasa-fondo 20           # anotar la carga de fondo (C02-AE-03)
La medicion se persiste en sb_consumption.latencia_streaming (PG-14).
Requiere el CA del Data Hub en PEM (config kafka.ca_pem).
"""
import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaProducer

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, consulta, RAIZ  # noqa: E402


def productor():
    c = cfg()
    u = c["usuarios"]["ingeniero"]
    return KafkaProducer(
        bootstrap_servers=c["kafka"]["brokers"].split(","), security_protocol="SASL_SSL",
        sasl_mechanism="PLAIN", sasl_plain_username=u["user"], sasl_plain_password=u["password"],
        ssl_cafile=str(RAIZ / c["kafka"]["ca_pem"]),
        value_serializer=lambda v: json.dumps(v).encode())


def evento(id_tx=None):
    return {"id_transaccion": id_tx or f"RT{uuid.uuid4().hex[:14].upper()}", "id_cuenta": random.randint(1, 2_000_000),
            "tipo": random.choice(["DEPOSITO", "RETIRO", "TRANSFERENCIA", "PAGO"]),
            "canal": random.choice(["APP", "WEB", "ATM"]), "monto": round(random.lognormvariate(4.5, 1.3), 2),
            "evento_ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eventos", type=int, default=100)
    ap.add_argument("--por-segundo", type=int, default=20)
    ap.add_argument("--medir", action="store_true")
    ap.add_argument("--tasa-fondo", type=int, default=0, help="eventos/s de otro productor corriendo en paralelo")
    ap.add_argument("--refresh", action="store_true",
                    help="forzar REFRESH en cada sondeo si la sincronizacion automatica de metadata de Impala tarda")
    a = ap.parse_args()
    p, topico = productor(), cfg()["kafka"]["topic_rt"]
    if a.medir:
        id_tx = f"RTMEDIR{int(time.time())}"
        t0 = time.time()
        enviado = datetime.now(timezone.utc)
        p.send(topico, evento(id_tx))
        p.flush()
        print(f"Evento {id_tx} enviado. Esperando disponibilidad en sb_consumption.v_transacciones_rt ...")
        while True:
            if a.refresh:
                consulta("REFRESH sb_curated.transacciones_rt")
            _, filas, _ = consulta(f"SELECT COUNT(*) FROM sb_consumption.v_transacciones_rt WHERE id_transaccion = '{id_tx}'")
            if filas[0][0] > 0:
                lat = time.time() - t0
                disponible = datetime.now(timezone.utc)
                print(f"LATENCIA EXTREMO A EXTREMO: {lat:.1f} s (evento -> consultable en la zona consumible)")
                consulta(f"""INSERT INTO sb_consumption.latencia_streaming VALUES ('{id_tx}', {a.tasa_fondo},
                    CAST('{enviado:%Y-%m-%d %H:%M:%S}' AS TIMESTAMP), CAST('{disponible:%Y-%m-%d %H:%M:%S}' AS TIMESTAMP), {lat:.2f})""")
                break
            time.sleep(1)
        return
    for i in range(a.eventos):
        p.send(topico, evento())
        time.sleep(1 / a.por_segundo)
    p.flush()
    print(f"{a.eventos} eventos enviados a {topico}")


if __name__ == "__main__":
    main()
