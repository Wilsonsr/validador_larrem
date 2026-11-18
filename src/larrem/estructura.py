"""Reconocimiento de población, correspondencia de columnas y cambios de estructura."""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .configuracion import Poblacion, Tematica
from .lectura import HojaLeida
from .normalizacion import clave_nombre_columna


@dataclass
class DeteccionPoblacion:
    codigo: str | None
    confianza: str  # alta | media | baja
    puntajes: dict[str, float]
    explicacion: list[str]
    hoja: str | None = None


@dataclass
class Correspondencia:
    variable: str
    indice: int
    encabezado_original: str
    metodo: str  # exacta | equivalencia_explicita | normalizada


@dataclass
class Estructura:
    poblacion: str
    archivo: str
    hoja: str
    correspondencias: dict[str, Correspondencia]
    columnas_nuevas: list[tuple[int, str]]
    columnas_ausentes: list[str]
    ausentes_requeridas: list[str]
    encabezados_duplicados: list[str]
    variables_ambiguas: dict[str, list[str]]
    columnas_vacias: list[str] = field(default_factory=list)
    huella_encontrada: str = ""
    huella_esperada: str | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def variables_disponibles(self) -> set[str]:
        return set(self.correspondencias) - set(self.variables_ambiguas)


def huella_columnas(nombres: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(nombres)).encode()).hexdigest()[:16]


def _claves_variable(p: Poblacion) -> dict[str, set[str]]:
    return {v.nombre: {clave_nombre_columna(v.nombre), *(clave_nombre_columna(e) for e in v.equivalencias)} for v in p.variables}


def detectar_poblacion(tem: Tematica, hoja: HojaLeida) -> DeteccionPoblacion:
    claves_enc = {clave_nombre_columna(h) for h in hoja.encabezados if h}
    idx_acta = None
    puntajes: dict[str, float] = {}
    explicacion: list[str] = []
    for p in tem.poblaciones:
        cv = _claves_variable(p)
        dist = p.firma.columnas_distintivas
        presentes = sum(1 for c in dist if cv.get(c, {clave_nombre_columna(c)}) & claves_enc)
        frac_cols = presentes / len(dist) if dist else 0.0
        # proporción de actas con el prefijo del formato
        if idx_acta is None:
            for i, h in enumerate(hoja.encabezados):
                if clave_nombre_columna(h) == clave_nombre_columna(p.variable_acta):
                    idx_acta = i
                    break
        frac_acta = 0.0
        if idx_acta is not None and hoja.filas:
            vals = [str(f[idx_acta]).strip().upper() for _, f in hoja.filas if f[idx_acta] is not None]
            if vals:
                frac_acta = sum(1 for v in vals if v.startswith(p.firma.prefijo_acta)) / len(vals)
        frac_nombre = 0.0
        if p.firma.patron_nombre_archivo and re.search(p.firma.patron_nombre_archivo, hoja.archivo, re.I):
            frac_nombre = 1.0
        puntajes[p.codigo] = round(0.6 * frac_cols + 0.35 * frac_acta + 0.05 * frac_nombre, 3)
        explicacion.append(
            f"{p.nombre}: {presentes}/{len(dist)} columnas distintivas, "
            f"{frac_acta:.0%} de actas con prefijo {p.firma.prefijo_acta}"
            + (", nombre de archivo coincide" if frac_nombre else ""))
    orden = sorted(puntajes.items(), key=lambda x: -x[1])
    mejor, p1 = orden[0]
    p2 = orden[1][1] if len(orden) > 1 else 0.0
    if p1 >= 0.85 and p1 - p2 >= 0.4:
        conf = "alta"
    elif p1 >= 0.6 and p1 - p2 >= 0.25:
        conf = "media"
    else:
        conf = "baja"
    return DeteccionPoblacion(codigo=mejor if conf != "baja" else None, confianza=conf,
                              puntajes=puntajes, explicacion=explicacion, hoja=hoja.hoja)


