# Mantenimiento de reglas

Las reglas están en `configuracion/aire/` como archivos YAML. Son **datos, no código**: cada regla tiene un tipo de una lista cerrada, y sus condiciones se escriben con una estructura fija. El validador nunca ejecuta texto de la configuración. Lo que no cabe en un tipo se programa como función registrada en `src/larrem/funciones.py`, revisable en el código fuente.

## Anatomía de una regla

```yaml
- id: M5_EDAD_COD                 # único; prefijo COM_, M5_, E_, A_ o PEND_
  version: 1                      # súbala cuando cambie el criterio
  descripcion: "Edad_Meses_COD: 1 = 2 a 11 meses; 2 = 13 a 59 meses"
  tipo: recodificacion_intervalos
  etapa: recodificacion           # captura | recodificacion | enriquecimiento
  severidad: error                # bloqueante | error | alerta | revision
  estado: implementada            # ver estados abajo
  poblaciones: [menores5]         # opcional: por defecto, las del archivo
  aplica_si: {var: X, en: [1]}    # opcional: condición para que la regla aplique
  parametros: {...}               # según el tipo
  especiales: "texto para el reporte sobre casos especiales"
  vigencia: {desde: 2026-07-01, documento: "I1 v10.1"}   # opcional, por fecha de encuesta
  fuentes:                        # obligatorias si la regla se ejecuta
    - {doc: D1, ubicacion: "filas 20-21", nota: "1 = 2 a 11 meses"}
  accion: "Qué debe hacer quien corrige"
  revision_tecnica: pendiente     # pendiente | aprobada | rechazada (por el equipo)
```

Códigos de documento (`tematica.yaml`): G1 guía de revisión de bases, I1 instructivo de diligenciamiento (páginas del PDF), D1/D2/D3 diccionarios (fila de Excel), O1 observaciones del equipo (hoja y fila), DX diagnóstico inicial.

## Estados

| Estado | Se ejecuta | Uso |
|---|---|---|
| `implementada` | sí | Criterio claro y respaldado |
| `provisional` | sí | Se aplica con una interpretación que el equipo debe confirmar. El hallazgo lo indica |
| `revision_humana` | sí | La fuente pide revisar el caso. Genera solicitudes de revisión, no errores |
| `pendiente_contradiccion` | no | Las fuentes se contradicen. Requiere `motivo_estado` y una decisión en `decisiones_pendientes.yaml` |
| `pendiente_incompleta` | no | Falta definir umbrales, códigos o unidades. Requiere `motivo_estado` |
| `requiere_insumo` | no | Falta un catálogo o un histórico. Requiere `motivo_estado` e `insumo_requerido` |

Un caso puntual en conflicto dentro de una regla clara (por ejemplo, exactamente 12 meses) se declara con `conflicto` en los parámetros: esos registros quedan *no evaluables* con el motivo, y el resto se valida.

## Condiciones

| Clave | Significado | Ejemplo |
|---|---|---|
| `en` / `no_en` | el código está / no está en la lista | `{var: P18_Fuma, en: [1]}` |
| `vacio` | celda vacía (true) o diligenciada (false) | `{var: P24_Cual, vacio: false}` |
| `numero` | es número (con `excepto` para códigos especiales) | `{var: P22, numero: true, excepto: [999]}` |
| `cmp` + `valor` | comparación numérica: `== != < <= > >=` | `{var: Edad, cmp: ">=", valor: 60}` |
| `patron` | expresión regular sobre el texto | `{var: Telefono, patron: "601\\d{7}"}` |
| `contiene` | el texto contiene alguno de los términos | `{var: Dirección, contiene: [" UN "]}` |
| `todas` / `alguna` | y / o de varias condiciones | `{todas: [{...}, {...}]}` |
| `negar` | negación | `{negar: {var: X, en: [1]}}` |

Resultado: verdadero, falso o **no evaluable** (columna ausente, valor vacío, error de Excel o texto donde se espera número). Los códigos se comparan normalizados: `1`, `1.0` y `" 1 "` son iguales.

> En YAML, escriba siempre `negar`, nunca `no:` como clave: `no`, `si`, `yes` sin comillas se leen como valores lógicos. La configuración rechaza claves no textuales para evitar ese error.

