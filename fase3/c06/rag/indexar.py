"""
C06-PRE-05 / AE-07: indexa el corpus normativo sintetico (PDF en S3 o local) con embeddings (Cloudera AI
Inference Service o modelo local en CPU, ver embeddings.py) y guarda un indice vectorial (numpy) en /home/cdsw/data/rag/.
  python fase3/c06/rag/indexar.py --docs /home/cdsw/data/documentos
(Descargar antes los PDF desde la Terminal de la sesion, credenciales via IDBroker:
   mkdir -p /home/cdsw/data/documentos && hdfs dfs -get s3a://CAMBIAR_BUCKET/sb/landing/documentos/*.pdf /home/cdsw/data/documentos/)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from pypdf import PdfReader

sys.path.insert(0, "/home/cdsw")
sys.path.insert(0, "/home/cdsw/fase3/c06/rag")
import embeddings  # noqa: E402

DESTINO = Path("/home/cdsw/data/rag")

# Calibracion del umbral de "fuera de alcance": cada modelo de embeddings tiene su propia escala de similitud
# (los e5 dan ~0.7 aun entre textos no relacionados). Se toma el punto medio entre la peor pregunta valida
# y la mejor pregunta fuera de alcance, y se guarda en indice.json para que app.py lo use.
DENTRO = ["Cual es el plazo para reportar un incidente de ciberseguridad significativo?",
          "Cuantos dias de atraso definen una operacion en mora para el indicador oficial?",
          "Que indicador de cobertura de liquidez minimo deben mantener las entidades?",
          "Cada cuanto se actualizan los datos de clientes de riesgo alto?"]
FUERA = ["Cual es la mejor receta de gallo pinto?",
         "Quien gano el ultimo mundial de futbol?",
         "Recomiendame una pelicula para el fin de semana"]


def fragmentos(docs: Path, tam=500, solape=100):
    for pdf in sorted(docs.glob("*.pdf")):
        for n, pag in enumerate(PdfReader(pdf).pages, start=1):
            texto = " ".join((pag.extract_text() or "").split())
            for i in range(0, max(len(texto), 1), tam - solape):
                if texto[i:i + tam].strip():
                    yield {"fuente": pdf.name, "pagina": n, "texto": texto[i:i + tam]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="/home/cdsw/data/documentos")
    a = ap.parse_args()
    descripcion, embeber = embeddings.crear()
    frags = list(fragmentos(Path(a.docs)))
    if not frags:
        sys.exit(f"No hay PDF en {a.docs}. Descargarlos primero (ver encabezado).")
    print(f"Embeddings: {descripcion}. Documentos: {len({f['fuente'] for f in frags})}, fragmentos: {len(frags)}")
    m = embeber([f["texto"] for f in frags])
    DESTINO.mkdir(parents=True, exist_ok=True)
    np.save(DESTINO / "vectores.npy", m)
    json.dump(frags, open(DESTINO / "fragmentos.json", "w"), ensure_ascii=False)
    print(f"Indice vectorial: {len(frags)} fragmentos, dimension {m.shape[1]}")

    def maxima(preguntas):
        return [float((m @ q).max()) for q in embeber(preguntas, es_pregunta=True)]
    dentro, fuera = maxima(DENTRO), maxima(FUERA)
    for p, v in zip(DENTRO + FUERA, dentro + fuera):
        print(f"  similitud {v:.3f}  {'VALIDA ' if p in DENTRO else 'FUERA  '} {p}")
    umbral = round((min(dentro) + max(fuera)) / 2, 3)
    if min(dentro) <= max(fuera):
        print("AVISO: una pregunta fuera de alcance se parece mas al corpus que una valida; revisar el corpus o el modelo")
    print(f"Umbral de similitud calibrado: {umbral}")
    json.dump({"embeddings": descripcion, "umbral": umbral}, open(DESTINO / "indice.json", "w"))


if __name__ == "__main__":
    main()
