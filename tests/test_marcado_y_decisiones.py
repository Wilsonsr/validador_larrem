import io
from datetime import date

import openpyxl
from conftest import ctx, registro
from test_motor_reportes_historial import PAR, base_menores5

from larrem.marcado import COLUMNAS_RESUMEN, generar_bases_marcadas, nombre_base_marcada
from larrem.motor import preparar_archivo, validar
from larrem.reglas import CUMPLE, IMPLEMENTACIONES


def _regla(tem, rid):
    return next(r for r in tem.reglas if r.id == rid)


def test_dp02_doce_meses_categoria_2(tem):
    r = _regla(tem, "M5_EDAD_COD")
    res = list(IMPLEMENTACIONES[r.tipo](r, [registro({"Edad_Meses": 12, "Edad_Meses_COD": 2})], ctx()))
    assert res[0].estado == CUMPLE


def test_dp03_propano_categoria_1(tem):
    for rid, origen in [("M5_ENERGIA_COD", "P60_Energia_Cocina"), ("E_ENERGIA_COD", "P67_Energía_Cocina")]:
        r = _regla(tem, rid)
        reg = registro({origen: "Gas Propano", "ENERGIA COCINAR CODIF.": 1})
        assert list(IMPLEMENTACIONES[r.tipo](r, [reg], ctx()))[0].estado == CUMPLE


def test_dp06_dieciseis_cigarrillos_severo(tem):
    r = _regla(tem, "A_NIVEL_CONSUMO")
    reg = registro({"P18_Fuma": 1, "P21_Cuantos_Cigarrillos": 16, "NIVEL CONSUMO TABACO TOTAL": "Severo"}, pob="mayores60")
    assert list(IMPLEMENTACIONES[r.tipo](r, [reg], ctx()))[0].estado == CUMPLE


def test_decisiones_respondidas_registradas(tem):
    resp = {d.id: d for d in tem.decisiones}
    for dp in ("DP-02", "DP-03", "DP-06"):
        assert resp[dp].respuesta and resp[dp].fecha_respuesta


def test_base_marcada_conserva_valores_y_marca_errores(tem):
    original = base_menores5(tem)
    ap = preparar_archivo(tem, original, "m5.xlsx")
    res = validar(tem, [ap], PAR)
    copia_original = bytes(original)
    out = generar_bases_marcadas(res, [ap])
    assert list(out) == [nombre_base_marcada("m5.xlsx")] == ["m5_MARCADA.xlsx"]
    assert original == copia_original  # el original no cambia
    wb_o = openpyxl.load_workbook(io.BytesIO(original))
    wb_m = openpyxl.load_workbook(io.BytesIO(out["m5_MARCADA.xlsx"]))
    o, m = wb_o.worksheets[0], wb_m.worksheets[0]
    assert "Leyenda_validacion" in wb_m.sheetnames
    for fila in range(1, o.max_row + 1):
        for col in range(1, o.max_column + 1):
            a, b = o.cell(fila, col).value, m.cell(fila, col).value
            assert a == b or (a in (None, "") and b in (None, "")), (fila, col, a, b)
    enc = [m.cell(1, c).value for c in range(1, m.max_column + 1)]
    assert enc[-4:] == COLUMNAS_RESUMEN
    # el ID duplicado (filas 2 y 3) se marca en la celda del ID con un comentario
    col_id = enc.index("ID_SIVIGILA") + 1
    for fila in (2, 3):
        celda = m.cell(fila, col_id)
        assert celda.comment is not None and "BLOQUEANTE" in celda.comment.text
    # la revisión humana se colorea, pero no suma en la columna de hallazgos
    errores = [h for h in res.hallazgos if h.severidad in ("bloqueante", "error", "alerta")]
    col_n = len(enc) - 3
    assert sum(m.cell(f, col_n).value or 0 for f in range(2, m.max_row + 1)) == len(errores)


def _tabaquismo(tem, cig, frec, tiempo, periodo, observado, p18=None, p19=None):
    r = _regla(tem, "A_TABAQUISMO_PESADO")
    fumador = cig != 999
    reg = registro({"P18_Fuma": p18 if p18 is not None else 2, "P19_Fumó_En_Algun_Momento": p19 if p19 is not None else (1 if fumador else 2),
                    "P21_Cuantos_Cigarrillos": cig, "P20_Frecuencia": frec, "P23_Tiempo_Fumar": tiempo,
                    "P23_Periodo_Fumar": periodo, "TABAQUISMO PESADO": observado}, pob="mayores60")
    return list(IMPLEMENTACIONES[r.tipo](r, [reg], ctx()))[0]


def test_tabaquismo_semanal_se_divide_entre_7(tem):
    # 5 cigarrillos semanales × 60 años: 5/7 × 60 / 20 = 2,1 → no pesado
    assert _tabaquismo(tem, 5, "Semanal", 60, "Año(s)", 2).estado == CUMPLE
    assert _tabaquismo(tem, 5, "Semanal", 60, "Año(s)", 1).estado != CUMPLE


def test_tabaquismo_diario_meses_y_umbral(tem):
    assert _tabaquismo(tem, 10, "Diario", 20, "Año(s)", 1).estado == CUMPLE      # 10 exacto = pesado
    assert _tabaquismo(tem, 20, "Diario", 6, "Mes(es)", 2).estado == CUMPLE      # 20 × 0,5 / 20 = 0,5
    assert _tabaquismo(tem, 999, "999", 999, "999", 2).estado == CUMPLE          # nunca fumó = 2


def test_tabaquismo_usa_p18_y_p19(tem):
    from larrem.reglas import INCUMPLE, NO_EVALUABLE
    # fuma hoy (P18 = 1) aunque P19 diga 2: se calcula
    assert _tabaquismo(tem, 20, "Diario", 40, "Año(s)", 1, p18=1, p19=2).estado == CUMPLE
    # caso A: nunca fumó pero tiene cigarrillos anotados: se exige 2, no se calcula
    assert _tabaquismo(tem, 20, "Diario", 40, "Año(s)", 2, p18=2, p19=2).estado == CUMPLE
    assert _tabaquismo(tem, 20, "Diario", 40, "Año(s)", 1, p18=2, p19=2).estado == INCUMPLE
    # caso B: dice que fumó pero los cigarrillos están en 999: falta el dato
    r = _tabaquismo(tem, 999, "999", 999, "999", 2, p18=2, p19=1)
    assert r.estado == NO_EVALUABLE and "faltan cigarrillos" in r.motivo
