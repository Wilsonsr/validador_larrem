"""Historial de ejecuciones y comparación entre cortes.

Cada ejecución se guarda en `resultados/ejecuciones/<id>/` con un manifiesto (parámetros,
versiones, huellas de archivos y configuración, indicadores), el reporte Excel y un archivo
de seguimiento con las claves de los hallazgos (sin valores observados).

La comparación usa la clave de seguimiento `población|regla|variable|registro`. La fila de
Excel no se usa como clave porque cambia entre entregas. En Streamlit Cloud el disco no es
persistente: allí la comparación se hace subiendo el reporte de la ejecución anterior.
"""
from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .motor import RAIZ_PROYECTO, Hallazgo, ResultadoEjecucion, indicadores

DIR_EJECUCIONES = RAIZ_PROYECTO / "resultados" / "ejecuciones"
HOJA_HALLAZGOS = "B_Hallazgos"
COLUMNA_CLAVE = "Clave de seguimiento"
ESTADOS_SEGUIMIENTO = ["pendiente", "confirmado", "corregido en origen", "excepción justificada", "cerrado"]


@dataclass
class HallazgoPrevio:
    clave: str
    poblacion: str
    regla: str
    variable: str
    id_registro: str
    severidad: str = ""
    estado_equipo: str = ""
    observacion_equipo: str = ""

    @property
    def comparable(self) -> bool:
        return not self.id_registro.startswith("FILA")

    @property
    def ocurrencia(self) -> int:
        return int(self.clave.split("#")[1]) if "#" in self.clave else 1


@dataclass
class Comparacion:
    id_previa: str
    avisos: list[str] = field(default_factory=list)
    nuevos: list[Hallazgo] = field(default_factory=list)
    persistentes: list[tuple[Hallazgo, HallazgoPrevio]] = field(default_factory=list)
    resueltos: list[HallazgoPrevio] = field(default_factory=list)
    no_comparables_actuales: list[Hallazgo] = field(default_factory=list)
    no_comparables_previos: list[HallazgoPrevio] = field(default_factory=list)

    def resumen(self) -> dict[str, int]:
        return {
            "nuevos": len(self.nuevos), "persistentes": len(self.persistentes), "resueltos": len(self.resueltos),
            "no_comparables_actuales": len(self.no_comparables_actuales),
            "no_comparables_previos": len(self.no_comparables_previos),
        }


def _desde_clave(clave: str, **extra: str) -> HallazgoPrevio:
    partes = clave.split("#")[0].split("|")
    if len(partes) != 4:
        raise ValueError(f"Clave de seguimiento inválida: {clave!r}")
    return HallazgoPrevio(clave, *partes, **extra)


def leer_previos_desde_reporte(origen: str | Path | bytes) -> tuple[list[HallazgoPrevio], dict[str, str]]:
    """Lee la hoja de hallazgos de un reporte Excel generado por el validador (incluye las
    columnas de estado y observación que haya diligenciado el equipo)."""
    import openpyxl

    fuente = io.BytesIO(origen) if isinstance(origen, (bytes, bytearray)) else origen
    wb = openpyxl.load_workbook(fuente, read_only=True, data_only=True)
    if HOJA_HALLAZGOS not in wb.sheetnames:
        raise ValueError(f"El archivo no tiene la hoja {HOJA_HALLAZGOS}: no parece un reporte del validador.")
    meta = {"id_ejecucion": "", "version_configuracion": "", "huella_configuracion": ""}
    etiquetas = {"Identificador de ejecución": "id_ejecucion", "Versión de la configuración": "version_configuracion",
                 "Huella de la configuración": "huella_configuracion"}
    if "A_Resumen" in wb.sheetnames:
        for fila in wb["A_Resumen"].iter_rows(min_row=1, max_row=20, values_only=True):
            if fila and fila[0] in etiquetas:
                meta[etiquetas[fila[0]]] = str(fila[1])
    filas = wb[HOJA_HALLAZGOS].iter_rows(values_only=True)
    encabezado: list[str] | None = None
    for fila in filas:
        if fila and COLUMNA_CLAVE in fila:
            encabezado = [str(c) if c is not None else "" for c in fila]
            break
    if encabezado is None:
        raise ValueError(f"No se encontró la columna '{COLUMNA_CLAVE}' en {HOJA_HALLAZGOS}.")
    i = {n: k for k, n in enumerate(encabezado)}
    out = []
    for fila in filas:
        if not fila or fila[i[COLUMNA_CLAVE]] in (None, ""):
            continue

        def val(col: str) -> str:
            k = i.get(col)
            return "" if k is None or k >= len(fila) or fila[k] is None else str(fila[k])

        out.append(_desde_clave(str(fila[i[COLUMNA_CLAVE]]), severidad=val("Severidad"),
                                estado_equipo=val("Estado del hallazgo"), observacion_equipo=val("Observación del equipo")))
    wb.close()
    return out, meta


