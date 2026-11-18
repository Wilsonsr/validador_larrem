"""Validador de bases LARREM – interfaz Streamlit.

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from larrem import VERSION_MOTOR  # noqa: E402
from larrem.cobertura import matriz_cobertura, resumen_cobertura  # noqa: E402
from larrem.historial import (comparar, guardar_ejecucion, leer_previos_desde_ejecucion,  # noqa: E402
                              leer_previos_desde_reporte, listar_ejecuciones)
from larrem.motor import Parametros, cargar_configuracion, indicadores, preparar_archivo, validar  # noqa: E402
from larrem.reglas import CUMPLE, INCUMPLE, NO_APLICA, NO_EVALUABLE  # noqa: E402
from larrem.reportes import NOMBRE_ESTADO, NOMBRE_POBLACION, NOMBRE_SEVERIDAD, ORDEN_SEVERIDAD, _es_personal  # noqa: E402
from estilo import (ICONO_SEVERIDAD, SEVERIDAD_COLOR, aplicar_estilo, encabezado, leyenda_colores,  # noqa: E402
                    paso, tarjetas)

st.set_page_config(page_title="Validador LARREM – Aire", page_icon="🌬️", layout="wide")
aplicar_estilo()

ETAPAS = {
    "captura": "Captura: solo las respuestas del formato",
    "recodificacion": "Recodificación: captura y variables derivadas (CODIF.)",
    "enriquecimiento": "Enriquecimiento: además, campos geográficos y de exposición",
}


@st.cache_resource(show_spinner="Cargando la configuración de reglas…")
def configuracion(huella: str):
    return cargar_configuracion()


def huella_config() -> str:
    h = hashlib.sha256()
    for f in sorted((RAIZ / "configuracion").rglob("*.yaml")):
        h.update(f.read_bytes())
    return h.hexdigest()


@st.cache_data(show_spinner=False, max_entries=12)
def _leer(tem_id: str, nombre: str, contenido: bytes):
    return preparar_archivo(configuracion(tem_id), contenido, nombre)


def es_local() -> bool:
    """En Streamlit Cloud el disco no persiste: el historial se guarda solo al ejecutar en un equipo."""
    return not Path("/mount/src").exists()


def graficos_panorama(res, desc: dict[str, str]) -> None:
    """Dos gráficos: hallazgos por población y severidad, y las reglas con más hallazgos."""
    if not res.hallazgos:
        st.success("No hay hallazgos para las reglas ejecutadas.")
        return
    orden = [NOMBRE_SEVERIDAD[s] for s in ORDEN_SEVERIDAD]
    escala = alt.Scale(domain=orden, range=[SEVERIDAD_COLOR[s][0] for s in ORDEN_SEVERIDAD])
    df = pd.DataFrame([{"Población": NOMBRE_POBLACION.get(h.poblacion, h.poblacion),
                        "Severidad": NOMBRE_SEVERIDAD.get(h.severidad, h.severidad),
                        "orden": ORDEN_SEVERIDAD.get(h.severidad, 9), "Regla": h.regla} for h in res.hallazgos])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Hallazgos por población**")
        agg = df.groupby(["Población", "Severidad", "orden"]).size().reset_index(name="Hallazgos")
        ch = alt.Chart(agg).mark_bar(cornerRadius=3).encode(
            y=alt.Y("Población:N", title=None, sort="-x"),
            x=alt.X("Hallazgos:Q", stack="zero"),
            color=alt.Color("Severidad:N", scale=escala, legend=alt.Legend(orient="bottom", title=None)),
            order=alt.Order("orden:Q"),
            tooltip=["Población", "Severidad", "Hallazgos"],
        ).properties(height=260)
        st.altair_chart(ch, width="stretch")
    with c2:
        st.markdown("**Reglas con más hallazgos**")
        top = df.groupby(["Regla", "Severidad"]).size().reset_index(name="Hallazgos")
        top = top.sort_values("Hallazgos", ascending=False).head(12)
        top["Descripción"] = top["Regla"].map(desc).fillna("")
        ch = alt.Chart(top).mark_bar(cornerRadius=3).encode(
            y=alt.Y("Regla:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)),
            x=alt.X("Hallazgos:Q"),
            color=alt.Color("Severidad:N", scale=escala, legend=None),
            tooltip=["Regla", "Descripción", "Severidad", "Hallazgos"],
        ).properties(height=320)
        st.altair_chart(ch, width="stretch")
    st.caption("Pase el cursor sobre una barra para ver el detalle. Un registro puede tener varios hallazgos.")


tem_id = huella_config()
tem = configuracion(tem_id)
pob_nombres = {p.codigo: p.nombre for p in tem.poblaciones}

# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.markdown('<p class="lr-side-marca">🌬️ Validador LARREM</p>'
                '<p class="lr-side-sub">Vigilancia en salud ambiental · temática aire</p>', unsafe_allow_html=True)
    st.markdown(f'<span class="lr-badge">Configuración {tem.version_configuracion}</span>'
                f'<span class="lr-badge">{tem.fecha_configuracion}</span>'
                f'<span class="lr-badge">Motor {VERSION_MOTOR}</span>', unsafe_allow_html=True)
    st.divider()
    estados = pd.Series([r.estado for r in tem.reglas]).value_counts()
    pend = sum(1 for d in tem.decisiones if not d.respuesta)
    c1, c2 = st.columns(2)
    c1.metric("Reglas", len(tem.reglas))
    c2.metric("Pendientes", pend, help="Decisiones pendientes con el equipo técnico")
    with st.expander("Reglas por estado"):
        for est, n in estados.items():
            st.write(f"- {NOMBRE_ESTADO.get(est, est)}: {n}")
    st.divider()
    st.markdown("**Colores en la base marcada**")
    leyenda_colores()
    st.divider()
    st.caption("Los archivos se procesan en memoria durante la sesión y no se modifican. "
               "El reporte oculta por defecto los valores de variables con datos personales.")

encabezado("Validación de bases LARREM – Aire",
           "Revisa las bases de menores de 5 años, 5 a 14 años y 60 años y más, y entrega el reporte y la base marcada.",
           [f"Configuración {tem.version_configuracion}", f"{len(tem.reglas)} reglas", "Los originales no se modifican"])
tab_val, tab_hist, tab_reglas = st.tabs(["📂 Validar archivos", "🕘 Historial", "📘 Reglas y decisiones"])

# ---------------------------------------------------------------- validar
with tab_val:
    paso(1, "Cargar las bases", "Uno o varios archivos Excel; el validador reconoce la población de cada uno.")
    subidos = st.file_uploader("Archivos Excel de las bases (una o varias poblaciones)", type=["xlsx", "xlsm"],
                               accept_multiple_files=True)
    if not subidos:
        st.info("Cargue uno o más archivos .xlsx. El validador detecta la población por las columnas y el número de acta.")
    preparados = []
    if subidos:
        paso(2, "Confirmar la población de cada archivo", "Revise que la población detectada sea la correcta.")
        opciones = list(pob_nombres)
        for i, up in enumerate(subidos):
            ap = _leer(tem_id, up.name, up.getvalue())
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"**{up.name}**")
                    if ap.hoja is None:
                        st.error("No se encontraron datos legibles. " + " ".join(ap.libro.avisos))
                        continue
                    st.caption(f"Hoja «{ap.hoja.hoja}», encabezado en la fila {ap.hoja.fila_encabezado}, "
                               f"{len(ap.hoja.filas):,} registros".replace(",", "."))
                    det = next((d for d in ap.deteccion if d.hoja == ap.hoja.hoja), None)
                    if det:
                        conf = {"alta": "🟢 alta", "media": "🟡 media", "baja": "🔴 baja"}[det.confianza]
                        st.write(f"Población detectada: **{pob_nombres.get(det.codigo, 'no identificada')}** · confianza {conf}")
                        with st.expander("¿Cómo se detectó?"):
                            for e in det.explicacion:
                                st.write("- " + e)
                    for av in ap.libro.avisos + ap.hoja.avisos:
                        st.warning(av)
                with c2:
                    defecto = opciones.index(ap.poblacion_detectada) if ap.poblacion_detectada in opciones else None
                    eleccion = st.selectbox("Población", opciones, index=defecto, key=f"pob_{i}_{up.name}",
                                            format_func=lambda c: pob_nombres[c],
                                            placeholder="Seleccione la población")
                    if ap.confianza == "baja":
                        st.caption("La confianza es baja: seleccione la población para validar este archivo.")
                    elif eleccion != ap.poblacion_detectada:
                        st.warning("La población elegida no coincide con la detectada. Verifique antes de validar.")
                ap.poblacion = eleccion
                preparados.append(ap)

        paso(3, "Definir los parámetros", "Periodo, etapa y, si quiere comparar, el reporte del corte anterior.")
        hoy = date.today()
        ini_def = date(hoy.year, 1, 1)
        fin_def = date(hoy.year, 6, 30)
        c1, c2, c3 = st.columns(3)
        with c1:
            p_ini = st.date_input("Inicio del periodo esperado", ini_def, format="DD/MM/YYYY")
            p_fin = st.date_input("Fin del periodo esperado", fin_def, format="DD/MM/YYYY")
        with c2:
            etapa = st.radio("Etapa de la base", list(ETAPAS), index=1, format_func=ETAPAS.get)
        with c3:
            subredes = st.multiselect("Subredes esperadas", list(tem.subredes), placeholder="Todas")
            localidades = st.multiselect("Localidades esperadas", tem.localidades, placeholder="Todas")
        ambito = st.text_input("Descripción del ámbito (opcional)", placeholder="Ej.: corte primer semestre, Subred Centro Oriente")
        c1, c2 = st.columns(2)
        with c1:
            ocultar = st.checkbox("Ocultar en el reporte los valores de datos personales", value=True)
        with c2:
            previo = st.file_uploader("Reporte de una ejecución anterior para comparar (opcional)", type=["xlsx"],
                                      key="previo")
            previa_local = None
            if es_local():
                hist = listar_ejecuciones()
                if hist:
                    etiquetas = {h["carpeta"]: f"{h['id_ejecucion']} · {', '.join(a['archivo'] for a in h['archivos'])[:80]}" for h in hist}
                    previa_local = st.selectbox("…o elegir una ejecución guardada", [None, *etiquetas],
                                                format_func=lambda c: "(ninguna)" if c is None else etiquetas[c])
        listos = [a for a in preparados if a.poblacion]
        faltan = len(preparados) - len(listos)
        if faltan:
            st.warning(f"{faltan} archivo(s) sin población confirmada no se validarán.")
        if p_ini > p_fin:
            st.error("El inicio del periodo es posterior al fin.")
        st.write("")
        if st.button("▶  Validar", type="primary", disabled=not listos or p_ini > p_fin, width="stretch"):
            with st.spinner("Validando…"):
                par = Parametros(periodo_inicio=p_ini, periodo_fin=p_fin, subredes=subredes,
                                 localidades=localidades, etapa=etapa, descripcion_ambito=ambito)
                res = validar(tem, listos, par)
                comp = None
                try:
                    if previo is not None:
                        prev, meta = leer_previos_desde_reporte(previo.getvalue())
                        comp = comparar(res, prev, meta)
                    elif previa_local:
                        prev, meta = leer_previos_desde_ejecucion(previa_local)
                        comp = comparar(res, prev, meta)
                except ValueError as exc:
                    st.error(f"No se pudo leer la ejecución anterior: {exc}")
                from larrem.marcado import generar_bases_marcadas
                from larrem.reportes import generar_reporte
                xlsx = generar_reporte(res, comp, ocultar_datos_personales=ocultar)
                marcadas = generar_bases_marcadas(res, listos)
                st.session_state["resultado"] = (res, comp, xlsx, ocultar)
                st.session_state["marcadas"] = marcadas
                st.session_state["guardado"] = None

    if "resultado" in st.session_state and subidos:
        res, comp, xlsx, ocultar = st.session_state["resultado"]
        ind = indicadores(res)
        st.divider()
        paso(4, "Resultados", "Descargue el reporte y las bases marcadas, o revise los hallazgos aquí mismo.")
        st.caption(f"Ejecución {res.id_ejecucion} · {res.duracion_segundos} s · configuración {res.version_configuracion} "
                   f"({res.huella_reglas})")
        for av in res.avisos:
            st.warning(av)
        sev_h, sev_r = ind["hallazgos_por_severidad"], ind["registros_por_severidad"]
        def _n(x):
            return f"{x:,}".replace(",", ".")
        tarjetas([("Registros revisados", _n(ind["registros"]), f"{len(res.archivos)} archivo(s)", "neutro")]
                 + [(f"{ICONO_SEVERIDAD[s]} {NOMBRE_SEVERIDAD[s]}", _n(sev_h.get(s, 0)),
                     f"hallazgos en {_n(sev_r.get(s, 0))} registros", s) for s in ORDEN_SEVERIDAD])
        st.caption(f"{ind['registros_afectados_sin_revision']} registros distintos con bloqueantes, errores o alertas · "
                   f"{ind['resultados_no_evaluables']} resultados no evaluables en {ind['controles_con_no_evaluables']} controles · "
                   f"{ind['reglas_no_ejecutadas']} reglas no ejecutadas. Un registro puede tener varios hallazgos.")
        nombre_xlsx = f"reporte_validacion_{res.id_ejecucion}.xlsx"
        c1, c2 = st.columns([1, 2])
        with c1:
            st.download_button("⬇  Descargar reporte Excel", xlsx, nombre_xlsx, type="primary", width="stretch",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            if es_local():
                if st.session_state.get("guardado"):
                    st.success(f"Guardada en {st.session_state['guardado']}")
                elif st.button("Guardar en el historial"):
                    st.session_state["guardado"] = str(guardar_ejecucion(res, xlsx))
                    st.rerun()
            else:
                st.caption("Para comparar el próximo corte, conserve el reporte descargado y súbalo en el paso 3.")

        marcadas = st.session_state.get("marcadas") or {}
        if marcadas:
            with st.container(border=True):
                st.markdown("**🖍️ Bases con los hallazgos marcados (copias de trabajo)**")
                st.caption("Copia de cada base con las celdas en rojo (error), amarillo (alerta) y azul (revisión humana), un comentario en cada "
                           "celda con la regla y lo esperado, y columnas de resumen al final para filtrar. Los registros "
                           "están en las mismas filas que en el original. El archivo original no se modifica. "
                           "La copia contiene todos los datos de la base: trátela con la misma reserva.")
                cols_m = st.columns(min(len(marcadas), 3))
                pob_archivo = {Path(a.archivo).stem: a.poblacion for a in res.archivos}
                for k, (nombre, contenido) in enumerate(marcadas.items()):
                    pob = next((NOMBRE_POBLACION.get(v, v) for st_, v in pob_archivo.items()
                                if nombre.startswith(st_)), "Base")
                    cols_m[k % len(cols_m)].download_button(
                        f"⬇  {pob} – marcada", contenido, nombre, key=f"marcada_{k}", width="stretch", help=nombre,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        personales = {p.codigo: {v.nombre for v in p.variables if v.personal} for p in tem.poblaciones}
        desc = {r.id: r.descripcion for r in tem.reglas}

        def tabla(hs):
            return pd.DataFrame([{
                "Severidad": f"{ICONO_SEVERIDAD.get(h.severidad, '')} {NOMBRE_SEVERIDAD.get(h.severidad, h.severidad)}",
                "Población": NOMBRE_POBLACION.get(h.poblacion),
                "Archivo": h.archivo, "Fila": h.fila_excel, "Registro": h.id_registro, "Acta": h.no_acta,
                "Regla": h.regla, "Descripción": desc.get(h.regla, ""), "Variable": h.variable,
                "Observado": "(oculto)" if ocultar and _es_personal(h, personales) else h.observado,
                "Esperado": h.esperado, "Explicación": h.explicacion, "Fuente": h.fuente,
            } for h in hs])

        t0, t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Panorama", "🔎 Hallazgos", "📋 Por regla", "⚪ No evaluables",
                                              "🧱 Estructura", "🗺️ Cobertura", "🔁 Comparación"])
        with t0:
            graficos_panorama(res, desc)
        with t1:
            df = tabla(sorted(res.hallazgos, key=lambda h: (ORDEN_SEVERIDAD.get(h.severidad, 9), h.archivo, h.fila_excel)))
            if df.empty:
                st.success("No hay hallazgos para las reglas ejecutadas. Esto no certifica la base: revise los no evaluables y las reglas no ejecutadas.")
            else:
                f1, f2, f3 = st.columns(3)
                fs = f1.multiselect("Severidad", df["Severidad"].unique().tolist(), placeholder="Todas")
                fp = f2.multiselect("Población", df["Población"].unique().tolist(), placeholder="Todas")
                fr = f3.multiselect("Regla", sorted(df["Regla"].unique().tolist()), placeholder="Todas")
                v = df
                if fs:
                    v = v[v["Severidad"].isin(fs)]
                if fp:
                    v = v[v["Población"].isin(fp)]
                if fr:
                    v = v[v["Regla"].isin(fr)]
                st.caption(f"{len(v)} hallazgos en {v[['Archivo', 'Fila']].drop_duplicates().shape[0]} registros")
                st.dataframe(v, hide_index=True, width="stretch", height=460)
        with t2:
            filas = []
            for a in res.archivos:
                for rr in a.resumen_reglas + []:
                    c = rr.conteos
                    ev = c[CUMPLE] + c[INCUMPLE]
                    filas.append({"Regla": rr.regla.id, "Población": NOMBRE_POBLACION.get(a.poblacion), "Tipo": rr.regla.tipo,
                                  "Estado": NOMBRE_ESTADO.get(rr.regla.estado), "Evaluados": ev, "Incumple": c[INCUMPLE],
                                  "No aplica": c[NO_APLICA], "No evaluable": c[NO_EVALUABLE],
                                  "Tasa de incumplimiento": (c[INCUMPLE] / ev) if ev else None})
            for rr in res.resumen_lote:
                c = rr.conteos
                ev = c[CUMPLE] + c[INCUMPLE]
                filas.append({"Regla": rr.regla.id, "Población": "cruce entre archivos", "Tipo": rr.regla.tipo,
                              "Estado": NOMBRE_ESTADO.get(rr.regla.estado), "Evaluados": ev, "Incumple": c[INCUMPLE],
                              "No aplica": c[NO_APLICA], "No evaluable": c[NO_EVALUABLE],
                              "Tasa de incumplimiento": (c[INCUMPLE] / ev) if ev else None})
            dfr = pd.DataFrame(filas)
            solo = st.checkbox("Solo reglas con incumplimientos o no evaluables", value=True)
            if solo and not dfr.empty:
                dfr = dfr[(dfr["Incumple"] > 0) | (dfr["No evaluable"] > 0)]
            st.dataframe(dfr, hide_index=True, width="stretch",
                         column_config={"Tasa de incumplimiento": st.column_config.NumberColumn(format="percent")})
            if res.reglas_no_ejecutadas:
                with st.expander(f"{len(res.reglas_no_ejecutadas)} reglas no ejecutadas"):
                    st.dataframe(pd.DataFrame([{"Regla": r.id, "Estado": NOMBRE_ESTADO.get(r.estado), "Motivo": m,
                                                "Insumo requerido": r.insumo_requerido or ""}
                                               for r, m in res.reglas_no_ejecutadas]), hide_index=True, width="stretch")
        with t3:
            if not res.no_evaluables:
                st.write("Todos los controles ejecutados pudieron evaluarse.")
            else:
                dne = pd.DataFrame([{"Población": NOMBRE_POBLACION.get(h.poblacion), "Regla": h.regla, "Motivo": h.explicacion,
                                     "Fila": h.fila_excel} for h in res.no_evaluables])
                agg = dne.groupby(["Población", "Regla", "Motivo"]).agg(Resultados=("Fila", "size")).reset_index()
                st.dataframe(agg.sort_values("Resultados", ascending=False), hide_index=True, width="stretch")
                st.caption("Un no evaluable nunca se cuenta como cumplido. Varios provienen de decisiones pendientes (ver Reglas y decisiones).")
        with t4:
            for a in res.archivos:
                e = a.estructura
                with st.expander(f"{a.archivo} – {NOMBRE_POBLACION.get(a.poblacion)}", expanded=True):
                    igual = e.huella_encontrada == e.huella_esperada
                    (st.success if igual else st.warning)(
                        "La estructura coincide con el instrumento configurado." if igual else
                        "La estructura difiere del instrumento configurado: revise columnas nuevas y ausentes.")
                    st.write(f"**Columnas nuevas:** {', '.join(n for _, n in e.columnas_nuevas) or 'ninguna'}")
                    st.write(f"**Ausentes:** {', '.join(e.columnas_ausentes) or 'ninguna'}"
                             + (f" — obligatorias: {', '.join(e.ausentes_requeridas)}" if e.ausentes_requeridas else ""))
                    st.write(f"**Ambiguas:** {', '.join(e.variables_ambiguas) or 'ninguna'}")
                    ren = [f"{c.encabezado_original} → {v}" for v, c in e.correspondencias.items() if c.metodo != "exacta"]
                    st.write(f"**Reconocidas con otro nombre:** {', '.join(ren) or 'ninguna'}")
                    st.write(f"**Columnas vacías:** {', '.join(e.columnas_vacias) or 'ninguna'}")
                    for av in e.avisos:
                        st.warning(av)
        with t5:
            filas = matriz_cobertura(tem, res)
            pobs = {a.poblacion for a in res.archivos}
            filas = [f for f in filas if f.poblacion in pobs]
            st.dataframe(pd.DataFrame(resumen_cobertura(filas)), hide_index=True, width="stretch")
            st.dataframe(pd.DataFrame([f.como_dict() for f in filas]), hide_index=True, width="stretch", height=400)
        with t6:
            if comp is None:
                st.write("No se cargó una ejecución anterior. Suba un reporte anterior en el paso 3 para ver nuevos, persistentes y resueltos.")
            else:
                for av in comp.avisos:
                    st.warning(av)
                r = comp.resumen()
                c = st.columns(4)
                c[0].metric("Nuevos", r["nuevos"])
                c[1].metric("Persistentes", r["persistentes"])
                c[2].metric("Resueltos", r["resueltos"])
                c[3].metric("No comparables", r["no_comparables_actuales"] + r["no_comparables_previos"])
                st.caption("Resuelto: la regla volvió a ejecutarse para esa población y el hallazgo no aparece. "
                           "No comparable: el registro no tiene ID estable, o la población/regla no se evaluó en esta ejecución.")
                if comp.nuevos:
                    st.markdown("**Nuevos**")
                    st.dataframe(tabla(comp.nuevos), hide_index=True, width="stretch", height=300)
                if comp.resueltos:
                    st.markdown("**Resueltos**")
                    st.dataframe(pd.DataFrame([{"Clave": p.clave, "Severidad": p.severidad, "Estado anterior": p.estado_equipo}
                                               for p in comp.resueltos]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- historial
with tab_hist:
    if not es_local():
        st.info("En la versión publicada el historial no se guarda en el servidor. Conserve los reportes descargados: "
                "al subir el reporte anterior en el paso 3 se obtiene la comparación entre cortes.")
    hist = listar_ejecuciones() if es_local() else []
    if es_local() and not hist:
        st.write("Aún no hay ejecuciones guardadas. Use «Guardar en el historial» después de validar.")
    if hist:
        st.dataframe(pd.DataFrame([{
            "Ejecución": h["id_ejecucion"], "Fecha": h["fecha_hora"], "Configuración": h["version_configuracion"],
            "Archivos": ", ".join(a["archivo"] for a in h["archivos"]),
            "Registros": h["indicadores"]["registros"], "Hallazgos": h["indicadores"]["hallazgos_total"],
            "Registros afectados (sin revisión)": h["indicadores"]["registros_afectados_sin_revision"],
            "Duración (s)": h.get("duracion_segundos"), "Carpeta": h["carpeta"],
        } for h in hist]), hide_index=True, width="stretch")

# ---------------------------------------------------------------- reglas
with tab_reglas:
    st.subheader("Decisiones pendientes")
    st.caption("Mientras no tengan respuesta, el validador aplica el tratamiento indicado. El cuestionario completo "
               "está en la hoja H_Decisiones del reporte.")
    for d in tem.decisiones:
        with st.expander(f"{d.id} · {d.tema}" + (" ✅" if d.respuesta else "")):
            st.write(f"**Diferencia:** {d.diferencia}")
            st.write(f"**Qué hace hoy el validador:** {d.efecto_en_validador}")
            st.write(f"**Pregunta:** {d.pregunta}")
            st.caption("Fuentes: " + "; ".join(f"{f.doc} {f.ubicacion}" for f in d.fuentes)
                       + (" · Reglas: " + ", ".join(d.reglas) if d.reglas else ""))
            if d.respuesta:
                st.success(f"Respuesta ({d.fecha_respuesta}): {d.respuesta}")
    st.subheader("Catálogo de reglas")
    c1, c2 = st.columns(2)
    fpob = c1.multiselect("Población ", list(pob_nombres), format_func=pob_nombres.get, placeholder="Todas")
    fest = c2.multiselect("Estado", list(NOMBRE_ESTADO), format_func=NOMBRE_ESTADO.get, placeholder="Todos")
    cat = [r for r in tem.reglas if (not fpob or set(fpob) & set(r.poblaciones)) and (not fest or r.estado in fest)]
    st.dataframe(pd.DataFrame([{
        "Regla": r.id, "Poblaciones": ", ".join(r.poblaciones), "Descripción": r.descripcion, "Tipo": r.tipo,
        "Etapa": r.etapa, "Severidad": NOMBRE_SEVERIDAD.get(r.severidad), "Estado": NOMBRE_ESTADO.get(r.estado),
        "Motivo": r.motivo_estado or "", "Fuentes": "; ".join(f"{f.doc} {f.ubicacion}" for f in r.fuentes),
    } for r in cat]), hide_index=True, width="stretch", height=500)
