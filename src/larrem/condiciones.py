"""Evaluación de condiciones estructuradas (sin `eval`).

Una condición devuelve True, False o None. None significa *no evaluable*: falta la
columna, el valor está vacío, tiene error de Excel o no es interpretable.
"""
from __future__ import annotations

import operator
import re
from typing import Any

from .normalizacion import Celda, clave_valor_config, codigo

Registro = dict[str, Celda]

_OPERADORES = {
    "==": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le,
    ">": operator.gt, ">=": operator.ge,
}
_CLAVES_VALIDAS = {"var", "en", "no_en", "vacio", "numero", "excepto", "cmp", "valor", "patron",
                   "contiene", "todas", "alguna", "negar"}


class ErrorCondicion(ValueError):
    pass


def variables_de(cond: dict[str, Any] | None) -> set[str]:
    if not cond:
        return set()
    out: set[str] = set()
    if "var" in cond:
        out.add(cond["var"])
    for k in ("todas", "alguna"):
        for c in cond.get(k, []):
            out |= variables_de(c)
    if "negar" in cond:
        out |= variables_de(cond["negar"])
    return out


def validar_condicion(cond: dict[str, Any]) -> None:
    if not isinstance(cond, dict):
        raise ErrorCondicion(f"La condición debe ser un diccionario: {cond!r}")
    if any(not isinstance(k, str) for k in cond):
        raise ErrorCondicion(f"Clave no textual en condición (revise 'no'/'si' sin comillas en YAML): {cond!r}")
    desconocidas = set(cond) - _CLAVES_VALIDAS
    if desconocidas:
        raise ErrorCondicion(f"Claves no permitidas en condición: {sorted(desconocidas)}")
    if "cmp" in cond and cond["cmp"] not in _OPERADORES:
        raise ErrorCondicion(f"Operador no permitido: {cond['cmp']}")
    for k in ("todas", "alguna"):
        for c in cond.get(k, []):
            validar_condicion(c)
    if "negar" in cond:
        validar_condicion(cond["negar"])


def conjunto(valores: list[Any]) -> set[str]:
    return {clave_valor_config(v) for v in valores}


def evaluar(cond: dict[str, Any] | None, reg: Registro, var_por_defecto: str | None = None) -> tuple[bool | None, str | None]:
    """Evalúa una condición. `var_por_defecto` permite condiciones sin 'var' (aplicadas a cada variable)."""
    if cond is None:
        return True, None
    if "todas" in cond:
        motivo = None
        resultado: bool | None = True
        for c in cond["todas"]:
            r, m = evaluar(c, reg, var_por_defecto)
            if r is False:
                return False, None
            if r is None:
                resultado, motivo = None, m
        return resultado, motivo
    if "alguna" in cond:
        motivo = None
        resultado = False
        for c in cond["alguna"]:
            r, m = evaluar(c, reg, var_por_defecto)
            if r is True:
                return True, None
            if r is None:
                resultado, motivo = None, m
        return resultado, motivo
    if "negar" in cond:
        r, m = evaluar(cond["negar"], reg, var_por_defecto)
        return (None, m) if r is None else (not r, None)

    var = cond.get("var", var_por_defecto)
    if var is None:
        raise ErrorCondicion(f"Condición sin variable: {cond}")
    if var not in reg:
        return None, f"columna {var} ausente o ambigua"
    c = reg[var]
    if "vacio" in cond:
        return (c.vacia == bool(cond["vacio"])), None
    if c.error_excel:
        return None, f"{var} contiene un error de Excel"
    if c.vacia:
        return None, f"{var} está vacío"
    cod = codigo(c)
    if "en" in cond:
        return cod in conjunto(cond["en"]), None
    if "no_en" in cond:
        return cod not in conjunto(cond["no_en"]), None
    if "numero" in cond:
        excepto = conjunto(cond.get("excepto", []))
        es_num = c.numero is not None and cod not in excepto
        return es_num == bool(cond["numero"]), None
    if "cmp" in cond:
        excepto = conjunto(cond.get("excepto", []))
        if cod in excepto:
            return False, None  # un código especial excluido no cumple la condición numérica
        if c.numero is None:
            return None, f"{var} no es numérico ({c.texto})"
        return bool(_OPERADORES[cond["cmp"]](c.numero, float(cond["valor"]))), None
    if "patron" in cond:
        return re.fullmatch(cond["patron"], c.texto) is not None, None
    if "contiene" in cond:
        return any(clave_valor_config(t) in c.clave for t in cond["contiene"]), None
    raise ErrorCondicion(f"Condición no reconocida: {cond}")


def describir(cond: dict[str, Any] | None) -> str:
    """Texto legible de una condición para reportes."""
    if not cond:
        return "siempre"
    if "todas" in cond:
        return " y ".join(f"({describir(c)})" for c in cond["todas"])
    if "alguna" in cond:
        return " o ".join(f"({describir(c)})" for c in cond["alguna"])
    if "negar" in cond:
        return f"no ({describir(cond['negar'])})"
    v = cond.get("var", "valor")
    if "en" in cond:
        return f"{v} ∈ {{{', '.join(map(str, cond['en']))}}}"
    if "no_en" in cond:
        return f"{v} ∉ {{{', '.join(map(str, cond['no_en']))}}}"
    if "vacio" in cond:
        return f"{v} {'vacío' if cond['vacio'] else 'diligenciado'}"
    if "numero" in cond:
        exc = f" (distinto de {', '.join(map(str, cond['excepto']))})" if cond.get("excepto") else ""
        return f"{v} {'es' if cond['numero'] else 'no es'} número{exc}"
    if "cmp" in cond:
        return f"{v} {cond['cmp']} {cond['valor']}"
    if "patron" in cond:
        return f"{v} cumple el patrón {cond['patron']}"
    if "contiene" in cond:
        return f"{v} contiene {', '.join(cond['contiene'])}"
    return str(cond)
