"""Reporte Excel de una ejecución.

Hojas:
  A_Resumen            ejecución, archivos, indicadores (hallazgos y registros distintos)
  B_Hallazgos          un hallazgo por fila, con clave de seguimiento y columnas para el equipo
  C_No_evaluables      controles que no pudieron evaluarse, agrupados por motivo, y su detalle
  D_Estructura         hoja, encabezado, columnas nuevas/ausentes/vacías/renombradas por archivo
  E_Resultado_reglas   por regla y archivo: evaluados, cumple, incumple, no aplica, no evaluable
  F_Catalogo_reglas    todas las reglas de la configuración con estado, fuentes y motivo
  G_Cobertura          matriz de cobertura por variable
  H_Decisiones         cuestionario de decisiones pendientes para el equipo técnico
  I_Comparacion        (si se cargó una ejecución anterior) nuevos, persistentes y resueltos

Los valores observados de variables marcadas como dato personal se ocultan por defecto: la
fila de Excel, el ID SIVIGILA y el número de acta bastan para ubicar el registro.
"""
from __future__ import annotations

import io
from collections import Counter, defaultdict
from typing import Any

import xlsxwriter

from .cobertura import matriz_cobertura, resumen_cobertura
from .condiciones import describir
from .configuracion import ESTADOS_EJECUTABLES
from .historial import COLUMNA_CLAVE, ESTADOS_SEGUIMIENTO, HOJA_HALLAZGOS, Comparacion
from .motor import Hallazgo, ResultadoEjecucion, indicadores
from .reglas import CUMPLE, INCUMPLE, NO_APLICA, NO_EVALUABLE

ORDEN_SEVERIDAD = {"bloqueante": 0, "error": 1, "alerta": 2, "revision": 3}
NOMBRE_SEVERIDAD = {"bloqueante": "Bloqueante", "error": "Error", "alerta": "Alerta", "revision": "Revisión humana"}
NOMBRE_ESTADO = {
    "implementada": "Implementada", "provisional": "Provisional (confirmar)", "revision_humana": "Revisión humana",
    "pendiente_contradiccion": "Pendiente: contradicción", "pendiente_incompleta": "Pendiente: definición incompleta",
    "requiere_insumo": "Pendiente: requiere insumo",
}
NOMBRE_POBLACION = {"menores5": "Menores de 5", "5a14": "5 a 14 años", "mayores60": "60 años y más"}


def _variables_personales(res: ResultadoEjecucion) -> dict[str, set[str]]:
    return {p.codigo: {v.nombre for v in p.variables if v.personal} for p in res.tem.poblaciones}


def _es_personal(h: Hallazgo, personales: dict[str, set[str]]) -> bool:
    nombres = {x.strip() for x in h.variable.split(",")}
    return bool(nombres & personales.get(h.poblacion, set()))


def _texto_observado(h: Hallazgo, personales: dict[str, set[str]], ocultar: bool) -> str:
    if ocultar and _es_personal(h, personales):
        return "(dato personal oculto: consultar en la base)"
    return h.observado


