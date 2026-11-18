# Actualizaciones del validador

Este documento explica cómo se pide un cambio, cómo se hace, cómo se publica y cómo lo reciben los usuarios. Está pensado para que cualquier persona pueda continuar el mantenimiento sin depender de quien lo desarrolló.

Repositorio: <https://github.com/wilsonsr/validador_larrem> · Descargas: <https://github.com/wilsonsr/validador_larrem/releases>

## 1. Versiones

| Qué | Dónde | Formato | Cuándo sube |
|---|---|---|---|
| Versión del validador (la que se publica) | `version_configuracion` en `configuracion/aire/tematica.yaml` | `año.mes.número` (2026.11.2, 2026.12.1…) | En **cada** publicación, aunque solo cambie la interfaz o la documentación |
| Versión del motor | `VERSION_MOTOR` en `src/larrem/__init__.py` | `mayor.menor.corrección` (1.1.0) | Cuando cambia el código de `src/larrem/`: corrección → 1.1.1; función nueva → 1.2.0; cambio que rompe configuraciones anteriores → 2.0.0 |
| Versión de cada regla | campo `version` de la regla | entero | Cuando cambia el criterio de esa regla |

El reporte (hoja A_Resumen) y la barra lateral de la aplicación muestran la versión del validador y del motor: así se sabe con qué versión se revisó cada base.

## 2. Pedir un cambio (equipo técnico y usuarios)

1. Abra una **Issue** en el repositorio (pestaña *Issues* → *New issue*) o, si no tiene cuenta de GitHub, escriba al responsable del validador.
2. Incluya: población, nombre de la regla que aparece en el reporte, **fila de Excel** del caso y qué esperaba. No pegue nombres, documentos ni direcciones: la fila y el ID SIVIGILA bastan.
3. El responsable registra la solicitud en `docs/registro_solicitudes.csv` con el siguiente número (SOL-027, SOL-028…) y su estado: *Aplicado*, *Aplicado (provisional)*, *No aplicado*, *Requiere evidencia*, *Requiere aclaración* o *Pendiente*.

**Criterio para aceptar un cambio.** Un hallazgo se retira solo si la regla contradice los documentos fuente o si hay un falso positivo demostrado con un caso. Una regla nueva entra solo si se puede verificar con los datos de la base y tiene respaldo documental (guía, instructivo, diccionario u observación escrita del equipo). Las contradicciones entre documentos no se resuelven en silencio: van a `decisiones_pendientes.yaml`.

## 3. Hacer el cambio (responsable del validador)

1. **Descargue la última versión** del repositorio (GitHub Desktop: *Fetch origin* → *Pull*).
2. **Haga el cambio:**
   - Reglas: edite los YAML de `configuracion/aire/reglas/` (ver `docs/mantenimiento_reglas.md`). Cite la solicitud en la regla (`nota: "SOL-027"`) y suba su `version`.
   - Variables nuevas o renombradas en la base: `variables/*.yaml` y `equivalencias/*.yaml`. Si cambia la obligatoriedad, ejecute `python herramientas/generar_obligatoriedad.py`.
   - Lógica nueva del motor: `src/larrem/` (requiere conocer Python). Agregue una prueba en `tests/`.
3. **Ejecute las pruebas** con `ejecutar_pruebas.bat`. Si alguna falla, no se publica.
4. **Pruebe con bases reales o de demostración** y compare con el reporte anterior (paso 3 de la aplicación). Revise que los hallazgos nuevos y resueltos sean los esperados.
5. **Suba la versión** en `tematica.yaml` (`version_configuracion` y `fecha_configuracion`).
6. **Anote el cambio** en `CHANGELOG.md` (qué cambió y qué solicitud lo originó) y actualice el estado en `registro_solicitudes.csv`.

## 4. Publicar la versión

1. En GitHub Desktop escriba un resumen (por ejemplo *2026.12.1: P13 en el rango de síntomas (SOL-013)*), pulse **Commit to main** y luego **Push origin**.
2. En GitHub, pestaña **Releases** → **Draft a new release**:
   - *Tag*: `v2026.12.1` (la misma versión de `tematica.yaml`).
   - *Título*: `Validador LARREM 2026.12.1`.
   - *Descripción*: copie la sección de esa versión del `CHANGELOG.md`.
   - Adjunte el zip del validador (`validador_larrem_<versión>.zip`, con la carpeta `validador_larrem` adentro) y, si quiere, el `TUTORIAL_VALIDADOR_LARREM.pdf`.
   - **Publish release**.
