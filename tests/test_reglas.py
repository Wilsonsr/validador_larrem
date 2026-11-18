from collections import Counter

from conftest import ctx, regla, registro

from larrem.reglas import CUMPLE, IMPLEMENTACIONES, INCUMPLE, NO_APLICA, NO_EVALUABLE


def correr(r, regs, **kw):
    return list(IMPLEMENTACIONES[r.tipo](r, regs, ctx(**kw)))


def estados(res):
    return Counter(x.estado for x in res)


def test_requerido():
    r = regla(tipo="requerido", variables=["A"])
    res = correr(r, [registro({"A": 1}), registro({"A": None}, 3), registro({"A": "#REF!"}, 4), registro({}, 5)])
    assert [x.estado for x in res] == [CUMPLE, INCUMPLE, INCUMPLE, NO_EVALUABLE]


def test_requerido_columna_vacia_no_evaluable():
    r = regla(tipo="requerido", variables=["A"], parametros={"columna_vacia_no_evaluable": True})
    res = correr(r, [registro({"A": None}), registro({"A": None}, 3)])
    assert estados(res) == {NO_EVALUABLE: 2}
    # si al menos un registro tiene dato, los vacíos sí son hallazgos
    res = correr(r, [registro({"A": 1}), registro({"A": None}, 3)])
    assert estados(res) == {CUMPLE: 1, INCUMPLE: 1}


def test_dominio():
    r = regla(tipo="dominio", variables=["A"], parametros={"valores": [1, 2, 999]})
    res = correr(r, [registro({"A": 1}), registro({"A": 3}, 3), registro({"A": "999"}, 4)])
    assert [x.estado for x in res] == [CUMPLE, INCUMPLE, CUMPLE]


def test_salto_condicional():
    r = regla(tipo="condicional", variables=["P2", "P3"], aplica_si={"var": "P1", "en": [2]},
              parametros={"entonces_cada": {"en": [999]}})
    regs = [registro({"P1": 2, "P2": 999, "P3": 1}), registro({"P1": 1, "P2": 5, "P3": 5}, 3),
            registro({"P1": None, "P2": 999, "P3": 999}, 4)]
    res = correr(r, regs)
    assert [(x.registro.fila_excel, x.variable, x.estado) for x in res] == [
        (2, "P2", CUMPLE), (2, "P3", INCUMPLE), (3, "P2", NO_APLICA), (3, "P3", NO_APLICA),
        (4, "P2", NO_EVALUABLE), (4, "P3", NO_EVALUABLE)]


def test_recodificacion_intervalos_con_conflicto_documental():
    r = regla(tipo="recodificacion_intervalos", parametros={
        "origen": "E", "destino": "C", "intervalos": [{"min": 2, "max": 11, "valor": 1}, {"min": 13, "max": 59, "valor": 2}],
        "conflicto": [{"min": 12, "max": 12, "motivo": "fuentes en conflicto"}]})
    res = correr(r, [registro({"E": 5, "C": 1}), registro({"E": 30, "C": 1}, 3), registro({"E": 12, "C": 2}, 4)])
    assert [x.estado for x in res] == [CUMPLE, INCUMPLE, NO_EVALUABLE]
    assert res[2].motivo == "fuentes en conflicto"


def test_unicidad_con_excepcion_por_estrato():
    r = regla(tipo="unicidad", variables=["Dir"], parametros={
        "maximo_por_grupo": 1, "excepcion_maximo": {"si": {"var": "Estrato", "en": [5, 6]}, "maximo": 2}})
    regs = [registro({"Dir": "CL 1 # 2-3", "Estrato": 2}), registro({"Dir": "cl 1 # 2-3", "Estrato": 2}, 3),
            registro({"Dir": "KR 9", "Estrato": 5}, 4), registro({"Dir": "KR 9", "Estrato": 6}, 5)]
    res = correr(r, regs)
    por_fila = {x.registro.fila_excel: x.estado for x in res}
    assert por_fila == {2: INCUMPLE, 3: INCUMPLE, 4: CUMPLE, 5: CUMPLE}


def test_comparacion_entre_variables():
    r = regla(tipo="comparacion", parametros={"izquierda": {"var": "M"}, "operador": "<=", "derecha": {"var": "P"}})
    res = correr(r, [registro({"M": 2, "P": 3}), registro({"M": 4, "P": 3}, 3), registro({"M": None, "P": 3}, 4)])
    assert [x.estado for x in res] == [CUMPLE, INCUMPLE, NO_EVALUABLE]


def test_periodo(tem):
    from datetime import date
    r = regla(tipo="periodo", variables=["Fecha_Encuesta"])
    regs = [registro({"Fecha_Encuesta": date(2026, 3, 1)}), registro({"Fecha_Encuesta": date(2026, 8, 1)}, 3)]
    res = correr(r, regs, periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 6, 30))
    assert [x.estado for x in res] == [CUMPLE, INCUMPLE]


def test_al_menos_uno_y_exclusion_ninguno():
    r = regla(tipo="exclusion_ninguno", parametros={"opciones": ["A", "B"], "ninguno": "N"})
    res = correr(r, [registro({"A": 1, "B": 2, "N": 1}), registro({"A": 2, "B": 2, "N": 1}, 3)])
    assert INCUMPLE in {x.estado for x in res if x.registro.fila_excel == 2}
    assert {x.estado for x in res if x.registro.fila_excel == 3} == {CUMPLE}
