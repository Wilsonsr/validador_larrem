"""Genera una copia anonimizada de una base LARREM para demostraciones y pruebas.

Reemplaza los datos personales directos (nombres, identificación, dirección, teléfono, celular,
correo, personal de campo, textos libres) por valores ficticios, de forma consistente: un mismo
valor original recibe siempre el mismo valor ficticio, así que las repeticiones (ID duplicado,
dirección repetida) se conservan y el validador encuentra los mismos hallazgos.
También se renumeran ID_SIVIGILA y No_Acta (se conserva el prefijo AR0x y la sigla de subred).

Se conservan las respuestas, las fechas, la localidad, la UPZ y el barrio. Por eso la copia
sigue teniendo riesgo residual de reidentificación: compártala solo para pruebas internas.

Uso:
  python herramientas/anonimizar_base.py BASE.xlsx [BASE2.xlsx ...] --salida carpeta/
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl
import xlsxwriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from larrem.motor import cargar_configuracion, preparar_archivo  # noqa: E402
from larrem.estructura import mapear_columnas  # noqa: E402

CODIGOS = {"999", "9999", "99", "8888", "7777", "SIN DATO", "NO TIENE", "NO PRESENTA", "0"}
NOMBRES = {"Nombre_Menor", "Nombre_adulto", "Nombre_Encuestado"}
PERSONAL_CAMPO = {"Encuestador", "Supervisor", "Digitador"}
IDENTIFICACIONES = {"Identificación", "Identificación_Encuestado", "Identificacion_Encuestado"}
CONTACTO = {"Telefono", "Celular"}
CORREOS = {"Correo_Electronico", "Correo_Electronico1"}
TEXTOS = {"Observaciones", "P26_Justificacion", "Justificacion_Lactancia"}
DIRECCIONES = {"Dirección"}


class Anonimizador:
    def __init__(self, semilla: int = 2026) -> None:
        self.rnd = random.Random(semilla)
        self.mapas: dict[str, dict[str, object]] = {}

    def _mapa(self, grupo: str) -> dict[str, object]:
        return self.mapas.setdefault(grupo, {})

    def _digitos(self, n: int) -> str:
        return "".join(self.rnd.choice("0123456789") for _ in range(n))

    def valor(self, variable: str, v: object) -> object:
        if v is None:
            return None
        texto = str(v).strip()
        if texto == "" or texto.upper() in CODIGOS:
            return v
        if variable in NOMBRES:
            m = self._mapa("nombre")
            return m.setdefault(texto.upper(), f"PERSONA FICTICIA {len(m) + 1:04d}")
        if variable in PERSONAL_CAMPO:
            m = self._mapa(variable)
            return m.setdefault(texto.upper(), f"{variable.upper()} {len(m) + 1:02d}")
        if variable in IDENTIFICACIONES:
            m = self._mapa("identificacion")
            if texto not in m:
                # conserva letras (sigla de documento extranjero) y longitud; cambia los dígitos
                nuevo = re.sub(r"\d", lambda _: self.rnd.choice("0123456789"), texto)
                if nuevo[:1] == "0" and texto[:1] != "0":
                    nuevo = "1" + nuevo[1:]
                m[texto] = nuevo
            return int(m[texto]) if isinstance(v, (int, float)) and str(m[texto]).isdigit() else m[texto]
        if variable in CONTACTO:
            m = self._mapa("contacto")
            if texto not in m:
                d = re.sub(r"\D", "", texto)
                pref = d[:3] if len(d) >= 3 else d
                m[texto] = pref + self._digitos(max(len(d) - len(pref), 0)) if d else texto
            nuevo = m[texto]
            return int(nuevo) if isinstance(v, (int, float)) and str(nuevo).isdigit() else nuevo
        if variable in CORREOS:
            m = self._mapa("correo")
            return m.setdefault(texto.lower(), f"usuario{len(m) + 1:04d}@correo.ficticio")
        if variable in DIRECCIONES:
            m = self._mapa("direccion")
            if texto.upper() not in m:
                m[texto.upper()] = re.sub(r"\d", lambda _: self.rnd.choice("123456789"), texto.upper())
            return m[texto.upper()]
        if variable in TEXTOS:
            return "[texto anonimizado]"
        if variable == "ID_SIVIGILA":
            m = self._mapa("id")
            return m.setdefault(texto, 900000 + len(m) + 1)
        if variable == "No_Acta":
            m = self._mapa("acta")
            if texto not in m:
                m[texto] = texto[:5] + self._digitos(max(len(texto) - 5, 6))
            return m[texto]
        return v


def anonimizar(ruta: Path, salida: Path, anon: Anonimizador) -> Path:
    tem = cargar_configuracion()
    ap = preparar_archivo(tem, ruta)
    if ap.hoja is None or ap.poblacion_detectada is None:
        raise SystemExit(f"{ruta.name}: no se reconoció la población")
    pob = tem.poblacion(ap.poblacion_detectada)
    est = mapear_columnas(pob, ap.hoja)
    por_indice = {c.indice: v for v, c in est.correspondencias.items()}
    destino = salida / f"DEMO_{ruta.stem}.xlsx"
    wb = xlsxwriter.Workbook(destino, {"strings_to_numbers": False, "strings_to_formulas": False,
                                       "strings_to_urls": False})
    ws = wb.add_worksheet(ap.hoja.hoja[:31])
    f_fecha = wb.add_format({"num_format": "dd/mm/yyyy"})
    f_enc = wb.add_format({"bold": True})
    fila_enc = ap.hoja.fila_encabezado - 1
    for c, nombre in enumerate(ap.hoja.encabezados):
        ws.write_string(fila_enc, c, nombre, f_enc)
    for fila, valores in ap.hoja.filas:
        for c, v in enumerate(valores[:len(ap.hoja.encabezados)]):
            v = anon.valor(por_indice.get(c, ""), v)
            if v is None:
                continue
            if isinstance(v, datetime):
                ws.write_datetime(fila - 1, c, v, f_fecha)
            elif isinstance(v, date):
                ws.write_datetime(fila - 1, c, datetime(v.year, v.month, v.day), f_fecha)
            elif isinstance(v, bool):
                ws.write_boolean(fila - 1, c, v)
            elif isinstance(v, (int, float)):
                ws.write_number(fila - 1, c, v)
            else:
                ws.write_string(fila - 1, c, str(v))
    ley = wb.add_worksheet("LEEME")
    ley.set_column(0, 0, 110)
    for i, t in enumerate([
        "BASE DE DEMOSTRACIÓN ANONIMIZADA – solo para pruebas del validador LARREM.",
        "Nombres, identificación, dirección, teléfono, celular, correo, personal de campo y textos libres son ficticios.",
        "ID_SIVIGILA y No_Acta fueron renumerados. Las respuestas, fechas, localidad, UPZ y barrio se conservan.",
        "No la use para reportes ni análisis oficiales. Compártala solo para pruebas internas.",
    ]):
        ley.write(i, 0, t)
    wb.close()
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archivos", nargs="+", type=Path)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    a.salida.mkdir(parents=True, exist_ok=True)
    anon = Anonimizador()  # un solo mapa para todas las bases: los cruces entre poblaciones se conservan
    for ruta in a.archivos:
        print(anonimizar(ruta, a.salida, anon))
    return 0


if __name__ == "__main__":
    sys.exit(main())