def elegir_hoja(tem: Tematica, hojas: list[HojaLeida]) -> tuple[HojaLeida | None, list[DeteccionPoblacion]]:
    """Elige la hoja con mejor reconocimiento de población."""
    detecciones = [detectar_poblacion(tem, h) for h in hojas]
    if not hojas:
        return None, detecciones
    i = max(range(len(hojas)), key=lambda k: (max(detecciones[k].puntajes.values()), len(hojas[k].filas)))
    return hojas[i], detecciones


def mapear_columnas(p: Poblacion, hoja: HojaLeida) -> Estructura:
    exactas = {v.nombre: v.nombre for v in p.variables}
    explicitas = {e: v.nombre for v in p.variables for e in v.equivalencias}
    por_clave: dict[str, set[str]] = defaultdict(set)
    for v in p.variables:
        por_clave[clave_nombre_columna(v.nombre)].add(v.nombre)
        for e in v.equivalencias:
            por_clave[clave_nombre_columna(e)].add(v.nombre)

    corr: dict[str, Correspondencia] = {}
    nuevas: list[tuple[int, str]] = []
    ambiguas: dict[str, list[str]] = {}
    conteo_enc = Counter(h for h in hoja.encabezados if h)
    duplicados = sorted(h for h, n in conteo_enc.items() if n > 1)
    avisos: list[str] = []
    candidatos_por_var: dict[str, list[Correspondencia]] = defaultdict(list)
    for i, h in enumerate(hoja.encabezados):
        if not h:
            if any(f[i] is not None for _, f in hoja.filas):
                nuevas.append((i, f"(columna {i + 1} sin encabezado)"))
            continue
        if h in exactas:
            candidatos_por_var[h].append(Correspondencia(h, i, h, "exacta"))
        elif h in explicitas:
            candidatos_por_var[explicitas[h]].append(Correspondencia(explicitas[h], i, h, "equivalencia_explicita"))
        else:
            cands = por_clave.get(clave_nombre_columna(h), set())
            if len(cands) == 1:
                v = next(iter(cands))
                candidatos_por_var[v].append(Correspondencia(v, i, h, "normalizada"))
            elif len(cands) > 1:
                for v in cands:
                    ambiguas.setdefault(v, []).append(h)
                avisos.append(f"El encabezado '{h}' coincide con varias variables ({', '.join(sorted(cands))}); no se asignó.")
            else:
                nuevas.append((i, h))
    for v, cs in candidatos_por_var.items():
        if len(cs) == 1:
            corr[v] = cs[0]
        else:
            corr[v] = cs[0]
            ambiguas[v] = [c.encabezado_original + f" (columna {c.indice + 1})" for c in cs]
            avisos.append(f"La variable {v} aparece en {len(cs)} columnas; las reglas que la usan quedan no evaluables.")
    opcionales = {v.nombre for v in p.variables if v.opcional}
    ausentes = [v.nombre for v in p.variables if v.nombre not in corr and not v.opcional]
    requeridas = [v for v in ausentes if (p.variable(v) and p.variable(v).requerido == "captura" and not p.variable(v).historica)]
    vacias = []
    for v, c in corr.items():
        if all(f[c.indice] is None or (isinstance(f[c.indice], str) and not f[c.indice].strip()) for _, f in hoja.filas):
            vacias.append(v)
    est = Estructura(
        poblacion=p.codigo, archivo=hoja.archivo, hoja=hoja.hoja, correspondencias=corr,
        columnas_nuevas=nuevas, columnas_ausentes=ausentes, ausentes_requeridas=requeridas,
        encabezados_duplicados=duplicados, variables_ambiguas=ambiguas, columnas_vacias=vacias,
        huella_encontrada=huella_columnas([v for v in corr if v not in opcionales]), huella_esperada=p.huella_instrumento, avisos=avisos,
    )
    if est.huella_esperada and est.huella_encontrada != est.huella_esperada:
        est.avisos.append("La estructura del archivo difiere de la versión del instrumento configurada.")
    return est
