# Registro de cambios

Cada versión se identifica con `año.mes.número` (el valor de `version_configuracion` en `configuracion/aire/tematica.yaml`). El detalle de cada solicitud está en `docs/registro_solicitudes.csv`.

## 2026.11.2 – 18 de noviembre de 2026

Primera versión publicada en GitHub. No cambia ninguna regla ni resultado.

**Interfaz**
- Nuevo diseño: encabezado, pasos numerados, tarjetas de resumen con los colores de la base marcada, pestaña «Panorama» con gráficos de hallazgos por población y por regla, y botones de descarga de las bases marcadas con el nombre de la población.

**Instalación y actualización**
- `requirements.txt` fija las versiones exactas de las librerías.
- `iniciar_validador.bat` detecta cuando cambia `requirements.txt` y reinstala solo (ya no hay que borrar `instalado.txt`).
- Nuevo `docs/actualizaciones.md`: cómo pedir, hacer, publicar y recibir actualizaciones, cómo actualizar librerías, cómo agregar temáticas y continuidad.
- Motor 1.1.0 (recoge los cambios de 2026.11.1: requerido con alternativa, colegios por mayoría, variables opcionales).

**Repositorio público**
- Bases de demostración nuevas, **sintéticas** (150, 100 y 150 registros): ningún registro corresponde a una persona y tienen errores sembrados de todas las severidades. Reemplazan a las anonimizadas, que derivaban de bases reales y ya no se distribuyen. Generador: `herramientas/generar_demo_sintetica.py`.
- Se retiraron nombres de personas de la documentación.

## 2026.11.1 – 14 de noviembre de 2026

Revisión del equipo técnico (`docs/solicitudes/2026-11-14_revision_validador.txt`): 26 solicitudes, 17 aplicadas.

**Base marcada**
- La revisión humana se colorea en azul con su comentario (SOL-004). No suma en la columna de hallazgos.

**Reglas corregidas**
- Barrio puede ir vacío si Otro_Barrio tiene dato (SOL-001).
- P22_Localidad tiene regla y mensaje propios: es la localidad del embarazo, no la del colegio (SOL-002).
- La regla `E_P38_SI` pasa a llamarse `E_P40_REQUERIDA` y explica que la celda por corregir es P40 (SOL-006).
- Colegios: se marca solo el valor minoritario de dirección, localidad, UPZ y barrio; con empate se marcan todos (SOL-009).

**Reglas más estrictas o nuevas**
- El 99 pasa de revisión humana a alerta en las tres poblaciones (SOL-010, SOL-020, SOL-024).
- Ausentismo = 99 cuando el niño asiste al colegio es error (SOL-011).
- Tipo de vivienda frente al complemento de la dirección, como alerta provisional (SOL-007).
- Inquilinato: hasta 2 encuestas en la misma dirección (SOL-008).
- Tarjeta de identidad desde los 8 años, como alerta provisional (SOL-005).
- Errores de digitación en el correo (SOL-012).
- P42 = 1 en 5 a 14: revisar la recomendación en observaciones (SOL-019).

**Reglas retiradas**
- `M5_P21_P25_CONFIRMAR` (bajo peso frente a edad gestacional) deja de ejecutarse, a condición de que se ajuste el instructivo (SOL-003).

**No aplicadas o en espera:** SOL-013 a SOL-017, SOL-022, SOL-023, SOL-025 y SOL-026 (ver el registro).

**Motor:** variables opcionales en el catálogo; parámetros `alternativa` (requerido), `marcar: minoria` (consistencia_grupo) y `esperado` (condicional).

## 2026.10.4 – 20 de octubre de 2026
- Tabaquismo pesado: se calcula para quien fuma o fumó (P18 o P19 = 1); frecuencia semanal ÷ 7; meses ÷ 12.
- Decisiones DP-02, DP-03 y DP-06 aplicadas según el diccionario.
- Nueva base marcada (`_MARCADA.xlsx`) con errores y alertas coloreados.

## 2026.10.1 – 10 de octubre de 2026
- Primera versión: 452 reglas para las tres poblaciones de aire, reporte Excel, historial y comparación entre cortes.
