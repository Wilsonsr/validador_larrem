# Validador de bases LARREM – temática Aire

Herramienta en Python y Streamlit que revisa las bases de las encuestas de vigilancia por contaminación del aire (menores de 5 años, 5 a 14 años y 60 años y más) y produce un reporte Excel con los hallazgos por registro.

**Qué hace:** valida y reporta. **Qué no hace:** no modifica ni corrige las bases. Los archivos originales se leen en modo solo lectura y nunca se sobrescriben. Las correcciones se hacen en el origen (aplicativo o formato físico) y la base corregida se vuelve a validar.

## Contenido

```
validador_larrem/
├── TUTORIAL_VALIDADOR_LARREM.pdf  Tutorial de instalación y uso para compañeros
├── app.py                       Interfaz Streamlit (en español)
├── estilo.py                    Apariencia de la interfaz (colores, tarjetas, pasos)
├── iniciar_validador.bat        Arranque en Windows (crea el entorno la primera vez)
├── ejecutar_pruebas.bat         Pruebas automáticas en Windows
├── requirements.txt
├── configuracion/aire/          Reglas versionadas (YAML) – lo que el equipo revisa y ajusta
│   ├── tematica.yaml            Documentos fuente, subredes, localidades, poblaciones
│   ├── variables/*.yaml         Catálogo de variables por población (tipo, obligatoriedad, fuente)
│   ├── equivalencias/*.yaml     Nombres alternativos de columnas
│   ├── reglas/00_comunes.yaml   Reglas de las tres poblaciones
│   ├── reglas/05_obligatoriedad.yaml  (generado) campos obligatorios por etapa
│   ├── reglas/10_menores5.yaml, 20_5a14.yaml, 30_mayores60.yaml
│   ├── reglas/90_pendientes.yaml      Reglas identificadas que aún no se ejecutan
│   └── decisiones_pendientes.yaml     Contradicciones e insumos que debe resolver el equipo
├── src/larrem/                  Motor (independiente de la interfaz)
├── datos_demostracion/          Tres bases sintéticas para practicar (ningún registro es real; ver LEEME.md)
├── herramientas/                Línea de comandos, generadores y anonimizador de bases
├── tests/                       Pruebas con datos sintéticos
├── docs/                        Guía de uso, actualizaciones, mantenimiento de reglas, despliegue, decisiones
└── resultados/ejecuciones/      Historial local (manifiesto, reporte y claves de seguimiento)
```

## Descargar

Última versión: <https://github.com/wilsonsr/validador_larrem/releases>. En la versión más reciente, descargue **validador_larrem_<versión>.zip** (en *Assets*) y descomprímalo en una carpeta propia (no dentro de OneDrive). Cómo pedir cambios y cómo actualizar: `docs/actualizaciones.md`.

## Uso en Windows

1. Instale Python 3.10 o superior si el equipo no lo tiene (python.org, marcando *Add python.exe to PATH*). Si no tiene permisos de administrador, la instalación "solo para mí" funciona.
2. Haga doble clic en `iniciar_validador.bat`. La primera vez crea la carpeta `.venv` e instala las dependencias (requiere internet). Si la red usa proxy, el archivo explica cómo configurarlo.
3. Se abre el navegador con el validador. Siga los pasos: cargar las bases, confirmar la población, definir el periodo y la etapa, **Validar** y **Descargar reporte Excel**.

Cuando una versión nueva cambia `requirements.txt`, `iniciar_validador.bat` lo detecta y reinstala las librerías la próxima vez que se abre.

Línea de comandos (sin interfaz):

```
.venv\Scripts\python herramientas\validar_cli.py --inicio 2026-01-01 --fin 2026-06-30 "ruta\base1.xlsx" "ruta\base2.xlsx"
```

## Cómo leer el reporte

| Hoja | Contenido |
|---|---|
| A_Resumen | Ejecución, versiones, archivos (con huella SHA-256), hallazgos y **registros distintos** por severidad y población |
| B_Hallazgos | Un hallazgo por fila: fila de Excel, ID SIVIGILA, acta, regla, valor observado y esperado, explicación, fuente documental, acción sugerida. Las columnas amarillas son para el equipo (estado y observación) |
| C_No_evaluables | Controles que no pudieron evaluarse y por qué. **Un no evaluable nunca cuenta como cumplido** |
| D_Estructura | Hoja y fila de encabezado detectadas, columnas nuevas, ausentes, vacías y renombradas |
| E_Resultado_reglas | Por regla: evaluados, cumple, incumple, no aplica, no evaluable y tasa de incumplimiento con su denominador |
| F_Catalogo_reglas | Todas las reglas, su estado, fuentes y motivo cuando no se ejecutan |
| G_Cobertura | Qué variables tienen reglas de contenido, cuáles solo de obligatoriedad y cuáles solo reglas pendientes |
| H_Decisiones | Cuestionario de decisiones pendientes para el equipo técnico |
| I_Comparacion | Si se cargó un reporte anterior: nuevos, persistentes y resueltos |

