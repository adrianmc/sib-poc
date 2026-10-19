# C07-AE-03 (canal notebook): CML como sb_analista01. La politica aplica porque la consulta pasa por Impala.
# Honestidad: Spark leyendo archivos directamente de S3 NO aplica masking de columnas de Ranger; en notebooks
# el acceso gobernado se hace via Impala/Hive (impyla, JDBC) o Hive Warehouse Connector.
import sys
sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import consulta

for rol in ["analista", "admin"]:
    _, filas, _ = consulta("SELECT identificacion, region FROM sb_curated.clientes ORDER BY id_cliente LIMIT 3", rol=rol)
    print(rol, filas)