class _Libro:
    def __init__(self) -> None:
        self.buf = io.BytesIO()
        self.wb = xlsxwriter.Workbook(self.buf, {"in_memory": True, "strings_to_numbers": False,
                                                 "strings_to_formulas": False, "strings_to_urls": False})
        f = self.wb.add_format
        self.titulo = f({"bold": True, "font_size": 14, "font_color": "#1F3864"})
        self.sub = f({"bold": True, "font_size": 11, "font_color": "#1F3864"})
        self.enc = f({"bold": True, "bg_color": "#1F3864", "font_color": "white", "text_wrap": True, "valign": "top", "border": 1})
        self.celda = f({"valign": "top", "text_wrap": True})
        self.celda_corta = f({"valign": "top"})
        self.nota = f({"italic": True, "font_color": "#595959", "text_wrap": True})
        self.negrita = f({"bold": True})
        self.pct = f({"num_format": "0.0%"})
        self.editable = f({"bg_color": "#FFF2CC", "valign": "top", "text_wrap": True, "border": 1})
        self.sev = {
            "bloqueante": f({"bg_color": "#C00000", "font_color": "white", "bold": True}),
            "error": f({"bg_color": "#F8CBAD"}),
            "alerta": f({"bg_color": "#FFE699"}),
            "revision": f({"bg_color": "#DDEBF7"}),
        }

    def tabla(self, ws, fila: int, columnas: list[tuple[str, int]], datos: list[list[Any]],
              formatos: dict[int, Any] | None = None, filtro: bool = True) -> int:
        for c, (nombre, ancho) in enumerate(columnas):
            ws.write(fila, c, nombre, self.enc)
            ws.set_column(c, c, ancho)
        for i, d in enumerate(datos, start=fila + 1):
            for c, v in enumerate(d):
                fmt = (formatos or {}).get(c, self.celda)
                if callable(fmt):
                    fmt = fmt(v)
                if v is None:
                    v = ""
                ws.write(i, c, v, fmt)
        if filtro and columnas:
            ws.autofilter(fila, 0, fila + max(len(datos), 1), len(columnas) - 1)
        return fila + len(datos) + 2

    def cerrar(self) -> bytes:
        self.wb.close()
        return self.buf.getvalue()


def generar_reporte(res: ResultadoEjecucion, comparacion: Comparacion | None = None,
                    ocultar_datos_personales: bool = True) -> bytes:
    L = _Libro()
    personales = _variables_personales(res)
    ind = indicadores(res)
    estado_comp: dict[str, str] = {}
    previo_por_clave = {}
    if comparacion is not None:
        estado_comp = {h.clave_seguimiento: "nuevo" for h in comparacion.nuevos}
        for h, p in comparacion.persistentes:
            estado_comp[h.clave_seguimiento] = "persistente"
            previo_por_clave[h.clave_seguimiento] = p

    _hoja_resumen(L, res, ind, comparacion)
    _hoja_hallazgos(L, res, personales, ocultar_datos_personales, estado_comp, previo_por_clave)
    _hoja_no_evaluables(L, res, personales, ocultar_datos_personales)
    _hoja_estructura(L, res)
    _hoja_resultado_reglas(L, res)
    _hoja_catalogo(L, res)
    _hoja_cobertura(L, res)
    _hoja_decisiones(L, res)
    if comparacion is not None:
        _hoja_comparacion(L, res, comparacion)
    return L.cerrar()


