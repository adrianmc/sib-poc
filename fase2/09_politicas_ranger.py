"""
FASE 2 - Paso 09: crea/actualiza ROLES y POLITICAS de Ranger para la PoC.

Por que roles de Ranger y no grupos: en el ambiente demo los grupos se sincronizan desde Keycloak en cada
inicio de sesion y los grupos asignados en CDP se borran. Los roles de Ranger son objetos propios de Ranger:
la sincronizacion del IdP no los toca. Las politicas (acceso, masking, filtro de filas, tags) se asignan a roles.

1. Crea/actualiza los roles con sus miembros, tomados de config.yaml (seccion usuarios) + datalake.ranger_admins_extra.
2. Carga los JSON de fase2/politicas_ranger/ y convierte "groups" -> "roles" para los nombres de ROLES.
   El grupo "public" (todos los usuarios) se mantiene como grupo.

  python fase2/09_politicas_ranger.py              # roles + todas las politicas
  python fase2/09_politicas_ranger.py roles        # solo roles
  python fase2/09_politicas_ranger.py 03_mask_pii  # una politica
  python fase2/09_politicas_ranger.py fase3/c08/c08_politica_externo_temporal.json
"""
import json
import sys
from pathlib import Path

# En Jobs de Cloudera AI (editor Workbench) el script corre en un kernel sin __file__: se usa la raiz del proyecto
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
except NameError:
    sys.path.insert(0, "/home/cdsw")
from lib.sbpoc import RAIZ, cfg, knox  # noqa: E402

DIR = RAIZ / "fase2" / "politicas_ranger"

# rol de Ranger -> claves de config.yaml (seccion usuarios) que son miembros
ROLES = {
    "sb_admin": ["admin"],
    "sb_ingeniero": ["ingeniero"],
    "sb_cientifico": ["cientifico", "cientifico2"],
    "sb_analista": ["analista", "analista2"],
    "sb_auditor": ["auditor"],
    "sb_mcp": ["mcp_restringido"],
    "attr_region_central": ["analista"],
    "attr_region_norte": ["analista2"],
    "attr_acceso_confidencial": ["analista2"],
}
LISTAS = ["policyItems", "denyPolicyItems", "allowExceptions", "denyExceptions",
          "dataMaskPolicyItems", "rowFilterPolicyItems"]


def miembros_por_rol():
    c = cfg()
    usuarios = c["usuarios"]
    resultado = {}
    for rol, claves in ROLES.items():
        nombres = [usuarios[k]["user"] for k in claves if k in usuarios]
        if rol == "sb_admin":
            nombres += c["datalake"].get("ranger_admins_extra", []) or []
        resultado[rol] = sorted(set(nombres))
    return resultado


def buscar_rol(s, base, rol):
    """Devuelve el id del rol si existe. Prueba por nombre y, si la version no lo soporta, lista todos."""
    r = s.get(f"{base}/name/{rol}")
    if r.status_code == 200:
        return r.json()["id"]
    r = s.get(base)
    if r.ok:
        for x in r.json():
            if x.get("name") == rol:
                return x["id"]
    return None


def crear_roles(s, ranger):
    base = f"{ranger}/service/public/v2/api/roles"
    for rol, usuarios in miembros_por_rol().items():
        cuerpo = {"name": rol, "description": "PoC SIB (rol de Ranger, independiente del IdP)",
                  "users": [{"name": u, "isAdmin": False} for u in usuarios], "groups": [], "roles": []}
        rid = buscar_rol(s, base, rol)
        if rid:
            r = s.put(f"{base}/{rid}", json=cuerpo)
            accion = "actualizado"
        else:
            r = s.post(base, params={"createNonExistUserGroup": "true"}, json=cuerpo)
            accion = "creado"
        print(f"Rol {rol} {usuarios}: {accion} -> {r.status_code}" + ("" if r.ok else f" {r.text[:200]}"))


def a_roles(pol):
    """En cada item de la politica, mueve a 'roles' los nombres que son roles de la PoC."""
    for lista in LISTAS:
        for item in pol.get(lista, []):
            grupos = item.get("groups", [])
            roles = [g for g in grupos if g in ROLES]
            if roles:
                item["roles"] = sorted(set(item.get("roles", []) + roles))
                item["groups"] = [g for g in grupos if g not in ROLES]
    return pol


def cargar(archivo: Path):
    c = cfg()["datalake"]
    txt = (archivo.read_text().replace("__HIVE__", c["ranger_hive_service"]).replace("__TAG__", c["ranger_tag_service"])
           .replace("__TRINO__", c.get("ranger_trino_service", "cm_trino")))
    return a_roles(json.loads(txt))


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
    if filtro in ("", "roles"):
        crear_roles(s, ranger)
        if filtro == "roles":
            return
    for f in sorted(DIR.glob("*.json")):
        if filtro in f.stem:
            aplicar(cargar(f), s, ranger)


if __name__ == "__main__":
    main()
