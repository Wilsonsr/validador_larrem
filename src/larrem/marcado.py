"""Copia de trabajo de la base con los hallazgos marcados en las celdas.

La base original NO se modifica: se construye un libro nuevo con los mismos valores,
en las mismas filas y columnas, y se colorean las celdas con errores y alertas.
Cada celda marcada lleva un comentario con la regla, lo esperado y la explicación.
Al final de cada fila se agregan columnas de resumen para filtrar.

Se escribe con XlsxWriter a partir de lo ya leído (no se vuelve a abrir el original
con openpyxl): un archivo con un rango declarado de un millón de filas tardaría
casi un minuto en abrirse y guardarse, y aquí tarda segundos.
"""
from __future__ import annotations

import io
import re
from collections import defaultdict
from datetime import date, datetime, time
from typing import Iterable

import xlsxwriter

from .lectura import HojaLeida
from .motor import ArchivoPreparado, Hallazgo, ResultadoArchivo, ResultadoEjecucion
from .reglas import variables_requeridas

SEVERIDADES_MARCADAS = ("bloqueante", "error", "alerta", "revision")
ORDEN = {"bloqueante": 0, "error": 1, "alerta": 2, "revision": 3}
NOMBRE = {"bloqueante": "BLOQUEANTE", "error": "ERROR", "alerta": "ALERTA", "revision": "REVISIÓN HUMANA"}
ESTILO = {  # relleno y color de letra por severidad (los mismos tonos que usa Excel para "incorrecto"/"neutral")
    "bloqueante": ("#C00000", "#FFFFFF"),
    "error": ("#FFC7CE", "#9C0006"),
    "alerta": ("#FFEB9C", "#7A4F00"),
    "revision": ("#DDEBF7", "#1F4E79"),
}
COLUMNAS_RESUMEN = ["Validación: hallazgos", "Validación: severidad máxima", "Validación: reglas",
                    "Validación: revisión humana"]


def _columnas_de(h: Hallazgo, res: ResultadoArchivo, regla) -> list[int]:
    """Columnas (índice 0) que corresponden a la variable del hallazgo."""
    corr = res.estructura.correspondencias
    if h.variable in corr:
        return [corr[h.variable].indice]
    partes = [x.strip() for x in re.split(r",\s+|\s\+\s", h.variable)]
    cols = sorted({corr[p].indice for p in partes if p in corr})
    if cols:
        return cols
    if regla is not None:  # etiqueta de grupo (p. ej. "P7-P18 (síntomas)"): las variables que valida la regla
        vs = set(regla.variables) | set(regla.parametros.get("opciones", []) if isinstance(regla.parametros.get("opciones"), list) else [])
        cols = sorted({corr[v].indice for v in vs if v in corr}) or sorted(
            {corr[v].indice for v in variables_requeridas(regla) if v in corr})
        if cols:
            return cols
    return []


def _texto_comentario(h: Hallazgo, regla) -> str:
    partes = [f"[{NOMBRE[h.severidad]}] {regla.descripcion if regla else h.regla}"]
    if h.esperado:
        partes.append(f"Esperado: {h.esperado}")
    if h.explicacion:
        partes.append(f"Detalle: {h.explicacion}")
    if h.accion:
        partes.append(f"Acción: {h.accion}")
    partes.append(f"Regla {h.regla} · {h.fuente}")
    return "\n".join(partes)


def _escribir_valor(ws, fila: int, col: int, valor, fmt, fmt_fecha, fmt_fecha_hora):
    if valor is None:
        if fmt is not None:
            ws.write_blank(fila, col, None, fmt)
        return
    if isinstance(valor, bool):
        ws.write_boolean(fila, col, valor, fmt)
    elif isinstance(valor, (int, float)):
        ws.write_number(fila, col, valor, fmt)
    elif isinstance(valor, datetime):
        ws.write_datetime(fila, col, valor, fmt_fecha_hora if (valor.hour or valor.minute or valor.second) else fmt_fecha)
    elif isinstance(valor, date):
        ws.write_datetime(fila, col, datetime(valor.year, valor.month, valor.day), fmt_fecha)
    elif isinstance(valor, time):
        ws.write_string(fila, col, valor.isoformat(), fmt)
    else:
        ws.write_string(fila, col, str(valor), fmt)