def _hoja_resumen(L: _Libro, res: ResultadoEjecucion, ind: dict, comp: Comparacion | None) -> None:
    ws = L.wb.add_worksheet("A_Resumen")
    ws.set_column(0, 0, 42)
    ws.set_column(1, 8, 18)
    ws.write(0, 0, f"Validación de bases LARREM – {res.tem.nombre}", L.titulo)
    p = res.parametros
    meta = [
        ("Identificador de ejecución", res.id_ejecucion),
        ("Fecha y hora", res.fecha_hora.strftime("%Y-%m-%d %H:%M:%S %z")),
        ("Versión del motor", res.version_motor),
        ("Versión de la configuración", res.version_configuracion),
        ("Huella de la configuración", res.huella_reglas),
        ("Periodo esperado", f"{p.periodo_inicio or '—'} a {p.periodo_fin or '—'}"),
        ("Etapa validada", p.etapa),
        ("Subredes esperadas", ", ".join(p.subredes) or "todas"),
        ("Localidades esperadas", ", ".join(p.localidades) or "todas"),
        ("Descripción del ámbito", p.descripcion_ambito or ""),
        ("Duración de la validación (s)", res.duracion_segundos),
    ]
    f = 2
    for k, v in meta:
        ws.write(f, 0, k, L.negrita)
        ws.write(f, 1, v)
        f += 1
    f += 1
    ws.write(f, 0, "Archivos procesados", L.sub)
    f += 1
    datos = []
    for a in res.archivos:
        e = a.estructura
        datos.append([a.archivo, NOMBRE_POBLACION.get(a.poblacion, a.poblacion), a.hoja, a.registros,
                      str(a.fechas_encuesta[0] or ""), str(a.fechas_encuesta[1] or ""),
                      "sí" if e.huella_encontrada == e.huella_esperada else "no (ver D_Estructura)", a.sha256[:16]])
    f = L.tabla(ws, f, [("Archivo", 42), ("Población", 18), ("Hoja", 18), ("Registros", 12), ("Primera encuesta", 16),
                        ("Última encuesta", 16), ("Estructura igual al instrumento", 18), ("Huella SHA-256 (16)", 20)],
                datos, filtro=False)
    if res.avisos:
        ws.write(f, 0, "Avisos", L.sub)
        f += 1
        for a in res.avisos:
            ws.write(f, 0, a, L.nota)
            f += 1
        f += 1

    ws.write(f, 0, "Indicadores", L.sub)
    f += 1
    ws.write(f, 0, "Un hallazgo es un control incumplido en un registro. Un registro puede tener varios hallazgos. "
                   "No se calcula un porcentaje global de calidad: ver E_Resultado_reglas para la tasa por regla.", L.nota)
    f += 1
    sev_h = ind["hallazgos_por_severidad"]
    sev_r = ind["registros_por_severidad"]
    datos = [[NOMBRE_SEVERIDAD[s], sev_h.get(s, 0), sev_r.get(s, 0)] for s in ORDEN_SEVERIDAD]
    datos.append(["Total", ind["hallazgos_total"], ind["registros_afectados_total"]])
    datos.append(["Total sin revisión humana", sum(sev_h.get(s, 0) for s in ORDEN_SEVERIDAD if s != "revision"),
                  ind["registros_afectados_sin_revision"]])
    f = L.tabla(ws, f, [("Severidad", 42), ("Hallazgos", 14), ("Registros distintos", 18)], datos, filtro=False)

    # por población y severidad
    ws.write(f, 0, "Registros distintos afectados por población", L.sub)
    f += 1
    regs: dict[tuple[str, str], set] = defaultdict(set)
    for h in res.hallazgos:
        regs[(h.poblacion, h.severidad)].add((h.archivo, h.fila_excel))
    total_pob = Counter()
    for a in res.archivos:
        total_pob[a.poblacion] += a.registros
    datos = []
    for pob in total_pob:
        fila = [NOMBRE_POBLACION.get(pob, pob), total_pob[pob]]
        fila += [len(regs[(pob, s)]) for s in ORDEN_SEVERIDAD]
        datos.append(fila)
    f = L.tabla(ws, f, [("Población", 42), ("Registros", 12)] + [(NOMBRE_SEVERIDAD[s], 16) for s in ORDEN_SEVERIDAD],
                datos, filtro=False)

    ws.write(f, 0, "Reglas", L.sub)
    f += 1
    for k, v in [("Reglas ejecutadas", ind["reglas_ejecutadas"]),
                 ("Reglas provisionales ejecutadas (sujetas a confirmación)", ind["reglas_provisionales"]),
                 ("Reglas no ejecutadas (pendientes, etapa o insumo)", ind["reglas_no_ejecutadas"]),
                 ("Controles con resultados no evaluables", ind["controles_con_no_evaluables"]),
                 ("Resultados no evaluables (registro × control)", ind["resultados_no_evaluables"]),
                 ("Decisiones pendientes con el equipo técnico", sum(1 for d in res.tem.decisiones if not d.respuesta))]:
        ws.write(f, 0, k)
        ws.write(f, 1, v)
        f += 1
    if comp is not None:
        f += 1
        ws.write(f, 0, f"Comparación con la ejecución {comp.id_previa or '(anterior)'}", L.sub)
        f += 1
        for k, v in comp.resumen().items():
            ws.write(f, 0, k.replace("_", " ").capitalize())
            ws.write(f, 1, v)
            f += 1
        for av in comp.avisos:
            ws.write(f, 0, av, L.nota)
            f += 1
    f += 1
    ws.write(f, 0, "Un control sin hallazgos no certifica la base: solo indica que las reglas ejecutadas se cumplieron. "
                   "Los no evaluables nunca se cuentan como cumplidos.", L.nota)


