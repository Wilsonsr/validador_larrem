"""Implementación de los tipos cerrados de regla.

Cada evaluación produce, por registro y variable, uno de cuatro estados:
cumple, incumple, no_aplica o no_evaluable. Una regla nunca da por cumplido
lo que no pudo evaluar.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterator

from . import condiciones as cnd
from .configuracion import Regla
from .normalizacion import Celda, clave_texto, clave_valor_config, codigo, interpretar_fecha

CUMPLE, INCUMPLE, NO_APLICA, NO_EVALUABLE = "cumple", "incumple", "no_aplica", "no_evaluable"


@dataclass
class RegistroDatos:
    indice: int
    archivo: str
    hoja: str
    fila_excel: int
    valores: dict[str, Celda]
    id_registro: str  # ID_SIVIGILA o, si falta, No_Acta
    poblacion: str


@dataclass
class Contexto:
    poblacion: str
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    subredes: list[str] = field(default_factory=list)
    localidades: list[str] = field(default_factory=list)
    etapa: str = "recodificacion"
    variables_disponibles: set[str] = field(default_factory=set)
    variable_fecha: str = "Fecha_Encuesta"


@dataclass
class Resultado:
    registro: RegistroDatos | None
    variable: str
    estado: str
    observado: str = ""
    esperado: str = ""
    motivo: str = ""


def _txt(c: Celda | None) -> str:
    if c is None:
        return ""
    return c.texto if not c.vacia else "(vacío)"


def _faltantes(regla_vars: set[str], ctx: Contexto) -> list[str]:
    return sorted(v for v in regla_vars if v not in ctx.variables_disponibles)


# --------------------------------------------------------------------------- tipos

def _requerido(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    # Con `columna_vacia_no_evaluable`, una columna sin ningún dato se informa como no evaluable
    # (el proceso que la llena no se ha ejecutado) en lugar de producir un hallazgo por registro.
    vacias: set[str] = set()
    if r.parametros.get("columna_vacia_no_evaluable") and regs:
        vacias = {v for v in r.variables
                  if all(v in reg.valores and reg.valores[v].vacia for reg in regs)}
    # `alternativa`: {variable: otra_variable}. Si la otra está diligenciada, la primera puede ir vacía
    # (p. ej. Barrio vacío cuando Otro_Barrio tiene dato). Si la otra columna no existe, se exige la primera.
    alternativas: dict[str, str] = r.parametros.get("alternativa") or {}
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        for v in r.variables:
            if v in vacias:
                yield Resultado(reg, v, NO_EVALUABLE,
                                motivo=f"la columna {v} está vacía en todo el archivo: el proceso de enriquecimiento no se ha ejecutado")
                continue
            if v not in reg.valores:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
                continue
            if ok is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
                continue
            if not ok:
                yield Resultado(reg, v, NO_APLICA)
                continue
            c = reg.valores[v]
            alt = alternativas.get(v)
            if c.error_excel:
                yield Resultado(reg, v, INCUMPLE, c.texto, "valor diligenciado", "la celda contiene un error de Excel")
            elif c.vacia and alt and alt in reg.valores and not reg.valores[alt].vacia:
                yield Resultado(reg, v, CUMPLE)  # vacío permitido: la variable alternativa está diligenciada
            elif c.vacia:
                esperado = f"valor diligenciado en {v} o en {alt}" if alt else "valor diligenciado"
                yield Resultado(reg, v, INCUMPLE, "(vacío)", esperado, "campo obligatorio vacío")
            else:
                yield Resultado(reg, v, CUMPLE)


def _dominio(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    permitidos = cnd.conjunto(r.parametros["valores"])
    exacto = r.parametros.get("comparacion") == "exacta"
    exactos = {str(v).strip() for v in r.parametros["valores"]}
    esperado = ", ".join(str(v) for v in r.parametros["valores"])
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        for v in r.variables:
            c = reg.valores.get(v)
            if c is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            elif ok is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
            elif not ok:
                yield Resultado(reg, v, NO_APLICA)
            elif c.vacia or c.error_excel:
                yield Resultado(reg, v, NO_EVALUABLE, _txt(c), motivo="valor vacío o con error; se reporta en la regla de obligatoriedad")
            else:
                cod = codigo(c)
                bien = (c.texto in exactos) if exacto else (cod in permitidos)
                if bien:
                    yield Resultado(reg, v, CUMPLE)
                else:
                    yield Resultado(reg, v, INCUMPLE, c.texto, esperado, "valor fuera de las categorías documentadas")


def _patron(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    patron = re.compile(r.parametros["patron"])
    permitidos = cnd.conjunto(r.parametros.get("permitidos", []))
    no_eval = cnd.conjunto(r.parametros.get("no_evaluables", {}).keys()) if isinstance(r.parametros.get("no_evaluables"), dict) else set()
    esperado = r.parametros.get("descripcion_esperado", f"patrón {r.parametros['patron']}")
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        for v in r.variables:
            c = reg.valores.get(v)
            if c is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            elif ok is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
            elif not ok:
                yield Resultado(reg, v, NO_APLICA)
            elif c.vacia or c.error_excel:
                yield Resultado(reg, v, NO_EVALUABLE, _txt(c), motivo="valor vacío o con error")
            elif codigo(c) in no_eval:
                motivo = r.parametros["no_evaluables"].get(c.texto) or next(iter(r.parametros["no_evaluables"].values()))
                yield Resultado(reg, v, NO_EVALUABLE, c.texto, motivo=motivo)
            elif codigo(c) in permitidos or patron.fullmatch(c.texto):
                yield Resultado(reg, v, CUMPLE)
            else:
                yield Resultado(reg, v, INCUMPLE, c.texto, esperado, "el valor no cumple el formato documentado")


def _rango(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    especiales = cnd.conjunto(p.get("especiales", []))
    mn, mx = p.get("min"), p.get("max")
    entero = p.get("entero", False)
    conflicto = {clave_valor_config(k): v for k, v in (p.get("conflicto") or {}).items()}
    esperado = f"número {'entero ' if entero else ''}entre {mn if mn is not None else '-∞'} y {mx if mx is not None else '∞'}"
    if especiales:
        esperado += f" o código {', '.join(map(str, p['especiales']))}"
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        for v in r.variables:
            c = reg.valores.get(v)
            if c is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            elif ok is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
            elif not ok:
                yield Resultado(reg, v, NO_APLICA)
            elif c.vacia or c.error_excel:
                yield Resultado(reg, v, NO_EVALUABLE, _txt(c), motivo="valor vacío o con error")
            elif codigo(c) in especiales:
                yield Resultado(reg, v, NO_APLICA)
            elif codigo(c) in conflicto:
                yield Resultado(reg, v, NO_EVALUABLE, c.texto, esperado, conflicto[codigo(c)])
            elif c.numero is None:
                yield Resultado(reg, v, INCUMPLE, c.texto, esperado, "valor no numérico")
            elif entero and not c.es_numero_entero():
                yield Resultado(reg, v, INCUMPLE, c.texto, esperado, "se esperaba un número entero")
            elif (mn is not None and c.numero < mn) or (mx is not None and c.numero > mx):
                yield Resultado(reg, v, INCUMPLE, c.texto, esperado, "valor fuera del intervalo documentado")
            else:
                yield Resultado(reg, v, CUMPLE)


def _condicional(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    cada = p.get("entonces_cada")
    conj = p.get("entonces")
    etiqueta = ", ".join(r.variables)
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if cada is not None:
            for v in r.variables:
                if v not in reg.valores:
                    yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
                    continue
                if ok is None:
                    yield Resultado(reg, v, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
                    continue
                if not ok:
                    yield Resultado(reg, v, NO_APLICA)
                    continue
                res, m2 = cnd.evaluar(cada, reg.valores, var_por_defecto=v)
                c = reg.valores[v]
                if res is None:
                    yield Resultado(reg, v, NO_EVALUABLE, _txt(c), cnd.describir({**cada, "var": v}), m2 or "")
                elif res:
                    yield Resultado(reg, v, CUMPLE)
                else:
                    yield Resultado(reg, v, INCUMPLE, _txt(c), p.get("esperado") or cnd.describir({**cada, "var": v}),
                                    p.get("explicacion", "la respuesta no corresponde a la condición del antecedente"))
        else:
            if ok is None:
                yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
                continue
            if not ok:
                yield Resultado(reg, etiqueta, NO_APLICA)
                continue
            res, m2 = cnd.evaluar(conj, reg.valores)
            obs = "; ".join(f"{v}={_txt(reg.valores.get(v))}" for v in sorted(cnd.variables_de(conj)))
            if res is None:
                yield Resultado(reg, etiqueta, NO_EVALUABLE, obs, cnd.describir(conj), m2 or "")
            elif res:
                yield Resultado(reg, etiqueta, CUMPLE)
            else:
                yield Resultado(reg, etiqueta, INCUMPLE, obs, cnd.describir(conj),
                                p.get("explicacion", "la combinación de respuestas no es coherente"))


def _al_menos_uno(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    valor = clave_valor_config(r.parametros.get("valor", 1))
    etiqueta = r.parametros.get("etiqueta", ", ".join(r.variables))
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if ok is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, etiqueta, NO_APLICA)
            continue
        faltan = [v for v in r.variables if v not in reg.valores]
        cods = [codigo(reg.valores[v]) for v in r.variables if v in reg.valores]
        if valor in cods:
            yield Resultado(reg, etiqueta, CUMPLE)
        elif faltan or any(c is None for c in cods):
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo="hay opciones ausentes o vacías" + (f": {', '.join(faltan)}" if faltan else ""))
        else:
            obs = "; ".join(f"{v}={_txt(reg.valores[v])}" for v in r.variables if v in reg.valores)
            yield Resultado(reg, etiqueta, INCUMPLE, obs, f"al menos una opción igual a {valor}",
                            r.parametros.get("explicacion", "no se registró ninguna opción afirmativa"))


def _exclusion_ninguno(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    opciones, ninguno = p["opciones"], p["ninguno"]
    si, no = clave_valor_config(p.get("si", 1)), clave_valor_config(p.get("no", 2))
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if ok is None:
            yield Resultado(reg, ninguno, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, ninguno, NO_APLICA)
            continue
        if any(v not in reg.valores for v in opciones + [ninguno]):
            yield Resultado(reg, ninguno, NO_EVALUABLE, motivo="alguna opción del grupo está ausente")
            continue
        cods = {v: codigo(reg.valores[v]) for v in opciones + [ninguno]}
        if any(c not in (si, no) for c in cods.values()):
            fuera = ", ".join(f"{v}={_txt(reg.valores[v])}" for v, c in cods.items() if c not in (si, no))
            yield Resultado(reg, ninguno, NO_EVALUABLE, fuera, motivo="hay respuestas fuera de 1/2 en el grupo")
            continue
        alguna = any(cods[v] == si for v in opciones)
        esperado = no if alguna else si
        if cods[ninguno] == esperado:
            yield Resultado(reg, ninguno, CUMPLE)
        else:
            marcadas = ", ".join(v for v in opciones if cods[v] == si) or "ninguna opción marcada"
            yield Resultado(reg, ninguno, INCUMPLE, f"{ninguno}={cods[ninguno]}; opciones afirmativas: {marcadas}",
                            f"{ninguno}={esperado}",
                            "la opción 'ninguno' contradice las respuestas afirmativas del grupo" if alguna
                            else "todas las opciones son NO y 'ninguno' no está marcado")


def _recod_mapa(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    origen, destino = p["origen"], p["destino"]
    mapa = {clave_valor_config(k): clave_valor_config(v) for k, v in p["mapa"].items()}
    conflicto = {clave_valor_config(k): v for k, v in (p.get("conflicto") or {}).items()}
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if origen not in reg.valores or destino not in reg.valores:
            yield Resultado(reg, destino, NO_EVALUABLE, motivo="columna de origen o destino ausente")
            continue
        if ok is None:
            yield Resultado(reg, destino, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, destino, NO_APLICA)
            continue
        co, cd = reg.valores[origen], reg.valores[destino]
        k = codigo(co)
        if k is None:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={_txt(co)}", motivo=f"{origen} vacío o con error")
        elif k in conflicto:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={co.texto}; {destino}={_txt(cd)}", motivo=conflicto[k])
        elif k not in mapa:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={co.texto}", motivo="categoría de origen no catalogada; ver regla de dominio")
        elif cd.vacia or cd.error_excel:
            yield Resultado(reg, destino, INCUMPLE, f"{origen}={co.texto}; {destino}=(vacío)", f"{destino}={mapa[k]}",
                            "la variable recodificada está vacía aunque la categoría fuente permite calcularla")
        elif codigo(cd) == mapa[k]:
            yield Resultado(reg, destino, CUMPLE)
        else:
            yield Resultado(reg, destino, INCUMPLE, f"{origen}={co.texto}; {destino}={cd.texto}", f"{destino}={mapa[k]}",
                            "la recodificación no corresponde a la categoría fuente")


def _recod_agrupada(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    opciones, destino = p["opciones"], p["destino"]
    si, no = clave_valor_config(p.get("si", 1)), clave_valor_config(p.get("no", 2))
    dsi, dno = clave_valor_config(p.get("destino_si", 1)), clave_valor_config(p.get("destino_no", 2))
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if destino not in reg.valores or any(v not in reg.valores for v in opciones):
            yield Resultado(reg, destino, NO_EVALUABLE, motivo="columna de origen o destino ausente")
            continue
        if ok is None:
            yield Resultado(reg, destino, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, destino, NO_APLICA)
            continue
        cods = [codigo(reg.valores[v]) for v in opciones]
        cd = reg.valores[destino]
        if si in cods:
            esperado = dsi
        elif all(c == no for c in cods):
            esperado = dno
        else:
            obs = "; ".join(f"{v}={_txt(reg.valores[v])}" for v in opciones if codigo(reg.valores[v]) not in (si, no))
            yield Resultado(reg, destino, NO_EVALUABLE, obs, motivo="opciones vacías o con códigos sin regla de agrupación (p. ej. NS/NR)")
            continue
        if codigo(cd) == esperado:
            yield Resultado(reg, destino, CUMPLE)
        else:
            marcadas = ", ".join(v for v in opciones if codigo(reg.valores[v]) == si) or "ninguna"
            yield Resultado(reg, destino, INCUMPLE, f"{destino}={_txt(cd)}; afirmativas: {marcadas}", f"{destino}={esperado}",
                            "la variable agrupada no corresponde a las opciones del grupo")


def _intervalo_de(n: float, intervalos: list[dict[str, Any]]) -> dict[str, Any] | None:
    for it in intervalos:
        if (it.get("min") is None or n >= it["min"]) and (it.get("max") is None or n <= it["max"]):
            return it
    return None


def _recod_intervalos(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    origen, destino = p["origen"], p["destino"]
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if origen not in reg.valores or destino not in reg.valores:
            yield Resultado(reg, destino, NO_EVALUABLE, motivo="columna de origen o destino ausente")
            continue
        if ok is None:
            yield Resultado(reg, destino, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, destino, NO_APLICA)
            continue
        co, cd = reg.valores[origen], reg.valores[destino]
        if co.numero is None:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={_txt(co)}", motivo=f"{origen} no es numérico")
            continue
        conf = _intervalo_de(co.numero, p.get("conflicto", []))
        if conf:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={co.texto}; {destino}={_txt(cd)}", motivo=conf["motivo"])
            continue
        it = _intervalo_de(co.numero, p["intervalos"])
        if it is None:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{origen}={co.texto}", motivo="valor fuera de los intervalos documentados")
            continue
        esperado = clave_valor_config(it["valor"])
        if codigo(cd) == esperado:
            yield Resultado(reg, destino, CUMPLE)
        else:
            yield Resultado(reg, destino, INCUMPLE, f"{origen}={co.texto}; {destino}={_txt(cd)}", f"{destino}={it['valor']}",
                            "la recodificación no corresponde al intervalo documentado")


def _recod_razon(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    num, den, destino = p["numerador"], p["denominador"], p["destino"]
    umbral = float(p["umbral"])
    si, no = clave_valor_config(p.get("si", 1)), clave_valor_config(p.get("no", 2))
    for reg in regs:
        if any(v not in reg.valores for v in (num, den, destino)):
            yield Resultado(reg, destino, NO_EVALUABLE, motivo="columna ausente")
            continue
        cn, cdn, cd = reg.valores[num], reg.valores[den], reg.valores[destino]
        if cn.numero is None or cdn.numero is None:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{num}={_txt(cn)}; {den}={_txt(cdn)}", motivo="numerador o denominador no numérico")
            continue
        if cdn.numero == 0:
            yield Resultado(reg, destino, NO_EVALUABLE, f"{num}={cn.texto}; {den}=0", motivo="denominador cero: no se puede calcular la razón")
            continue
        razon = cn.numero / cdn.numero
        esperado = si if razon >= umbral else no
        if codigo(cd) == esperado:
            yield Resultado(reg, destino, CUMPLE)
        else:
            yield Resultado(reg, destino, INCUMPLE, f"{num}={cn.texto}; {den}={cdn.texto}; razón={razon:.2f}; {destino}={_txt(cd)}",
                            f"{destino}={esperado} (umbral {umbral:g})", "la variable calculada no corresponde a la razón")


def _operando(espec: dict[str, Any], reg: RegistroDatos, especiales: set[str]) -> tuple[float | None, str, str | None]:
    if "valor" in espec:
        return float(espec["valor"]), "", None
    v = espec["var"]
    if v not in reg.valores:
        return None, "", f"columna {v} ausente"
    c = reg.valores[v]
    if c.vacia or c.error_excel:
        return None, f"{v}={_txt(c)}", f"{v} vacío o con error"
    if codigo(c) in especiales:
        return None, f"{v}={c.texto}", "especial"
    if c.numero is None:
        return None, f"{v}={c.texto}", f"{v} no numérico"
    return c.numero + float(espec.get("suma", 0)), f"{v}={c.texto}", None


def _comparacion(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    especiales = cnd.conjunto(p.get("especiales", []))
    op = cnd._OPERADORES[p["operador"]]
    iz, de = p["izquierda"], p["derecha"]
    etiqueta = iz.get("var", "")
    desc = f"{iz.get('var', iz.get('valor'))}{'+' + str(iz['suma']) if iz.get('suma') else ''} {p['operador']} " \
           f"{de.get('var', de.get('valor'))}{(' ' + ('+' if de['suma'] > 0 else '-') + ' ' + str(abs(de['suma']))) if de.get('suma') else ''}"
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if ok is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, etiqueta, NO_APLICA)
            continue
        a, ta, ma = _operando(iz, reg, especiales)
        b, tb, mb = _operando(de, reg, especiales)
        if ma == "especial" or mb == "especial":
            yield Resultado(reg, etiqueta, NO_APLICA)
        elif a is None or b is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, "; ".join(x for x in (ta, tb) if x), desc, ma or mb or "")
        elif op(a, b):
            yield Resultado(reg, etiqueta, CUMPLE)
        else:
            yield Resultado(reg, etiqueta, INCUMPLE, "; ".join(x for x in (ta, tb) if x), desc,
                            p.get("explicacion", "los valores no guardan la relación documentada"))


def _clave_grupo(c: Celda) -> str:
    return clave_texto(re.sub(r"\s+", " ", c.texto))


def _unicidad(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    ignorar = cnd.conjunto(p.get("ignorar", []))
    etiqueta = " + ".join(r.variables)
    grupos: dict[tuple, list[RegistroDatos]] = defaultdict(list)
    pendientes: list[Resultado] = []
    for reg in regs:
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if any(v not in reg.valores for v in r.variables):
            pendientes.append(Resultado(reg, etiqueta, NO_EVALUABLE, motivo="columna ausente"))
            continue
        if ok is None:
            pendientes.append(Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}"))
            continue
        if not ok:
            pendientes.append(Resultado(reg, etiqueta, NO_APLICA))
            continue
        celdas = [reg.valores[v] for v in r.variables]
        if any(c.vacia for c in celdas):
            pendientes.append(Resultado(reg, etiqueta, NO_EVALUABLE, motivo="valor vacío"))
            continue
        if any(codigo(c) in ignorar for c in celdas):
            pendientes.append(Resultado(reg, etiqueta, NO_APLICA))
            continue
        clave = tuple(_clave_grupo(c) for c in celdas)
        grupos[clave].append(reg)
    yield from pendientes
    maximo = int(p.get("maximo_por_grupo", 1))
    for clave, miembros in grupos.items():
        limite = maximo
        if p.get("excepcion_maximo") and miembros:
            exc = p["excepcion_maximo"]
            if all(cnd.evaluar(exc["si"], m.valores)[0] for m in miembros):
                limite = int(exc["maximo"])
        if p.get("entre_poblaciones"):
            excede = len({m.poblacion for m in miembros}) > 1
        else:
            excede = len(miembros) > limite
        if not excede:
            for m in miembros:
                yield Resultado(m, etiqueta, CUMPLE)
        else:
            for m in miembros:
                otras = ", ".join(f"{x.archivo} fila {x.fila_excel}" if x.archivo != m.archivo else f"fila {x.fila_excel}"
                                  for x in miembros if x is not m)
                yield Resultado(m, etiqueta, INCUMPLE, " | ".join(m.valores[v].texto for v in r.variables),
                                "valor sin repetición entre poblaciones" if p.get("entre_poblaciones") else f"máximo {limite} registro(s) por valor",
                                p.get("explicacion", "valor repetido") + f" ({len(miembros)} registros; también en: {otras})")


def _consistencia_grupo(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    p = r.parametros
    clave_v, dep = p["clave"], p["dependiente"]
    ignorar = cnd.conjunto(p.get("ignorar", []))
    grupos: dict[str, list[RegistroDatos]] = defaultdict(list)
    for reg in regs:
        if clave_v not in reg.valores or dep not in reg.valores:
            yield Resultado(reg, dep, NO_EVALUABLE, motivo="columna ausente")
            continue
        ck, cd = reg.valores[clave_v], reg.valores[dep]
        if ck.vacia or codigo(ck) in ignorar:
            yield Resultado(reg, dep, NO_APLICA)
            continue
        if cd.vacia or codigo(cd) in ignorar:
            yield Resultado(reg, dep, NO_APLICA)
            continue
        grupos[_clave_grupo(ck)].append(reg)
    for k, miembros in grupos.items():
        valores = defaultdict(list)
        for m in miembros:
            valores[_clave_grupo(m.valores[dep])].append(m)
        if len(valores) <= 1:
            for m in miembros:
                yield Resultado(m, dep, CUMPLE)
        else:
            resumen = "; ".join(f"'{v[0].valores[dep].texto}' ({len(v)})" for v in valores.values())
            # Con `marcar: minoria`, si un valor es el más frecuente (sin empate) se toma como referencia
            # y solo se marcan los registros que difieren. Con empate se marcan todos.
            orden = sorted(valores.values(), key=len, reverse=True)
            if p.get("marcar") == "minoria" and len(orden[0]) > len(orden[1]):
                ref = orden[0][0].valores[dep].texto
                for m in orden[0]:
                    yield Resultado(m, dep, CUMPLE)
                for grupo in orden[1:]:
                    for m in grupo:
                        yield Resultado(m, dep, INCUMPLE,
                                        f"{clave_v}='{m.valores[clave_v].texto}'; {dep}='{m.valores[dep].texto}'",
                                        f"'{ref}' (valor más frecuente para este {clave_v}: {len(orden[0])} registros)",
                                        f"difiere del valor más frecuente del mismo {clave_v}: {resumen}")
                continue
            for m in miembros:
                yield Resultado(m, dep, INCUMPLE, f"{clave_v}='{m.valores[clave_v].texto}'; {dep}='{m.valores[dep].texto}'",
                                f"un único valor de {dep} por {clave_v}", f"el mismo {clave_v} tiene valores distintos: {resumen}")


def _periodo(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    v = r.variables[0]
    for reg in regs:
        c = reg.valores.get(v)
        if c is None:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            continue
        if ctx.periodo_inicio is None or ctx.periodo_fin is None:
            yield Resultado(reg, v, NO_EVALUABLE, motivo="no se indicó el periodo esperado")
            continue
        f, nota = interpretar_fecha(c)
        if f is None:
            yield Resultado(reg, v, NO_EVALUABLE, _txt(c), motivo=f"fecha no interpretable: {nota}")
        elif ctx.periodo_inicio <= f <= ctx.periodo_fin:
            yield Resultado(reg, v, CUMPLE)
        else:
            yield Resultado(reg, v, INCUMPLE, f.strftime("%d/%m/%Y"),
                            f"entre {ctx.periodo_inicio:%d/%m/%Y} y {ctx.periodo_fin:%d/%m/%Y}",
                            "la fecha está fuera del periodo esperado de la entrega")


def _fecha_valida(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    minimo = r.parametros.get("min")
    for reg in regs:
        for v in r.variables:
            c = reg.valores.get(v)
            if c is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
                continue
            if c.vacia:
                yield Resultado(reg, v, NO_EVALUABLE, "(vacío)", motivo="fecha vacía; se reporta en obligatoriedad")
                continue
            f, nota = interpretar_fecha(c)
            if f is None:
                yield Resultado(reg, v, INCUMPLE, c.texto, "fecha válida dd/mm/aaaa", f"no se pudo interpretar como fecha ({nota})")
            elif minimo and f < date.fromisoformat(str(minimo)):
                yield Resultado(reg, v, INCUMPLE, f.strftime("%d/%m/%Y"), f"fecha posterior a {minimo}", "fecha implausible")
            else:
                yield Resultado(reg, v, CUMPLE)


def _ambito(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    v = r.variables[0]
    tipo = r.parametros.get("ambito", "subred")
    seleccion = ctx.subredes if tipo == "subred" else ctx.localidades
    permitidos = {clave_texto(s) for s in seleccion}
    for reg in regs:
        c = reg.valores.get(v)
        if c is None:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
        elif not permitidos:
            yield Resultado(reg, v, NO_APLICA)
        elif c.vacia:
            yield Resultado(reg, v, NO_EVALUABLE, "(vacío)", motivo="valor vacío")
        elif c.clave in permitidos:
            yield Resultado(reg, v, CUMPLE)
        else:
            yield Resultado(reg, v, INCUMPLE, c.texto, ", ".join(seleccion), "el registro está fuera del ámbito territorial indicado para esta revisión")


def _almacenado_texto(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    for reg in regs:
        for v in r.variables:
            c = reg.valores.get(v)
            if c is None:
                yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            elif c.vacia:
                yield Resultado(reg, v, NO_APLICA)
            elif isinstance(c.original, (int, float)) and not isinstance(c.original, bool):
                yield Resultado(reg, v, INCUMPLE, c.texto, "texto",
                                "identificador almacenado como número en Excel: los ceros a la izquierda o dígitos finales pudieron perderse")
            else:
                yield Resultado(reg, v, CUMPLE)


def _revision(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    solicitud = r.parametros.get("solicitud", r.accion or "verificar contra el soporte")
    etiqueta = ", ".join(r.variables)
    if "valores" in r.parametros:  # una solicitud por variable cuyo valor esté en la lista (p. ej. 99 = NS/NR)
        objetivo = cnd.conjunto(r.parametros["valores"])
        for reg in regs:
            ok, m = cnd.evaluar(r.aplica_si, reg.valores)
            for v in r.variables:
                c = reg.valores.get(v)
                if c is None:
                    yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
                elif ok is None:
                    yield Resultado(reg, v, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
                elif ok and codigo(c) in objetivo:
                    yield Resultado(reg, v, INCUMPLE, c.texto, "revisión del equipo", solicitud)
                else:
                    yield Resultado(reg, v, NO_APLICA)
        return
    for reg in regs:
        if any(v not in reg.valores for v in r.variables):
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo="columna ausente")
            continue
        ok, m = cnd.evaluar(r.aplica_si, reg.valores)
        if ok is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"condición no evaluable: {m}")
        elif ok:
            obs = "; ".join(f"{v}={_txt(reg.valores[v])}" for v in r.variables[:4])
            yield Resultado(reg, etiqueta, INCUMPLE, obs, "revisión del equipo", solicitud)
        else:
            yield Resultado(reg, etiqueta, NO_APLICA)


def _funcion(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    from .funciones import REGISTRO_FUNCIONES
    nombre = r.parametros["nombre"]
    if nombre not in REGISTRO_FUNCIONES:
        raise ValueError(f"Función no registrada: {nombre}")
    yield from REGISTRO_FUNCIONES[nombre](r, regs, ctx)


IMPLEMENTACIONES: dict[str, Callable[[Regla, list[RegistroDatos], Contexto], Iterator[Resultado]]] = {
    "requerido": _requerido, "dominio": _dominio, "patron": _patron, "rango": _rango,
    "condicional": _condicional, "al_menos_uno": _al_menos_uno, "exclusion_ninguno": _exclusion_ninguno,
    "recodificacion_mapa": _recod_mapa, "recodificacion_agrupada": _recod_agrupada,
    "recodificacion_intervalos": _recod_intervalos, "recodificacion_razon": _recod_razon,
    "comparacion": _comparacion, "unicidad": _unicidad, "consistencia_grupo": _consistencia_grupo,
    "periodo": _periodo, "fecha_valida": _fecha_valida, "ambito": _ambito,
    "almacenado_como_texto": _almacenado_texto, "revision": _revision, "funcion": _funcion,
}


def variables_requeridas(r: Regla) -> set[str]:
    """Todas las variables que la regla necesita (para determinar si es evaluable)."""
    vs = set(r.variables) | cnd.variables_de(r.aplica_si)
    p = r.parametros
    for k in ("origen", "destino", "ninguno", "numerador", "denominador", "clave", "dependiente"):
        if isinstance(p.get(k), str):
            vs.add(p[k])
    if isinstance(p.get("opciones"), list):  # en al_menos_uno / exclusion_ninguno son variables
        vs |= set(p["opciones"])
    for k in ("izquierda", "derecha"):
        if isinstance(p.get(k), dict) and "var" in p[k]:
            vs.add(p[k]["var"])
    for k in ("entonces",):
        vs |= cnd.variables_de(p.get(k))
    for k in ("args",):
        a = p.get(k) or {}
        for clave, val in a.items():
            if clave == "etiqueta":  # texto descriptivo, no es una variable
                continue
            if isinstance(val, str) and not val.startswith("="):
                vs.add(val)
            elif isinstance(val, list):
                vs |= {x for x in val if isinstance(x, str)}
    return vs
