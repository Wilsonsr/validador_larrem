"""Cambios de la revisión del equipo del 14/11/2026 (docs/registro_solicitudes.csv)."""
import io

import openpyxl
from conftest import ctx, regla, registro
from test_motor_reportes_historial import PAR, base_menores5

from larrem.marcado import generar_bases_marcadas
from larrem.motor import preparar_archivo, validar
from larrem.reglas import CUMPLE, IMPLEMENTACIONES, INCUMPLE, NO_APLICA


def _r(tem, rid):
    return next(r for r in tem.reglas if r.id == rid)


def _uno(tem, rid, valores, pob="menores5"):
    r = _r(tem, rid)
    return list(IMPLEMENTACIONES[r.tipo](r, [registro(valores, pob=pob)], ctx()))[0]


def test_sol001_barrio_vacio_con_otro_barrio(tem):
    assert _uno(tem, "COM_BARRIO_REQUERIDO", {"Barrio": None, "Otro_Barrio": "VEREDA X"}).estado == CUMPLE
    assert _uno(tem, "COM_BARRIO_REQUERIDO", {"Barrio": None, "Otro_Barrio": None}).estado == INCUMPLE
    assert _uno(tem, "COM_BARRIO_REQUERIDO", {"Barrio": None}).estado == INCUMPLE  # la base no trae Otro_Barrio
    assert _uno(tem, "COM_BARRIO_REQUERIDO", {"Barrio": "CENTRO"}).estado == CUMPLE


def test_sol001_otro_barrio_no_cambia_la_estructura_esperada(tem):
    ap = preparar_archivo(tem, base_menores5(tem), "m5.xlsx")
    res = validar(tem, [ap], PAR)
    e = res.archivos[0].estructura
    assert "Otro_Barrio" not in e.columnas_ausentes


def test_sol002_p22_tiene_regla_propia(tem):
    assert "P22_Localidad" not in _r(tem, "M5_COLEGIO_LOCALIDAD_DOMINIO").variables
    assert _uno(tem, "M5_P22_LOCALIDAD_DOMINIO", {"P22_Localidad": "Kenedy"}).estado == INCUMPLE
    assert _uno(tem, "M5_P22_LOCALIDAD_DOMINIO", {"P22_Localidad": "Kennedy"}).estado == CUMPLE


def test_sol003_bajo_peso_no_se_ejecuta(tem):
    r = _r(tem, "M5_P21_P25_CONFIRMAR")
    assert not r.ejecutable and "SOL-003" in r.motivo_estado


def test_sol009_colegio_marca_solo_la_minoria():
    r = regla(tipo="consistencia_grupo", parametros={"clave": "Col", "dependiente": "Dir", "ignorar": [999], "marcar": "minoria"})
    regs = [registro({"Col": "A", "Dir": "KR 1"}, 2), registro({"Col": "A", "Dir": "KR 1"}, 3), registro({"Col": "A", "Dir": "KR 9"}, 4),
            registro({"Col": "B", "Dir": "CL 5"}, 5), registro({"Col": "B", "Dir": "CL 6"}, 6), registro({"Col": "C", "Dir": "CL 7"}, 7)]
    res = {x.registro.fila_excel: x.estado for x in IMPLEMENTACIONES[r.tipo](r, regs, ctx())}
    assert res == {2: CUMPLE, 3: CUMPLE, 4: INCUMPLE,   # mayoría clara: solo la distinta
                   5: INCUMPLE, 6: INCUMPLE,            # empate: se marcan las dos
                   7: CUMPLE}                           # un colegio mencionado una sola vez no se marca


def test_sol010_el_99_es_alerta(tem):
    for rid in ("M5_NSNR_REVISION", "E_NSNR_REVISION", "A_NSNR_REVISION"):
        assert _r(tem, rid).severidad == "alerta"


def test_sol011_ausentismo_99_cuando_asiste(tem):
    assert _uno(tem, "M5_AUSENTISMO_ASISTE", {"P3_Asiste_Colegio": 1, "P13_Ausentismo_Escolar": 99}).estado == INCUMPLE
    assert _uno(tem, "M5_AUSENTISMO_ASISTE", {"P3_Asiste_Colegio": 1, "P13_Ausentismo_Escolar": 2}).estado == CUMPLE
    assert _uno(tem, "E_AUSENTISMO_ASISTE", {"P3_Asiste_Colegio": 1, "P23_Ausentismo_Escolar": 99}, "5a14").estado == INCUMPLE


