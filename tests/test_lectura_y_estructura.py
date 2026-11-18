from datetime import date

from conftest import libro_sintetico

from larrem.estructura import mapear_columnas
from larrem.lectura import leer_libro
from larrem.motor import preparar_archivo
from larrem.normalizacion import construir_celda, interpretar_fecha


def columnas(tem, pob):
    return [v.nombre for v in tem.poblacion(pob).variables]


def test_encabezado_desplazado_y_filas_vacias(tem):
    cols = columnas(tem, "menores5")
    filas = [[f"AR02E{i:06d}" if c == "No_Acta" else None for c in cols] for i in range(3)]
    filas.insert(1, [None] * len(cols))  # fila vacía intermedia
    datos = libro_sintetico(cols, filas, fila_encabezado=3, filas_previas=[["Título del reporte"], []])
    ap = preparar_archivo(tem, datos, "base.xlsx")
    assert ap.hoja.fila_encabezado == 3
    assert len(ap.hoja.filas) == 3
    assert [f for f, _ in ap.hoja.filas] == [4, 6, 7]  # filas de Excel reales


def test_deteccion_de_poblacion_por_columnas_y_acta(tem):
    for pob, pref in [("menores5", "AR02"), ("5a14", "AR03"), ("mayores60", "AR04")]:
        cols = columnas(tem, pob)
        filas = [[f"{pref}N{i:06d}" if c == "No_Acta" else None for c in cols] for i in range(5)]
        ap = preparar_archivo(tem, libro_sintetico(cols, filas), "sin_nombre.xlsx")
        assert ap.poblacion_detectada == pob
        assert ap.confianza == "alta"


def test_archivo_ambiguo_requiere_confirmacion(tem):
    datos = libro_sintetico(["ID_SIVIGILA", "No_Acta", "Subred"], [[1, "X1", "Subred Norte"]])
    ap = preparar_archivo(tem, datos, "otro.xlsx")
    assert ap.confianza == "baja"
    assert ap.poblacion is None


def test_columnas_nuevas_ausentes_y_equivalencias(tem):
    p = tem.poblacion("mayores60")
    cols = [v.nombre for v in p.variables]
    cols = ["P31_Cocinó_En_Su_Vida" if c == "P31_Cocicó_En_Su_Vida" else c for c in cols]  # nombre del diccionario
    cols.remove("Estrato")
    cols.append("Columna_Nueva")
    libro = leer_libro(libro_sintetico(cols, [[None] * len(cols)]), "a.xlsx")
    est = mapear_columnas(p, libro.hojas[0])
    assert est.correspondencias["P31_Cocicó_En_Su_Vida"].metodo == "equivalencia_explicita"
    assert "Estrato" in est.columnas_ausentes
    assert "Estrato" in est.ausentes_requeridas
    assert any(n == "Columna_Nueva" for _, n in est.columnas_nuevas)
    assert est.huella_encontrada != est.huella_esperada


def test_fechas():
    assert interpretar_fecha(construir_celda(date(2026, 3, 5)))[0] == date(2026, 3, 5)
    assert interpretar_fecha(construir_celda("05/03/2026"))[0] == date(2026, 3, 5)
    assert interpretar_fecha(construir_celda(46086))[0] == date(2026, 3, 5)  # número de serie de Excel
    assert interpretar_fecha(construir_celda("2026-13-40"))[0] is None


def test_identificacion_conserva_texto():
    c = construir_celda("0012345678")
    assert c.texto == "0012345678"
