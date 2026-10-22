"""C05: reglas de calidad de datos ejecutadas en CDW. Sale con codigo 1 si alguna regla falla."""
import sys
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import consulta, error_ci  # noqa: E402

REGLAS = {
    "Tabla transacciones no vacia": ("SELECT COUNT(*) FROM sb_curated.transacciones", lambda v: v > 0),
    "Sin id_transaccion nulo": ("SELECT COUNT(*) FROM sb_curated.transacciones WHERE id_transaccion IS NULL", lambda v: v == 0),
    "Sin duplicados de id_transaccion": (
        "SELECT COUNT(*) FROM (SELECT id_transaccion FROM sb_curated.transacciones GROUP BY id_transaccion HAVING COUNT(*) > 1) d",
        lambda v: v == 0),
    "Montos positivos": ("SELECT COUNT(*) FROM sb_curated.transacciones WHERE monto <= 0", lambda v: v == 0),
    "Canales validos": ("SELECT COUNT(*) FROM sb_curated.transacciones WHERE canal NOT IN ('APP','WEB','ATM','SUCURSAL','APP_MOVIL')",
                        lambda v: v == 0),
}
fallas = 0
for nombre, (sql, regla) in REGLAS.items():
    _, filas, ms = consulta(sql, rol="ingeniero")
    valor = filas[0][0]
    ok = regla(valor)
    fallas += 0 if ok else 1
    print(f"[{'OK' if ok else 'FALLA'}] {nombre}: {valor} ({ms:.0f} ms)")
    if not ok:
        error_ci(f"Regla de calidad fallida: {nombre}")
sys.exit(1 if fallas else 0)
