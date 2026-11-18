import re
from pathlib import Path

import pytest
import yaml

from larrem.cobertura import matriz_cobertura, variables_desconocidas
from larrem.configuracion import ESTADOS_EJECUTABLES, Regla
from larrem.reglas import IMPLEMENTACIONES

RAIZ = Path(__file__).resolve().parents[1]


def test_carga_tres_poblaciones(tem):
    assert {p.codigo for p in tem.poblaciones} == {"menores5", "5a14", "mayores60"}
    assert all(p.variables for p in tem.poblaciones)


def test_ids_unicos_y_tipos_implementados(tem):
    ids = [r.id for r in tem.reglas]
    assert len(ids) == len(set(ids))
    assert {r.tipo for r in tem.reglas} <= set(IMPLEMENTACIONES)


def test_reglas_ejecutables_citan_fuente_y_pendientes_explican(tem):
    for r in tem.reglas:
        if r.estado in ESTADOS_EJECUTABLES:
            assert r.fuentes, r.id
        else:
            assert r.motivo_estado, r.id
        if r.estado == "requiere_insumo":
            assert r.insumo_requerido, r.id


def test_reglas_citan_variables_del_catalogo(tem):
    assert variables_desconocidas(tem) == []


def test_decisiones_enlazan_reglas_existentes(tem):
    ids = {r.id for r in tem.reglas}
    assert tem.decisiones
    for d in tem.decisiones:
        assert set(d.reglas) <= ids, d.id


def test_codigos_de_fuente_declarados(tem):
    docs = {d.codigo for d in tem.documentos}
    for r in tem.reglas:
        for f in r.fuentes:
            assert f.doc in docs, (r.id, f.doc)


def test_cobertura_sin_variables_huerfanas(tem):
    filas = matriz_cobertura(tem)
    assert all(f.estado != "sin_regla" for f in filas)


def test_clave_no_sin_comillas_es_rechazada():
    # En YAML, `no:` se interpreta como False: la configuración debe rechazarlo.
    cond = yaml.safe_load("{no: {var: X, en: [1]}}")
    with pytest.raises(ValueError):
        Regla(id="X", descripcion="d", tipo="condicional", fuentes=[{"doc": "T", "ubicacion": "u"}],
              variables=["X"], aplica_si=cond)


def test_regla_pendiente_sin_motivo_es_rechazada():
    with pytest.raises(ValueError):
        Regla(id="X", descripcion="d", tipo="dominio", estado="pendiente_contradiccion")


def test_el_codigo_no_usa_eval_ni_exec():
    for f in (RAIZ / "src").rglob("*.py"):
        texto = f.read_text(encoding="utf-8")
        assert not re.search(r"(?<![\w.])(eval|exec)\s*\(", texto), f


def test_obligatoriedad_generada_esta_al_dia(tmp_path):
    """El archivo 05_obligatoriedad.yaml debe coincidir con lo que produce el generador."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", RAIZ / "herramientas" / "generar_obligatoriedad.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    actual = (RAIZ / "configuracion" / "aire" / "reglas" / "05_obligatoriedad.yaml").read_text(encoding="utf-8")
    gen.CONF = RAIZ / "configuracion" / "aire"
    destino = tmp_path / "reglas"
    destino.mkdir()
    original = gen.CONF
    # ejecuta el generador escribiendo en una copia
    import shutil
    copia = tmp_path / "aire"
    shutil.copytree(original, copia)
    gen.CONF = copia
    gen.main()
    assert (copia / "reglas" / "05_obligatoriedad.yaml").read_text(encoding="utf-8") == actual
