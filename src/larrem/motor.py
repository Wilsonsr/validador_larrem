"""Motor de validación: orquesta lectura, estructura, reglas y cruces.

Es independiente de la interfaz: la aplicación Streamlit, las pruebas y los
scripts de línea de comandos usan las mismas funciones.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import VERSION_MOTOR
from .configuracion import ESTADOS_EJECUTABLES, ORDEN_ETAPA, Regla, Tematica, cargar_tematica
from .estructura import DeteccionPoblacion, Estructura, elegir_hoja, huella_columnas, mapear_columnas
from .lectura import HojaLeida, LibroLeido, leer_libro
from .normalizacion import clave_nombre_columna, construir_celda, interpretar_fecha
from .reglas import (CUMPLE, IMPLEMENTACIONES, INCUMPLE, NO_APLICA, NO_EVALUABLE, Contexto, RegistroDatos,
                     Resultado, variables_requeridas)

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CONFIG_AIRE = RAIZ_PROYECTO / "configuracion" / "aire"


@dataclass
class Parametros:
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    subredes: list[str] = field(default_factory=list)
    localidades: list[str] = field(default_factory=list)
    etapa: str = "recodificacion"
    descripcion_ambito: str = ""

    def como_dict(self) -> dict[str, Any]:
        return {
            "periodo_inicio": self.periodo_inicio.isoformat() if self.periodo_inicio else None,
            "periodo_fin": self.periodo_fin.isoformat() if self.periodo_fin else None,
            "subredes": self.subredes, "localidades": self.localidades, "etapa": self.etapa,
            "descripcion_ambito": self.descripcion_ambito,
        }


@dataclass
class ArchivoPreparado:
    """Archivo leído con su población detectada o seleccionada."""
    libro: LibroLeido
    hoja: HojaLeida | None
    deteccion: list[DeteccionPoblacion]
    poblacion_detectada: str | None
    confianza: str
    poblacion: str | None = None  # confirmada por el usuario o detectada con confianza alta/media

    @property
    def nombre(self) -> str:
        return self.libro.archivo


@dataclass
class Hallazgo:
    poblacion: str
    archivo: str
    hoja: str
    fila_excel: int
    id_registro: str
    no_acta: str
    regla: str
    version_regla: int
    tipo_regla: str
    estado_regla: str
    variable: str
    observado: str
    esperado: str
    explicacion: str
    severidad: str
    fuente: str
    accion: str
    resultado: str  # incumple | no_evaluable
    ocurrencia: int = 1  # >1 cuando el mismo registro (p. ej. un ID repetido) produce la misma clave

    @property
    def clave_seguimiento(self) -> str:
        base = f"{self.poblacion}|{self.regla}|{self.variable}|{self.id_registro}"
        return base if self.ocurrencia == 1 else f"{base}#{self.ocurrencia}"


@dataclass
class ResumenRegla:
    regla: Regla
    poblacion: str
    archivo: str
    conteos: Counter
    motivos_no_evaluable: Counter
    columnas_faltantes: list[str]

    @property
    def evaluados(self) -> int:
        return self.conteos[CUMPLE] + self.conteos[INCUMPLE]


@dataclass
class ResultadoArchivo:
    archivo: str
    sha256: str
    hoja: str
    poblacion: str
    nombre_poblacion: str
    registros: int
    estructura: Estructura
    lectura_avisos: list[str]
    fila_encabezado: int
    dimension_declarada: str
    ultima_fila: int
    resumen_reglas: list[ResumenRegla]
    fechas_encuesta: tuple[date | None, date | None]
    subredes: Counter
    localidades: Counter


@dataclass
class ResultadoEjecucion:
    id_ejecucion: str
    fecha_hora: datetime
    version_motor: str
    tematica: str
    version_configuracion: str
    huella_reglas: str
    parametros: Parametros
    archivos: list[ResultadoArchivo]
    hallazgos: list[Hallazgo]
    no_evaluables: list[Hallazgo]
    reglas_no_ejecutadas: list[tuple[Regla, str]]  # (regla, motivo)
    resumen_lote: list[ResumenRegla]
    avisos: list[str]
    tem: Tematica
    duracion_segundos: float = 0.0


def cargar_configuracion(directorio: str | Path | None = None) -> Tematica:
    tem = cargar_tematica(directorio or CONFIG_AIRE)
    for p in tem.poblaciones:
        if not p.huella_instrumento:
            p.huella_instrumento = huella_columnas([v.nombre for v in p.variables if not v.opcional])
    return tem


def claves_conocidas(tem: Tematica) -> set[str]:
    out: set[str] = set()
    for p in tem.poblaciones:
        for v in p.variables:
            out.add(clave_nombre_columna(v.nombre))
            out |= {clave_nombre_columna(e) for e in v.equivalencias}
    return out


def preparar_archivo(tem: Tematica, origen: str | Path | bytes, nombre: str | None = None) -> ArchivoPreparado:
    libro = leer_libro(origen, nombre, claves_conocidas(tem))
    hoja, detecciones = elegir_hoja(tem, libro.hojas)
    det = next((d for d in detecciones if hoja and d.hoja == hoja.hoja), None)
    codigo = det.codigo if det else None
    conf = det.confianza if det else "baja"
    return ArchivoPreparado(libro=libro, hoja=hoja, deteccion=detecciones, poblacion_detectada=codigo,
                            confianza=conf, poblacion=codigo if conf in ("alta", "media") else None)


def _construir_registros(tem: Tematica, pob_cod: str, hoja: HojaLeida, est: Estructura) -> list[RegistroDatos]:
    p = tem.poblacion(pob_cod)
    disponibles = est.variables_disponibles
    regs = []
    for k, (fila, valores) in enumerate(hoja.filas):
        vals = {}
        for var, corr in est.correspondencias.items():
            if var in disponibles:
                vals[var] = construir_celda(valores[corr.indice] if corr.indice < len(valores) else None)
        idc = vals.get(p.variable_id)
        acta = vals.get(p.variable_acta)
        ident = idc.texto if idc is not None and not idc.vacia else (acta.texto if acta is not None and not acta.vacia else f"FILA{fila}")
        regs.append(RegistroDatos(indice=k, archivo=hoja.archivo, hoja=hoja.hoja, fila_excel=fila, valores=vals,
                                  id_registro=ident, poblacion=pob_cod))
    return regs


def _filtrar_vigencia(r: Regla, regs: list[RegistroDatos], var_fecha: str) -> tuple[list[RegistroDatos], int]:
    if not r.vigencia or (r.vigencia.desde is None and r.vigencia.hasta is None):
        return regs, 0
    dentro, fuera = [], 0
    for reg in regs:
        c = reg.valores.get(var_fecha)
        f = interpretar_fecha(c)[0] if c is not None else None
        if f is None:
            dentro.append(reg)  # sin fecha: la regla decide (y la fecha se reporta aparte)
        elif (r.vigencia.desde and f < r.vigencia.desde) or (r.vigencia.hasta and f > r.vigencia.hasta):
            fuera += 1
        else:
            dentro.append(reg)
    return dentro, fuera


def _fuente(r: Regla) -> str:
    return "; ".join(f"{f.doc} {f.ubicacion}" for f in r.fuentes)


def _a_hallazgo(r: Regla, res: Resultado, tem: Tematica) -> Hallazgo:
    reg = res.registro
    p = tem.poblacion(reg.poblacion)
    acta = reg.valores.get(p.variable_acta)
    explicacion = res.motivo
    if r.estado == "provisional":
        explicacion = f"[Regla provisional, sujeta a confirmación] {explicacion}"
    return Hallazgo(
        poblacion=reg.poblacion, archivo=reg.archivo, hoja=reg.hoja, fila_excel=reg.fila_excel,
        id_registro=reg.id_registro, no_acta=acta.texto if acta is not None else "", regla=r.id,
        version_regla=r.version, tipo_regla=r.tipo, estado_regla=r.estado, variable=res.variable,
        observado=res.observado, esperado=res.esperado, explicacion=explicacion,
        severidad=r.severidad, fuente=_fuente(r), accion=r.accion or "",
        resultado="incumple" if res.estado == INCUMPLE else "no_evaluable",
    )


def _ejecutar_regla(r: Regla, regs: list[RegistroDatos], ctx: Contexto, tem: Tematica,
                    hallazgos: list[Hallazgo], noev: list[Hallazgo]) -> tuple[Counter, Counter]:
    conteos: Counter = Counter()
    motivos: Counter = Counter()
    regs_v, fuera = _filtrar_vigencia(r, regs, ctx.variable_fecha)
    conteos[NO_APLICA] += fuera
    for res in IMPLEMENTACIONES[r.tipo](r, regs_v, ctx):
        conteos[res.estado] += 1
        if res.estado == INCUMPLE:
            hallazgos.append(_a_hallazgo(r, res, tem))
        elif res.estado == NO_EVALUABLE:
            motivos[res.motivo or "sin motivo"] += 1
            if res.registro is not None:
                noev.append(_a_hallazgo(r, res, tem))
    return conteos, motivos


def regla_aplica(r: Regla, pob: str, etapa: str) -> bool:
    return pob in r.poblaciones and ORDEN_ETAPA[r.etapa] <= ORDEN_ETAPA[etapa]


def validar(tem: Tematica, archivos: list[ArchivoPreparado], parametros: Parametros,
            id_ejecucion: str | None = None) -> ResultadoEjecucion:
    ahora = datetime.now().astimezone()
    t0 = time.perf_counter()
    id_ej = id_ejecucion or ahora.strftime("%Y%m%d-%H%M%S")
    hallazgos: list[Hallazgo] = []
    noev: list[Hallazgo] = []
    resultados: list[ResultadoArchivo] = []
    avisos: list[str] = []
    todos_regs: list[RegistroDatos] = []
    no_ejecutadas: dict[str, tuple[Regla, str]] = {}
    pobs_lote: set[str] = set()

    for ap in archivos:
        if ap.hoja is None:
            avisos.append(f"{ap.nombre}: no se encontraron datos legibles. " + " ".join(ap.libro.avisos))
            continue
        if ap.poblacion is None:
            avisos.append(f"{ap.nombre}: no se validó porque la población no fue confirmada.")
            continue
        p = tem.poblacion(ap.poblacion)
        pobs_lote.add(p.codigo)
        est = mapear_columnas(p, ap.hoja)
        regs = _construir_registros(tem, p.codigo, ap.hoja, est)
        todos_regs.extend(regs)
        ctx = Contexto(poblacion=p.codigo, periodo_inicio=parametros.periodo_inicio, periodo_fin=parametros.periodo_fin,
                       subredes=parametros.subredes, localidades=parametros.localidades, etapa=parametros.etapa,
                       variables_disponibles=est.variables_disponibles, variable_fecha=p.variable_fecha)
        resumen: list[ResumenRegla] = []
        for r in tem.reglas_de(p.codigo):
            if not r.ejecutable:
                no_ejecutadas.setdefault(r.id, (r, r.motivo_estado or ""))
                continue
            if not regla_aplica(r, p.codigo, parametros.etapa):
                no_ejecutadas.setdefault(r.id, (r, f"no corresponde a la etapa seleccionada ({parametros.etapa}); la regla es de {r.etapa}"))
                continue
            if r.parametros.get("alcance") == "lote":
                continue
            faltan = sorted(v for v in variables_requeridas(r) if v not in est.variables_disponibles)
            conteos, motivos = _ejecutar_regla(r, regs, ctx, tem, hallazgos, noev)
            resumen.append(ResumenRegla(r, p.codigo, ap.nombre, conteos, motivos, faltan))
        fechas = [interpretar_fecha(rg.valores[p.variable_fecha])[0] for rg in regs if p.variable_fecha in rg.valores]
        fechas = [f for f in fechas if f]
        resultados.append(ResultadoArchivo(
            archivo=ap.nombre, sha256=ap.libro.sha256, hoja=ap.hoja.hoja, poblacion=p.codigo, nombre_poblacion=p.nombre,
            registros=len(regs), estructura=est, lectura_avisos=ap.libro.avisos + ap.hoja.avisos,
            fila_encabezado=ap.hoja.fila_encabezado, dimension_declarada=ap.hoja.dimension_declarada,
            ultima_fila=ap.hoja.ultima_fila_con_contenido, resumen_reglas=resumen,
            fechas_encuesta=(min(fechas) if fechas else None, max(fechas) if fechas else None),
            subredes=Counter(rg.valores[p.variable_subred].texto for rg in regs if p.variable_subred in rg.valores),
            localidades=Counter(rg.valores["Localidad"].texto for rg in regs if "Localidad" in rg.valores),
        ))

    # Reglas de lote (cruces entre archivos/poblaciones)
    resumen_lote: list[ResumenRegla] = []
    vistas: set[str] = set()
    for r in tem.reglas:
        if r.parametros.get("alcance") != "lote" or r.id in vistas:
            continue
        vistas.add(r.id)
        if not r.ejecutable:
            no_ejecutadas.setdefault(r.id, (r, r.motivo_estado or ""))
            continue
        regs_r = [g for g in todos_regs if g.poblacion in r.poblaciones and all(v in g.valores for v in r.variables)]
        if not regs_r:
            continue
        ctx = Contexto(poblacion="lote", periodo_inicio=parametros.periodo_inicio, periodo_fin=parametros.periodo_fin,
                       subredes=parametros.subredes, etapa=parametros.etapa,
                       variables_disponibles=set().union(*(set(g.valores) for g in regs_r)))
        conteos, motivos = _ejecutar_regla(r, regs_r, ctx, tem, hallazgos, noev)
        resumen_lote.append(ResumenRegla(r, ", ".join(sorted({g.poblacion for g in regs_r})), "(lote)", conteos, motivos, []))

    _numerar_ocurrencias(hallazgos)
    return ResultadoEjecucion(
        id_ejecucion=id_ej, fecha_hora=ahora, version_motor=VERSION_MOTOR, tematica=tem.codigo,
        version_configuracion=tem.version_configuracion, huella_reglas=tem.huella_reglas, parametros=parametros,
        archivos=resultados, hallazgos=hallazgos, no_evaluables=noev,
        reglas_no_ejecutadas=[v for k, v in no_ejecutadas.items() if any(p in pobs_lote for p in v[0].poblaciones)],
        resumen_lote=resumen_lote, avisos=avisos, tem=tem,
        duracion_segundos=round(time.perf_counter() - t0, 2),
    )


def _numerar_ocurrencias(hallazgos: list[Hallazgo]) -> None:
    """Hace única la clave de seguimiento cuando dos registros comparten identificador (en orden de archivo y fila)."""
    vistos: Counter = Counter()
    for h in sorted(hallazgos, key=lambda h: (h.archivo, h.fila_excel)):
        vistos[h.clave_seguimiento] += 1
        h.ocurrencia = vistos[h.clave_seguimiento]


def validar_rutas(rutas: list[str | Path], parametros: Parametros, poblaciones: dict[str, str] | None = None,
                  tem: Tematica | None = None) -> ResultadoEjecucion:
    """Atajo para scripts y pruebas: lee, detecta y valida."""
    tem = tem or cargar_configuracion()
    preparados = []
    for ruta in rutas:
        ap = preparar_archivo(tem, ruta)
        if poblaciones and Path(ruta).name in poblaciones:
            ap.poblacion = poblaciones[Path(ruta).name]
        preparados.append(ap)
    return validar(tem, preparados, parametros)


def indicadores(res: ResultadoEjecucion) -> dict[str, Any]:
    """Totales del resumen. Distingue hallazgos de registros distintos afectados."""
    por_sev = Counter(h.severidad for h in res.hallazgos)
    registros_sev: dict[str, set] = defaultdict(set)
    for h in res.hallazgos:
        registros_sev[h.severidad].add((h.archivo, h.fila_excel))
    afectados = {(h.archivo, h.fila_excel) for h in res.hallazgos if h.severidad != "revision"}
    todas = [rr for a in res.archivos for rr in a.resumen_reglas] + res.resumen_lote
    reglas_con_ne = {(rr.regla.id, rr.archivo) for rr in todas if rr.conteos[NO_EVALUABLE] > 0}
    return {
        "archivos": len(res.archivos),
        "registros": sum(a.registros for a in res.archivos),
        "reglas_ejecutadas": len({rr.regla.id for rr in todas}),
        "ejecuciones_regla_archivo": len(todas),
        "reglas_provisionales": len({rr.regla.id for rr in todas if rr.regla.estado == "provisional"}),
        "reglas_no_ejecutadas": len(res.reglas_no_ejecutadas),
        "controles_con_no_evaluables": len(reglas_con_ne),
        "resultados_no_evaluables": len(res.no_evaluables),
        "hallazgos_por_severidad": dict(por_sev),
        "registros_por_severidad": {k: len(v) for k, v in registros_sev.items()},
        "hallazgos_total": len(res.hallazgos),
        "registros_afectados_sin_revision": len(afectados),
        "registros_afectados_total": len({(h.archivo, h.fila_excel) for h in res.hallazgos}),
    }
