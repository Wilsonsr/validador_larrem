# Decisiones pendientes – temática aire

Configuración 2026.11.1 (2026-11-14). Archivo generado con `herramientas/exportar_decisiones.py`; la fuente es `configuracion/aire/decisiones_pendientes.yaml`.

Cada decisión describe una diferencia entre documentos que el validador no resuelve por su cuenta. Mientras no haya respuesta, se aplica el tratamiento de «Qué hace hoy el validador».

Fuentes: **G1** = 22. Guia_Bases_Aire.pdf; **I1** = 14. Ins_Aire.pdf; **D1** = 1. DICCIONARIO_LARREM_AIRE_MENORES5_Ok_.xlsx; **D2** = 2. DICCIONARIO_LARREM_AIRE_5-14ANOS_Ok_.xlsx; **D3** = 3. DICCIONARIO_LARREM_AIRE_MAYOR60-.xlsx; **O1** = Variables Aire para Automatizar.xlsx; **PT** = Procedimiento del equipo para el cálculo de tabaquismo pesado (comunicado el 20/10/2026); **RV** = docs/solicitudes/2026-11-14_revision_validador.txt; **DX** = diagnostico_aire/Diagnostico_inicial_AIRE.md.

## DP-01. Vigencia de los documentos para el primer semestre de 2026

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** La portada del instructivo dice v10.0 y su control de cambios incluye la v10.1 de julio de 2026. La guía tiene portada de enero de 2025 y control de cambios v4 de julio de 2026. Las bases son de enero a junio.

**Fuentes.** I1 pp.1 y 142; G1 pp.1 y 82; DX sección 4, Vigencia

**Qué hace hoy el validador.** Las reglas se aplican sin fecha de vigencia. Ninguna regla está marcada como exclusiva de la versión de julio.

**Reglas enlazadas.** —

**Pregunta.** ¿Qué versión de la guía y del instructivo rige las encuestas de enero a junio de 2026? ¿Qué cambió en la v10.1 y en la v4?

**Respuesta.** _(pendiente)_

## DP-02. Edad de 12 meses en la recodificación de edad (menores de 5)

*Poblaciones:* menores de 5

**Diferencia.** D1 clasifica 2 a 11 meses en la categoría 1 y 12 a 59 meses en la 2. O1 incluye los 12 meses en la categoría 1.

**Fuentes.** D1 filas 20-21; O1 MENOR 5 fila 15

**Qué hace hoy el validador.** Los 12 meses se codifican en la categoría 2.

**Reglas enlazadas.** `M5_EDAD_COD`

**Pregunta.** Un niño de 12 meses, ¿se codifica en la categoría 1 o en la 2?

**Respuesta.** Se aplica el diccionario: 1 = 2 a 11 meses; 2 = 12 a 59 meses.

## DP-03. Gas propano en la recodificación de energía para cocinar

*Poblaciones:* menores de 5, 5 a 14 años

**Diferencia.** D1 y D2 incluyen el gas propano en la categoría 1 (riesgo). O1 resume 'gas' en la categoría 2.

**Fuentes.** D1 fila 345; D2 fila 382; O1 MENOR 5 fila 145; 5 A 14 fila 162

**Qué hace hoy el validador.** El gas propano se valida como categoría 1.

**Reglas enlazadas.** `M5_ENERGIA_COD`, `E_ENERGIA_COD`

**Pregunta.** ¿El gas propano es categoría 1 o 2? ¿Se aprueba la tabla completa de energía distinguiendo gas natural y propano?

**Respuesta.** Se aplica el diccionario: el gas propano es categoría 1.

## DP-04. Recodificación de cocina no ventilada

*Poblaciones:* menores de 5, 5 a 14 años

**Diferencia.** O1 repite en la ventilación de la cocina el texto de ubicación de la cocina. Se aplica la definición del diccionario: el riesgo corresponde a la opción 2 de la pregunta de ventilación.

**Fuentes.** D1 filas 331-336; D2 filas 368-373; O1 MENOR 5 fila 143; 5 A 14 fila 160; I1 p.47

**Qué hace hoy el validador.** Las reglas se ejecutan como provisionales con la definición del diccionario.

**Reglas enlazadas.** `M5_COCINA_NO_VENTILADA_COD`, `E_COCINA_NO_VENTILADA_COD`

**Pregunta.** ¿Se confirma que COCINA NO VENTILADA CODIF. se obtiene solo de la pregunta de ventilación (riesgo = no ventilada)?

**Respuesta.** _(pendiente)_