def _hoja_hallazgos(L: _Libro, res: ResultadoEjecucion, personales, ocultar: bool,
                    estado_comp: dict[str, str], previos: dict) -> None:
    ws = L.wb.add_worksheet(HOJA_HALLAZGOS)
    columnas = [(COLUMNA_CLAVE, 30), ("Severidad", 13), ("Población", 13), ("Archivo", 24), ("Fila Excel", 9),
                ("Registro (ID SIVIGILA)", 16), ("No. acta", 16), ("Regla", 28), ("Descripción de la regla", 40),
                ("Estado de la regla", 16), ("Variable", 26), ("Valor observado", 26), ("Valor esperado", 26),
                ("Explicación", 42), ("Fuente", 28), ("Acción sugerida", 36), ("Comparación", 12),
                ("Estado del hallazgo", 18), ("Observación del equipo", 36)]
    desc = {r.id: r.descripcion for r in res.tem.reglas}
    hs = sorted(res.hallazgos, key=lambda h: (ORDEN_SEVERIDAD.get(h.severidad, 9), h.archivo, h.fila_excel, h.regla))
    datos = []
    for h in hs:
        prev = previos.get(h.clave_seguimiento)
        datos.append([h.clave_seguimiento, NOMBRE_SEVERIDAD.get(h.severidad, h.severidad), h.poblacion, h.archivo,
                      h.fila_excel, h.id_registro, h.no_acta, h.regla, desc.get(h.regla, ""),
                      NOMBRE_ESTADO.get(h.estado_regla, h.estado_regla), h.variable,
                      _texto_observado(h, personales, ocultar), h.esperado, h.explicacion, h.fuente, h.accion,
                      estado_comp.get(h.clave_seguimiento, ""),
                      (prev.estado_equipo if prev and prev.estado_equipo else "pendiente"),
                      (prev.observacion_equipo if prev else "")])
    inv = {v: k for k, v in NOMBRE_SEVERIDAD.items()}
    L.tabla(ws, 0, columnas, datos, formatos={1: lambda v: L.sev.get(inv.get(v), L.celda_corta), 4: L.celda_corta,
                                              17: L.editable, 18: L.editable})
    ws.freeze_panes(1, 2)
    if datos:
        ws.data_validation(1, 17, len(datos), 17, {"validate": "list", "source": ESTADOS_SEGUIMIENTO})


def _hoja_no_evaluables(L: _Libro, res: ResultadoEjecucion, personales, ocultar: bool) -> None:
    ws = L.wb.add_worksheet("C_No_evaluables")
    ws.write(0, 0, "Controles no evaluables", L.titulo)
    ws.write(1, 0, "Un resultado no evaluable no es un cumplimiento: falta la columna, el valor de un antecedente "
                   "está vacío o es inválido, o la regla depende de una decisión pendiente.", L.nota)
    agrup: dict[tuple, list[Hallazgo]] = defaultdict(list)
    for h in res.no_evaluables:
        agrup[(h.poblacion, h.regla, h.explicacion)].append(h)
    datos = []
    for (pob, regla, motivo), hs in sorted(agrup.items(), key=lambda x: -len(x[1])):
        filas = sorted({h.fila_excel for h in hs})
        muestra = ", ".join(map(str, filas[:15])) + (" …" if len(filas) > 15 else "")
        datos.append([pob, regla, motivo, len(hs), len(filas), muestra])
    # reglas con columnas faltantes
    for a in res.archivos:
        for rr in a.resumen_reglas:
            if rr.columnas_faltantes and rr.conteos[NO_EVALUABLE] and not any(d[1] == rr.regla.id and d[0] == a.poblacion for d in datos):
                datos.append([a.poblacion, rr.regla.id, "columnas ausentes: " + ", ".join(rr.columnas_faltantes),
                              rr.conteos[NO_EVALUABLE], "", ""])
    f = L.tabla(ws, 3, [("Población", 13), ("Regla", 30), ("Motivo", 70), ("Resultados", 11), ("Registros", 11),
                        ("Filas Excel (muestra)", 40)], datos, filtro=False)
    ws.write(f, 0, "Detalle", L.sub)
    det = [[h.poblacion, h.archivo, h.fila_excel, h.id_registro, h.regla, h.variable,
            _texto_observado(h, personales, ocultar), h.explicacion]
           for h in sorted(res.no_evaluables, key=lambda h: (h.archivo, h.regla, h.fila_excel))]
    L.tabla(ws, f + 1, [("Población", 13), ("Archivo", 24), ("Fila Excel", 9), ("Registro", 16), ("Regla", 30),
                        ("Variable", 24), ("Valor observado", 22), ("Motivo", 60)], det)