3. Avise al equipo con un mensaje corto: versión, qué cambió y el enlace de *Releases*.

**El zip.** Se arma comprimiendo la carpeta del repositorio (sin `.venv`, `.git` ni `resultados`). Incluye las bases de demostración **sintéticas**; si cambian las reglas o la estructura de las bases, se regeneran con `python herramientas/generar_demo_sintetica.py <bases de referencia>` (ver `datos_demostracion/LEEME.md`). GitHub también agrega un *Source code (zip)*, que sirve igual.

**Datos personales.** Nunca suba bases, reportes, bases marcadas ni la carpeta `resultados/` al repositorio. El archivo `.gitignore` los excluye; aun así, antes de cada *Commit* revise en GitHub Desktop la lista de archivos: solo deben aparecer `.py`, `.yaml`, `.md`, `.csv` de documentación, `.bat`, `.txt` y el PDF del tutorial.

## 5. Recibir una actualización (usuarios)

1. Cierre el validador (la ventana negra).
2. Si quiere conservar su historial, copie la carpeta `resultados\ejecuciones` a otro lugar.
3. Descargue `validador_larrem_<versión>.zip` desde *Releases* y descomprímalo **reemplazando** la carpeta anterior (o en una carpeta nueva).
4. Si copió el historial, vuelva a ponerlo en `resultados\ejecuciones`.
5. Abra `iniciar_validador.bat`. Si la versión nueva cambió las librerías, el archivo lo detecta e instala lo necesario (requiere internet, unos minutos).
6. Verifique en la barra lateral, o en la hoja A_Resumen del reporte, que aparece la versión nueva.

Las bases de cada usuario viven en sus propias carpetas: la actualización no las toca.

## 6. Librerías

`requirements.txt` fija las versiones exactas (`==`) con las que se probó el validador, para que todos los equipos instalen lo mismo y nada cambie solo.

Una vez al año, o cuando salga una versión de Python que el equipo vaya a usar:

1. En un entorno de prueba: `pip install --upgrade openpyxl pydantic PyYAML XlsxWriter pandas altair streamlit pytest`.
2. Ejecute las pruebas y abra la aplicación con las bases de demostración.
3. Si todo funciona, anote las versiones nuevas (`pip freeze`) en `requirements.txt`, suba la versión del validador y publique.

Al cambiar `requirements.txt`, `iniciar_validador.bat` reinstala las librerías la próxima vez que cada usuario lo abra.

## 7. Nuevas temáticas (ruido, radiación electromagnética, quejas…)

El motor no depende de la temática. Una temática nueva es una carpeta nueva con la misma estructura:

```
configuracion/ruido/
├── tematica.yaml          documentos fuente, poblaciones, versión propia
├── variables/*.yaml       catálogo de variables por población
├── equivalencias/*.yaml   nombres alternativos de columnas
└── reglas/*.yaml          reglas
```

Pasos: (1) reunir los documentos fuente de la temática (guía, instructivo, diccionario); (2) generar el catálogo de variables con `herramientas/generar_catalogo_variables.py`; (3) escribir las reglas citando las fuentes; (4) agregar pruebas; (5) agregar el selector de temática en la aplicación (cambio pequeño en `app.py` y `cargar_configuracion`, que hoy carga `aire`). Cada temática conserva su propia versión, de modo que un cambio en ruido no altera las reglas de aire.

## 8. Continuidad

- **Dos personas con permisos.** Además del responsable, al menos una persona de planta debe tener acceso de escritura al repositorio (GitHub: *Settings* → *Collaborators* → *Add people*).
- **Repositorio institucional.** Cuando la entidad tenga una organización en GitHub, el repositorio se transfiere (*Settings* → *Transfer ownership*) sin perder historial, Issues ni Releases.
- **Todo está escrito.** `README.md` (qué es), `docs/guia_usuario.md` (uso), `docs/mantenimiento_reglas.md` (reglas), este documento (actualizaciones), `CHANGELOG.md` (historia) y `docs/registro_solicitudes.csv` (decisiones).
