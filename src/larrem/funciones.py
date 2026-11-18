"""Funciones de validación registradas.

Son la única vía para reglas que no caben en los tipos genéricos. Se invocan por
nombre desde la configuración (`tipo: funcion`, `parametros.nombre`) y sus
argumentos son nombres de variables. No hay evaluación de texto libre.
"""
from __future__ import annotations

from datetime import date
from typing import Iterator

from . import condiciones as cnd
from .configuracion import Regla
from .normalizacion import clave_texto, clave_valor_config, codigo, interpretar_fecha
from .reglas import CUMPLE, INCUMPLE, NO_APLICA, NO_EVALUABLE, Contexto, RegistroDatos, Resultado


def edad_meses(nac: date, ref: date) -> int:
    m = (ref.year - nac.year) * 12 + (ref.month - nac.month)
    if ref.day < nac.day:
        m -= 1
    return m


def edad_anios(nac: date, ref: date) -> int:
    return ref.year - nac.year - ((ref.month, ref.day) < (nac.month, nac.day))


def _fechas(reg: RegistroDatos, a: str, b: str) -> tuple[date | None, date | None, str | None]:
    if a not in reg.valores or b not in reg.valores:
        return None, None, "columna de fecha ausente"
    fa, na = interpretar_fecha(reg.valores[a])
    fb, nb = interpretar_fecha(reg.valores[b])
    if fa is None:
        return None, None, f"{a} no interpretable ({na})"
    if fb is None:
        return None, None, f"{b} no interpretable ({nb})"
    return fa, fb, None


def _aplica(r: Regla, reg: RegistroDatos) -> tuple[bool | None, str | None]:
    return cnd.evaluar(r.aplica_si, reg.valores)


def edad_calculada(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    a = r.parametros["args"]
    unidad = r.parametros.get("opciones", {}).get("unidad", "anios")
    for reg in regs:
        nac, enc, err = _fechas(reg, a["nacimiento"], a["encuesta"])
        v = a["edad"]
        if v not in reg.valores:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=f"columna {v} ausente")
            continue
        if err:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=err)
            continue
        if nac > enc:
            yield Resultado(reg, v, NO_EVALUABLE, motivo="fecha de nacimiento posterior a la encuesta; ver regla de orden de fechas")
            continue
        calc = edad_meses(nac, enc) if unidad == "meses" else edad_anios(nac, enc)
        c = reg.valores[v]
        if c.numero is None:
            yield Resultado(reg, v, INCUMPLE, c.texto or "(vacío)", f"{calc} {unidad}", "edad declarada no numérica")
        elif int(c.numero) == calc:
            yield Resultado(reg, v, CUMPLE)
        else:
            yield Resultado(reg, v, INCUMPLE, f"{c.texto} (nac. {nac:%d/%m/%Y}; encuesta {enc:%d/%m/%Y})",
                            f"{calc} {'meses' if unidad == 'meses' else 'años'} cumplidos a la fecha de encuesta",
                            "la edad registrada difiere de la calculada; verificar fecha de nacimiento, fecha de encuesta y edad contra el soporte")


def edad_poblacion(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    a = r.parametros["args"]
    op = r.parametros.get("opciones", {})
    unidad, mn, mx = op.get("unidad", "anios"), op.get("min"), op.get("max")
    etiqueta = a.get("etiqueta", a["nacimiento"])
    for reg in regs:
        nac, enc, err = _fechas(reg, a["nacimiento"], a["encuesta"])
        if err:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=err)
            continue
        calc = edad_meses(nac, enc) if unidad == "meses" else edad_anios(nac, enc)
        u = "meses" if unidad == "meses" else "años"
        if (mn is not None and calc < mn) or (mx is not None and calc > mx):
            yield Resultado(reg, etiqueta, INCUMPLE, f"{calc} {u} a la fecha de encuesta",
                            f"entre {mn if mn is not None else ''} y {mx if mx is not None else 'más'} {u}",
                            "la persona no pertenece al grupo de edad de esta base (criterio de inclusión)")
        else:
            yield Resultado(reg, etiqueta, CUMPLE)


