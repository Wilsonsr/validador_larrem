"""Genera bases de demostración SINTÉTICAS (ninguna fila corresponde a una persona).

Cómo se construyen:
1. La estructura (hoja, encabezados y su orden) se toma de una base plantilla de la misma población.
2. Cada respuesta codificada se sortea de forma independiente, columna por columna, entre los códigos
   que aparecen al menos 5 veces en la plantilla. Ninguna fila de la plantilla se copia: los valores
   de una fila sintética provienen de personas distintas y luego se ajustan.
3. Los datos personales (nombres, documentos, direcciones, teléfonos, correos, colegios, textos
   libres, personal de campo) se inventan. Las coordenadas y variables de enriquecimiento quedan vacías.
   Subred, localidad, UPZ y barrio se toman como combinación geográfica (es información pública del
   territorio, no de las personas).
4. Se corrigen las incoherencias con las mismas reglas del validador (saltos, recodificaciones,
   edad calculada…), probando valores hasta que la regla se cumple.
5. Se siembran errores a propósito en una parte de los registros, para que la demostración muestre
   hallazgos de cada severidad.

Uso:
  python herramientas/generar_demo_sintetica.py PLANTILLA_M5.xlsx PLANTILLA_5A14.xlsx PLANTILLA_60.xlsx --salida datos_demostracion
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import xlsxwriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from larrem.condiciones import evaluar, variables_de  # noqa: E402
from larrem.estructura import mapear_columnas  # noqa: E402
from larrem.motor import (_construir_registros, cargar_configuracion, preparar_archivo,  # noqa: E402
                          regla_aplica)
from larrem.normalizacion import construir_celda  # noqa: E402
from larrem.reglas import (IMPLEMENTACIONES, INCUMPLE, NO_EVALUABLE, Contexto, RegistroDatos,  # noqa: E402
                           variables_requeridas)

FILAS = {"menores5": 150, "5a14": 100, "mayores60": 150}
NOMBRE = {"menores5": "DEMO_1. LARREM_AIRE_MENORES5_SINTETICA.xlsx",
          "5a14": "DEMO_2. LARREM_AIRE_5-14ANIOS_SINTETICA.xlsx",
          "mayores60": "DEMO_3. LARREM_AIRE_MAYORES60_SINTETICA.xlsx"}
EDAD = {"menores5": ("meses", 2, 59), "5a14": ("anios", 5, 14), "mayores60": ("anios", 60, 92)}
INICIO, FIN = date(2026, 1, 1), date(2026, 6, 30)

GEO = ["Subred", "Zona_Urbana", "Localidad", "N_UPZ", "Nombre_UPZ", "Barrio", "Otro_Barrio", "Estrato"]
COLEGIO = ["P4_Colegio", "P4_Dirección_Colegio", "P4_Localidad_Colegio", "P4_Num_UPZ_Colegio",
           "P4_UPZ_Colegio", "P4_Barrio_Colegio", "P4_Otro_Barrio_Colegio"]
NOMBRES = {"Nombre_Menor", "Nombre_adulto", "Nombre_Encuestado"}
CAMPO = {"Encuestador", "Supervisor", "Digitador"}
IDENT = {"Identificación", "Identificación_Encuestado", "Identificacion_Encuestado"}
CORREOS = {"Correo_Electronico", "Correo_Electronico1"}
OBSERVACIONES = ["Sin observaciones adicionales.", "Se brinda educación sobre ventilación de la vivienda.",
                 "Se dejan recomendaciones sobre exposición a humo de tabaco.",
                 "Encuestado refiere no saber la respuesta (NS/NR).",
                 "Se orienta sobre consulta médica por síntomas respiratorios.",
                 "Se canaliza a la EAPB por síntomas respiratorios persistentes.",
                 "Estado nutricional reportado por el cuidador; se orienta a control de crecimiento y desarrollo."]
VIAS = ["CL", "KR", "AK", "DG", "TV", "AC"]
EXCLUIR_REPARACION = {"unicidad", "consistencia_grupo", "revision"}


class Generador:
    def __init__(self, tem, plantilla: Path, semilla: int) -> None:
        self.tem = tem
        self.rnd = random.Random(semilla)
        ap = preparar_archivo(tem, plantilla)
        if ap.hoja is None or ap.poblacion_detectada is None:
            raise SystemExit(f"{plantilla.name}: no se reconoció la población")
        self.ap = ap
        self.pob = tem.poblacion(ap.poblacion_detectada)
        self.est = mapear_columnas(self.pob, ap.hoja)
        plantilla_regs = _construir_registros(tem, self.pob.codigo, ap.hoja, self.est)
        self.tipos = {v.nombre: v for v in self.pob.variables}
        self.vars = [v for v in self.est.correspondencias if v in self.est.variables_disponibles]
        # Distribuciones por columna (solo valores frecuentes, nunca una fila completa)
        self.pool: dict[str, list] = {}
        self.pesos: dict[str, list] = {}
        for v in self.vars:
            cnt = Counter()
            for rg in plantilla_regs:
                c = rg.valores.get(v)
                if c is not None and not c.vacia and not isinstance(c.original, (datetime, date)):
                    cnt[c.original] += 1
            vals = [(k, n) for k, n in cnt.items() if n >= 5]
            self.pool[v] = [k for k, _ in vals]
            self.pesos[v] = [n for _, n in vals]
        # Combinaciones geográficas (territorio) y valor más común de colegio cuando no asiste
        self.siglas = next((r.parametros["opciones"]["siglas"] for r in tem.reglas if r.id == "COM_ACTA_SUBRED"), {})
        self.geo = [tuple(rg.valores[g].original if g in rg.valores else None for g in GEO if g in self.vars)
                    for rg in plantilla_regs
                    if "Subred" in rg.valores and rg.valores["Subred"].texto in self.siglas
                    and "Localidad" in rg.valores and not rg.valores["Localidad"].vacia]
        self.geo_vars = [g for g in GEO if g in self.vars]
        self.colegio_no = {}
        for v in COLEGIO:
            if v in self.vars:
                cnt = Counter(rg.valores[v].original for rg in plantilla_regs
                              if "P3_Asiste_Colegio" in rg.valores and rg.valores["P3_Asiste_Colegio"].texto != "1"
                              and not rg.valores[v].vacia)
                self.colegio_no[v] = cnt.most_common(1)[0][0] if cnt else 999
        self.colegios = self._colegios()
        self.siglas = next((r.parametros["opciones"]["siglas"] for r in tem.reglas if r.id == "COM_ACTA_SUBRED"), {})
        self.direcciones: set[str] = set()

    # ------------------------------------------------------------ valores inventados
    def _sortear(self, v: str):
        if not self.pool.get(v):
            return None
        return self.rnd.choices(self.pool[v], weights=self.pesos[v])[0]

    def _direccion(self, complemento: str = "") -> str:
        while True:
            d = f"{self.rnd.choice(VIAS)} {self.rnd.randint(1, 180)} # {self.rnd.randint(1, 120)} - {self.rnd.randint(2, 98)}"
            if complemento:
                d += f" {complemento}"
            if d not in self.direcciones:
                self.direcciones.add(d)
                return d

    def _colegios(self) -> list[dict]:
        out = []
        for i in range(1, 13):
            g = dict(zip(self.geo_vars, self.rnd.choice(self.geo)))
            out.append({"P4_Colegio": f"COLEGIO DEMO {i:02d}",
                        "P4_Dirección_Colegio": f"{self.rnd.choice(VIAS)} {self.rnd.randint(1, 180)} # {self.rnd.randint(1, 120)} - {self.rnd.randint(2, 98)}",
                        "P4_Localidad_Colegio": g.get("Localidad"), "P4_Num_UPZ_Colegio": g.get("N_UPZ"),
                        "P4_UPZ_Colegio": g.get("Nombre_UPZ"), "P4_Barrio_Colegio": g.get("Barrio"),
                        "P4_Otro_Barrio_Colegio": 999})
        return out

    def _personal(self, v: str, i: int, fila: dict):
        if v == self.pob.variable_id:
            return 800000 + {"menores5": 0, "5a14": 2000, "mayores60": 4000}[self.pob.codigo] + i
        if v == self.pob.variable_acta:
            sig = self.siglas.get(str(fila.get("Subred")), "E")
            return f"{self.pob.firma.prefijo_acta}{sig}{self.rnd.randint(100000, 999999)}"
        if v in NOMBRES:
            return f"PERSONA FICTICIA {i:04d}" if v != "Nombre_Encuestado" else f"CUIDADOR FICTICIO {i:04d}"
        if v in CAMPO:
            return f"{v.upper()} {self.rnd.randint(1, 6):02d}"
        if v in IDENT:
            return str(self.rnd.randint(10**9, 10**10 - 1))
        if v == "Telefono":
            return int(f"601{self.rnd.randint(2000000, 7999999)}")
        if v == "Celular":
            return int(f"3{self.rnd.choice(['00', '01', '10', '13', '15', '20', '22'])}{self.rnd.randint(1000000, 9999999)}")
        if v in CORREOS:
            return f"demo.usuario{i:04d}@example.com"
        if v == "Observaciones":
            return self.rnd.choice(OBSERVACIONES)
        return None

    # ------------------------------------------------------------ registros
    def fila_inicial(self, i: int) -> dict:
        fila: dict = {}
        g = dict(zip(self.geo_vars, self.rnd.choice(self.geo)))
        for v in self.vars:
            t = self.tipos[v]
            if v in g:
                fila[v] = g[v]
            elif t.tipo == "geografico":
                fila[v] = None
            elif v == "Fecha_Encuesta":
                fila[v] = INICIO + timedelta(days=self.rnd.randint(0, (FIN - INICIO).days))
            elif v == "Fecha_Nacimiento":
                continue
            elif v in COLEGIO or v == "Dirección":
                continue
            elif t.personal or t.tipo in ("identificador", "contacto") or v == "Observaciones":
                fila[v] = self._personal(v, i, fila)
            else:
                fila[v] = self._sortear(v)
        # fecha de nacimiento coherente con la población
        unidad, lo, hi = EDAD[self.pob.codigo]
        fe = fila.get("Fecha_Encuesta") or INICIO
        if unidad == "meses":
            dias = self.rnd.randint(int(lo * 30.5) + 5, int(hi * 30.4) - 10)
        else:
            dias = self.rnd.randint(lo * 366 + 30, (hi + 1) * 365 - 30)
        fila["Fecha_Nacimiento"] = nac = fe - timedelta(days=dias)
        anios = fe.year - nac.year - ((fe.month, fe.day) < (nac.month, nac.day))
        meses = (fe.year - nac.year) * 12 + fe.month - nac.month - (1 if fe.day < nac.day else 0)
        if "Edad_Meses" in self.vars:
            fila["Edad_Meses"] = meses
        if "Edad" in self.vars:
            fila["Edad"] = anios
        # colegio
        if "P4_Colegio" in self.vars:
            if str(fila.get("P3_Asiste_Colegio")) == "1":
                fila.update({k: v for k, v in self.rnd.choice(self.colegios).items() if k in self.vars})
            else:
                fila.update({k: self.colegio_no[k] for k in COLEGIO if k in self.vars})
        fila["Dirección"] = self._direccion()
        fila[self.pob.variable_acta] = self._personal(self.pob.variable_acta, i, fila)
        return fila

    def candidatos(self, v: str, esperado: str, i: int) -> list:
        out: list = []
        e = (esperado or "").strip()
        m = re.match(r"(-?\d+(?:\.\d+)?)\b", e)
        if m:
            out.append(int(float(m.group(1))) if float(m.group(1)).is_integer() else float(m.group(1)))
        elif e and len(e) < 40 and " " not in e:
            out.append(e)
        t = self.tipos.get(v)
        if v == "Fecha_Nacimiento":
            return out
        if v == "Dirección":
            return [self._direccion(c) for c in ("", "AP 201", "PI 2", "UN 1", "IN 3", "CA 5")]
        if t is not None and (t.personal or t.tipo in ("identificador", "contacto")) and v not in COLEGIO:
            out += [self._personal(v, i, {}) for _ in range(5)]
        pool = list(self.pool.get(v, []))
        self.rnd.shuffle(pool)
        return out + pool[:40] + [999, None]

    def reparar(self, regs: list[RegistroDatos], ctx: Contexto, rondas: int = 25) -> None:
        reglas = [r for r in self.tem.reglas_de(self.pob.codigo)
                  if r.ejecutable and regla_aplica(r, self.pob.codigo, "recodificacion")
                  and r.tipo not in EXCLUIR_REPARACION and r.parametros.get("alcance") != "lote"]
        self._reglas = reglas
        protegidas = {self.pob.variable_id, self.pob.variable_acta, "Fecha_Encuesta", "Fecha_Nacimiento",
                      "Edad", "Edad_Meses"} | set(COLEGIO)
        for _ in range(rondas):
            cambios = 0
            for r in reglas:
                malos = [res for res in IMPLEMENTACIONES[r.tipo](r, regs, ctx) if res.estado in (INCUMPLE, NO_EVALUABLE)]
                for res in malos:
                    reg = res.registro
                    if reg is None or self._puntaje(r, reg, ctx) == 0:
                        continue
                    objetivo = [res.variable] if res.variable in reg.valores else []
                    otras = [v for v in variables_requeridas(r) if v in reg.valores and v not in objetivo]
                    antecedentes = variables_de(r.aplica_si)
                    orden = objetivo + [v for v in otras if v not in antecedentes] + [v for v in otras if v in antecedentes]
                    if self._probar(r, reg, ctx, [v for v in orden if v not in protegidas], res.esperado):
                        cambios += 1
                    elif self._satisfacer_conjunto(r, reg, ctx):
                        cambios += 1
            if cambios == 0:
                break

    def _incumple(self, r, reg, ctx) -> bool:
        return any(x.estado == INCUMPLE for x in IMPLEMENTACIONES[r.tipo](r, [reg], ctx))

    def _puntaje(self, r, reg, ctx) -> int:
        """Incumplimientos y no evaluables de la regla en el registro (menos es mejor)."""
        return sum(1 for x in IMPLEMENTACIONES[r.tipo](r, [reg], ctx) if x.estado in (INCUMPLE, NO_EVALUABLE))

    def _satisfacer_conjunto(self, r, reg, ctx) -> bool:
        """Para condiciones 'todas': asigna a la vez un valor que cumpla cada parte."""
        conj = r.parametros.get("entonces")
        if not isinstance(conj, dict) or "todas" not in conj:
            return False
        antes = dict(reg.valores)
        base, total = self._puntaje(r, reg, ctx), self._total(reg, ctx)
        for sub in conj["todas"]:
            v = sub.get("var")
            if v not in reg.valores:
                continue
            for cand in self.candidatos(v, "", reg.indice + 1):
                reg.valores[v] = construir_celda(cand)
                if evaluar(sub, reg.valores)[0]:
                    break
            else:
                reg.valores.update(antes)
                return False
        if self._puntaje(r, reg, ctx) < base and self._total(reg, ctx) <= total:
            return True
        reg.valores.clear()
        reg.valores.update(antes)
        return False

    def _total(self, reg, ctx) -> int:
        """Puntaje del registro en todas las reglas; los valores fuera de dominio pesan más."""
        return sum(self._puntaje(r, reg, ctx) * (3 if r.tipo in ("dominio", "requerido") else 1) for r in self._reglas)

    def _probar(self, r, reg, ctx, variables, esperado) -> bool:
        """Acepta un valor si mejora la regla sin empeorar el registro en el conjunto de reglas."""
        base = self._puntaje(r, reg, ctx)
        total = None
        for v in variables:
            antes = reg.valores[v]
            for cand in self.candidatos(v, esperado, reg.indice + 1):
                reg.valores[v] = construir_celda(cand)
                if self._puntaje(r, reg, ctx) < base:
                    if total is None:
                        nuevo = reg.valores[v]
                        reg.valores[v] = antes
                        total = self._total(reg, ctx)
                        reg.valores[v] = nuevo
                    if self._total(reg, ctx) <= total:
                        return True
            reg.valores[v] = antes
        return False

    def sembrar_errores(self, regs: list[RegistroDatos], ctx: Contexto, proporcion: float = 0.06) -> int:
        reglas = [r for r in self.tem.reglas_de(self.pob.codigo)
                  if r.ejecutable and regla_aplica(r, self.pob.codigo, "recodificacion")
                  and r.tipo in ("condicional", "dominio", "recodificacion_mapa", "rango", "requerido", "al_menos_uno")
                  and r.severidad in ("error", "alerta")]
        sembrados = 0
        for reg in self.rnd.sample(regs, max(1, int(len(regs) * proporcion))):
            for r in self.rnd.sample(reglas, len(reglas)):
                vs = [v for v in r.variables if v in reg.valores and v not in (self.pob.variable_id, self.pob.variable_acta)]
                if not vs or self._incumple(r, reg, ctx):
                    continue
                v = self.rnd.choice(vs)
                antes = reg.valores[v]
                hecho = False
                for cand in self.candidatos(v, "", reg.indice + 1):
                    reg.valores[v] = construir_celda(cand)
                    if self._incumple(r, reg, ctx):
                        hecho = True
                        break
                if hecho:
                    sembrados += 1
                    break
                reg.valores[v] = antes
        # un acta repetida (bloqueante) y, si hay colegios, un colegio con otra dirección (alerta)
        a, b = self.rnd.sample(regs, 2)
        b.valores[self.pob.variable_acta] = a.valores[self.pob.variable_acta]
        sembrados += 1
        con_colegio = [rg for rg in regs if "P4_Colegio" in rg.valores and rg.valores["P4_Colegio"].texto.startswith("COLEGIO DEMO")]
        if len(con_colegio) > 3:
            rg = self.rnd.choice(con_colegio)
            rg.valores["P4_Dirección_Colegio"] = construir_celda(f"KR {self.rnd.randint(1, 99)} # {self.rnd.randint(1, 99)} - {self.rnd.randint(2, 98)}")
            sembrados += 1
        # errores típicos de digitación
        for reg in self.rnd.sample(regs, 2):
            if "Correo_Electronico" in reg.valores:
                reg.valores["Correo_Electronico"] = construir_celda(f"demo.usuario{reg.indice + 1:04d}@gmial.com")
                sembrados += 1
        return sembrados

    def generar(self, n: int) -> list[RegistroDatos]:
        filas = [self.fila_inicial(i + 1) for i in range(n)]
        enc = self.ap.hoja.fila_encabezado
        regs = [RegistroDatos(indice=i, archivo="sintetica", hoja=self.ap.hoja.hoja, fila_excel=enc + 1 + i,
                              valores={v: construir_celda(f.get(v)) for v in self.vars},
                              id_registro=str(f.get(self.pob.variable_id)), poblacion=self.pob.codigo)
                for i, f in enumerate(filas)]
        ctx = Contexto(poblacion=self.pob.codigo, periodo_inicio=INICIO, periodo_fin=FIN, etapa="recodificacion",
                       variables_disponibles=set(self.vars), variable_fecha=self.pob.variable_fecha)
        self.reparar(regs, ctx)
        self.sembrar_errores(regs, ctx)
        return regs

    def escribir(self, regs: list[RegistroDatos], destino: Path) -> None:
        wb = xlsxwriter.Workbook(destino, {"strings_to_numbers": False, "strings_to_formulas": False,
                                           "strings_to_urls": False})
        ws = wb.add_worksheet(self.ap.hoja.hoja[:31])
        f_fecha = wb.add_format({"num_format": "dd/mm/yyyy"})
        f_enc = wb.add_format({"bold": True})
        fila_enc = self.ap.hoja.fila_encabezado - 1
        indice = {c.indice: v for v, c in self.est.correspondencias.items()}
        for c, nombre in enumerate(self.ap.hoja.encabezados):
            ws.write_string(fila_enc, c, nombre, f_enc)
        for k, reg in enumerate(regs):
            for c in range(len(self.ap.hoja.encabezados)):
                v = indice.get(c)
                if v is None or v not in reg.valores:
                    continue
                o = reg.valores[v].original
                if o is None or o == "":
                    continue
                if isinstance(o, datetime):
                    ws.write_datetime(fila_enc + 1 + k, c, o, f_fecha)
                elif isinstance(o, date):
                    ws.write_datetime(fila_enc + 1 + k, c, datetime(o.year, o.month, o.day), f_fecha)
                elif isinstance(o, bool):
                    ws.write_boolean(fila_enc + 1 + k, c, o)
                elif isinstance(o, (int, float)):
                    ws.write_number(fila_enc + 1 + k, c, o)
                else:
                    ws.write_string(fila_enc + 1 + k, c, str(o))
        ley = wb.add_worksheet("LEEME")
        ley.set_column(0, 0, 110)
        for i, t in enumerate([
            "BASE DE DEMOSTRACIÓN SINTÉTICA – solo para practicar con el validador LARREM.",
            "Ningún registro corresponde a una persona: las respuestas se sortearon columna por columna y se ajustaron",
            "con las reglas del validador; nombres, documentos, direcciones, teléfonos, correos y colegios son inventados.",
            "Contiene errores sembrados a propósito. No la use para reportes ni análisis.",
            "Generada con herramientas/generar_demo_sintetica.py.",
        ]):
            ley.write_string(i, 0, t)
        wb.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plantillas", nargs="+", type=Path)
    ap.add_argument("--salida", type=Path, default=Path("datos_demostracion"))
    ap.add_argument("--semilla", type=int, default=2026)
    a = ap.parse_args()
    tem = cargar_configuracion()
    a.salida.mkdir(parents=True, exist_ok=True)
    for k, p in enumerate(a.plantillas):
        g = Generador(tem, p, a.semilla + k)
        regs = g.generar(FILAS.get(g.pob.codigo, 100))
        destino = a.salida / NOMBRE.get(g.pob.codigo, f"DEMO_{g.pob.codigo}_SINTETICA.xlsx")
        g.escribir(regs, destino)
        print(f"{destino.name}: {len(regs)} registros sintéticos")


if __name__ == "__main__":
    main()