**Base marcada.** Además del reporte, el validador entrega una copia de cada base (`<nombre>_MARCADA.xlsx`) con las celdas con error en rojo, con alerta en amarillo y con revisión humana en azul, un comentario en cada celda (regla, valor esperado, explicación y acción) y cuatro columnas de resumen al final de cada fila para filtrar. Los registros quedan en las mismas filas que en el original. La revisión humana no suma en la columna de hallazgos: se lista en la última columna. Es una copia nueva: el archivo original no se modifica. Contiene todos los datos de la base, así que se trata con la misma reserva. En línea de comandos se pide con `--marcar`.

**Severidades.** *Bloqueante*: impide usar la base (ID o acta repetidos, edad fuera de la población). *Error*: contradice una regla documentada. *Alerta*: probable error que requiere verificación. *Revisión humana*: la fuente pide revisar el caso (por ejemplo, NS/NR o texto libre), no es un error.

**Datos personales.** Por defecto el reporte oculta los valores observados de variables marcadas como personales (nombres, identificación, dirección, teléfono, correo). El registro se ubica con la fila de Excel, el ID SIVIGILA y el acta. No se infiere el sexo a partir del nombre.

## Estado de la configuración (versión 2026.11.2)

| Población | Reglas | Implementadas | Revisión humana | Provisionales | Pendientes |
|---|---|---|---|---|---|
| Menores de 5 | 193 | 167 | 10 | 5 | 11 |
| 5 a 14 años | 200 | 175 | 9 | 6 | 10 |
| 60 años y más | 138 | 121 | 7 | 2 | 8 |

(Las reglas comunes se cuentan en cada población.) El 20/10/2026 se respondieron DP-02 (12 meses = categoría 2), DP-03 (gas propano = categoría 1) y DP-06 (16 cigarrillos = severo), todas según el diccionario. Quedan **12 decisiones pendientes** (`docs/decisiones_pendientes.md`). Mientras no se respondan, los casos afectados quedan como *no evaluables* o la regla no se ejecuta; ninguna contradicción se resuelve en silencio.

Todas las reglas tienen `revision_tecnica: pendiente`: fueron extraídas de los documentos por el desarrollador y deben ser aprobadas por el equipo técnico de bases de aire antes de usarse como criterio oficial.

## Control de cambios

El proceso completo (pedir, hacer, publicar y recibir actualizaciones, librerías, nuevas temáticas) está en `docs/actualizaciones.md`.

- `CHANGELOG.md`: qué cambió en cada versión.
- `docs/registro_solicitudes.csv`: cada solicitud del equipo con su número (SOL-001…), estado, versión en que se aplicó y la decisión tomada. Se abre con Excel.
- `docs/solicitudes/`: los documentos originales que envió el equipo.
- Criterio: un hallazgo se retira solo si la regla contradice los documentos o hay un falso positivo demostrado con un caso; una regla nueva entra solo si es verificable con los datos y tiene respaldo.

## Validar el siguiente corte

Ver `docs/guia_usuario.md`. En resumen: cargue las bases nuevas, ajuste el periodo y suba el reporte del corte anterior (con los estados que haya diligenciado el equipo) para obtener nuevos, persistentes y resueltos. Si la estructura cambió (columnas nuevas o renombradas), la hoja D_Estructura lo informa y las reglas afectadas quedan como no evaluables.

## Cambiar reglas

Ver `docs/mantenimiento_reglas.md`. Las reglas son datos (YAML) de tipos cerrados, con condiciones estructuradas: ningún texto de la configuración se ejecuta como código. Después de cualquier cambio, suba `version_configuracion` en `tematica.yaml` y ejecute las pruebas.

## Publicar en Streamlit Cloud

Ver `docs/despliegue_streamlit_cloud.md`. La aplicación funciona igual en la nube. Allí el historial no se conserva en disco: la comparación entre cortes se hace subiendo el reporte anterior.

## Pruebas

```
python -m pytest -q tests        (o ejecutar_pruebas.bat)
```

Las pruebas usan solo datos sintéticos. Incluyen una verificación de que el código no usa `eval` ni `exec` y de que `05_obligatoriedad.yaml` está al día con el catálogo.
