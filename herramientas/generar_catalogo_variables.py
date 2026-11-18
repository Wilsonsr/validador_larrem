"""Genera el catálogo inicial de variables a partir de las fuentes documentales.

Uso (desde la carpeta del proyecto):
    python herramientas/generar_catalogo_variables.py RUTA_CARPETA_BASES

Lee el encabezado de cada base, ubica la fila del diccionario (incluidas las
definiciones agrupadas en celdas combinadas) y la fila de la hoja de observaciones.
Asigna tipo y obligatoriedad con listas explícitas definidas abajo. El resultado
(configuracion/aire/variables/*.yaml) es un insumo revisable: después de generarlo se
edita a mano y se versiona. Volver a ejecutar este script sobrescribe esas ediciones.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import openpyxl
import yaml

FUENTES = {
    "menores5": ("1. LARREM_AIRE_MENORES5_2026_1SEM_Prelim.xlsx", "1. DICCIONARIO_LARREM_AIRE_MENORES5_Ok_.xlsx", "MENOR 5", "D1"),
    "5a14": ("2. LARREM_AIRE_5-14ANIOS_2026_1SEM_Prelim.xlsx", "2. DICCIONARIO_LARREM_AIRE_5-14ANOS_Ok_.xlsx", "5 A 14", "D2"),
    "mayores60": ("3. LARREM_AIRE_MAYORES60_2026_1SEM_Prelim.xlsx", "3. DICCIONARIO_LARREM_AIRE_MAYOR60-.xlsx", "MAYOR 60", "D3"),
}
OBS = "Variables Aire para Automatizar.xlsx"

# Definiciones agrupadas del diccionario: prefijo de la columna -> fila donde está la definición del grupo.
GRUPOS = {
    "menores5": {r"^P6_": 83, r"^P24_(?!Cual)": 149, r"^P24_Cual": 149, r"^P68_": 372, r"^P76_(?!Ninguno)": 407, r"^P76_Ninguno": 424},
    "5a14": {r"^P12_": 106, r"^P34_": 198, r"^P39_": 225, r"^P75_": 410, r"^P83_(?!Ninguno)": 442, r"^P83_Ninguno": 459},
    "mayores60": {r"^P4_": 68, r"^P5_Exp": 78, r"^P6_": 93, r"^P7_": 105, r"^P9_": 116, r"^P10_": 130, r"^P11_": 138,
                  r"^P32_Combustible_": 274, r"^P32_Años_": 280, r"^P40_(?!Ninguno)": 317, r"^P40_Ninguno": 333},
}
FECHAS = {"Fecha_Encuesta", "Fecha_Nacimiento"}
IDENTIFICADORES = {"ID_SIVIGILA", "No_Acta", "Identificación", "Identificación_Encuestado", "Identificacion_Encuestado"}
PERSONALES = {"Nombre_Menor", "Nombre_adulto", "Nombre_Encuestado", "Identificación", "Identificación_Encuestado",
              "Identificacion_Encuestado", "Correo_Electronico", "Correo_Electronico1", "Dirección", "Telefono", "Celular",
              "Encuestador", "Supervisor", "Digitador", "Observaciones", "P26_Justificacion", "Justificacion_Lactancia"}
GEOGRAFICAS = {"RIESGO ACRE", "valor_acre", "Min_PM25", "Max_PM25", "X", "Y", "x", "y", "id_geo", "id_geo4",
               "X Colegio", "Y Colegio", "Valor ACRE COLEGIO"}
HISTORICAS = {"P27_Cual_Otra", "P32_Combustible", "P32_Años"}
DERIVADA_PATRON = re.compile(r"(CODIF|COFID|COD$|COD\b|^HACINAMIENTO|^FUENTES|AFECTACI|RIESGO_POSIBLE|TABAQUISMO PESADO|NIVEL CONSUMO|Sexo- Cod|DX_Malnutricion)", re.I)
TEXTO_LIBRE = re.compile(r"(Observaciones|_Cual|P22_2_Donde|Justificacion|P4_Colegio$|Dirección|Barrio|Nombre_|Encuestador|Supervisor|Digitador|Otra_EAPB|Otra_EPS|P22_Localidad|Correo)", re.I)
ENTEROS = re.compile(r"^(Edad|Edad_Meses|N_UPZ|P4_Num_UPZ_Colegio|Estrato|P20_Edad|P9_Ataques|P19_Ataques|P13_Cuantos|P14_Cuantos|"
                     r"P26_Tiempo|P27_Tiempo|P51_|P52_|P53_|P54_|P56_Cuantas|P56_Tiempo|P57_Hab|P58_Cuantas|P59_Cuantos|P61_Cuantas|"
                     r"P63_Tiempo|P68_Cuant|P75_Cuant|P10_Tiempo|P13_Horas|P21_|P22_Edad|P23_Tiempo|P24_Tiempo|P29_Tiempo|P32_Años_)")
CATEGORIA_TEXTO = {"Subred", "Tipo_Documento", "Tipo_documento", "Sexo", "Grupo_etnico", "Pais_Procedencia", "Tipo_Documento_Encuestado",
                   "Parentesco_Encuestado", "Localidad", "Nombre_UPZ", "P1_SGSS", "P2_EAPB", "P2_EPS", "P4_Localidad_Colegio", "P4_UPZ_Colegio",
                   "P21_Edad_Gestacional", "P45_Ingresos_Hogar", "P46_Nivel_Educativo_Cuidador", "P47_Ocupacion_Cuidador", "P49_Tipo_Vivienda",
                   "P50_Ubicacion_Vivienda", "P57_Permanencia_Ventanas", "P58_Donde_Cocina", "P60_Energia_Cocina", "P62_Material_Paredes",
                   "P63_Material_Pisos", "P64_Secado_Ropa", "P69_Donde_Duermen_Mascotas", "P74_Trafico_Cerca", "P50_Ingresos_Hogar",
                   "P51_Nivel_Educativo_Cuidador", "P52_Ocupacion_Cuidador", "P54_Tipo_Vivienda", "P55_Ubicacion_Vivienda",
                   "P56_Periodo_Vive_Vivienda", "P62_Tipo_Almohada", "P63_Periodo_Uso_Colchon", "P64_Permanencia_Ventanas",
                   "P65_Donde_Cocina", "P67_Energía_Cocina", "P69_Material_Paredes", "P70_Material_Pisos", "P71_Secado_Ropa",
                   "P76_Donde_Duermen_Mascotas", "P81_Trafico_Cerca", "Nivel_Educativo", "P10_Frecuencia_Oxigeno", "P10_Periodo",
                   "P14_Horario", "P16_Tipo_Espacio", "P17_Frecuencia", "P20_Frecuencia", "P23_Periodo_Fumar", "P26_Ocupacion_Principal",
                   "P28_Espacio_Exposicion", "P29_Periodo_Exposicion", "P30_Ubicacion_Cocina", "P33_Tipo_Vivienda", "P34_Zona_Vivienda",
                   "P35_Material_Paredes", "P36_Material_Pisos", "P38_Trafico_Cerca"}
CONDICIONALES = {"P4_Barrio_Colegio", "P4_Otro_Barrio_Colegio"}
NO_ENTEROS = {"P21_Sibilancia_Impide_Habla", "P53_Persona_Contacto_Niños_Pacientes", "P52_Ocupacion_Cuidador",
              "P51_Nivel_Educativo_Cuidador", "P54_Tipo_Vivienda", "P56_Periodo_Vive_Vivienda", "P59_Cuantos_Menores_Habitan_x"}
# Nombre en la base -> nombre en el diccionario cuando difieren (equivalencias explícitas documentadas).
ALIAS_DICCIONARIO = {
    "menores5": {"PE_Discapacitado": "PE_Discapacidad", "P27_1_Desnutrición2": "P27_1_Desnutrición",
                 "P51_Meses_Viviendo_Barrio": "P51_Meses_Viviendo_Vivienda", "id_geo4": "id_geo"},
    "5a14": {"PE_Discapacitado": "PE_Discapacidad"},
    "mayores60": {"PE_Discapacitado": "PE_Discapacidad", "P31_Cocicó_En_Su_Vida": "P31_Cocinó_En_Su_Vida", "valor_acre": "RIESGO ACRE"},
}


def clave(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def tipo_de(n: str) -> str:
    if n in GEOGRAFICAS:
        return "geografico"
    if n in HISTORICAS:
        return "historica"
    if n in FECHAS:
        return "fecha"
    if n in IDENTIFICADORES:
        return "identificador"
    if n in {"Telefono", "Celular", "Correo_Electronico", "Correo_Electronico1"}:
        return "contacto"
    if DERIVADA_PATRON.search(n):
        return "derivada"
    if n in CATEGORIA_TEXTO:
        return "categoria_texto"
    if ENTEROS.match(n) and n not in NO_ENTEROS:
        return "entero"
    if TEXTO_LIBRE.search(n):
        return "texto_libre"
    return "codigo"


def main(carpeta: Path) -> None:
    raiz = Path(__file__).resolve().parents[1] / "configuracion" / "aire"
    wb_obs = openpyxl.load_workbook(carpeta / OBS, read_only=True)
    for pob, (base, dic, hoja_obs, cod_dic) in FUENTES.items():
        ws = openpyxl.load_workbook(carpeta / base, read_only=True).worksheets[0]
        encabezado = [str(v).strip() for v in next(ws.iter_rows(values_only=True, max_row=1)) if v is not None]
        wd = openpyxl.load_workbook(carpeta / dic).worksheets[0]
        filas_dic: dict[str, int] = {}
        nombres_dic: dict[str, str] = {}
        for i in range(2, 520):
            a = wd.cell(i, 1).value
            if a and str(a).strip():
                k = clave(a)
                filas_dic.setdefault(k, i)
                nombres_dic.setdefault(k, str(a).strip())
        etiquetas = {i: wd.cell(i, 2).value for i in range(2, 520)}
        filas_obs = {}
        for i, r in enumerate(wb_obs[hoja_obs].iter_rows(values_only=True, max_row=260), start=1):
            if r[0]:
                filas_obs.setdefault(str(r[0]).strip(), i)
        variables = []
        for n in encabezado:
            alias = ALIAS_DICCIONARIO[pob].get(n)
            fila = filas_dic.get(clave(alias or n))
            nota = None
            if fila is None:
                for patron, f in GRUPOS[pob].items():
                    if re.search(patron, n):
                        fila, nota = f, "definición agrupada en el diccionario; las categorías se reparten entre varias filas"
                        break
            t = tipo_de(n)
            v = {
                "nombre": n,
                "etiqueta": (str(etiquetas.get(fila)).strip() if fila and etiquetas.get(fila) else None),
                "tipo": t,
                "requerido": ("enriquecimiento" if t == "geografico" else "no" if t == "historica" else
                              "condicional" if n in CONDICIONALES else "recodificacion" if t == "derivada" else "captura"),
                "personal": n in PERSONALES,
                "historica": t == "historica",
                "fuente_diccionario": f"{cod_dic} fila {fila}" if fila else None,
                "fuente_observacion": f"O1 {hoja_obs} fila {filas_obs[n]}" if n in filas_obs else None,
            }
            if nota:
                v["nota"] = nota
            if alias:
                v["equivalencias"] = [alias]
            variables.append({k: x for k, x in v.items() if x not in (None, False)})
        destino = raiz / "variables" / f"{pob}.yaml"
        cabecera = (f"# Catálogo de variables {pob}. Generado con herramientas/generar_catalogo_variables.py y revisado a mano.\n"
                    f"# D = diccionario, O1 = Variables Aire para Automatizar.xlsx. Una fila del diccionario puede definir un grupo.\n")
        destino.write_text(cabecera + yaml.safe_dump({"variables": variables}, allow_unicode=True, sort_keys=False, width=140), encoding="utf-8")
        print(pob, len(variables), "variables ->", destino)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