def _hoja_estructura(L: _Libro, res: ResultadoEjecucion) -> None:
    ws = L.wb.add_worksheet("D_Estructura")
    ws.set_column(0, 0, 36)
    ws.set_column(1, 1, 90)
    ws.write(0, 0, "Estructura de los archivos", L.titulo)
    f = 2
    for a in res.archivos:
        e = a.estructura
        ws.write(f, 0, f"{a.archivo} – {NOMBRE_POBLACION.get(a.poblacion, a.poblacion)}", L.sub)
        f += 1
        renombradas = [f"{c.encabezado_original} → {v} ({c.metodo})" for v, c in e.correspondencias.items()
                       if c.metodo != "exacta"]
        filas = [
            ("Hoja leída", a.hoja),
            ("Fila de encabezados", a.fila_encabezado),
            ("Rango declarado / última fila con contenido", f"{a.dimension_declarada} / {a.ultima_fila}"),
            ("Registros leídos", a.registros),
            ("Columnas reconocidas", len(e.correspondencias)),
            ("Huella de columnas (encontrada / esperada)", f"{e.huella_encontrada} / {e.huella_esperada}"),
            ("Columnas nuevas (no están en el catálogo)", ", ".join(f"{n} (col. {i + 1})" for i, n in e.columnas_nuevas) or "ninguna"),
            ("Variables del catálogo ausentes", ", ".join(e.columnas_ausentes) or "ninguna"),
            ("Ausentes que son obligatorias", ", ".join(e.ausentes_requeridas) or "ninguna"),
            ("Encabezados duplicados", ", ".join(e.encabezados_duplicados) or "ninguno"),
            ("Variables ambiguas (no se validan)", "; ".join(f"{k}: {', '.join(v)}" for k, v in e.variables_ambiguas.items()) or "ninguna"),
            ("Reconocidas por equivalencia o normalización", "; ".join(renombradas) or "ninguna"),
            ("Columnas completamente vacías", ", ".join(e.columnas_vacias) or "ninguna"),
            ("Subredes encontradas", "; ".join(f"{k or '(vacío)'}: {v}" for k, v in a.subredes.most_common())),
            ("Localidades encontradas", "; ".join(f"{k or '(vacío)'}: {v}" for k, v in a.localidades.most_common())),
        ]
        for k, v in filas:
            ws.write(f, 0, k, L.negrita)
            ws.write(f, 1, v, L.celda)
            f += 1
        for av in a.lectura_avisos + e.avisos:
            ws.write(f, 0, "Aviso", L.negrita)
            ws.write(f, 1, av, L.nota)
            f += 1
        f += 1
    if res.reglas_no_ejecutadas:
        ws.write(f, 0, "Reglas afectadas por la estructura o no ejecutadas", L.sub)
        f += 1
        for a in res.archivos:
            for rr in a.resumen_reglas:
                if rr.columnas_faltantes:
                    ws.write(f, 0, f"{rr.regla.id} ({a.poblacion})")
                    ws.write(f, 1, "no evaluable por columnas ausentes: " + ", ".join(rr.columnas_faltantes), L.celda)
                    f += 1


