from datetime import date

import openpyxl
import pytest
from conftest import libro_sintetico

from larrem.historial import (HallazgoPrevio, comparar, guardar_ejecucion, leer_previos_desde_ejecucion,
                              leer_previos_desde_reporte, listar_ejecuciones)
from larrem.motor import Parametros, indicadores, preparar_archivo, validar
from larrem.reglas import INCUMPLE
from larrem.reportes import generar_reporte

PAR = Parametros(date(2026, 1, 1), date(2026, 6, 30))


def base_menores5(tem, n=4, duplicar_id=True, fecha=date(2026, 3, 10), extra=None):
    cols = [v.nombre for v in tem.poblacion("menores5").variables]
    filas = []
    for i in range(n):
        f = {c: None for c in cols}
        f.update({"ID_SIVIGILA": 1000 + (0 if duplicar_id and i < 2 else i), "No_Acta": f"AR02E{i:06d}",
                  "Subred": "Subred Centro Oriente", "Fecha_Encuesta": fecha, "Fecha_Nacimiento": date(2024, 1, 15),
                  "Edad_Meses": 25, "Identificación": f"10{i:08d}", "Tipo_Documento": "NUIP",
                  "Nombre_Menor": "NOMBRE SINTÉTICO"})
        f.update(extra or {})
        filas.append([f[c] for c in cols])
    return libro_sintetico(cols, filas)


@pytest.fixture(scope="module")
def ejecucion(tem):
    ap = preparar_archivo(tem, base_menores5(tem), "sintetica_m5.xlsx")
    return validar(tem, [ap], PAR, id_ejecucion="prueba-1")


def test_totales_cuadran(ejecucion):
    ind = indicadores(ejecucion)
    assert ind["registros"] == 4
    incumple = sum(rr.conteos[INCUMPLE] for a in ejecucion.archivos for rr in a.resumen_reglas)
    incumple += sum(rr.conteos[INCUMPLE] for rr in ejecucion.resumen_lote)
    assert incumple == ind["hallazgos_total"] == len(ejecucion.hallazgos)
    assert sum(ind["hallazgos_por_severidad"].values()) == ind["hallazgos_total"]
    assert ind["registros_afectados_total"] <= ind["registros"]


def test_id_duplicado_es_bloqueante(ejecucion):
    dup = [h for h in ejecucion.hallazgos if h.regla == "COM_ID_UNICO"]
    assert {h.fila_excel for h in dup} == {2, 3}
    assert all(h.severidad == "bloqueante" for h in dup)


def test_campos_vacios_generan_obligatoriedad(ejecucion):
    assert any(h.regla == "M5_OBLIGATORIAS_CAPTURA" for h in ejecucion.hallazgos)


def test_fuera_de_periodo(tem):
    ap = preparar_archivo(tem, base_menores5(tem, fecha=date(2026, 9, 1)), "m5.xlsx")
    res = validar(tem, [ap], PAR)
    assert any(h.regla.endswith("PERIODO") or "PERIODO" in h.regla for h in res.hallazgos)


def test_reporte_hojas_y_datos_personales(ejecucion):
    x = generar_reporte(ejecucion)
    import io
    wb = openpyxl.load_workbook(io.BytesIO(x), read_only=True)
    assert wb.sheetnames[:4] == ["A_Resumen", "B_Hallazgos", "C_No_evaluables", "D_Estructura"]
    filas = list(wb["B_Hallazgos"].iter_rows(values_only=True))
    assert len(filas) - 1 == len(ejecucion.hallazgos)
    texto = " ".join(str(c) for f in filas for c in f if c is not None)
    assert "NOMBRE SINTÉTICO" not in texto
    assert "1000000001" not in texto  # identificación oculta
    # sin ocultar, el valor sí aparece donde haya hallazgo sobre la variable personal
    x2 = generar_reporte(ejecucion, ocultar_datos_personales=False)
    assert x2 != x


def test_comparacion_nuevos_persistentes_resueltos(tem, ejecucion, tmp_path):
    previos, meta = leer_previos_desde_reporte(generar_reporte(ejecucion))
    assert meta["id_ejecucion"] == "prueba-1"
    assert len(previos) == len(ejecucion.hallazgos)
    # corte siguiente: se corrige el ID duplicado
    ap = preparar_archivo(tem, base_menores5(tem, duplicar_id=False), "sintetica_m5.xlsx")
    res2 = validar(tem, [ap], PAR, id_ejecucion="prueba-2")
    comp = comparar(res2, previos, meta)
    resueltos = {p.regla for p in comp.resueltos}
    assert "COM_ID_UNICO" in resueltos
    assert comp.persistentes
    assert not comp.avisos  # misma configuración
    # un hallazgo de una población no cargada queda como no comparable, no como resuelto
    ajeno = HallazgoPrevio("mayores60|A_X|V|123", "mayores60", "A_X", "V", "123")
    comp = comparar(res2, previos + [ajeno], meta)
    assert ajeno in comp.no_comparables_previos
    # historial en disco
    carpeta = guardar_ejecucion(res2, generar_reporte(res2, comp), tmp_path)
    assert (carpeta / "manifiesto.json").exists()
    prev2, meta2 = leer_previos_desde_ejecucion(carpeta)
    assert meta2["id_ejecucion"] == "prueba-2" and len(prev2) == len(res2.hallazgos)
    assert listar_ejecuciones(tmp_path)[0]["id_ejecucion"] == "prueba-2"


def test_aviso_si_cambia_la_configuracion(ejecucion):
    previos, meta = leer_previos_desde_reporte(generar_reporte(ejecucion))
    meta["huella_configuracion"] = "otra"
    assert comparar(ejecucion, previos, meta).avisos


def test_seguimiento_conserva_estado_del_equipo(tem, ejecucion, tmp_path):
    import io
    x = generar_reporte(ejecucion)
    wb = openpyxl.load_workbook(io.BytesIO(x))
    ws = wb["B_Hallazgos"]
    enc = [c.value for c in ws[1]]
    ws.cell(2, enc.index("Estado del hallazgo") + 1, "confirmado")
    ws.cell(2, enc.index("Observación del equipo") + 1, "se llamó a la subred")
    clave = ws.cell(2, 1).value
    buf = io.BytesIO()
    wb.save(buf)
    previos, meta = leer_previos_desde_reporte(buf.getvalue())
    comp = comparar(ejecucion, previos, meta)
    x2 = generar_reporte(ejecucion, comp)
    filas = list(openpyxl.load_workbook(io.BytesIO(x2), read_only=True)["B_Hallazgos"].iter_rows(values_only=True))
    fila = next(f for f in filas if f[0] == clave)
    assert "confirmado" in fila and "se llamó a la subred" in fila
