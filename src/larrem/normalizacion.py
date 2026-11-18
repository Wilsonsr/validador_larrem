"""Normalización trazable de valores de celda.

Cada celda conserva su valor original y expone vistas normalizadas. Ninguna
transformación cambia el dato de captura: solo se usa para comparar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

ERRORES_EXCEL = {"#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!", "#GETTING_DATA", "#SPILL!", "#CALC!"}

_ESPACIOS = re.compile(r"\s+")
_FORMATOS_FECHA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S")
_EPOCA_EXCEL = datetime(1899, 12, 30)


def clave_texto(valor: str) -> str:
    """Clave de comparación: sin tildes, mayúsculas, espacios colapsados.

    Se usa solo para comparar categorías; nunca reemplaza el valor original.
    """
    s = unicodedata.normalize("NFKD", valor)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _ESPACIOS.sub(" ", s).strip().upper()
    return s


def clave_nombre_columna(nombre: str) -> str:
    """Clave para reconocer encabezados: quita tildes, mayúsculas, espacios y signos.

    Se usa solo para *detectar* equivalencias y reportarlas; nunca se aplica en silencio.
    """
    s = clave_texto(nombre)
    return re.sub(r"[^A-Z0-9]", "", s)


@dataclass
class Celda:
    original: object
    texto: str = ""            # representación textual sin espacios externos
    clave: str = ""            # clave de comparación normalizada
    numero: float | None = None
    fecha: date | None = None
    vacia: bool = True
    error_excel: bool = False
    notas: list[str] = field(default_factory=list)

    def es_numero_entero(self) -> bool:
        return self.numero is not None and float(self.numero).is_integer()


def _texto_desde_original(v: object) -> tuple[str, list[str]]:
    notas: list[str] = []
    if v is None:
        return "", notas
    if isinstance(v, bool):
        return ("1" if v else "0"), ["valor booleano"]
    if isinstance(v, int):
        return str(v), notas
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v)), notas
        return repr(v), notas
    if isinstance(v, datetime):
        if v.time() == datetime.min.time():
            return v.date().isoformat(), notas
        return v.isoformat(sep=" "), notas
    if isinstance(v, date):
        return v.isoformat(), notas
    s = str(v)
    t = s.strip()
    if t != s:
        notas.append("espacios externos recortados")
    return t, notas


def a_numero(texto: str) -> float | None:
    if texto == "":
        return None
    t = texto.replace(",", ".") if re.fullmatch(r"-?\d+,\d+", texto) else texto
    try:
        return float(t)
    except ValueError:
        return None


def construir_celda(v: object) -> Celda:
    texto, notas = _texto_desde_original(v)
    c = Celda(original=v, texto=texto, notas=notas)
    c.vacia = texto == ""
    if isinstance(v, str) and texto.upper() in ERRORES_EXCEL:
        c.error_excel = True
        c.notas.append("celda con error de Excel")
    c.clave = clave_texto(texto) if texto else ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        c.numero = float(v)
    elif not c.vacia and not c.error_excel:
        c.numero = a_numero(texto)
    if isinstance(v, datetime):
        c.fecha = v.date()
    elif isinstance(v, date):
        c.fecha = v
    return c


def interpretar_fecha(c: Celda) -> tuple[date | None, str | None]:
    """Interpreta una celda como fecha de forma explícita.

    Devuelve (fecha, nota). Una nota indica la transformación aplicada o el motivo del fallo.
    """
    if c.fecha is not None:
        return c.fecha, None
    if c.vacia or c.error_excel:
        return None, "vacía o con error"
    if isinstance(c.original, (int, float)) and not isinstance(c.original, bool):
        n = float(c.original)
        if 20000 <= n <= 80000:  # serial de Excel aproximadamente entre 1954 y 2119
            return (_EPOCA_EXCEL + timedelta(days=int(n))).date(), "convertida desde número de serie de Excel"
        return None, "número que no corresponde a una fecha"
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(c.texto, fmt).date(), f"interpretada con formato {fmt}"
        except ValueError:
            continue
    return None, "texto que no corresponde a una fecha con formato dd/mm/aaaa"


def codigo(c: Celda) -> str | None:
    """Representación canónica de un código: '1' para 1, 1.0 o ' 1 '."""
    if c.vacia or c.error_excel:
        return None
    if c.numero is not None and c.es_numero_entero() and re.fullmatch(r"-?\d+(\.0+)?", c.texto.replace(",", ".")):
        return str(int(c.numero))
    return c.clave


def clave_valor_config(v: object) -> str:
    """Clave canónica para valores escritos en la configuración."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if re.fullmatch(r"-?\d+", s):
        return str(int(s))
    return clave_texto(s)