## DP-05. Longitud de la identificación según el tipo de documento

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** O1 pide un mínimo de diez dígitos para algunos documentos; G1 da como ejemplo un máximo de diez para NUIP. En el corte hay NUIP y tarjetas de identidad de 11 caracteres.

**Fuentes.** O1 MENOR 5 fila 10; 5 A 14 fila 10; G1 p.5; I1 p.12

**Qué hace hoy el validador.** No se valida la longitud. Se valida que el NUIP sea numérico y que la identificación esté almacenada como texto.

**Reglas enlazadas.** `PEND_ID_LONGITUD`

**Pregunta.** ¿Cuál es la longitud mínima y máxima aceptada por tipo de documento (NUIP, TI, CC, CE, PEP, PPT)?

**Respuesta.** _(pendiente)_

## DP-06. Consumo de exactamente 16 cigarrillos al día (mayores de 60)

*Poblaciones:* 60 años y más

**Diferencia.** D3 define el nivel severo como 16 y más. O1 dice 1-5, 6-15 y 'mayor a 16', dejando sin categoría el valor 16.

**Fuentes.** D3 filas 192-197; O1 MAYOR 60 fila 90

**Qué hace hoy el validador.** 16 cigarrillos se valida como severo.

**Reglas enlazadas.** `A_NIVEL_CONSUMO`

**Pregunta.** ¿16 cigarrillos diarios corresponde al nivel moderado o al severo?

**Respuesta.** Se aplica el diccionario: 16 cigarrillos diarios es severo (16 y más).

## DP-07. Número de menores igual al total de personas del hogar

*Poblaciones:* menores de 5, 5 a 14 años

**Diferencia.** O1 impide que el número de menores sea mayor o igual al total de personas; I1 solo prohíbe que sea superior (y que sea cero).

**Fuentes.** I1 p.45; O1 MENOR 5 fila 133

**Qué hace hoy el validador.** Se marca como error solo cuando los menores superan a las personas. La igualdad no se marca.

**Reglas enlazadas.** `M5_MENORES_NO_SUPERAN_PERSONAS`, `E_MENORES_NO_SUPERAN_PERSONAS`

**Pregunta.** ¿Es válido un hogar en el que todas las personas son menores? Si no, ¿qué severidad tiene?

**Respuesta.** _(pendiente)_

## DP-08. Tiempo de uso del colchón o almohada en 12 meses (5 a 14)

*Poblaciones:* 5 a 14 años

**Diferencia.** I1 indica registrar en años a partir de los 12 meses. O1 dice que el valor en meses no debe superar 12.

**Fuentes.** I1 p.96; O1 5 A 14 fila 154; D2 fila 352

**Qué hace hoy el validador.** Un valor de 12 en la unidad meses queda como no evaluable.

**Reglas enlazadas.** `E_P63_MESES`

**Pregunta.** ¿Se acepta '12 meses' o debe registrarse como '1 año'?

**Respuesta.** _(pendiente)_

## DP-09. Relación entre país de procedencia y tipo de documento

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** G1 formula una relación restrictiva (documento distinto de NUIP/CC implica país distinto de Colombia). I1 admite país distinto de Colombia con documento colombiano y aclaración.

**Fuentes.** G1 pp.5-6, p.62; I1 p.12

**Qué hace hoy el validador.** Se marca como alerta solo un documento extranjero con país Colombia. El caso inverso (documento colombiano con país extranjero) no se valida. No se infiere nacionalidad ni situación migratoria.

**Reglas enlazadas.** `COM_PAIS_REQUERIDO_DOC_EXT`, `A_PAIS_DOC_EXT`, `PEND_PAIS_DOCUMENTO_COLOMBIANO`, `PEND_PAIS_DOCUMENTO_COLOMBIANO_A`

**Pregunta.** ¿Un documento extranjero con país Colombia es error o alerta? ¿Qué aclaración debe tener un documento colombiano con país extranjero?

**Respuesta.** _(pendiente)_

## DP-10. Opciones de P34 y P39 cuando no aplican (5 a 14)

*Poblaciones:* 5 a 14 años

**Diferencia.** La documentación indica 999 cuando no aplica la pregunta. La base registra 2 en esas opciones.

**Fuentes.** D2 filas 198-209, 225-233; O1 5 A 14 filas 94-118; G1 p.46

**Qué hace hoy el validador.** Se aceptan 1, 2 y 999. Las opciones de P34 y P39 no se incluyen en los controles de salto.

**Reglas enlazadas.** `E_DOM_P34_P39`, `E_P29_SALTO`, `E_P38_SALTO`

