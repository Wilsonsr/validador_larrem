"""Apariencia de la interfaz: estilos, encabezado, pasos y tarjetas de resumen.

Solo presentación: no contiene lógica de validación. Los colores de severidad son los mismos
de la base marcada (rojo error, amarillo alerta, azul revisión humana).
"""
from __future__ import annotations

from html import escape

import streamlit as st

AZUL = "#1F3864"
SEVERIDAD_COLOR = {  # (acento, fondo, texto)
    "bloqueante": ("#C00000", "#FBE3E3", "#7A0000"),
    "error": ("#E0565B", "#FDECEE", "#9C0006"),
    "alerta": ("#E0A800", "#FFF6D6", "#7A4F00"),
    "revision": ("#2E75B6", "#E6F0FA", "#1F4E79"),
}
ICONO_SEVERIDAD = {"bloqueante": "⛔", "error": "🔴", "alerta": "🟡", "revision": "🔵"}

_CSS = f"""
<style>
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 4.5rem !important; max-width: 1400px; }}
.lr-hero {{
  background: linear-gradient(120deg, {AZUL} 0%, #2E5C9A 60%, #3D7CC9 100%);
  color: #fff; border-radius: 14px; padding: 22px 28px; margin-bottom: 18px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
}}
.lr-hero h1 {{ color: #fff; font-size: 1.7rem; margin: 0; padding: 0; font-weight: 700; }}
.lr-hero p {{ margin: 4px 0 0; opacity: .88; font-size: .95rem; }}
.lr-chips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.lr-chip {{
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
  border-radius: 999px; padding: 4px 12px; font-size: .8rem; white-space: nowrap;
}}
.lr-paso {{ display: flex; align-items: center; gap: 12px; margin: 22px 0 6px; }}
.lr-num {{
  background: {AZUL}; color: #fff; width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-weight: 700; flex: none;
}}
.lr-paso-t {{ font-size: 1.2rem; font-weight: 650; color: {AZUL}; line-height: 1.2; }}
.lr-paso-s {{ font-size: .85rem; color: #5B6575; }}
.lr-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 8px 0 6px; }}
.lr-card {{
  border-radius: 12px; padding: 14px 16px; border-left: 6px solid var(--acento);
  background: var(--fondo); color: var(--texto);
}}
.lr-card .t {{ font-size: .82rem; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; opacity: .85; }}
.lr-card .v {{ font-size: 2rem; font-weight: 750; line-height: 1.15; margin-top: 2px; }}
.lr-card .s {{ font-size: .8rem; opacity: .85; }}
.lr-side-marca {{ font-size: 1.25rem; font-weight: 750; color: {AZUL}; margin-bottom: 0; }}
.lr-side-sub {{ font-size: .8rem; color: #5B6575; margin-top: -2px; }}
.lr-badge {{
  display: inline-block; background: #E6ECF5; color: {AZUL}; border-radius: 6px;
  padding: 2px 8px; font-size: .78rem; font-weight: 600; margin: 2px 4px 2px 0;
}}
.lr-leyenda span {{ display: inline-block; margin-right: 14px; font-size: .85rem; }}
div[data-testid="stFileUploader"] section {{ border: 2px dashed #9DB3D6; background: #F5F8FC; border-radius: 12px; }}
button[data-baseweb="tab"] p {{ font-size: 1rem; font-weight: 600; }}
</style>
"""


def aplicar_estilo() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str, chips: list[str]) -> None:
    c = "".join(f'<span class="lr-chip">{escape(x)}</span>' for x in chips)
    st.markdown(f'<div class="lr-hero"><div><h1>{escape(titulo)}</h1><p>{escape(subtitulo)}</p></div>'
                f'<div class="lr-chips">{c}</div></div>', unsafe_allow_html=True)


def paso(numero: int | str, titulo: str, ayuda: str = "") -> None:
    s = f'<div class="lr-paso-s">{escape(ayuda)}</div>' if ayuda else ""
    st.markdown(f'<div class="lr-paso"><div class="lr-num">{numero}</div>'
                f'<div><div class="lr-paso-t">{escape(titulo)}</div>{s}</div></div>', unsafe_allow_html=True)


def tarjetas(items: list[tuple[str, str, str, str]]) -> None:
    """items: (título, valor, subtítulo, severidad o 'neutro')."""
    html = []
    for titulo, valor, sub, sev in items:
        acento, fondo, texto = SEVERIDAD_COLOR.get(sev, (AZUL, "#EEF2F8", AZUL))
        html.append(f'<div class="lr-card" style="--acento:{acento};--fondo:{fondo};--texto:{texto}">'
                    f'<div class="t">{escape(titulo)}</div><div class="v">{escape(valor)}</div>'
                    f'<div class="s">{escape(sub)}</div></div>')
    st.markdown(f'<div class="lr-cards">{"".join(html)}</div>', unsafe_allow_html=True)


def leyenda_colores() -> None:
    st.markdown('<div class="lr-leyenda"><span>🔴 Error</span><span>🟡 Alerta</span>'
                '<span>🔵 Revisión humana</span><span>⛔ Bloqueante</span></div>', unsafe_allow_html=True)
