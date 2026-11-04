"""
C06-AE-07: embeddings del RAG, compartido por indexar.py y app.py (los dos deben usar el MISMO modelo).

Dos modos, segun config.yaml > inferencia.emb_base_url:
  - URL de Cloudera AI Inference Service (API compatible OpenAI): embeddings servidos en la plataforma.
  - "local": modelo multilingue pequeno en CPU dentro del proyecto (sentence-transformers), sin GPU ni endpoint.
    Modelo por defecto intfloat/multilingual-e5-small (384 dimensiones, espanol). Se descarga una vez de Hugging Face.
"""
import json
import sys

import numpy as np

sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg  # noqa: E402

MODELO_LOCAL = "intfloat/multilingual-e5-small"


def jwt():
    """Token de la sesion, Job o Application de Cloudera AI: autentica contra AI Inference Service."""
    return json.load(open("/tmp/jwt"))["access_token"]


def crear():
    """Devuelve (descripcion, funcion). funcion(textos, es_pregunta) -> matriz normalizada float32."""
    c = cfg()["inferencia"]
    if str(c.get("emb_base_url", "local")).strip().lower() == "local":
        from sentence_transformers import SentenceTransformer
        nombre = c.get("emb_modelo") or MODELO_LOCAL
        if "CAMBIAR" in nombre:
            nombre = MODELO_LOCAL
        modelo = SentenceTransformer(nombre, device="cpu")

        def f(textos, es_pregunta=False):
            prefijo = "query: " if es_pregunta else "passage: "        # convencion de la familia e5
            m = modelo.encode([prefijo + t for t in textos], batch_size=32, normalize_embeddings=True)
            return np.asarray(m, dtype=np.float32)
        return f"local CPU ({nombre})", f

    from openai import OpenAI
    cli = OpenAI(base_url=c["emb_base_url"], api_key=jwt())

    def f(textos, es_pregunta=False):
        extra = {"input_type": "query" if es_pregunta else "passage"}   # requerido por los NIM de embeddings
        vecs = []
        for i in range(0, len(textos), 32):
            r = cli.embeddings.create(model=c["emb_modelo"], input=textos[i:i + 32], extra_body=extra)
            vecs.extend(d.embedding for d in r.data)
        m = np.array(vecs, dtype=np.float32)
        return m / np.linalg.norm(m, axis=1, keepdims=True)
    return f"AI Inference ({c['emb_modelo']})", f