def generar_base_marcada(ejecucion: ResultadoEjecucion, archivo: ResultadoArchivo, hoja: HojaLeida,
                         severidades: Iterable[str] = SEVERIDADES_MARCADAS) -> bytes:
    severidades = set(severidades)
    reglas = {r.id: r for r in ejecucion.tem.reglas}
    p = ejecucion.tem.poblacion(archivo.poblacion)
    col_id = archivo.estructura.correspondencias.get(p.variable_id)
    col_respaldo = col_id.indice if col_id else 0

    marcas: dict[tuple[int, int], list[Hallazgo]] = defaultdict(list)   # (fila_excel, col) -> hallazgos
    por_fila: dict[int, list[Hallazgo]] = defaultdict(list)
    revision_fila: dict[int, list[Hallazgo]] = defaultdict(list)
    for h in ejecucion.hallazgos:
        if h.archivo != archivo.archivo:
            continue
        if h.severidad == "revision":
            revision_fila[h.fila_excel].append(h)   # se cuenta aparte: no es un error
        elif h.severidad in severidades:
            por_fila[h.fila_excel].append(h)
        if h.severidad in severidades:
            for c in _columnas_de(h, archivo, reglas.get(h.regla)) or [col_respaldo]:
                marcas[(h.fila_excel, c)].append(h)

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_numbers": False, "strings_to_formulas": False,
                                   "strings_to_urls": False})
    nombre_hoja = (hoja.hoja or "Datos")[:31]
    ws = wb.add_worksheet(nombre_hoja)
    f_enc = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1, "text_wrap": True, "valign": "top"})
    f_enc_val = wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "#FFFFFF", "border": 1,
                               "text_wrap": True, "valign": "top"})
    f_fecha = wb.add_format({"num_format": "dd/mm/yyyy"})
    f_fecha_hora = wb.add_format({"num_format": "dd/mm/yyyy hh:mm"})
    f_sev = {}
    for s, (fondo, letra) in ESTILO.items():
        base = {"bg_color": fondo, "font_color": letra, "border": 1, "border_color": letra}
        f_sev[s] = (wb.add_format(base), wb.add_format({**base, "num_format": "dd/mm/yyyy"}),
                    wb.add_format({**base, "num_format": "dd/mm/yyyy hh:mm"}))

    fila_enc = hoja.fila_encabezado - 1
    ncols = len(hoja.encabezados)
    for c, nombre in enumerate(hoja.encabezados):
        ws.write_string(fila_enc, c, nombre, f_enc)
    for k, nombre in enumerate(COLUMNAS_RESUMEN):
        ws.write_string(fila_enc, ncols + k, nombre, f_enc_val)
    ws.set_column(0, max(ncols - 1, 0), 14)
    ws.set_column(ncols, ncols + 1, 16)
    ws.set_column(ncols + 2, ncols + 3, 40)
    ws.set_row(fila_enc, 45)

    ultima = fila_enc
    for fila_excel, valores in hoja.filas:
        r = fila_excel - 1
        ultima = max(ultima, r)
        for c in range(ncols):
            v = valores[c] if c < len(valores) else None
            hs = marcas.get((fila_excel, c))
            if hs:
                peor = min(hs, key=lambda h: ORDEN[h.severidad]).severidad
                fmt, fmt_d, fmt_dt = f_sev[peor]
                _escribir_valor(ws, r, c, v, fmt, fmt_d, fmt_dt)
                texto = "\n\n".join(_texto_comentario(h, reglas.get(h.regla))
                                      for h in sorted(hs, key=lambda h: ORDEN[h.severidad]))
                lineas = texto.count("\n") + 1 + len(texto) // 60
                ws.write_comment(r, c, texto[:2500], {"x_scale": 3, "y_scale": min(1 + lineas * 0.35, 6),
                                                       "author": "Validador LARREM"})
            else:
                _escribir_valor(ws, r, c, v, None, f_fecha, f_fecha_hora)
        hs = por_fila.get(fila_excel, [])
        rev = revision_fila.get(fila_excel, [])
        ws.write_number(r, ncols, len(hs))
        if hs:
            peor = min(hs, key=lambda h: ORDEN[h.severidad]).severidad
            ws.write_string(r, ncols + 1, NOMBRE[peor], f_sev[peor][0])
            ws.write_string(r, ncols + 2, ", ".join(sorted({h.regla for h in hs})))
        if rev:
            ws.write_string(r, ncols + 3, f"{len(rev)}: " + ", ".join(sorted({h.regla for h in rev})))

    ws.freeze_panes(fila_enc + 1, 0)
    ws.autofilter(fila_enc, 0, max(ultima, fila_enc + 1), ncols + len(COLUMNAS_RESUMEN) - 1)

    ley = wb.add_worksheet("Leyenda_validacion")
    f_t = wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F3864"})
    f_w = wb.add_format({"text_wrap": True, "valign": "top"})
    ley.set_column(0, 0, 28)
    ley.set_column(1, 1, 90)
    ley.write(0, 0, "Copia de trabajo con hallazgos marcados", f_t)
    filas = [
        ("Archivo original", archivo.archivo),
        ("Importante", "Esta es una COPIA generada por el validador. El archivo original no se modificó. "
                       "Corrija en el origen (aplicativo o formato físico) y vuelva a validar la base corregida."),
        ("Ejecución", ejecucion.id_ejecucion),
        ("Configuración", f"{ejecucion.version_configuracion} (huella {ejecucion.huella_reglas})"),
        ("Filas", "Cada registro está en la misma fila que en el archivo original: la «Fila Excel» del reporte coincide."),
        ("Colores", "Rojo oscuro = bloqueante; rojo = error; amarillo = alerta; azul = revisión humana. Pase el cursor "
                    "sobre la celda para ver la regla, lo esperado y la explicación."),
        ("Revisión humana", "Azul: no es un error. La guía pide que una persona verifique el caso (casi siempre en "
                            "Observaciones). No suma en «Validación: hallazgos»; se lista en «Validación: revisión humana»."),
        ("Columnas agregadas", "Las cuatro columnas «Validación: …» al final resumen cada fila. Use el filtro de la "
                               "columna «Validación: hallazgos» (mayor que 0) para ver solo los registros con errores o alertas."),
        ("Celdas sin columna propia", "Un hallazgo que no corresponde a una sola variable (p. ej. un ID repetido) se marca "
                                      "en la celda del ID SIVIGILA."),
    ]
    if hoja.otras_hojas:
        filas.append(("Otras hojas", "El original tiene otras hojas que no se copiaron: " + ", ".join(hoja.otras_hojas)))
    for i, (k, v) in enumerate(filas, start=2):
        ley.write(i, 0, k, wb.add_format({"bold": True, "valign": "top"}))
        ley.write(i, 1, v, f_w)
    i = len(filas) + 3
    ley.write(i, 0, "Resumen", f_t)
    conteo: dict[str, int] = defaultdict(int)
    for hs in por_fila.values():
        for h in hs:
            conteo[h.severidad] += 1
    for k, s in enumerate(["bloqueante", "error", "alerta"], start=i + 1):
        ley.write(k, 0, NOMBRE[s], f_sev[s][0])
        ley.write(k, 1, f"{conteo.get(s, 0)} hallazgos en "
                        f"{len({f for f, hs in por_fila.items() if any(h.severidad == s for h in hs)})} registros")
    ley.write(i + 4, 0, "REVISIÓN HUMANA", f_sev["revision"][0])
    ley.write(i + 4, 1, f"{sum(len(v) for v in revision_fila.values())} solicitudes en {len(revision_fila)} registros")
    wb.close()
    return buf.getvalue()


def nombre_base_marcada(nombre_original: str) -> str:
    base = nombre_original.rsplit(".", 1)[0]
    return f"{base}_MARCADA.xlsx"


def generar_bases_marcadas(ejecucion: ResultadoEjecucion, preparados: list[ArchivoPreparado]) -> dict[str, bytes]:
    """{nombre de la copia: contenido} para cada archivo validado."""
    hojas = {ap.nombre: ap.hoja for ap in preparados if ap.hoja is not None}
    out = {}
    for a in ejecucion.archivos:
        if a.archivo in hojas:
            out[nombre_base_marcada(a.archivo)] = generar_base_marcada(ejecucion, a, hojas[a.archivo])
    return out
