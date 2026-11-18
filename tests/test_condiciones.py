from conftest import registro

from larrem.condiciones import evaluar


def test_en_y_no_en():
    r = registro({"A": 1, "B": "2"}).valores
    assert evaluar({"var": "A", "en": [1, 2]}, r)[0] is True
    assert evaluar({"var": "B", "en": [1]}, r)[0] is False
    assert evaluar({"var": "B", "no_en": [1]}, r)[0] is True


def test_codigos_numericos_equivalentes():
    r = registro({"A": 1.0, "B": " 1 "}).valores
    assert evaluar({"var": "A", "en": ["1"]}, r)[0] is True
    assert evaluar({"var": "B", "en": [1]}, r)[0] is True


def test_vacio_y_columna_ausente_no_evaluables():
    r = registro({"A": None}).valores
    assert evaluar({"var": "A", "en": [1]}, r)[0] is None
    assert evaluar({"var": "Z", "en": [1]}, r)[0] is None
    assert evaluar({"var": "A", "vacio": True}, r)[0] is True


def test_cmp_con_excepto():
    r = registro({"A": 999, "B": 5}).valores
    assert evaluar({"var": "A", "cmp": ">", "valor": 3, "excepto": [999]}, r)[0] is False
    assert evaluar({"var": "B", "cmp": ">", "valor": 3, "excepto": [999]}, r)[0] is True


def test_compuestas():
    r = registro({"A": 1, "B": 2, "C": None}).valores
    assert evaluar({"todas": [{"var": "A", "en": [1]}, {"var": "B", "en": [2]}]}, r)[0] is True
    assert evaluar({"todas": [{"var": "A", "en": [1]}, {"var": "C", "en": [2]}]}, r)[0] is None
    assert evaluar({"todas": [{"var": "A", "en": [2]}, {"var": "C", "en": [2]}]}, r)[0] is False
    assert evaluar({"alguna": [{"var": "A", "en": [2]}, {"var": "B", "en": [2]}]}, r)[0] is True
    assert evaluar({"negar": {"var": "A", "en": [1]}}, r)[0] is False


def test_errores_de_excel_no_evaluables():
    r = registro({"A": "#N/A"}).valores
    assert evaluar({"var": "A", "en": [1]}, r)[0] is None
