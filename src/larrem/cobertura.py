"""Matriz de cobertura: qué variables tienen reglas, en qué estado y cuáles no tienen ninguna.

La cobertura es documental (depende de la configuración, no de los datos), pero puede
enriquecerse con una ejecución para indicar si la columna estaba presente y vacía.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .configuracion import ESTADOS_EJECUTABLES, Regla, Tematica
from .reglas import variables_requeridas

ESTADO_COBERTURA = {
    "ejecutable": "Con regla de contenido ejecutable (dominio, salto, recodificación, cruce…)",
    "solo_obligatoriedad": "Solo se verifica que esté diligenciada",
    "solo_pendiente": "Solo con reglas pendientes (contradicción, definición incompleta o insumo)",
    "solo_como_condicion": "Solo aparece como condición de otras reglas",
    "sin_regla": "Sin regla: revisar si requiere validación o documentar por qué no",
}


@dataclass
class FilaCobertura:
    poblacion: str
    variable: str
    etiqueta: str
    tipo: str
    requerido: str
    personal: bool
    historica: bool
    fuente_diccionario: str
    fuente_observacion: str
    reglas_validan: list[str] = field(default_factory=list)       # la variable es objeto de la regla
    reglas_condicion: list[str] = field(default_factory=list)     # la variable solo participa como condición
    reglas_pendientes: list[str] = field(default_factory=list)
    tipos_regla: list[str] = field(default_factory=list)
    estado: str = "sin_regla"
    columna_presente: bool | None = None
    columna_vacia: bool | None = None

    def como_dict(self) -> dict:
        return {
            "Población": self.poblacion, "Variable": self.variable, "Etiqueta": self.etiqueta,
            "Tipo": self.tipo, "Obligatoriedad": self.requerido,
            "Dato personal": "sí" if self.personal else "", "Histórica": "sí" if self.historica else "",
            "Fuente diccionario": self.fuente_diccionario, "Fuente observaciones": self.fuente_observacion,
            "Estado de cobertura": ESTADO_COBERTURA[self.estado],
            "Reglas que la validan": ", ".join(self.reglas_validan),
            "Tipos de regla": ", ".join(sorted(set(self.tipos_regla))),
            "Reglas en que es condición": ", ".join(self.reglas_condicion),
            "Reglas pendientes": ", ".join(self.reglas_pendientes),
            "Columna en el archivo": "" if self.columna_presente is None else ("sí" if self.columna_presente else "no"),
            "Columna vacía": "" if self.columna_vacia is None else ("sí" if self.columna_vacia else ""),
        }


def _objetivo(r: Regla) -> set[str]:
    """Variables que la regla valida (no las que solo usa como condición)."""
    vs = set(r.variables)
    p = r.parametros
    if isinstance(p.get("alternativa"), dict):
        vs |= set(p["alternativa"].values())
    if isinstance(p.get("destino"), str):
        vs.add(p["destino"])
    if r.tipo in ("al_menos_uno", "exclusion_ninguno"):
        vs |= set(p.get("opciones", []))
        if isinstance(p.get("ninguno"), str):
            vs.add(p["ninguno"])
    if r.tipo == "comparacion" and isinstance(p.get("izquierda"), dict) and "var" in p["izquierda"]:
        vs.add(p["izquierda"]["var"])
    return vs


def matriz_cobertura(tem: Tematica, ejecucion=None) -> list[FilaCobertura]:
    presentes: dict[str, set[str]] = defaultdict(set)
    vacias: dict[str, set[str]] = defaultdict(set)
    poblaciones_ejecutadas: set[str] = set()
    if ejecucion is not None:
        for a in ejecucion.archivos:
            poblaciones_ejecutadas.add(a.poblacion)
            presentes[a.poblacion] |= a.estructura.variables_disponibles
            vacias[a.poblacion] |= set(a.estructura.columnas_vacias)

    filas: list[FilaCobertura] = []
    for p in tem.poblaciones:
        reglas = [r for r in tem.reglas if p.codigo in r.poblaciones]
        objetivo = {r.id: _objetivo(r) for r in reglas}
        todas = {r.id: variables_requeridas(r) for r in reglas}
        for v in p.variables:
            f = FilaCobertura(
                poblacion=p.codigo, variable=v.nombre, etiqueta=v.etiqueta or "", tipo=v.tipo,
                requerido=v.requerido, personal=v.personal, historica=v.historica,
                fuente_diccionario=v.fuente_diccionario or "", fuente_observacion=v.fuente_observacion or "",
            )
            for r in reglas:
                if v.nombre in objetivo[r.id]:
                    if r.estado in ESTADOS_EJECUTABLES:
                        f.reglas_validan.append(r.id)
                        f.tipos_regla.append(r.tipo)
                    else:
                        f.reglas_pendientes.append(r.id)
                elif v.nombre in todas[r.id]:
                    f.reglas_condicion.append(r.id)
            if set(f.tipos_regla) - {"requerido"}:
                f.estado = "ejecutable"
            elif f.reglas_validan:
                f.estado = "solo_obligatoriedad"
            elif f.reglas_pendientes:
                f.estado = "solo_pendiente"
            elif f.reglas_condicion:
                f.estado = "solo_como_condicion"
            if p.codigo in poblaciones_ejecutadas:
                f.columna_presente = v.nombre in presentes[p.codigo]
                f.columna_vacia = v.nombre in vacias[p.codigo]
            filas.append(f)
    return filas


def resumen_cobertura(filas: list[FilaCobertura]) -> list[dict]:
    """Conteo por población y estado de cobertura."""
    conteo: dict[tuple[str, str], int] = defaultdict(int)
    for f in filas:
        conteo[(f.poblacion, f.estado)] += 1
    pobs = sorted({f.poblacion for f in filas}, key=lambda x: [f.poblacion for f in filas].index(x))
    out = []
    for p in pobs:
        fila = {"Población": p, "Variables": sum(v for (pp, _), v in conteo.items() if pp == p)}
        for e, txt in ESTADO_COBERTURA.items():
            fila[txt] = conteo.get((p, e), 0)
        out.append(fila)
    return out


def variables_desconocidas(tem: Tematica) -> list[tuple[str, str, str]]:
    """Variables citadas por reglas que no están en el catálogo de su población (error de configuración)."""
    out = []
    for r in tem.reglas:
        for pc in r.poblaciones:
            nombres = {v.nombre for v in tem.poblacion(pc).variables}
            for v in sorted(variables_requeridas(r) - nombres):
                out.append((r.id, pc, v))
    return out
