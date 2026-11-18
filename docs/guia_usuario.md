# Guía de uso del validador

## Antes de validar

- Use los archivos tal como llegan de la subred o del aplicativo. No es necesario quitar filas ni columnas. El validador busca la fila de encabezados, ignora filas vacías y se detiene cuando el rango declarado de la hoja es mucho mayor que el contenido real (lo informa como aviso).
- Puede cargar una, dos o las tres poblaciones a la vez. Al cargarlas juntas también se ejecutan los cruces entre archivos (ID, acta e identificación repetidos entre poblaciones).

## Paso a paso

1. **Cargar las bases.** Arrastre los archivos `.xlsx`.
2. **Confirmar la población.** El validador la detecta por las columnas propias de cada formato y por el prefijo del acta (AR02 menores de 5, AR03 de 5 a 14, AR04 de 60 y más). Con confianza baja se debe elegir a mano. Si elige una población distinta de la detectada, aparece una advertencia.
3. **Parámetros.**
   - *Periodo esperado:* las fechas de encuesta fuera del periodo se reportan como error.
   - *Etapa:* **captura** valida solo las respuestas del formato. **Recodificación** (por defecto) valida además las variables `CODIF.` y derivadas. **Enriquecimiento** valida también coordenadas, ACRE y PM2,5; si una de estas columnas está vacía en todo el archivo, se informa como no evaluable (el proceso aún no se ha hecho) y no como un error por registro.
   - *Subredes y localidades esperadas:* si se indican, los registros de otras subredes o localidades se reportan.
   - *Reporte anterior:* opcional, para comparar con el corte previo.
4. **Validar** y revisar los resultados en pantalla.
5. **Descargar reporte Excel** y compartirlo con quien corrige.

## Trabajar el reporte

- La hoja **B_Hallazgos** tiene filtros. Ordénela por archivo y fila para corregir registro por registro, o por regla para ver un mismo problema en toda la base.
- Diligencie **Estado del hallazgo** (pendiente, confirmado, corregido en origen, excepción justificada, cerrado) y **Observación del equipo**. Esos valores se conservan al comparar con el siguiente corte.
- Revise **C_No_evaluables**: indica controles que no se pudieron hacer. Varios dependen de decisiones pendientes (DP-xx).
- Un archivo sin hallazgos **no** queda certificado: solo se cumplieron las reglas ejecutadas.

## Corregir con la base marcada

En la sección de resultados, descargue la base marcada de cada población (`<nombre>_MARCADA.xlsx`). Es una copia nueva; el archivo original no se modifica.

- Rojo oscuro: bloqueante. Rojo: error. Amarillo: alerta. Azul: revisión humana (no es un error; hay que verificar el caso, casi siempre en Observaciones). Pase el cursor sobre la celda para ver la regla, el valor esperado, la explicación y la acción sugerida.
- Las cuatro columnas «Validación: …» al final de cada fila dicen cuántos hallazgos tiene el registro, la severidad más alta, las reglas que incumple y las solicitudes de revisión humana. Filtre «Validación: hallazgos» mayor que 0 para ver solo los registros por corregir.
- Cada registro queda en la misma fila que en el original, así que la «Fila Excel» del reporte también sirve para ubicarlo en la base marcada.
- Un hallazgo que no corresponde a una sola columna (por ejemplo, un ID repetido) se marca en la celda del ID SIVIGILA. Un salto incumplido marca cada pregunta afectada.
- La revisión humana (azul) no suma en «Validación: hallazgos»; se lista en «Validación: revisión humana».
- La copia conserva los valores, pero no los formatos, fórmulas ni otras hojas del original.

## Validar el siguiente corte

1. Cargue las bases nuevas y ajuste el periodo.
2. En *Reporte de una ejecución anterior*, suba el reporte Excel del corte previo, idealmente el que ya tiene los estados diligenciados por el equipo. Si usa el validador en su equipo y guardó la ejecución en el historial, puede elegirla de la lista.
3. Después de validar, la pestaña **Comparación** y la hoja **I_Comparacion** muestran:
   - **Nuevos:** hallazgos que no estaban.
   - **Persistentes:** siguen igual. Conservan el estado y la observación anteriores.
   - **Resueltos:** la regla se volvió a ejecutar para esa población y el hallazgo ya no aparece.
   - **No comparables:** el registro no tiene un identificador estable, o la población o la regla no se evaluó esta vez (por ejemplo, porque no se cargó ese archivo).
4. Si entre un corte y otro cambió la configuración de reglas, aparece un aviso: parte de los nuevos y resueltos puede deberse a ese cambio.

La comparación usa la clave `población|regla|variable|ID SIVIGILA` (o el acta si falta el ID), no la fila de Excel, que cambia de una entrega a otra.

## Si el formato cambió

La hoja **D_Estructura** compara las columnas recibidas con el instrumento configurado:

- *Columnas nuevas:* no están en el catálogo y no se validan. Si es una variable nueva del instrumento, hay que agregarla al catálogo y a las reglas.
- *Ausentes:* las reglas que las usan quedan como no evaluables (nunca como cumplidas).
- *Reconocidas con otro nombre:* se resolvieron con `equivalencias/*.yaml` o por normalización (tildes, mayúsculas, espacios). Conviene confirmarlas.
- *Ambiguas:* dos columnas corresponden a la misma variable. No se validan hasta corregir el archivo.

## Historial

Al ejecutar en un equipo, el botón **Guardar en el historial** crea `resultados/ejecuciones/<id>/` con:

- `manifiesto.json`: parámetros, versiones del motor y de la configuración, huella de cada archivo, indicadores y duración.
- `reporte_<id>.xlsx`.
- `seguimiento.csv`: solo las claves de los hallazgos y la fila de Excel, sin valores observados.

Las carpetas de resultados contienen datos de las encuestas: guárdelas en una ubicación con acceso restringido.

La duración de cada ejecución queda registrada en el manifiesto y sirve para compararla con el tiempo de la revisión manual.
