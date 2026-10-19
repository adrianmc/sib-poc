"""
C06-PRE-05 / AE-07: indexa el corpus normativo sintetico (PDF en S3 o local) con embeddings del
Cloudera AI Inference Service y guarda un indice vectorial (numpy) en /home/cdsw/data/rag/.
  python fase3/c06/rag/indexar.py --docs /home/cdsw/data/documentos
(Descargar antes los PDF desde la Terminal de la sesion, credenciales via IDBroker:
   mkdir -p /home/cdsw/data/documentos && hdfs dfs -get s3a://CAMBIAR_BUCKET/sb/landing/documentos/*.pdf /home/cdsw/data/documentos/)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from openai import OpenAI
from pypdf import PdfReader

sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg  # noqa: E402

DESTINO = Path("/home/cdsw/data/rag")


def cliente_emb():
    c = cfg()["inferencia"]
    token = json.load(open("/tmp/jwt"))["access_token"]     # JWT de la sesion CML
    return OpenAI(base_url=c["emb_base_url"], api_key=token), c["emb_modelo"]


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
    cli, modelo = cliente_emb()
    frags = list(fragmentos(Path(a.docs)))
    vecs = []
    for i in range(0, len(frags), 32):
        r = cli.embeddings.create(model=modelo, input=[f["texto"] for f in frags[i:i + 32]])
        vecs.extend(d.embedding for d in r.data)
    m = np.array(vecs, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    DESTINO.mkdir(parents=True, exist_ok=True)
    np.save(DESTINO / "vectores.npy", m)
    json.dump(frags, open(DESTINO / "fragmentos.json", "w"), ensure_ascii=False)
    print(f"Indice vectorial: {len(frags)} fragmentos, dimension {m.shape[1]}")


if __name__ == "__main__":
    main()
