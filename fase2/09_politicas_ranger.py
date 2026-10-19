"""
FASE 2 - Paso 09: crea/actualiza las politicas Ranger de la PoC desde fase2/politicas_ranger/*.json.
Reemplaza los marcadores __HIVE__ y __TAG__ por los nombres de servicio del config.

  python fase2/09_politicas_ranger.py              # todas
  python fase2/09_politicas_ranger.py 03_mask_pii  # una
  python fase2/09_politicas_ranger.py fase3/c08/c08_politica_externo_temporal.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sbpoc import cfg, knox  # noqa: E402

DIR = Path(__file__).parent / "politicas_ranger"


def cargar(archivo: Path):
    c = cfg()["datalake"]
    txt = (archivo.read_text().replace("__HIVE__", c["ranger_hive_service"]).replace("__TAG__", c["ranger_tag_service"])
           .replace("__TRINO__", c.get("ranger_trino_service", "cm_trino")))
    return json.loads(txt)


def aplicar(pol, s, ranger):
    url = f"{ranger}/service/public/v2/api/service/{pol['service']}/policy/{pol['name']}"
    r = s.get(url)
    if r.status_code == 200:
        pid = r.json()["id"]
        r = s.put(f"{ranger}/service/public/v2/api/policy/{pid}", json=pol)
        accion = "actualizada"
    else:
        r = s.post(f"{ranger}/service/public/v2/api/policy", json=pol)
        accion = "creada"
    print(f"{pol['name']}: {accion} -> {r.status_code}" + ("" if r.ok else f" {r.text[:200]}"))


def main():
    s, ranger = knox("ranger")
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    if filtro.endswith(".json"):          # ruta explicita, ej. fase3/c08/c08_politica_externo_temporal.json
        aplicar(cargar(Path(filtro)), s, ranger)
        return
    for f in sorted(DIR.glob("*.json")):
        if filtro in f.stem:
            aplicar(cargar(f), s, ranger)


if __name__ == "__main__":
    main()
