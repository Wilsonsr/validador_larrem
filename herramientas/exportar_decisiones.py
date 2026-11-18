"""Genera docs/decisiones_pendientes.md (cuestionario para el equipo técnico) desde la configuración."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from larrem.motor import cargar_configuracion  # noqa: E402

POB = {"menores5": "menores de 5", "5a14": "5 a 14 años", "mayores60": "60 años y más"}


def main() -> int:
    tem = cargar_configuracion()
    docs = {d.codigo: d.archivo for d in tem.documentos}
    lineas = [
        "# Decisiones pendientes – temática aire",
        "",
        f"Configuración {tem.version_configuracion} ({tem.fecha_configuracion}). Archivo generado con "
        "`herramientas/exportar_decisiones.py`; la fuente es `configuracion/aire/decisiones_pendientes.yaml`.",
        "",
        "Cada decisión describe una diferencia entre documentos que el validador no resuelve por su cuenta. "
        "Mientras no haya respuesta, se aplica el tratamiento de «Qué hace hoy el validador».",
        "",
        "Fuentes: " + "; ".join(f"**{k}** = {v}" for k, v in docs.items()) + ".",
        "",
    ]
    for d in tem.decisiones:
        lineas += [
            f"## {d.id}. {d.tema}",
            "",
            f"*Poblaciones:* {', '.join(POB.get(p, p) for p in d.poblaciones)}",
            "",
            f"**Diferencia.** {d.diferencia}",
            "",
            f"**Fuentes.** {'; '.join(f'{f.doc} {f.ubicacion}' for f in d.fuentes)}",
            "",
            f"**Qué hace hoy el validador.** {d.efecto_en_validador}",
            "",
            f"**Reglas enlazadas.** {', '.join(f'`{r}`' for r in d.reglas) or '—'}",
            "",
            f"**Pregunta.** {d.pregunta}",
            "",
            f"**Respuesta.** {d.respuesta or '_(pendiente)_'}",
            "",
        ]
    salida = RAIZ / "docs" / "decisiones_pendientes.md"
    salida.write_text("\n".join(lineas), encoding="utf-8")
    print(f"{len(tem.decisiones)} decisiones → {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
