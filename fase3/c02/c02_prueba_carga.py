"""
C02-PRE-06 / AE-03 / AE-10 y PG (registros/ms, registros/dolar): prueba de concurrencia 50 -> 500 usuarios
contra un VW Impala con recursos fijos, y luego con autoscaling (WAA) activo.

  python fase3/c02/c02_prueba_carga.py --prueba recursos_fijos --niveles 50,100,200,300,400,500 --segundos 120
  python fase3/c02/c02_prueba_carga.py --prueba autoscaling   --niveles 50,500 --segundos 180
  python fase3/c02/c02_prueba_carga.py --prueba aislamiento --niveles 500 --segundos 300 --sonda-depto b   # C02-AE-09
    (--sonda-depto: un usuario sonda consulta el VW del OTRO departamento durante la carga y reporta su latencia;
     ejecutar antes una corrida de la sonda sin carga para tener la linea base)

Ejecutar en una sesion de Cloudera AI con perfil de 8 vCPU / 16 GB (500 conexiones concurrentes). Resultados:
  resultados_carga_<prueba>.csv (detalle) + fila resumen en sb_consumption.metricas_rendimiento.
"""
import argparse
import collections
import csv
import random
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg, impala  # noqa: E402

CONSULTAS = [
    "SELECT region, COUNT(*), SUM(monto_total) FROM sb_consumption.resumen_cliente_mensual GROUP BY region",
    "SELECT canal, COUNT(*) FROM sb_curated.transacciones WHERE fecha_hora >= '2026-07-{d:02d}' "
    "AND fecha_hora < '2026-07-{d2:02d}' GROUP BY canal",
    "SELECT * FROM sb_consumption.resumen_cliente_mensual WHERE id_cliente = {c}",
]


def usuario(fin, resultados, candado, depto):
    try:
        con = impala("analista2", depto)
        cur = con.cursor()
    except Exception as e:  # noqa: BLE001
        with candado:
            resultados.append((0, 0, str(e)[:80]))
        return
    while time.time() < fin:
        d = random.randint(1, 28)
        sql = random.choice(CONSULTAS).format(d=d, d2=d + 1, c=random.randint(1, 1_000_000))
        t0 = time.perf_counter()
        try:
            cur.execute(sql)
            n = len(cur.fetchall())
            err = ""
        except Exception as e:  # noqa: BLE001
            n, err = 0, str(e)[:80]
        with candado:
            resultados.append(((time.perf_counter() - t0) * 1000, n, err))
    con.close()


def nivel(n_usuarios, segundos, depto, sonda_depto=None):
    resultados, candado = [], threading.Lock()
    fin = time.time() + segundos
    hilos = [threading.Thread(target=usuario, args=(fin, resultados, candado, depto)) for _ in range(n_usuarios)]
    sonda, candado_s = [], threading.Lock()
    if sonda_depto:
        hilos.append(threading.Thread(target=usuario, args=(fin, sonda, candado_s, sonda_depto)))
    for h in hilos:
        h.start()
        time.sleep(0.02)
    for h in hilos:
        h.join()
    ok = [r for r in resultados if not r[2]]
    lat = sorted(r[0] for r in ok) or [0]
    registros = sum(r[1] for r in ok)
    lat_s = sorted(r[0] for r in sonda if not r[2]) or [0]
    tipos = collections.Counter(r[2][:60] for r in resultados if r[2]).most_common(2)
    return {"usuarios": n_usuarios, "consultas": len(resultados), "errores": len(resultados) - len(ok),
            "exitosas_s": round(len(ok) / segundos, 1), "tipos_error": " | ".join(f"{n}x {t}" for t, n in tipos),
            "p50_ms": statistics.median(lat), "p95_ms": lat[int(len(lat) * .95) - 1] if len(lat) > 1 else lat[0],
            "registros_por_ms": registros / (segundos * 1000),
            "sonda_p50_ms": statistics.median(lat_s) if sonda_depto else ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", default="recursos_fijos")
    ap.add_argument("--niveles", default="50,100,200,300,400,500")
    ap.add_argument("--segundos", type=int, default=120)
    ap.add_argument("--depto", default="a")
    ap.add_argument("--sonda-depto", choices=["a", "b"], help="VW del otro tenant a observar durante la carga")
    ap.add_argument("--sin-registro", action="store_true", help="no insertar en sb_consumption.metricas_rendimiento")
    a = ap.parse_args()
    usd_hora = cfg()["costos"]["usd_hora_vw_impala"] or 0
    salida = Path(f"resultados_carga_{a.prueba}.csv")
    with open(salida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["usuarios", "consultas", "errores", "exitosas_s", "p50_ms", "p95_ms", "registros_por_ms",
                                          "sonda_p50_ms", "tipos_error"])
        w.writeheader()
        for n in [int(x) for x in a.niveles.split(",")]:
            r = nivel(n, a.segundos, a.depto, a.sonda_depto)
            w.writerow(r)
            f.flush()
            costo = usd_hora * a.segundos / 3600
            reg_usd = (r["registros_por_ms"] * a.segundos * 1000 / costo) if costo else 0
            print(f"{n:>4} usuarios | {r['consultas']:>6} consultas | {r['errores']:>4} errores | "
                  f"{r['exitosas_s']:>6} ok/s | p50 {r['p50_ms']:.0f} ms | p95 {r['p95_ms']:.0f} ms | {r['registros_por_ms']:.2f} reg/ms"
                  + (f" | sonda depto {a.sonda_depto} p50 {r['sonda_p50_ms']:.0f} ms" if a.sonda_depto else ""), flush=True)
            if r["tipos_error"]:
                print(f"       errores: {r['tipos_error']}", flush=True)
            if a.sin_registro:
                continue
            con = impala("admin", a.depto)
            cur = con.cursor()
            cur.execute(f"""INSERT INTO sb_consumption.metricas_rendimiento VALUES ('{a.prueba}', {n}, {r['consultas']},
                {r['errores']}, {r['p50_ms']:.1f}, {r['p95_ms']:.1f}, {r['registros_por_ms']:.4f}, {reg_usd:.2f},
                CAST('{datetime.utcnow():%Y-%m-%d %H:%M:%S}' AS TIMESTAMP))""")
            con.close()
    print("Detalle en", salida.resolve())


if __name__ == "__main__":
    main()
