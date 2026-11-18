"""Genera configuracion/aire/reglas/05_obligatoriedad.yaml a partir del catálogo de variables.

Una regla por población y etapa. Las variables con requerido=condicional o =no quedan fuera
(sus reglas de salto están en los archivos de cada población). Tampoco entran las variables históricas. Ejecutar de nuevo cuando cambie el catálogo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONF = RAIZ / "configuracion" / "aire"
POBLACIONES = {"menores5": ("M5", "D1"), "5a14": ("E", "D2"), "mayores60": ("A", "D3")}
# Exclusiones manuales adicionales (las variables con regla `requerido` propia se excluyen solas).
EXCLUIR: set[str] = set()
ETAPAS = {
    "captura": ("error", "Campo obligatorio vacío: completar desde el formato físico o el aplicativo de captura."),
    "recodificacion": ("error", "Variable derivada vacía: aplicar la recodificación definida en el diccionario."),
    "enriquecimiento": ("alerta", "Variable geográfica vacía: completar con el proceso de georreferenciación (requiere la capa de referencia)."),
}


def cubiertas_por_otras_reglas() -> dict[str, set[str]]:
    """Variables que ya tienen una regla `requerido` propia o son destino de una recodificación."""
    out: dict[str, set[str]] = {p: set() for p in POBLACIONES}
    for f in sorted((CONF / "reglas").glob("*.yaml")):
        if f.name.startswith("05_"):
            continue
        datos = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        defecto = datos.get("poblaciones", list(POBLACIONES))
        for r in datos.get("reglas", []):
            cubre: set[str] = set()
            if r.get("tipo") == "requerido":
                cubre = set(r.get("variables", []))
            elif str(r.get("tipo", "")).startswith("recodificacion") and isinstance((r.get("parametros") or {}).get("destino"), str):
                cubre = {r["parametros"]["destino"]}  # la regla de recodificación ya informa el destino vacío
            for p in r.get("poblaciones", defecto):
                out[p] |= cubre
    return out


def main() -> int:
    reglas = []
    cubiertas = cubiertas_por_otras_reglas()
    for pob, (pref, dic) in POBLACIONES.items():
        cat = yaml.safe_load((CONF / "variables" / f"{pob}.yaml").read_text(encoding="utf-8"))["variables"]
        for etapa, (sev, accion) in ETAPAS.items():
            vs = [v["nombre"] for v in cat if v.get("requerido") == etapa and not v.get("historica") and v["nombre"] not in EXCLUIR | cubiertas[pob]]
            if not vs:
                continue
            reglas.append({
                "id": f"{pref}_OBLIGATORIAS_{etapa.upper()}",
                "descripcion": f"Las variables de la etapa {etapa} definidas en el diccionario están diligenciadas ({len(vs)} variable{'s' if len(vs) != 1 else ''})",
                "tipo": "requerido",
                "etapa": etapa,
                "severidad": sev,
                "poblaciones": [pob],
                "variables": vs,
                **({"parametros": {"columna_vacia_no_evaluable": True}} if etapa == "enriquecimiento" else {}),
                "fuentes": [
                    {"doc": dic, "ubicacion": "columna de obligatoriedad / descripción de cada variable"},
                    {"doc": "G1", "ubicacion": "p.3", "nota": "los valores 0, 999 o espacios en blanco indican que la información no fue ingresada o digitada en su totalidad"},
                ],
                "accion": accion,
            })
    salida = CONF / "reglas" / "05_obligatoriedad.yaml"
    encabezado = "# GENERADO por herramientas/generar_obligatoriedad.py a partir de variables/*.yaml. No editar a mano.\n"
    salida.write_text(encabezado + yaml.safe_dump({"reglas": reglas}, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    print(f"{len(reglas)} reglas escritas en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
