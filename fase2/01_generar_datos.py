"""
FASE 2 - Paso 01: Generador de datos sinteticos bancarios (100% ficticios).

Genera en ./salida/:
  rds/clientes.csv, rds/cuentas.csv            -> cargar a RDS Oracle (core bancario)
  rds/creditos.csv                              -> cargar a RDS SQL Server
  landing/transacciones/{csv,json,avro,parquet} -> muestra multiformato (PG-07)
  landing/maestras/entidades_financieras.csv
  landing/maestras/catalogo_productos.xlsx (+ .csv)
  landing/documentos/*.pdf, *.png              -> no estructurados y corpus RAG (C06)

El volumen masivo de transacciones (20-50M) se genera en CDE con 02_transacciones_masivas_spark.py.

Uso (Terminal):
  python 01_generar_datos.py                       # volumen PoC (1M clientes)
  python 01_generar_datos.py --escala 0.01         # prueba rapida
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 20260801
REGIONES = np.array(["CENTRAL", "NORTE", "SUR", "ESTE", "OESTE"])
SEGMENTOS = np.array(["PERSONAL", "PYME", "CORPORATIVO"])
NOMBRES = np.array(["Ana", "Luis", "Maria", "Jose", "Carmen", "Carlos", "Laura", "Jorge", "Sofia", "Diego",
                    "Elena", "Andres", "Paula", "Miguel", "Lucia", "Daniel", "Valeria", "Ricardo", "Gabriela", "Fernando"])
APELLIDOS = np.array(["Rojas", "Mora", "Vargas", "Jimenez", "Castro", "Solano", "Araya", "Herrera", "Chaves", "Brenes",
                      "Ramirez", "Alvarado", "Quesada", "Salazar", "Campos", "Villalobos", "Cordero", "Arias", "Madrigal", "Fallas"])
TIPOS_TX = np.array(["DEPOSITO", "RETIRO", "TRANSFERENCIA", "PAGO"])
CANALES = np.array(["APP", "WEB", "ATM", "SUCURSAL"])


def fechas(rng, n, inicio, fin):
    a, b = pd.Timestamp(inicio).value // 10**9, pd.Timestamp(fin).value // 10**9
    return pd.to_datetime(rng.integers(a, b, n), unit="s")


def clientes(rng, n):
    nac = fechas(rng, n, "1950-01-01", "2006-12-31")
    alta = fechas(rng, n, "2010-01-01", "2026-06-30")
    nombre = (rng.choice(NOMBRES, n) + " " + rng.choice(APELLIDOS, n) + " " + rng.choice(APELLIDOS, n))
    ids = np.arange(1, n + 1)
    return pd.DataFrame({
        "id_cliente": ids,
        "identificacion": (100000000 + ids * 7 % 899999999).astype(str),
        "nombre": nombre,
        "email": [f"cliente{i}@correo-ficticio.test" for i in ids],
        "telefono": (80000000 + rng.integers(0, 9999999, n)).astype(str),
        "fecha_nacimiento": nac.strftime("%Y-%m-%d"),
        "region": rng.choice(REGIONES, n, p=[.4, .15, .15, .15, .15]),
        "segmento": rng.choice(SEGMENTOS, n, p=[.8, .15, .05]),
        "ingreso_mensual": np.round(rng.lognormal(7.2, 0.6, n), 2),
        "fecha_alta": alta.strftime("%Y-%m-%d"),
        "fecha_actualizacion": alta.strftime("%Y-%m-%d %H:%M:%S"),
    })


def cuentas(rng, n, n_clientes, n_entidades):
    return pd.DataFrame({
        "id_cuenta": np.arange(1, n + 1),
        "id_cliente": rng.integers(1, n_clientes + 1, n),
        "tipo_cuenta": rng.choice(["AHORRO", "CORRIENTE", "PLAZO"], n, p=[.6, .3, .1]),
        "moneda": rng.choice(["LOCAL", "USD"], n, p=[.75, .25]),
        "saldo": np.round(rng.lognormal(8, 1.2, n), 2),
        "estado": rng.choice(["ACTIVA", "INACTIVA", "CERRADA"], n, p=[.85, .1, .05]),
        "fecha_apertura": fechas(rng, n, "2010-01-01", "2026-06-30").strftime("%Y-%m-%d"),
        "id_entidad": rng.integers(1, n_entidades + 1, n),
    })


def creditos(rng, n, cli, n_productos):
    idx = rng.integers(0, len(cli), n)
    ingreso = cli["ingreso_mensual"].to_numpy()[idx]
    monto = np.round(rng.lognormal(9, 0.9, n), 2)
    mora = np.where(rng.random(n) < .82, 0, rng.integers(1, 180, n))
    calif = np.select([mora == 0, mora < 30, mora < 60, mora < 90], ["A", "B", "C", "D"], "E")
    # Probabilidad de default coherente con mora y carga financiera (para el caso ML)
    logit = -3.2 + 0.03 * mora + 0.9 * np.log1p(monto / (ingreso * 12)) + rng.normal(0, .5, n)
    default = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame({
        "id_credito": np.arange(1, n + 1),
        "identificacion_cliente": cli["identificacion"].to_numpy()[idx],
        "id_producto": rng.integers(1, n_productos + 1, n),
        "monto_original": monto,
        "saldo_pendiente": np.round(monto * rng.uniform(.05, 1, n), 2),
        "tasa_interes": np.round(rng.uniform(6, 28, n), 2),
        "plazo_meses": rng.choice([12, 24, 36, 48, 60, 120, 240], n),
        "dias_mora": mora,
        "calificacion_riesgo": calif,
        "fecha_desembolso": fechas(rng, n, "2018-01-01", "2026-06-30").strftime("%Y-%m-%d"),
        "default_12m": default,
    })


def transacciones(rng, n, n_cuentas, n_entidades, offset):
    return pd.DataFrame({
        "id_transaccion": [f"TX{offset + i:012d}" for i in range(n)],
        "id_cuenta": rng.integers(1, n_cuentas + 1, n),
        "fecha_hora": fechas(rng, n, "2026-01-01", "2026-07-31").strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": rng.choice(TIPOS_TX, n),
        "canal": rng.choice(CANALES, n, p=[.45, .25, .2, .1]),
        "monto": np.round(rng.lognormal(4.5, 1.3, n), 2),
        "moneda": rng.choice(["LOCAL", "USD"], n, p=[.8, .2]),
        "id_entidad_destino": rng.integers(1, n_entidades + 1, n),
        "descripcion": rng.choice(["pago servicios", "transferencia propia", "compra comercio",
                                   "retiro efectivo", "deposito planilla"], n),
    })


def maestras(rng, n_entidades, n_productos):
    ent = pd.DataFrame({
        "id_entidad": np.arange(1, n_entidades + 1),
        "codigo": [f"EF{i:03d}" for i in range(1, n_entidades + 1)],
        "nombre": [f"Entidad Financiera Ficticia {i}" for i in range(1, n_entidades + 1)],
        "tipo": rng.choice(["BANCO_PUBLICO", "BANCO_PRIVADO", "COOPERATIVA", "FINANCIERA"], n_entidades),
        "pais": "PAIS_FICTICIO",
    })
    prod = pd.DataFrame({
        "id_producto": np.arange(1, n_productos + 1),
        "nombre_producto": [f"Producto Credito {i}" for i in range(1, n_productos + 1)],
        "tipo_producto": rng.choice(["HIPOTECARIO", "PERSONAL", "VEHICULO", "TARJETA", "PYME"], n_productos),
        "tasa_referencia": np.round(rng.uniform(6, 26, n_productos), 2),
        "activo": rng.choice(["S", "N"], n_productos, p=[.9, .1]),
    })
    return ent, prod


DOCUMENTOS = {
    "reglamento_gestion_liquidez": ("Reglamento sintetico de gestion del riesgo de liquidez", [
        "Articulo 1. Las entidades supervisadas deben mantener un indicador de cobertura de liquidez igual o superior al 100 por ciento.",
        "Articulo 2. El calculo del indicador se remite al supervisor con frecuencia mensual, a mas tardar el decimo dia habil del mes siguiente.",
        "Articulo 3. Ante un indicador inferior al minimo, la entidad presenta un plan de restablecimiento en un plazo de cinco dias habiles."]),
    "reglamento_riesgo_credito": ("Reglamento sintetico de calificacion de deudores", [
        "Articulo 1. Los deudores se clasifican en categorias A, B, C, D y E segun sus dias de atraso.",
        "Articulo 2. Se considera operacion en mora aquella con mas de 90 dias de atraso para efectos del indicador oficial de morosidad.",
        "Articulo 3. La estimacion minima para la categoria E corresponde al 100 por ciento del saldo expuesto."]),
    "norma_conozca_su_cliente": ("Norma sintetica de debida diligencia del cliente", [
        "Articulo 1. Toda entidad debe identificar y verificar la identidad del cliente antes de iniciar la relacion comercial.",
        "Articulo 2. La actualizacion de datos de clientes de riesgo alto se realiza al menos una vez al ano.",
        "Articulo 3. Los registros de identificacion se conservan por un plazo minimo de cinco anos."]),
    "lineamiento_ciberseguridad": ("Lineamiento sintetico de ciberseguridad", [
        "Seccion 1. Las entidades reportan incidentes de ciberseguridad significativos en un plazo maximo de 24 horas.",
        "Seccion 2. Los accesos privilegiados requieren autenticacion multifactor y revision trimestral.",
        "Seccion 3. Los registros de auditoria se protegen contra alteracion y se conservan por al menos un ano."]),
    "lineamiento_gobierno_datos": ("Lineamiento sintetico de gobierno de datos", [
        "Seccion 1. Cada activo de datos critico tiene un propietario y un custodio formalmente designados.",
        "Seccion 2. Los datos personales se clasifican como sensibles y se protegen mediante enmascaramiento o cifrado.",
        "Seccion 3. Las definiciones de indicadores oficiales se documentan en un glosario institucional unico."]),
}


def documentos(destino: Path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from PIL import Image, ImageDraw
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, (titulo, parrafos) in DOCUMENTOS.items():
        c = canvas.Canvas(str(destino / f"{nombre}.pdf"), pagesize=letter)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, 740, titulo)
        c.setFont("Helvetica", 9)
        c.drawString(60, 725, "DOCUMENTO SINTETICO PARA PRUEBA DE CONCEPTO - SIN VALIDEZ NORMATIVA")
        y = 700
        c.setFont("Helvetica", 10)
        for p in parrafos:
            for linea in [p[i:i + 95] for i in range(0, len(p), 95)]:
                c.drawString(60, y, linea)
                y -= 14
            y -= 8
        c.save()
        img = Image.new("RGB", (900, 200), "white")
        ImageDraw.Draw(img).text((20, 80), f"{titulo} (imagen sintetica)", fill="black")
        img.save(destino / f"{nombre}.png")


def escribir_avro(df, ruta):
    from fastavro import writer, parse_schema
    esquema = parse_schema({"type": "record", "name": "transaccion", "fields": [
        {"name": "id_transaccion", "type": "string"}, {"name": "id_cuenta", "type": "long"},
        {"name": "fecha_hora", "type": "string"}, {"name": "tipo", "type": "string"},
        {"name": "canal", "type": "string"}, {"name": "monto", "type": "double"},
        {"name": "moneda", "type": "string"}, {"name": "id_entidad_destino", "type": "long"},
        {"name": "descripcion", "type": "string"}]})
    with open(ruta, "wb") as f:
        writer(f, esquema, df.to_dict("records"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escala", type=float, default=1.0)
    ap.add_argument("--salida", default="salida")
    a = ap.parse_args()
    rng = np.random.default_rng(SEMILLA)
    s = Path(a.salida)
    n_cli, n_cta, n_cre = int(1_000_000 * a.escala), int(2_000_000 * a.escala), int(500_000 * a.escala)
    n_tx_formato, n_ent, n_prod = int(250_000 * a.escala), 50, 100

    for d in ["rds", "landing/transacciones/csv", "landing/transacciones/json", "landing/transacciones/avro",
              "landing/transacciones/parquet", "landing/maestras"]:
        (s / d).mkdir(parents=True, exist_ok=True)

    cli = clientes(rng, n_cli)
    cli.to_csv(s / "rds/clientes.csv", index=False)
    cuentas(rng, n_cta, n_cli, n_ent).to_csv(s / "rds/cuentas.csv", index=False)
    creditos(rng, n_cre, cli, n_prod).to_csv(s / "rds/creditos.csv", index=False)
    print(f"RDS: {n_cli} clientes, {n_cta} cuentas, {n_cre} creditos")

    for i, fmt in enumerate(["csv", "json", "avro", "parquet"]):
        tx = transacciones(rng, n_tx_formato, n_cta, n_ent, offset=i * n_tx_formato)
        ruta = s / f"landing/transacciones/{fmt}/transacciones_{fmt}_0001.{fmt}"
        if fmt == "csv":
            tx.to_csv(ruta, index=False)
        elif fmt == "json":
            tx.to_json(ruta, orient="records", lines=True)
        elif fmt == "avro":
            escribir_avro(tx, ruta)
        else:
            tx.to_parquet(ruta, index=False)
    print(f"Landing: {4 * n_tx_formato} transacciones en 4 formatos")

    ent, prod = maestras(rng, n_ent, n_prod)
    ent.to_csv(s / "landing/maestras/entidades_financieras.csv", index=False)
    prod.to_excel(s / "landing/maestras/catalogo_productos.xlsx", index=False)
    prod.to_csv(s / "landing/maestras/catalogo_productos.csv", index=False)
    documentos(s / "landing/documentos")
    with open(s / "manifiesto.json", "w") as f:
        json.dump({"semilla": SEMILLA, "clientes": n_cli, "cuentas": n_cta, "creditos": n_cre,
                   "transacciones_muestra": 4 * n_tx_formato}, f, indent=2)
    print("Listo:", s.resolve())


if __name__ == "__main__":
    main()
