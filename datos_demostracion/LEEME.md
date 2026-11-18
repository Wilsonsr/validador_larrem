# Bases de demostración

Tres bases **sintéticas**, una por población, para practicar con el validador:

- `DEMO_1. LARREM_AIRE_MENORES5_SINTETICA.xlsx` (150 registros)
- `DEMO_2. LARREM_AIRE_5-14ANIOS_SINTETICA.xlsx` (100 registros)
- `DEMO_3. LARREM_AIRE_MAYORES60_SINTETICA.xlsx` (150 registros)

**Ningún registro corresponde a una persona.** Se generaron con `herramientas/generar_demo_sintetica.py`:

1. Cada respuesta codificada se sorteó columna por columna entre los códigos frecuentes (que aparecen al menos 5 veces) de una base de referencia; no se copió ninguna fila.
2. Nombres, documentos, direcciones, teléfonos, correos, colegios, personal de campo y observaciones son inventados. Las coordenadas y las variables de enriquecimiento están vacías.
3. Subred, localidad, UPZ y barrio son combinaciones del territorio (información pública, no de personas).
4. Las incoherencias se corrigieron con las mismas reglas del validador y luego se sembraron errores a propósito (acta repetida, saltos, dominios, correos mal digitados, un colegio con otra dirección), para que la demostración muestre hallazgos de todas las severidades.

Control: ninguna fila sintética se parece a una fila de la base de referencia más de lo que se parecen entre sí dos registros reales distintos.

No las use para reportes ni análisis: los resultados no representan a la población.
