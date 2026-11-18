"""Validación por línea de comandos (sin interfaz).

Ejemplo:
  python herramientas/validar_cli.py --inicio 2026-01-01 --fin 2026-06-30 ruta/base1.xlsx ruta/base2.xlsx
  python herramientas/validar_cli.py --inicio 2026-07-01 --fin 2026-12-31 --anterior resultados/ejecuciones/<id> bases/*.xlsx

Guarda el reporte y el manifiesto en resultados/ejecuciones/<id>/ y muestra un resumen.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from larrem.historial import (comparar, guardar_ejecucion, leer_previos_desde_ejecucion,  # noqa: E402
                              leer_previos_desde_reporte)
from larrem.motor import Parametros, cargar_configuracion, indicadores, preparar_archivo, validar  # noqa: E402
from larrem.reportes import generar_reporte  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Validador de bases LARREM")
    ap.add_argument("archivos", nargs="+", type=Path)
    ap.add_argument("--inicio", type=date.fromisoformat, required=True, help="inicio del periodo esperado (AAAA-MM-DD)")
    ap.add_argument("--fin", type=date.fromisoformat, required=True, help="fin del periodo esperado (AAAA-MM-DD)")
    ap.add_argument("--etapa", choices=["captura", "recodificacion", "enriquecimiento"], default="recodificacion")
    ap.add_argument("--subred", action="append", default=[], help="subred esperada (repetible)")
    ap.add_argument("--poblacion", action="append", default=[], metavar="ARCHIVO=CODIGO",
                    help="fuerza la población de un archivo (menores5, 5a14, mayores60)")
    ap.add_argument("--anterior", type=Path, help="carpeta de una ejecución guardada o reporte .xlsx anterior")
    ap.add_argument("--mostrar-datos-personales", action="store_true")
    ap.add_argument("--marcar", action="store_true",
                    help="genera también una copia de cada base con los errores y alertas marcados")
    ap.add_argument("--salida", type=Path, help="carpeta del historial (por defecto resultados/ejecuciones)")
    a = ap.parse_args()

    tem = cargar_configuracion()
    forzadas = dict(x.split("=", 1) for x in a.poblacion)
    preparados = []
    for ruta in a.archivos:
        prep = preparar_archivo(tem, ruta)
        if ruta.name in forzadas:
            prep.poblacion = forzadas[ruta.name]
        estado = prep.poblacion or "SIN CONFIRMAR (use --poblacion)"
        print(f"{ruta.name}: población {estado} (detectada {prep.poblacion_detectada}, confianza {prep.confianza})")
        preparados.append(prep)
    res = validar(tem, preparados, Parametros(a.inicio, a.fin, subredes=a.subred, etapa=a.etapa))
    comp = None
    if a.anterior:
        prev, meta = (leer_previos_desde_ejecucion(a.anterior) if a.anterior.is_dir()
                      else leer_previos_desde_reporte(a.anterior.read_bytes()))
        comp = comparar(res, prev, meta)
    xlsx = generar_reporte(res, comp, ocultar_datos_personales=not a.mostrar_datos_personales)
    carpeta = guardar_ejecucion(res, xlsx, a.salida)
    if a.marcar:
        from larrem.marcado import generar_bases_marcadas
        destino = carpeta / "bases_marcadas"
        destino.mkdir()
        for nombre, contenido in generar_bases_marcadas(res, preparados).items():
            (destino / nombre).write_bytes(contenido)
            print(f"Base marcada: {destino / nombre}")
    ind = indicadores(res)
    print(f"\nEjecución {res.id_ejecucion} ({res.duracion_segundos} s) → {carpeta}")
    print(f"Registros: {ind['registros']} · hallazgos: {ind['hallazgos_total']} "
          f"en {ind['registros_afectados_total']} registros")
    for s, n in sorted(ind["hallazgos_por_severidad"].items()):
        print(f"  {s}: {n} hallazgos, {ind['registros_por_severidad'][s]} registros")
    print(f"No evaluables: {ind['resultados_no_evaluables']} · reglas no ejecutadas: {ind['reglas_no_ejecutadas']}")
    if comp:
        print("Comparación:", comp.resumen())
        for av in comp.avisos:
            print("AVISO:", av)
    for av in res.avisos:
        print("AVISO:", av)
    return 0


if __name__ == "__main__":
    sys.exit(main())