## Tipos de regla y parámetros

| Tipo | Valida | Parámetros principales |
|---|---|---|
| `requerido` | celda diligenciada | `columna_vacia_no_evaluable` |
| `dominio` | valor en la lista permitida | `valores`, `comparacion: exacta` |
| `patron` | formato por expresión regular | `patron`, `permitidos`, `no_evaluables`, `descripcion_esperado` |
| `rango` | número entre `min` y `max` | `min`, `max`, `entero`, `especiales`, `conflicto` |
| `condicional` | si `aplica_si`, entonces… | `entonces_cada` (cada variable) o `entonces` (combinación), `explicacion` |
| `al_menos_uno` | al menos una opción marcada | `opciones`, `valor`, `etiqueta` |
| `exclusion_ninguno` | "ninguno" no se marca junto con otra opción | `opciones`, `ninguno`, `si`, `no` |
| `recodificacion_mapa` | destino según tabla de origen | `origen`, `destino`, `mapa`, `conflicto` |
| `recodificacion_agrupada` | destino = sí si alguna opción es sí | `opciones`, `destino`, `si`, `no`, `destino_si`, `destino_no` |
| `recodificacion_intervalos` | destino según intervalos numéricos | `origen`, `destino`, `intervalos`, `conflicto` |
| `recodificacion_razon` | destino según cociente y umbral | `numerador`, `denominador`, `umbral`, `destino`, `si`, `no` |
| `comparacion` | relación entre dos variables | `izquierda`, `operador`, `derecha`, `especiales` |
| `unicidad` | valor sin repetición | `maximo_por_grupo`, `excepcion_maximo`, `ignorar`, `alcance: lote`, `entre_poblaciones` |
| `consistencia_grupo` | un mismo valor clave tiene un único valor dependiente | `clave`, `dependiente`, `ignorar` |
| `periodo` | fecha dentro del periodo de la ejecución | — |
| `fecha_valida` | fecha interpretable | `min` |
| `ambito` | subred o localidad esperada | `ambito` |
| `almacenado_como_texto` | identificador guardado como texto | — |
| `revision` | genera solicitud de revisión | `solicitud`, valores por variable |
| `funcion` | función registrada | `nombre`, `args`, `opciones` |

Funciones registradas: `edad_calculada`, `edad_poblacion`, `orden_fechas`, `acta_subred`, `lactancia_justificacion`, `meses_hasta_edad`, `tabaquismo_pesado`, `suma_edad_tabaco`. Para agregar una, escríbala en `funciones.py`, agréguela a `REGISTRO_FUNCIONES` y cree pruebas.

## Flujo de un cambio

1. Edite el YAML. Para responder una decisión, complete `respuesta` y `fecha_respuesta` en `decisiones_pendientes.yaml`, ajuste las reglas enlazadas (estado, parámetros, quitar `conflicto`) y suba su `version`.
2. Si cambió el catálogo de variables, ejecute `python herramientas/generar_obligatoriedad.py`.
3. Suba `version_configuracion` y `fecha_configuracion` en `tematica.yaml`.
4. Ejecute `python herramientas/exportar_decisiones.py` (actualiza `docs/decisiones_pendientes.md`).
5. Ejecute las pruebas: `python -m pytest -q tests`.
6. Valide un corte conocido y compare con la ejecución anterior. El aviso de cambio de configuración es esperado.

## Catálogo de variables

`variables/<población>.yaml` lista cada columna con: `tipo`, `requerido` (captura, recodificacion, enriquecimiento, condicional, no), `personal` (se oculta en el reporte), `historica`, y la fila del diccionario y de las observaciones. Se generó con `herramientas/generar_catalogo_variables.py` a partir de las bases y los diccionarios, y luego se revisó a mano; no lo regenere sobre la versión revisada sin comparar las diferencias.

Si una base nueva trae una columna con otro nombre, agréguela a `equivalencias/<población>.yaml` en lugar de renombrar la variable.

## Otra temática

El motor es genérico. Para otra temática (ruido, REM, etc.), cree `configuracion/<temática>/` con la misma estructura y cargue esa carpeta con `cargar_configuracion(ruta)`. La interfaz actual carga `aire`.
