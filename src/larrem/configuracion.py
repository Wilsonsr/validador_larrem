"""Carga y validación de la configuración versionada (YAML).

Las reglas se describen con tipos cerrados y condiciones estructuradas. Ningún texto
de la configuración se ejecuta como código. Las reglas de tipo `funcion` solo pueden
invocar funciones registradas en `larrem.funciones`, revisables en el código fuente.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ESTADOS_REGLA = (
    "implementada",          # clara y respaldada: se ejecuta
    "provisional",           # se ejecuta, pero requiere confirmación del equipo
    "revision_humana",       # se ejecuta y genera solicitudes de revisión
    "pendiente_contradiccion",
    "pendiente_incompleta",
    "requiere_insumo",
)
ESTADOS_EJECUTABLES = {"implementada", "provisional", "revision_humana"}
SEVERIDADES = ("bloqueante", "error", "alerta", "revision")
ETAPAS = ("captura", "recodificacion", "enriquecimiento")
ORDEN_ETAPA = {e: i for i, e in enumerate(ETAPAS)}

TIPOS_REGLA = (
    "requerido", "dominio", "patron", "rango", "condicional", "al_menos_uno",
    "exclusion_ninguno", "recodificacion_mapa", "recodificacion_agrupada",
    "recodificacion_intervalos", "recodificacion_razon", "comparacion", "unicidad",
    "consistencia_grupo", "periodo", "fecha_valida", "ambito", "almacenado_como_texto",
    "funcion", "revision",
)


class Fuente(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc: str
    ubicacion: str
    nota: str | None = None


class Vigencia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    desde: date | None = None
    hasta: date | None = None
    documento: str | None = None


class Regla(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: int = 1
    descripcion: str
    tipo: Literal[TIPOS_REGLA]  # type: ignore[valid-type]
    etapa: Literal[ETAPAS] = "captura"  # type: ignore[valid-type]
    severidad: Literal[SEVERIDADES] = "error"  # type: ignore[valid-type]
    estado: Literal[ESTADOS_REGLA] = "implementada"  # type: ignore[valid-type]
    motivo_estado: str | None = None
    insumo_requerido: str | None = None
    variables: list[str] = Field(default_factory=list)
    aplica_si: dict[str, Any] | None = None
    parametros: dict[str, Any] = Field(default_factory=dict)
    especiales: str | None = None
    fuentes: list[Fuente] = Field(default_factory=list)
    vigencia: Vigencia | None = None
    accion: str | None = None
    revision_tecnica: Literal["pendiente", "aprobada", "rechazada"] = "pendiente"
    poblaciones: list[str] = Field(default_factory=list)  # se completa al cargar

    @model_validator(mode="after")
    def _coherencia(self) -> "Regla":
        if self.estado not in ESTADOS_EJECUTABLES and not self.motivo_estado:
            raise ValueError(f"La regla {self.id} está en estado {self.estado} y debe explicar motivo_estado")
        if self.estado == "requiere_insumo" and not self.insumo_requerido:
            raise ValueError(f"La regla {self.id} requiere indicar insumo_requerido")
        if self.estado in ESTADOS_EJECUTABLES and not self.fuentes:
            raise ValueError(f"La regla ejecutable {self.id} debe citar al menos una fuente")
        return self

    @model_validator(mode="after")
    def _condiciones_validas(self) -> "Regla":
        from .condiciones import validar_condicion
        for c in (self.aplica_si, self.parametros.get("entonces"), self.parametros.get("entonces_cada")):
            if c is not None:
                try:
                    validar_condicion(c)
                except ValueError as exc:
                    raise ValueError(f"Regla {self.id}: {exc}") from exc
        if any(not isinstance(k, str) for k in self.parametros):
            raise ValueError(f"Regla {self.id}: parámetro con clave no textual (use comillas en YAML)")
        return self

    @property
    def ejecutable(self) -> bool:
        return self.estado in ESTADOS_EJECUTABLES


class Variable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    etiqueta: str | None = None
    seccion: str | None = None
    tipo: Literal["codigo", "categoria_texto", "texto_libre", "entero", "fecha", "identificador",
                  "contacto", "geografico", "historica", "derivada"] = "codigo"
    requerido: Literal["captura", "recodificacion", "enriquecimiento", "condicional", "no"] = "captura"
    personal: bool = False
    historica: bool = False
    opcional: bool = False  # la columna puede no venir en el archivo (no cuenta para la estructura esperada)
    equivalencias: list[str] = Field(default_factory=list)
    fuente_diccionario: str | None = None
    fuente_observacion: str | None = None
    nota: str | None = None


class FirmaPoblacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columnas_distintivas: list[str]
    prefijo_acta: str
    patron_nombre_archivo: str | None = None


class Poblacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    nombre: str
    formato: str
    firma: FirmaPoblacion
    variable_id: str = "ID_SIVIGILA"
    variable_acta: str = "No_Acta"
    variable_fecha: str = "Fecha_Encuesta"
    variable_subred: str = "Subred"
    variables: list[Variable] = Field(default_factory=list)
    huella_instrumento: str | None = None

    def variable(self, nombre: str) -> Variable | None:
        for v in self.variables:
            if v.nombre == nombre:
                return v
        return None


class DecisionPendiente(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    tema: str
    poblaciones: list[str]
    diferencia: str
    fuentes: list[Fuente]
    efecto_en_validador: str
    reglas: list[str] = Field(default_factory=list)
    pregunta: str
    responsable_sugerido: str = "Equipo técnico de bases de aire"
    respuesta: str | None = None
    fecha_respuesta: date | None = None


class Documento(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    archivo: str
    descripcion: str
    version: str | None = None


class Tematica(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    nombre: str
    version_configuracion: str
    fecha_configuracion: date
    documentos: list[Documento]
    subredes: dict[str, str]  # nombre -> sigla
    localidades: list[str]
    poblaciones: list[Poblacion] = Field(default_factory=list)
    reglas: list[Regla] = Field(default_factory=list)
    decisiones: list[DecisionPendiente] = Field(default_factory=list)
    huella_reglas: str = ""

    def poblacion(self, codigo: str) -> Poblacion:
        for p in self.poblaciones:
            if p.codigo == codigo:
                return p
        raise KeyError(codigo)

    def reglas_de(self, codigo_poblacion: str) -> list[Regla]:
        return [r for r in self.reglas if codigo_poblacion in r.poblaciones]


def _leer_yaml(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_tematica(directorio: str | Path) -> Tematica:
    """Carga la configuración de una temática y valida su consistencia."""
    d = Path(directorio)
    base = _leer_yaml(d / "tematica.yaml")
    poblaciones_cfg = base.pop("poblaciones")
    tem = Tematica(**base)
    for pc in poblaciones_cfg:
        archivo_vars = pc.pop("archivo_variables")
        datos_vars = _leer_yaml(d / "variables" / archivo_vars)
        eq_path = d / "equivalencias" / archivo_vars
        equivalencias = _leer_yaml(eq_path) if eq_path.exists() else {}
        variables = []
        for v in datos_vars["variables"]:
            v = dict(v)
            v["equivalencias"] = list(v.get("equivalencias", [])) + list((equivalencias or {}).get(v["nombre"], []))
            variables.append(Variable(**v))
        tem.poblaciones.append(Poblacion(**pc, variables=variables))

    ids: set[str] = set()
    for archivo in sorted((d / "reglas").glob("*.yaml")):
        contenido = _leer_yaml(archivo) or {}
        pobl_archivo = contenido.get("poblaciones", [])
        for r in contenido.get("reglas", []):
            r = dict(r)
            r.setdefault("poblaciones", pobl_archivo)
            regla = Regla(**r)
            if regla.id in ids:
                raise ValueError(f"Identificador de regla duplicado: {regla.id} ({archivo.name})")
            ids.add(regla.id)
            tem.reglas.append(regla)

    dec = d / "decisiones_pendientes.yaml"
    if dec.exists():
        tem.decisiones = [DecisionPendiente(**x) for x in (_leer_yaml(dec) or {}).get("decisiones", [])]

    _validar_referencias(tem)
    tem.huella_reglas = huella_configuracion(d)
    return tem


def _validar_referencias(tem: Tematica) -> None:
    codigos = {p.codigo for p in tem.poblaciones}
    for r in tem.reglas:
        for p in r.poblaciones:
            if p not in codigos:
                raise ValueError(f"Regla {r.id}: población desconocida {p}")
    for dpend in tem.decisiones:
        for rid in dpend.reglas:
            if rid not in {r.id for r in tem.reglas}:
                raise ValueError(f"Decisión {dpend.id}: regla inexistente {rid}")


def huella_configuracion(directorio: str | Path) -> str:
    """Huella SHA-256 de todos los archivos YAML de configuración (orden estable)."""
    d = Path(directorio)
    h = hashlib.sha256()
    for f in sorted(d.rglob("*.yaml")):
        h.update(str(f.relative_to(d)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def resumen_regla(r: Regla) -> dict[str, Any]:
    return {
        "id": r.id, "version": r.version, "descripcion": r.descripcion, "tipo": r.tipo,
        "etapa": r.etapa, "severidad": r.severidad, "estado": r.estado,
        "poblaciones": ", ".join(r.poblaciones), "variables": ", ".join(r.variables) or _vars_param(r),
        "condicion": json.dumps(r.aplica_si, ensure_ascii=False) if r.aplica_si else "",
        "parametros": json.dumps(r.parametros, ensure_ascii=False, default=str) if r.parametros else "",
        "especiales": r.especiales or "",
        "fuentes": "; ".join(f"{f.doc} {f.ubicacion}" + (f" ({f.nota})" if f.nota else "") for f in r.fuentes),
        "vigencia": (f"{r.vigencia.desde or ''} a {r.vigencia.hasta or 'vigente'}" if r.vigencia else ""),
        "motivo_estado": r.motivo_estado or "", "insumo_requerido": r.insumo_requerido or "",
        "accion": r.accion or "", "revision_tecnica": r.revision_tecnica,
    }


def _vars_param(r: Regla) -> str:
    p = r.parametros
    keys = [k for k in ("origen", "destino", "ninguno", "izquierda", "derecha", "clave", "dependiente") if k in p]
    vals = []
    for k in keys:
        v = p[k]
        vals.append(v if isinstance(v, str) else (v.get("var") if isinstance(v, dict) else str(v)))
    if "opciones" in p:
        vals.extend(p["opciones"])
    return ", ".join(str(x) for x in vals if x)