**Pregunta.** Cuando la pregunta no aplica, ¿las opciones deben registrarse con 999 o con 2?

**Respuesta.** _(pendiente)_

## DP-11. Estratos superiores a 3 por localidad

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** O1 limita los estratos 4 a 6 a seis localidades, sin catálogo territorial. La lista no incluye localidades como Usaquén o Chapinero.

**Fuentes.** O1 MENOR 5 fila 34; 5 A 14 fila 34; MAYOR 60 fila 29; DX sección 4, Estrato y localidad

**Qué hace hoy el validador.** La regla no se ejecuta. Se valida solo que el estrato esté entre 1 y 6.

**Reglas enlazadas.** `PEND_ESTRATO_LOCALIDAD`

**Pregunta.** ¿La lista de O1 corresponde a las localidades atendidas por una subred? ¿Qué catálogo oficial de estratos debe usarse?

**Respuesta.** _(pendiente)_

## DP-12. Variables históricas (mayores de 60)

*Poblaciones:* 60 años y más

**Diferencia.** O1 identifica P27_Cual_Otra como pendiente de eliminar y P32_Combustible/P32_Años como campos del sistema antiguo. D3 repite P32_Años en las filas 271 y 280.

**Fuentes.** O1 MAYOR 60 filas 101, 113-114; D3 filas 229-231, 268-272, 280

**Qué hace hoy el validador.** No se exige su diligenciamiento. Se emite una alerta si aparecen datos en esos campos.

**Reglas enlazadas.** `A_HISTORICAS_SIN_DATO`

**Pregunta.** ¿Desde qué fecha se retiran estos campos? ¿Qué valor deben tener mientras sigan en la base?

**Respuesta.** _(pendiente)_

## DP-13. Código 9999 en teléfono, celular y correo

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** El diccionario admite 9999 = Sin dato. O1 indica 8888 (no tiene) o 7777 (no presenta) y 'no más opciones'. G1 pide verificar que no existan 999 ni 9999.

**Fuentes.** D1 filas 34-37, 55, 58; D3 filas 34, 55; O1 MENOR 5 filas 23, 35-36; G1 p.6

**Qué hace hoy el validador.** El valor 9999 queda como no evaluable en las reglas de formato de contacto.

**Reglas enlazadas.** `COM_TELEFONO_FORMATO`, `COM_CELULAR_FORMATO`, `COM_CORREO_FORMATO`

**Pregunta.** ¿Es válido 9999 en teléfono, celular o correo, o debe corregirse a 8888/7777?

**Respuesta.** _(pendiente)_

## DP-14. Repetición anual de personas y hogares, y cambio de población por edad

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** La guía pide revisar la repetición de direcciones en todos los meses del año. No se define cómo tratar a una persona encuestada en dos cortes ni a un niño que cambia de grupo de edad durante el año.

**Fuentes.** G1 p.7; DX sección 7, Próxima etapa: concertar la metodología

**Qué hace hoy el validador.** Se compara solo dentro de los archivos de la misma ejecución. Las coincidencias de identificación entre poblaciones van a revisión humana.

**Reglas enlazadas.** `PEND_REPETICION_ANUAL`, `COM_IDENTIFICACION_UNICA`, `COM_IDENTIFICACION_ENTRE_POBLACIONES`

**Pregunta.** ¿Una persona u hogar puede encuestarse más de una vez en el año? ¿Qué se hace si la misma persona aparece en dos poblaciones?

**Respuesta.** _(pendiente)_

## DP-15. Momento de entrega de los campos geográficos y de exposición

*Poblaciones:* menores de 5, 5 a 14 años, 60 años y más

**Diferencia.** Las columnas de coordenadas, ACRE y PM2,5 están vacías en las tres bases del corte.

**Fuentes.** DX sección 3, Campos geográficos y de exposición pendientes

**Qué hace hoy el validador.** Su completitud se valida solo en la etapa de enriquecimiento. Si la columna está vacía en todo el archivo, se informa como no evaluable.

**Reglas enlazadas.** `PEND_GEOGRAFIA_EXPOSICION_M5`, `PEND_GEOGRAFIA_EXPOSICION_E`, `PEND_GEOGRAFIA_EXPOSICION_A`, `M5_OBLIGATORIAS_ENRIQUECIMIENTO`, `E_OBLIGATORIAS_ENRIQUECIMIENTO`, `A_OBLIGATORIAS_ENRIQUECIMIENTO`

**Pregunta.** ¿En qué etapa se reciben estos campos y contra qué capa se validan?

**Respuesta.** _(pendiente)_