def orden_fechas(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    a = r.parametros["args"]
    for reg in regs:
        f1, f2, err = _fechas(reg, a["anterior"], a["posterior"])
        if err:
            yield Resultado(reg, a["anterior"], NO_EVALUABLE, motivo=err)
        elif f1 <= f2:
            yield Resultado(reg, a["anterior"], CUMPLE)
        else:
            yield Resultado(reg, a["anterior"], INCUMPLE, f"{f1:%d/%m/%Y} > {f2:%d/%m/%Y}",
                            f"{a['anterior']} ≤ {a['posterior']}", "la fecha de nacimiento es posterior a la fecha de encuesta")


def acta_subred(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    a = r.parametros["args"]
    siglas = {clave_texto(k): v for k, v in r.parametros["opciones"]["siglas"].items()}
    pos = int(r.parametros["opciones"].get("posicion", 4))
    for reg in regs:
        ca, cs = reg.valores.get(a["acta"]), reg.valores.get(a["subred"])
        if ca is None or cs is None:
            yield Resultado(reg, a["acta"], NO_EVALUABLE, motivo="columna ausente")
            continue
        if ca.vacia or cs.vacia or len(ca.texto) <= pos:
            yield Resultado(reg, a["acta"], NO_EVALUABLE, motivo="acta o subred vacía o incompleta")
            continue
        esperado = siglas.get(cs.clave)
        if esperado is None:
            yield Resultado(reg, a["acta"], NO_EVALUABLE, cs.texto, motivo="subred no reconocida en el catálogo de siglas")
            continue
        letra = ca.texto[pos].upper()
        if letra == esperado:
            yield Resultado(reg, a["acta"], CUMPLE)
        else:
            yield Resultado(reg, a["acta"], INCUMPLE, f"{ca.texto} (sigla {letra}); Subred={cs.texto}",
                            f"sigla {esperado}", "la sigla de subred del acta no corresponde a la subred registrada")


def lactancia_justificacion(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    """Justificación de lactancia según instructivo (P26/P27):
    - NO lactancia exclusiva: debe registrarse la razón.
    - SI y 6 meses: no se justifica (9999).
    - SI y menos de 6 meses, igual al tiempo de vida: no se justifica.
    - SI y menos o más de 6 meses en otro caso: debe justificarse.
    """
    a = r.parametros["args"]
    sin_just = cnd.conjunto(r.parametros.get("opciones", {}).get("codigos_sin_justificacion", [9999, 999, "SIN DATO"]))
    v = a["justificacion"]
    for reg in regs:
        if any(x not in reg.valores for x in (a["lactancia"], a["tiempo"], v)):
            yield Resultado(reg, v, NO_EVALUABLE, motivo="columna ausente")
            continue
        cl, ct, cj = reg.valores[a["lactancia"]], reg.valores[a["tiempo"]], reg.valores[v]
        lact = codigo(cl)
        tiene_just = not cj.vacia and codigo(cj) not in sin_just
        if lact == "2":
            if tiene_just:
                yield Resultado(reg, v, CUMPLE)
            else:
                yield Resultado(reg, v, INCUMPLE, f"{a['lactancia']}=2; {v}={cj.texto or '(vacío)'}", "razón por la que no recibió lactancia exclusiva",
                                "no recibió lactancia materna exclusiva y no se registró la justificación")
            continue
        if lact != "1":
            yield Resultado(reg, v, NO_APLICA if lact == "99" else NO_EVALUABLE, motivo="" if lact == "99" else "respuesta de lactancia vacía o no reconocida")
            continue
        if ct.numero is None or codigo(ct) in {"999", "9999"}:
            yield Resultado(reg, v, NO_EVALUABLE, f"{a['tiempo']}={ct.texto}", motivo="tiempo de lactancia no numérico")
            continue
        t = ct.numero
        nac, enc, err = _fechas(reg, a["nacimiento"], a["encuesta"]) if "nacimiento" in a else (None, None, "sin fechas")
        edad_m = edad_meses(nac, enc) if not err else None
        if t == 6:
            requerida = False
        elif t < 6 and edad_m is not None and t >= edad_m:
            requerida = False
        elif t < 6 and edad_m is None:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=f"no se pudo calcular la edad en meses ({err})")
            continue
        else:
            requerida = True
        if requerida and not tiene_just:
            yield Resultado(reg, v, INCUMPLE, f"{a['tiempo']}={ct.texto}; edad={edad_m} meses; {v}={cj.texto or '(vacío)'}",
                            "justificación del tiempo de lactancia distinto de 6 meses",
                            "la duración de la lactancia exclusiva requiere justificación y no se registró")
        elif not requerida and tiene_just:
            yield Resultado(reg, v, INCUMPLE, f"{a['tiempo']}={ct.texto}; edad={edad_m} meses; {v}='{cj.texto}'",
                            "9999 (no requiere justificación)",
                            "se registró justificación cuando el instructivo indica cerrar el espacio (9999); verificar")
        else:
            yield Resultado(reg, v, CUMPLE)


def meses_hasta_edad(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    """Una duración en meses no puede superar la edad en meses calculada desde las fechas."""
    a = r.parametros["args"]
    especiales = cnd.conjunto(r.parametros.get("opciones", {}).get("especiales", []))
    v = a["meses"]
    for reg in regs:
        ok, m = _aplica(r, reg)
        if v not in reg.valores:
            yield Resultado(reg, v, NO_EVALUABLE, motivo="columna ausente")
            continue
        if ok is None:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, v, NO_APLICA)
            continue
        c = reg.valores[v]
        if codigo(c) in especiales:
            yield Resultado(reg, v, NO_APLICA)
            continue
        if c.numero is None:
            yield Resultado(reg, v, NO_EVALUABLE, c.texto, motivo="valor no numérico")
            continue
        nac, enc, err = _fechas(reg, a["nacimiento"], a["encuesta"])
        if err:
            yield Resultado(reg, v, NO_EVALUABLE, motivo=err)
            continue
        em = edad_meses(nac, enc)
        if c.numero <= em:
            yield Resultado(reg, v, CUMPLE)
        else:
            yield Resultado(reg, v, INCUMPLE, f"{c.texto} meses; edad {em} meses", f"≤ {em} meses",
                            r.parametros.get("explicacion", "la duración supera la edad del menor"))


def tabaquismo_pesado(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    """Paquetes/año = cigarrillos diarios × años fumando / 20; pesado si ≥ 10 (diccionario D3).

    Procedimiento del equipo: si la frecuencia es semanal, los cigarrillos se pasan a diarios
    dividiendo entre 7; si el tiempo está en meses, se pasa a años dividiendo entre 12.
    El cálculo se hace para quien fuma (P18 = 1) o fumó alguna vez (P19 = 1); quien no fuma ni
    fumó debe tener 2. Si fumó pero faltan cigarrillos o tiempo, queda no evaluable con el motivo.
    """
    a = r.parametros["args"]
    op = r.parametros.get("opciones", {})
    umbral, divisor = float(op.get("umbral", 10)), float(op.get("divisor", 20))
    dest = a["destino"]
    for reg in regs:
        frec_var = a.get("frecuencia")
        filtros = [v for v in (a.get("fuma"), a.get("fumo")) if v]
        if any(x not in reg.valores for x in (a["cigarrillos"], a["tiempo"], a["periodo"], dest, *filtros)) or (
                frec_var and frec_var not in reg.valores):
            yield Resultado(reg, dest, NO_EVALUABLE, motivo="columna ausente")
            continue
        cc, ct, cp, cd = (reg.valores[a[k]] for k in ("cigarrillos", "tiempo", "periodo", "destino"))
        codigos = {v: codigo(reg.valores[v]) for v in filtros}
        estado_fumador = "; ".join(f"{v}={reg.valores[v].texto or '(vacío)'}" for v in filtros)
        if filtros and "1" not in codigos.values():
            if all(c == "2" for c in codigos.values()):
                esperado = "2"
                detalle = f"no fuma ni fumó ({estado_fumador})"
            else:
                yield Resultado(reg, dest, NO_EVALUABLE, estado_fumador,
                                motivo="no se sabe si fuma o fumó (respuesta distinta de 1 o 2)")
                continue
        elif not filtros and codigo(cc) == "999" and codigo(ct) == "999":
            esperado = "2"
            detalle = "no fuma ni fumó (cigarrillos y tiempo 999)"
        elif cc.numero is None or ct.numero is None or codigo(cc) == "999" or codigo(ct) == "999":
            yield Resultado(reg, dest, NO_EVALUABLE,
                            f"{estado_fumador + '; ' if filtros else ''}{a['cigarrillos']}={cc.texto}; {a['tiempo']}={ct.texto}",
                            motivo="fuma o fumó, pero faltan cigarrillos o tiempo para calcular el índice"
                            if filtros else "cigarrillos o tiempo no disponibles para calcular paquetes/año")
            continue
        else:
            periodo = clave_texto(cp.texto)
            if periodo.startswith("ANO"):
                anios = ct.numero
            elif periodo.startswith("MES"):
                anios = ct.numero / 12
            else:
                yield Resultado(reg, dest, NO_EVALUABLE, f"{a['periodo']}={cp.texto}", motivo="periodo de tiempo fumando no reconocido")
                continue
            diarios, unidad = cc.numero, "cig/día"
            if frec_var:
                frec = clave_texto(reg.valores[frec_var].texto)
                if frec.startswith("SEMAN"):
                    diarios, unidad = cc.numero / 7, f"cig/semana ÷ 7 = {cc.numero / 7:.2f} cig/día"
                elif not frec.startswith("DIAR"):
                    yield Resultado(reg, dest, NO_EVALUABLE, f"{frec_var}={reg.valores[frec_var].texto}",
                                    motivo="frecuencia de consumo no reconocida (se espera Diario o Semanal)")
                    continue
            pa = diarios * anios / divisor
            esperado = "1" if pa >= umbral else "2"
            detalle = f"{cc.texto} {unidad} × {anios:g} años / {divisor:g} = {pa:.1f} paquetes/año"
        if codigo(cd) == esperado:
            yield Resultado(reg, dest, CUMPLE)
        else:
            yield Resultado(reg, dest, INCUMPLE, f"{detalle}; {dest}={cd.texto or '(vacío)'}", f"{dest}={esperado}",
                            "la clasificación de tabaquismo pesado no corresponde al cálculo de paquetes/año")


def suma_edad_tabaco(r: Regla, regs: list[RegistroDatos], ctx: Contexto) -> Iterator[Resultado]:
    """Para fumadores actuales: edad de inicio + tiempo fumando (años) = edad actual (O1 MAYOR 60 fila 86; G1 p.73-74)."""
    a = r.parametros["args"]
    etiqueta = f"{a['inicio']}, {a['tiempo']}"
    for reg in regs:
        ok, m = _aplica(r, reg)
        if any(x not in reg.valores for x in (a["edad"], a["inicio"], a["tiempo"], a["periodo"])):
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo="columna ausente")
            continue
        if ok is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, motivo=f"antecedente no evaluable: {m}")
            continue
        if not ok:
            yield Resultado(reg, etiqueta, NO_APLICA)
            continue
        ce, ci, ct, cp = (reg.valores[a[k]] for k in ("edad", "inicio", "tiempo", "periodo"))
        if any(c.numero is None or codigo(c) == "999" for c in (ce, ci, ct)):
            yield Resultado(reg, etiqueta, NO_EVALUABLE, f"edad={ce.texto}; inicio={ci.texto}; tiempo={ct.texto}",
                            motivo="valores no numéricos o 999")
            continue
        periodo = clave_texto(cp.texto)
        anios = ct.numero if periodo.startswith("ANO") else (0 if periodo.startswith("MES") else None)
        if anios is None:
            yield Resultado(reg, etiqueta, NO_EVALUABLE, f"periodo={cp.texto}", motivo="periodo no reconocido")
            continue
        total = ci.numero + anios
        if total == ce.numero:
            yield Resultado(reg, etiqueta, CUMPLE)
        else:
            yield Resultado(reg, etiqueta, INCUMPLE, f"inicio {ci.texto} + tiempo {ct.texto} {cp.texto} = {total:g}; edad {ce.texto}",
                            f"suma = {ce.texto}", "la edad de inicio más el tiempo fumando no coincide con la edad actual")


REGISTRO_FUNCIONES = {
    "edad_calculada": edad_calculada,
    "edad_poblacion": edad_poblacion,
    "orden_fechas": orden_fechas,
    "acta_subred": acta_subred,
    "lactancia_justificacion": lactancia_justificacion,
    "meses_hasta_edad": meses_hasta_edad,
    "tabaquismo_pesado": tabaquismo_pesado,
    "suma_edad_tabaco": suma_edad_tabaco,
}
