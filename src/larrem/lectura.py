"""Lectura robusta de libros Excel.

- Detecta hoja y fila de encabezado.
- Ignora filas realmente vacías y no recorre rangos sobredimensionados indefinidamente.
- Conserva archivo, hoja y fila original de cada registro.
- No convierte errores de lectura en vacíos: los marca.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from .normalizacion import clave_nombre_columna

MAX_FILAS_VACIAS_CONSECUTIVAS = 2000
FILAS_BUSQUEDA_ENCABEZADO = 30


@dataclass
class HojaLeida:
    archivo: str
    hoja: str
    fila_encabezado: int
    encabezados: list[str]                 # nombre original de cada columna (texto)
    filas: list[tuple[int, tuple]]         # (fila_excel, valores)
    dimension_declarada: str
    max_fila_declarada: int | None
    ultima_fila_con_contenido: int
    filas_vacias_omitidas: int
    lectura_detenida_por_vacias: bool
    otras_hojas: list[str] = field(default_factory=list)
    puntaje_encabezado: int = 0
    avisos: list[str] = field(default_factory=list)


@dataclass
class LibroLeido:
    archivo: str
    sha256: str
    tamano_bytes: int
    hojas: list[HojaLeida]
    avisos: list[str] = field(default_factory=list)


def _es_vacia(fila: tuple) -> bool:
    for v in fila:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return False
    return True


def huella_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def leer_libro(origen: str | Path | bytes, nombre: str | None = None,
               nombres_conocidos: set[str] | None = None) -> LibroLeido:
    """Lee todas las hojas con contenido de un libro.

    `nombres_conocidos` (claves normalizadas de variables) ayuda a reconocer la fila de encabezado.
    """
    if isinstance(origen, (str, Path)):
        ruta = Path(origen)
        datos = ruta.read_bytes()
        nombre = nombre or ruta.name
    else:
        datos = origen
        nombre = nombre or "archivo.xlsx"
    libro = LibroLeido(archivo=nombre, sha256=huella_bytes(datos), tamano_bytes=len(datos), hojas=[])
    try:
        wb = openpyxl.load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - se informa al usuario
        libro.avisos.append(f"No fue posible abrir el archivo como Excel (.xlsx): {exc}")
        return libro
    conocidos = nombres_conocidos or set()
    try:
        nombres_hojas = list(wb.sheetnames)
        for ws in wb.worksheets:
            hoja = _leer_hoja(ws, nombre, conocidos)
            if hoja is not None:
                hoja.otras_hojas = [h for h in nombres_hojas if h != ws.title]
                libro.hojas.append(hoja)
    finally:
        wb.close()
    if not libro.hojas:
        libro.avisos.append("El libro no contiene hojas con datos.")
    return libro


def _leer_hoja(ws, archivo: str, conocidos: set[str]) -> HojaLeida | None:
    try:
        dimension = ws.calculate_dimension()
    except Exception:  # noqa: BLE001
        dimension = "desconocida"
    max_decl = ws.max_row
    candidatos: list[tuple[int, tuple]] = []
    filas: list[tuple[int, tuple]] = []
    vacias_seguidas = 0
    vacias_total = 0
    detenida = False
    ultima = 0
    for i, fila in enumerate(ws.iter_rows(values_only=True), start=1):
        if _es_vacia(fila):
            vacias_seguidas += 1
            vacias_total += 1
            if vacias_seguidas >= MAX_FILAS_VACIAS_CONSECUTIVAS:
                detenida = max_decl is not None and i < max_decl
                break
            continue
        vacias_seguidas = 0
        ultima = i
        if len(candidatos) < FILAS_BUSQUEDA_ENCABEZADO:
            candidatos.append((i, fila))
        filas.append((i, fila))
    if not filas:
        return None

    # Encabezado: la fila (entre las primeras) con más nombres reconocidos; si no hay
    # nombres conocidos, la primera fila con contenido mayoritariamente textual.
    mejor_i, mejor_p = candidatos[0][0], -1
    for i, fila in candidatos:
        textos = [str(v).strip() for v in fila if isinstance(v, str) and v.strip()]
        puntaje = sum(1 for t in textos if clave_nombre_columna(t) in conocidos) if conocidos else len(textos)
        if puntaje > mejor_p:
            mejor_i, mejor_p = i, puntaje
    fila_enc = next(f for i, f in filas if i == mejor_i)
    # recortar columnas vacías al final del encabezado
    n = len(fila_enc)
    while n > 0 and (fila_enc[n - 1] is None or (isinstance(fila_enc[n - 1], str) and not fila_enc[n - 1].strip())):
        n -= 1
    encabezados = ["" if v is None else str(v).strip() for v in fila_enc[:n]]
    datos = [(i, tuple(f[:n]) + (None,) * max(0, n - len(f))) for i, f in filas if i > mejor_i]
    # filas con contenido fuera de las columnas con encabezado
    fuera = sum(1 for i, f in filas if i > mejor_i and len(f) > n and not _es_vacia(f[n:]))
    hoja = HojaLeida(
        archivo=archivo, hoja=ws.title, fila_encabezado=mejor_i, encabezados=encabezados, filas=datos,
        dimension_declarada=dimension, max_fila_declarada=max_decl, ultima_fila_con_contenido=ultima,
        filas_vacias_omitidas=max(0, (ultima - mejor_i) - len(datos)),
        lectura_detenida_por_vacias=detenida, puntaje_encabezado=max(mejor_p, 0),
    )
    if mejor_i != 1:
        hoja.avisos.append(f"El encabezado se detectó en la fila {mejor_i}, no en la fila 1.")
    if max_decl and max_decl > ultima + 1000:
        hoja.avisos.append(
            f"La hoja declara un rango hasta la fila {max_decl:,} pero la última fila con contenido es la {ultima:,}. "
            "Se leyó solo el contenido real.".replace(",", "."))
    if detenida:
        hoja.avisos.append(
            f"La lectura se detuvo tras {MAX_FILAS_VACIAS_CONSECUTIVAS} filas vacías consecutivas después de la fila {ultima}. "
            "Si existe contenido más abajo, elimine las filas vacías intermedias y vuelva a cargar el archivo.")
    if fuera:
        hoja.avisos.append(f"{fuera} filas tienen valores en columnas sin encabezado; esos valores no se validan.")
    return hoja