def leer_previos_desde_ejecucion(carpeta: str | Path) -> tuple[list[HallazgoPrevio], dict[str, str]]:
    carpeta = Path(carpeta)
    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    out = []
    with open(carpeta / "seguimiento.csv", encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            out.append(_desde_clave(fila["clave"], severidad=fila.get("severidad", "")))
    return out, {k: manifiesto.get(k, "") for k in ("id_ejecucion", "version_configuracion", "huella_configuracion")}


def _reglas_evaluadas(res: ResultadoEjecucion) -> set[tuple[str, str]]:
    """(población, regla) efectivamente ejecutadas en la ejecución actual."""
    out = set()
    for a in res.archivos:
        for rr in a.resumen_reglas:
            out.add((a.poblacion, rr.regla.id))
    cargadas = {a.poblacion for a in res.archivos}
    for rr in res.resumen_lote:
        # un cruce entre archivos solo es comparable si se cargaron todas las poblaciones que cruza
        if set(rr.regla.poblaciones) <= cargadas:
            for p in rr.poblacion.split(", "):
                out.add((p, rr.regla.id))
    return out


def comparar(res: ResultadoEjecucion, previos: list[HallazgoPrevio], meta_previa: dict[str, str] | None = None) -> Comparacion:
    meta_previa = meta_previa or {}
    comp = Comparacion(id_previa=meta_previa.get("id_ejecucion", ""))
    huella = meta_previa.get("huella_configuracion")
    if huella and huella != res.huella_reglas:
        comp.avisos.append(
            f"La ejecución anterior usó otra configuración de reglas ({meta_previa.get('version_configuracion')}, "
            f"huella {huella}; ahora {res.version_configuracion}, huella {res.huella_reglas}). Parte de los nuevos y "
            "resueltos puede deberse al cambio de reglas y no a correcciones en la base.")
    evaluadas = _reglas_evaluadas(res)
    previos_por_clave = {p.clave: p for p in previos if p.comparable}
    comp.no_comparables_previos = [p for p in previos if not p.comparable]
    actuales: set[str] = set()
    for h in res.hallazgos:
        if h.id_registro.startswith("FILA"):
            comp.no_comparables_actuales.append(h)
            continue
        actuales.add(h.clave_seguimiento)
        prev = previos_por_clave.get(h.clave_seguimiento)
        if prev is None:
            comp.nuevos.append(h)
        else:
            comp.persistentes.append((h, prev))
    for clave, p in previos_por_clave.items():
        if clave in actuales:
            continue
        if (p.poblacion, p.regla) in evaluadas:
            comp.resueltos.append(p)
        else:
            # la población no se cargó o la regla no se ejecutó: no se puede afirmar que se resolvió
            comp.no_comparables_previos.append(p)
    return comp


def manifiesto(res: ResultadoEjecucion) -> dict[str, Any]:
    return {
        "id_ejecucion": res.id_ejecucion,
        "fecha_hora": res.fecha_hora.isoformat(timespec="seconds"),
        "tematica": res.tematica,
        "version_motor": res.version_motor,
        "version_configuracion": res.version_configuracion,
        "huella_configuracion": res.huella_reglas,
        "duracion_segundos": res.duracion_segundos,
        "parametros": res.parametros.como_dict(),
        "archivos": [
            {"archivo": a.archivo, "sha256": a.sha256, "hoja": a.hoja, "poblacion": a.poblacion,
             "registros": a.registros, "fila_encabezado": a.fila_encabezado,
             "fecha_encuesta_min": a.fechas_encuesta[0].isoformat() if a.fechas_encuesta[0] else None,
             "fecha_encuesta_max": a.fechas_encuesta[1].isoformat() if a.fechas_encuesta[1] else None,
             "huella_columnas": a.estructura.huella_encontrada,
             "coincide_con_instrumento": a.estructura.huella_encontrada == a.estructura.huella_esperada}
            for a in res.archivos
        ],
        "indicadores": indicadores(res),
        "hallazgos_por_regla": dict(Counter(h.regla for h in res.hallazgos).most_common()),
        "avisos": res.avisos,
    }


def guardar_ejecucion(res: ResultadoEjecucion, reporte_xlsx: bytes | None = None,
                      directorio: str | Path | None = None) -> Path:
    base = Path(directorio or DIR_EJECUCIONES)
    carpeta = base / res.id_ejecucion
    n = 2
    while carpeta.exists():
        carpeta = base / f"{res.id_ejecucion}-{n}"
        n += 1
    carpeta.mkdir(parents=True)
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto(res), ensure_ascii=False, indent=2), encoding="utf-8")
    with open(carpeta / "seguimiento.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clave", "severidad", "archivo", "fila_excel"])
        for h in res.hallazgos:
            w.writerow([h.clave_seguimiento, h.severidad, h.archivo, h.fila_excel])
    if reporte_xlsx is not None:
        (carpeta / f"reporte_{res.id_ejecucion}.xlsx").write_bytes(reporte_xlsx)
    return carpeta


def listar_ejecuciones(directorio: str | Path | None = None) -> list[dict[str, Any]]:
    base = Path(directorio or DIR_EJECUCIONES)
    if not base.exists():
        return []
    out = []
    for m in sorted(base.glob("*/manifiesto.json"), reverse=True):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
            d["carpeta"] = str(m.parent)
            out.append(d)
        except (OSError, json.JSONDecodeError):
            continue
    return out
