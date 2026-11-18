"""Utilidades de prueba. Todos los datos son sintéticos: no se usan las bases reales."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from larrem.configuracion import Regla  # noqa: E402
from larrem.motor import cargar_configuracion  # noqa: E402
from larrem.normalizacion import construir_celda  # noqa: E402
from larrem.reglas import Contexto, RegistroDatos  # noqa: E402


@pytest.fixture(scope="session")
def tem():
    return cargar_configuracion()


def registro(valores: dict, fila: int = 2, pob: str = "menores5", archivo: str = "prueba.xlsx", ident: str | None = None):
    return RegistroDatos(indice=fila - 2, archivo=archivo, hoja="H", fila_excel=fila,
                         valores={k: construir_celda(v) for k, v in valores.items()},
                         id_registro=ident or f"ID{fila}", poblacion=pob)


def regla(**kw) -> Regla:
    base = {"id": "PRUEBA", "descripcion": "regla de prueba", "fuentes": [{"doc": "T", "ubicacion": "prueba"}],
            "poblaciones": ["menores5"]}
    base.update(kw)
    return Regla(**base)


def ctx(**kw) -> Contexto:
    return Contexto(poblacion="menores5", **kw)


def libro_sintetico(encabezados: list[str], filas: list[list], fila_encabezado: int = 1, titulo_hoja: str = "Datos",
                    filas_previas: list[list] | None = None) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo_hoja
    for i, f in enumerate(filas_previas or [], start=1):
        for j, v in enumerate(f, start=1):
            ws.cell(i, j, v)
    for j, h in enumerate(encabezados, start=1):
        ws.cell(fila_encabezado, j, h)
    for i, f in enumerate(filas, start=fila_encabezado + 1):
        for j, v in enumerate(f, start=1):
            ws.cell(i, j, v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