def test_sol012_correo_mal_digitado(tem):
    malos = ["persona@gmial.com", "persona@gmail.con", "persona@hotmal.com", "persona@gmail", "persona@outlok.es", "persona prueba@gmail.com", "persona@gmail.co"]
    buenos = ["persona@gmail.com", "persona@hotmail.com", "persona@hotmail.es", "persona@outlook.com", "persona@saludcapital.gov.co", "persona@yahoo.es"]
    for c in malos:
        assert _uno(tem, "COM_CORREO_DIGITACION", {"Correo_Electronico": c}).estado == INCUMPLE, c
    for c in buenos:
        assert _uno(tem, "COM_CORREO_DIGITACION", {"Correo_Electronico": c}).estado == CUMPLE, c
    assert _uno(tem, "COM_CORREO_DIGITACION", {"Correo_Electronico": 8888}).estado == NO_APLICA


def test_sol007_vivienda_y_complemento(tem):
    apto = "Apartamento (Independiente)"
    assert _uno(tem, "M5_VIVIENDA_COMPLEMENTO_APTO_IND", {"P49_Tipo_Vivienda": apto, "Dirección": "KR 5 10 20"}).estado == INCUMPLE
    assert _uno(tem, "M5_VIVIENDA_COMPLEMENTO_APTO_IND", {"P49_Tipo_Vivienda": apto, "Dirección": "KR 5 10 20 PI 2"}).estado == CUMPLE
    assert _uno(tem, "M5_VIVIENDA_COMPLEMENTO_APTO_IND", {"P49_Tipo_Vivienda": apto, "Dirección": "KR 5 10 20 AP201"}).estado == CUMPLE
    assert _uno(tem, "M5_VIVIENDA_COMPLEMENTO_APTO_IND", {"P49_Tipo_Vivienda": "Casa (Independiente)", "Dirección": "KR 5 10 20"}).estado == NO_APLICA
    # "APARTADO" o "PISCINA" no cuentan como complemento
    assert _uno(tem, "M5_VIVIENDA_COMPLEMENTO_APTO_IND", {"P49_Tipo_Vivienda": apto, "Dirección": "KR 5 10 20 APARTADO"}).estado == INCUMPLE


def test_sol005_tarjeta_de_identidad_desde_8(tem):
    assert _uno(tem, "E_TI_DESDE_8", {"Edad": 9, "Tipo_Documento": "NUIP"}, "5a14").estado == INCUMPLE
    assert _uno(tem, "E_TI_DESDE_8", {"Edad": 9, "Tipo_Documento": "Tarjeta de Identidad"}, "5a14").estado == CUMPLE
    assert _uno(tem, "E_TI_DESDE_8", {"Edad": 7, "Tipo_Documento": "NUIP"}, "5a14").estado == NO_APLICA
    assert _uno(tem, "E_TI_DESDE_8", {"Edad": 9, "Tipo_Documento": "Documento de Extranjería"}, "5a14").estado == NO_APLICA


def test_sol004_revision_humana_se_colorea_en_azul(tem):
    datos = base_menores5(tem, duplicar_id=False, extra={"Parentesco_Encuestado": "ABUELA", "Observaciones": "sin soporte"})
    ap = preparar_archivo(tem, datos, "m5.xlsx")
    res = validar(tem, [ap], PAR)
    assert any(h.regla == "M5_PARENTESCO_REVISION" for h in res.hallazgos)
    ws = openpyxl.load_workbook(io.BytesIO(generar_bases_marcadas(res, [ap])["m5_MARCADA.xlsx"])).worksheets[0]
    enc = [c.value for c in ws[1]]
    celda = ws.cell(2, enc.index("Parentesco_Encuestado") + 1)
    assert celda.comment is not None and "REVISIÓN HUMANA" in celda.comment.text
    assert celda.fill.fgColor.rgb.endswith("DDEBF7")
    # no suma en la columna de hallazgos (errores y alertas)
    errores = [h for h in res.hallazgos if h.severidad != "revision"]
    col_n = len(enc) - 3
    assert sum(ws.cell(f, col_n).value or 0 for f in range(2, ws.max_row + 1)) == len(errores)
