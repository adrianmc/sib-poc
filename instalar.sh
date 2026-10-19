#!/bin/bash
# Instala dependencias del kit SIN modificar paquetes que ya trae el runtime de Cloudera AI.
# Uso:  ./instalar.sh        (proyecto principal)
#       ./instalar.sh rag    (proyecto del asistente RAG)
set -e
cd "$(dirname "$0")"
REQ=requirements.txt
[ "$1" = "rag" ] && REQ=requirements-rag.txt

# 1. Foto de las versiones del runtime (solo si no existe: se toma en el primer uso del proyecto limpio)
if [ ! -f ~/.runtime_base.txt ]; then
  pip freeze | grep -v ' @ ' | grep -v '^-e' > ~/.runtime_base.txt
  echo "Versiones base del runtime guardadas en ~/.runtime_base.txt"
fi

# 2. Instalar solo lo que falta; si algo exigiera cambiar una version del runtime, pip falla en vez de actualizar
if [ "$1" = "rag" ]; then
  pip install -r "$REQ"          # proyecto aislado: se permite resolver libremente
else
  pip install -r "$REQ" -c ~/.runtime_base.txt
fi

# 3. Verificacion
python - <<'PY'
import importlib
for m in ["pandas", "pyarrow", "yaml", "requests"]:
    importlib.import_module(m)
try:
    import mlflow
    print("mlflow del runtime:", mlflow.__version__)
except ImportError:
    pass
print("Instalacion OK")
PY