def _hoja_resultado_reglas(L: _Libro, res: ResultadoEjecucion) -> None:
    ws = L.wb.add_worksheet("E_Resultado_reglas")
    datos = []
    todas = [(a.archivo, rr) for a in res.archivos for rr in a.resumen_reglas] + [("(lote)", rr) for rr in res.resumen_lote]
    for archivo, rr in todas:
        c = rr.conteos
        ev = c[CUMPLE] + c[INCUMPLE]
        datos.append([rr.regla.id, rr.poblacion, archivo, rr.regla.tipo, NOMBRE_SEVERIDAD.get(rr.regla.severidad),
                      NOMBRE_ESTADO.get(rr.regla.estado), ev, c[CUMPLE], c[INCUMPLE], c[NO_APLICA], c[NO_EVALUABLE],
                      (c[INCUMPLE] / ev) if ev else None,
                      "; ".join(f"{m} ({n})" for m, n in rr.motivos_no_evaluable.most_common(3))])
    for r, motivo in res.reglas_no_ejecutadas:
        datos.append([r.id, ", ".join(r.poblaciones), "", r.tipo, NOMBRE_SEVERIDAD.get(r.severidad),
                      NOMBRE_ESTADO.get(r.estado), "", "", "", "", "", None, f"No ejecutada: {motivo}"])
    L.tabla(ws, 0, [("Regla", 30), ("Población", 13), ("Archivo", 24), ("Tipo", 18), ("Severidad", 12),
                    ("Estado", 18), ("Evaluados", 10), ("Cumple", 10), ("Incumple", 10), ("No aplica", 10),
                    ("No evaluable", 11), ("Tasa de incumplimiento", 12), ("Motivos no evaluable / observación", 60)],
            datos, formatos={i: L.celda_corta for i in range(6, 11)} | {11: L.pct})
    ws.freeze_panes(1, 1)
    ws.write_comment(0, 11, "Incumple / (cumple + incumple). No incluye no aplica ni no evaluables.")


def _hoja_catalogo(L: _Libro, res: ResultadoEjecucion) -> None:
    ws = L.wb.add_worksheet("F_Catalogo_reglas")
    dec_por_regla: dict[str, list[str]] = defaultdict(list)
    for d in res.tem.decisiones:
        for rid in d.reglas:
            dec_por_regla[rid].append(d.id)
    datos = []
    for r in res.tem.reglas:
        datos.append([r.id, r.version, ", ".join(r.poblaciones), r.descripcion, r.tipo, r.etapa,
                      NOMBRE_SEVERIDAD.get(r.severidad), NOMBRE_ESTADO.get(r.estado),
                      "sí" if r.estado in ESTADOS_EJECUTABLES else "no", ", ".join(r.variables),
                      describir(r.aplica_si) if r.aplica_si else "", r.motivo_estado or "", r.insumo_requerido or "",
                      ", ".join(dec_por_regla.get(r.id, [])), r.especiales or "",
                      "; ".join(f"{f.doc} {f.ubicacion}" + (f" ({f.nota})" if f.nota else "") for f in r.fuentes),
                      r.accion or "", r.revision_tecnica])
    L.tabla(ws, 0, [("Regla", 30), ("Versión", 8), ("Poblaciones", 18), ("Descripción", 50), ("Tipo", 18),
                    ("Etapa", 14), ("Severidad", 12), ("Estado", 20), ("Se ejecuta", 9), ("Variables", 36),
                    ("Aplica si", 36), ("Motivo del estado", 50), ("Insumo requerido", 36), ("Decisiones", 12),
                    ("Casos especiales", 40), ("Fuentes", 50), ("Acción sugerida", 36), ("Revisión técnica", 14)], datos)
    ws.freeze_panes(1, 1)


def _hoja_cobertura(L: _Libro, res: ResultadoEjecucion) -> None:
    ws = L.wb.add_worksheet("G_Cobertura")
    filas = matriz_cobertura(res.tem, res)
    pobs = {a.poblacion for a in res.archivos} or {f.poblacion for f in filas}
    filas = [f for f in filas if f.poblacion in pobs]
    ws.write(0, 0, "Cobertura de variables por reglas", L.titulo)
    resumen = resumen_cobertura(filas)
    if resumen:
        cols = list(resumen[0])
        f = L.tabla(ws, 2, [(c, 18) for c in cols], [list(r.values()) for r in resumen], filtro=False)
    else:
        f = 2
    dicts = [x.como_dict() for x in filas]
    if dicts:
        cols = list(dicts[0])
        anchos = {"Etiqueta": 36, "Reglas que la validan": 40, "Reglas en que es condición": 36, "Estado de cobertura": 30}
        L.tabla(ws, f, [(c, anchos.get(c, 16)) for c in cols], [list(d.values()) for d in dicts])
        ws.freeze_panes(f + 1, 2)


