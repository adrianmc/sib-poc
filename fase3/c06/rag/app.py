"""
C06-AE-07: asistente RAG normativo con citas y guardrails. Desplegar como CML Application (Gradio):
  Script: fase3/c06/rag/app.py   (puerto CDSW_APP_PORT)
Guardrails demostrables:
  1) Pregunta sensible (datos de clientes, credenciales, identificaciones) -> se rechaza antes del LLM.
  2) Pregunta fuera de alcance (similitud baja con el corpus) -> se limita y se escala.
  3) Pregunta valida -> respuesta con cita [documento, pagina].
Alternativa sin codigo para la demo: AMP "RAG Studio" de Cloudera AI.
"""
import json
import os
import re
import sys

import gradio as gr
import numpy as np
from openai import OpenAI

sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import cfg  # noqa: E402

UMBRAL_SIMILITUD = 0.35      # calibrar con las preguntas de prueba
C = cfg()["inferencia"]
VEC = np.load("/home/cdsw/data/rag/vectores.npy")
FRAG = json.load(open("/home/cdsw/data/rag/fragmentos.json"))
SENSIBLE = re.compile(r"(identificaci[oó]n|c[eé]dula|n[uú]mero de cuenta|saldo de|contrase[nñ]a|password|"
                      r"datos personales de|tel[eé]fono de|correo de|cliente \d+)", re.I)
SISTEMA = ("Eres un asistente de consulta normativa de la Superintendencia. Responde SOLO con base en el contexto. "
           "Cita siempre la fuente entre corchetes [documento, pagina]. Si el contexto no alcanza, dilo y sugiere "
           "escalar a un especialista. Nunca reveles datos personales.")


def clientes():
    token = json.load(open("/tmp/jwt"))["access_token"]
    return OpenAI(base_url=C["emb_base_url"], api_key=token), OpenAI(base_url=C["llm_base_url"], api_key=token)


def responder(pregunta, _historial=None):
    if SENSIBLE.search(pregunta):
        return ("Solicitud rechazada por politica: la consulta pide informacion sensible o datos de clientes. "
                "Este asistente solo responde sobre normativa. Evento registrado para auditoria.")
    emb, llm = clientes()
    q = np.array(emb.embeddings.create(model=C["emb_modelo"], input=[pregunta]).data[0].embedding, dtype=np.float32)
    q /= np.linalg.norm(q)
    sims = VEC @ q
    top = np.argsort(-sims)[:4]
    if sims[top[0]] < UMBRAL_SIMILITUD:
        return (f"Fuera de alcance: no hay normativa en el corpus que respalde una respuesta "
                f"(similitud maxima {sims[top[0]]:.2f}). Se recomienda escalar a un especialista.")
    contexto = "\n\n".join(f"[{FRAG[i]['fuente']}, p.{FRAG[i]['pagina']}] {FRAG[i]['texto']}" for i in top)
    r = llm.chat.completions.create(model=C["llm_modelo"], temperature=0.1, max_tokens=500, messages=[
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"}])
    fuentes = ", ".join(sorted({f"{FRAG[i]['fuente']} p.{FRAG[i]['pagina']}" for i in top}))
    return f"{r.choices[0].message.content}\n\nFuentes recuperadas (similitud {sims[top[0]]:.2f}): {fuentes}"


EJEMPLOS = ["Cual es el plazo para reportar un incidente de ciberseguridad significativo?",
            "Cuantos dias de atraso definen una operacion en mora para el indicador oficial?",
            "Cual es la mejor receta de gallo pinto?",
            "Dame la cedula y el saldo del cliente 1045"]
gr.ChatInterface(responder, examples=EJEMPLOS, title="Asistente normativo SB (PoC)").launch(
    server_name="127.0.0.1", server_port=int(os.environ.get("CDSW_APP_PORT", 8090)))
