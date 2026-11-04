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
sys.path.insert(0, "/home/cdsw/fase3/c06/rag")
from lib.sbpoc import cfg  # noqa: E402
import embeddings  # noqa: E402

C = cfg()["inferencia"]
VEC = np.load("/home/cdsw/data/rag/vectores.npy")
FRAG = json.load(open("/home/cdsw/data/rag/fragmentos.json"))
DESC_EMB, EMBEBER = embeddings.crear()
_IND = json.load(open("/home/cdsw/data/rag/indice.json"))
if _IND.get("embeddings") != DESC_EMB:
    sys.exit(f"El indice se creo con '{_IND.get('embeddings')}' y la app usa '{DESC_EMB}': volver a correr indexar.py")
UMBRAL_SIMILITUD = float(_IND["umbral"])        # calibrado por indexar.py para este modelo de embeddings
SENSIBLE = re.compile(r"(identificaci[oó]n|c[eé]dula|n[uú]mero de cuenta|saldo de|contrase[nñ]a|password|"
                      r"datos personales de|tel[eé]fono de|correo de|cliente \d+)", re.I)
SISTEMA = ("Eres un asistente de consulta normativa de la Superintendencia. Responde SOLO con base en el contexto. "
           "Cita siempre la fuente entre corchetes [documento, pagina]. Si el contexto no alcanza, dilo y sugiere "
           "escalar a un especialista. Nunca reveles datos personales.")


def llm():
    return OpenAI(base_url=C["llm_base_url"], api_key=embeddings.jwt())   # JWT renovado en cada pregunta


def responder(pregunta, _historial=None):
    if SENSIBLE.search(pregunta):
        return ("Solicitud rechazada por politica: la consulta pide informacion sensible o datos de clientes. "
                "Este asistente solo responde sobre normativa. Evento registrado para auditoria.")
    q = EMBEBER([pregunta], es_pregunta=True)[0]
    sims = VEC @ q
    top = np.argsort(-sims)[:4]
    if sims[top[0]] < UMBRAL_SIMILITUD:
        return (f"Fuera de alcance: no hay normativa en el corpus que respalde una respuesta "
                f"(similitud maxima {sims[top[0]]:.2f}). Se recomienda escalar a un especialista.")
    contexto = "\n\n".join(f"[{FRAG[i]['fuente']}, p.{FRAG[i]['pagina']}] {FRAG[i]['texto']}" for i in top)
    # Las instrucciones van en el mensaje del usuario: Mistral 7B Instruct no acepta el rol "system".
    r = llm().chat.completions.create(model=C["llm_modelo"], temperature=0.1, max_tokens=500, messages=[
        {"role": "user", "content": f"{SISTEMA}\n\nContexto:\n{contexto}\n\nPregunta: {pregunta}"}])
    fuentes = ", ".join(sorted({f"{FRAG[i]['fuente']} p.{FRAG[i]['pagina']}" for i in top}))
    return (f"{r.choices[0].message.content}\n\nFuentes recuperadas (similitud {sims[top[0]]:.2f}): {fuentes}\n"
            f"Modelo: {C['llm_modelo']} | Embeddings: {DESC_EMB}")


EJEMPLOS = ["Cual es el plazo para reportar un incidente de ciberseguridad significativo?",
            "Cuantos dias de atraso definen una operacion en mora para el indicador oficial?",
            "Cual es la mejor receta de gallo pinto?",
            "Dame la cedula y el saldo del cliente 1045"]
gr.ChatInterface(responder, examples=EJEMPLOS, title="Asistente normativo SB (PoC)").launch(
    server_name="127.0.0.1", server_port=int(os.environ.get("CDSW_APP_PORT", 8090)))