def _hoja_decisiones(L: _Libro, res: ResultadoEjecucion) -> None:
    ws = L.wb.add_worksheet("H_Decisiones")
    ws.write(0, 0, "Decisiones pendientes para el equipo técnico", L.titulo)
    ws.write(1, 0, "Diligencie las columnas amarillas. Con la respuesta se ajustan las reglas enlazadas y se sube "
                   "la versión de la configuración.", L.nota)
    datos = [[d.id, d.tema, ", ".join(NOMBRE_POBLACION.get(p, p) for p in d.poblaciones), d.diferencia,
              "; ".join(f"{f.doc} {f.ubicacion}" for f in d.fuentes), d.efecto_en_validador, ", ".join(d.reglas),
              d.pregunta, d.responsable_sugerido, d.respuesta or "", str(d.fecha_respuesta or "")]
             for d in res.tem.decisiones]
    L.tabla(ws, 3, [("Id", 7), ("Tema", 30), ("Poblaciones", 18), ("Diferencia entre fuentes", 55), ("Fuentes", 30),
                    ("Qué hace hoy el validador", 45), ("Reglas", 30), ("Pregunta", 50), ("Responsable sugerido", 24),
                    ("Respuesta", 40), ("Fecha de respuesta", 14)], datos,
            formatos={9: L.editable, 10: L.editable})
    ws.freeze_panes(4, 2)


def _hoja_comparacion(L: _Libro, res: ResultadoEjecucion, comp: Comparacion) -> None:
    ws = L.wb.add_worksheet("I_Comparacion")
    ws.write(0, 0, f"Comparación con la ejecución {comp.id_previa or '(anterior)'}", L.titulo)
    fila_av = 2
    for av in comp.avisos:
        ws.write(fila_av, 0, av, L.nota)
        fila_av += 1
    ws.write(1, 0, "La comparación usa la clave población|regla|variable|registro. 'Resuelto' significa que la regla se "
                   "ejecutó de nuevo para esa población y el hallazgo ya no aparece. Si la población no se cargó o la "
                   "regla no se ejecutó, el hallazgo anterior queda como no comparable.", L.nota)
    datos = [[k.replace("_", " ").capitalize(), v] for k, v in comp.resumen().items()]
    f = L.tabla(ws, fila_av + 1, [("Grupo", 30), ("Hallazgos", 12)], datos, filtro=False)
    por_regla: dict[str, Counter] = defaultdict(Counter)
    for h in comp.nuevos:
        por_regla[h.regla]["nuevos"] += 1
    for h, _ in comp.persistentes:
        por_regla[h.regla]["persistentes"] += 1
    for p in comp.resueltos:
        por_regla[p.regla]["resueltos"] += 1
    datos = [[r, c["nuevos"], c["persistentes"], c["resueltos"]] for r, c in sorted(por_regla.items())]
    f = L.tabla(ws, f, [("Regla", 30), ("Nuevos", 10), ("Persistentes", 12), ("Resueltos", 10)], datos)
    ws.write(f, 0, "Hallazgos resueltos y no comparables de la ejecución anterior", L.sub)
    datos = [[p.clave, "resuelto", p.severidad, p.estado_equipo, p.observacion_equipo] for p in comp.resueltos]
    datos += [[p.clave, "no comparable", p.severidad, p.estado_equipo, p.observacion_equipo] for p in comp.no_comparables_previos]
    L.tabla(ws, f + 1, [(COLUMNA_CLAVE, 50), ("Resultado", 14), ("Severidad", 12), ("Estado anterior", 18),
                        ("Observación anterior", 40)], datos, filtro=False)
