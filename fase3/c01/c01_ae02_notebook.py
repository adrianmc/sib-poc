# C01-AE-02 (parte notebook). Herramienta: CML, sesion Python (JupyterLab) en el proyecto sb-poc.
# Ejecuta la misma consulta por dos vias: (1) Impala via impyla y (2) Spark leyendo la misma tabla Iceberg.
# Resultado esperado: mismos numeros, misma ubicacion fisica, cero copias.
import sys
sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import consulta

SQL = open("/home/cdsw/fase3/c01/c01_ae02_misma_consulta.sql").read().split(";")[0]

cols, filas, ms = consulta(SQL, rol="analista2")
print(f"Impala desde notebook: {len(filas)} filas en {ms:.0f} ms")
for f in filas[:10]:
    print(f)

# Via Spark (conexion de datos de CML hacia el Data Lake). Nombre de la conexion: ver "Data" en el proyecto.
import cml.data_v1 as cmldata
spark = cmldata.get_connection("CAMBIAR_NOMBRE_CONEXION_SPARK").get_spark_session()
spark.conf.set("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
spark.sql(SQL).show(10, truncate=False)
# Comparar con la salida de Impala: mismas filas y mismos valores (consulta con funciones exactas).
