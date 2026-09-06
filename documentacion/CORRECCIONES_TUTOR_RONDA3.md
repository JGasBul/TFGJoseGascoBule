# Correcciones del tutor — Ronda 3 (sobre el 3.er borrador)

Fuente: PDF `correccionTutores/TFG_Tercer_Borrador_Corregido_Jose_Gasco_Bule.pdf`
(24 comentarios de jalberola) + correo de Juanmi.

**Valoración general del tutor:** "está bastante bien, pero aún puedes pulirlo".
Tres ejes grandes en el correo + 24 comentarios puntuales en el PDF.

---

## A. Los tres ejes del correo (lo más importante)

- **E1 — Alargar hacia ~50 páginas** (cuenta intro → fin de referencias). Ahora
  ~46. Objetivo ≥ 50. *No es "añadir relleno"*: se consigue desarrollando lo que
  ya hay (explicar figuras, conectores, ejemplos, ruta de viaje del cap. 6,
  justificar pesos, readme). El propio tutor lo dice: "mejorando el cap. 6 y
  alargando frases esquemáticas... se aproxima a las 50".

- **E2 — Capítulo 6 caótico (LO QUE MÁS HAY QUE TRABAJAR).** Muchas secciones y
  subsecciones; el lector se pierde. Acción: **al inicio del cap. 6, una "ruta de
  viaje"** que anticipe TODO lo que se va a contar y por qué, para que no sea
  "pruebas y resultados uno detrás de otro". Reforzar con un **diagrama visual**
  de la evolución experimental (ver #12) y **enlazar** las secciones entre sí
  (ver #21).

- **E3 — Frases esquemáticas → desarrollarlas** con conectores y verbos (ver
  #14, #16, #17, #20).

- **E4 — Conclusiones: aportación al estado del arte.** El trabajo analiza el
  estado del arte al principio pero **no se compara con otros algoritmos**. En la
  conclusión tienen que quedar claros: (a) **la respuesta a la pregunta de
  investigación**, y (b) **qué contribución se hace al estado del arte**.

---

## B. Los 24 comentarios del PDF (mapeados a su sección)

| # | Pág | Sección | Comentario del tutor | Acción |
|---|-----|---------|----------------------|--------|
| 1 | 8 | Cap. 1 Introducción | Evita el abuso de dos puntos (:) y punto y coma (;) — marcas de ChatGPT | Reescribir frases con exceso de `:` y `;` en TODO el documento |
| 2 | 11 | 2.1 Magic | Quita todos los guiones largos (—), típicos de ChatGPT, y pon paréntesis | Sustituir los 11 "—...—" por paréntesis o reescritura |
| 3 | 12 | 2.1/ecuaciones | Cada ecuación referenciada en el texto **y explicada** | Referenciar y explicar eq. de Karsten (2.1) y espacio (2.2) |
| 4 | 12 | (nota) | "Revisa todas" | Aplicar #3 a TODAS las ecuaciones (2.1, 2.2, 4.1, 4.2, fitness gauntlet) |
| 5 | 13 | 2.2/Impl. | Footnote con la URL | Pasar el URL inline (repo GitHub §5.1) a nota a pie de página |
| 6 | 15 | 2.4 Estado del arte | Explica las principales conclusiones que quieres resaltar | Añadir cierre del estado del arte resaltando conclusiones clave |
| 7 | 22 | 4.3 Fitness | Pesos α/β fijos = criticable; defender o hacer pruebas | Justificar α=0,7/β=0,3 (texto + idealmente sensibilidad, T6) |
| 8 | 22 | 4.3 Fitness | Lo mismo con los pesos de calidad (0,35/0,35/0,30): "parece random" | Justificar los pesos de la métrica de calidad (vienen del CoV, §6.3) |
| 9 | 23 | 4.4 Cruce | Figura donde se vean los **2 hijos** | Rehacer fig. de cruce para mostrar los dos descendientes |
| 10 | 27 | 5.1 Implementación | ¿Readme/manual para lanzar las pruebas? Ponerlo para el tribunal | Añadir mención a un README de reproducción (crearlo en el repo) |
| 11 | 29 | 6.1 | Puntos decimales, **no comas**. Revísalo en todo el documento | Cambiar ~171 números "0,9755" → "0.9755" en todo el TFG |
| 12 | 30 | 6.2 | Dar más peso a la evolución experimental: **diagrama visual** + explicar cómo cada experimento lleva a cambios, enlazando con la metodología iterativa | Añadir figura del recorrido experimental (prototipo→A/B→refinamiento→gauntlet→run final) |
| 13 | 32 | Tabla 6.2 | Comenta lo que quieres resaltar en la gráfica | Añadir frase interpretativa tras la tabla/figura |
| 14 | 33 | 6.2.3 | Un par de líneas para introducir la sección, no entres tan a saco | Añadir intro a §6.2.3 (y revisar todas las subsecciones) |
| 15 | 33 | 6.2.3 | "A modo de ejemplo, ..." | Añadir ejemplo/verbosidad |
| 16 | 33 | 6.2.3 | No escribas tan esquemático, pon conectores y algún verbo | Desarrollar frases telegráficas |
| 17 | 33 | 6.2.3 | "Por contra... bla bla bla" | Añadir conectores de contraste |
| 18 | 34 | 6.2.5 | "Como se puede observar... bla bla bla" | Introducir y explicar la figura/tabla |
| 19 | 34 | 6.2.5 | Define TFG la primera vez y luego úsalo siempre | Definir "Trabajo de Fin de Grado (TFG)" en intro; unificar (7×TdFdG / 8×TFG ahora) |
| 20 | 36 | 6.3.2 | Dale un poco más de verbosidad | Desarrollar §6.3.2 |
| 21 | 37 | 6.3.3 | Enlaza mejor el fin de 6.3 con 6.4/6.5. Cierra 6.3 con una conclusión sin adelantar 6.5; enlaza con 6.4 | Reescribir cierre de §6.3.3 + frase de unión al inicio de §6.4 |
| 22 | 41 | fig. run final | "Como se puede observar..." | Explicar la gráfica de evolución del fitness |
| 23 | 41 | 6.5 | Explica lo que quieres resaltar de estas 3 figuras | Añadir interpretación de las figuras de dinámica de población |
| 24 | 43 | 6.5.2 | "Como se puede observar, bla bla bla" — explica lo que resaltas | Explicar la figura de curva de maná del campeón |

---

## C. Agrupación por temas (para ejecutar eficientemente)

### TEMA 1 — Estilo "anti-IA" [transversal, rápido] (#1, #2)
- **Quitar los guiones largos (—)** → paréntesis. Hay 11 en el cuerpo (propuesta 4,
  evaluación 3, metodología 2, marco 1, conclusiones 1).
- **Reducir el abuso de `:` y `;`.** Reescribir las frases más cargadas.
- *Nota honesta: estos tics los introdujeron las últimas revisiones; el tutor
  quiere registro formal pero sin marcas de IA.*

### TEMA 2 — Decimales coma → punto [transversal, mecánico] (#11)
- ~171 números. Cambiar `X,Y` decimal → `X.Y` en todos los `.tex` (cuerpo, tablas,
  figuras generadas, resúmenes). Cuidado con separadores de millar (4.130 → 4130
  o 4,130 según convenio de punto).

### TEMA 3 — Explicar TODAS las figuras y tablas [transversal] (#6, #13, #18, #22, #23, #24)
- Regla del tutor: cada figura/tabla necesita una frase tipo "Como se puede
  observar, ..." que diga **qué resaltar**. Aplicar a las 22 figuras/tablas.

### TEMA 4 — Desesquematizar / verbosidad [transversal] (E3, #14, #15, #16, #17, #20)
- Introducir cada (sub)sección con 1-2 líneas; desarrollar frases telegráficas con
  conectores y verbos. Es lo que más aporta a las páginas (E1).

### TEMA 5 — Capítulo 6: ruta de viaje + diagrama + enlaces [LO MÁS IMPORTANTE] (E2, #12, #14, #21)
- **Ruta de viaje** al inicio del cap. 6 (ampliar la intro actual a un párrafo que
  guíe todo el recorrido y su lógica).
- **Diagrama del recorrido experimental** (#12): prototipo → A/B → refinamiento →
  gauntlet (descartado) → run final → 2.ª ejecución, mostrando cómo cada uno motiva
  el siguiente (enlaza con la metodología iterativa del cap. 3).
- **Enlaces entre secciones** (#21): cerrar cada sección con una mini-conclusión y
  abrir la siguiente con una frase de unión.

### TEMA 6 — Ecuaciones referenciadas y explicadas (#3, #4)
- Cada ecuación (Karsten 2.1, espacio 2.2, fitness 4.1, calidad 4.2, fitness+gauntlet)
  citada en el texto por su número y explicada en palabras.

### TEMA 7 — Justificar los pesos (#7, #8)
- α=0,7/β=0,3 y 0,35/0,35/0,30: explicar de dónde salen (β y las 3 componentes ya
  tienen justificación en §6.3 vía CoV; α/β se puede defender por escrito y, mejor,
  con una prueba de sensibilidad — coincide con la tarea T6 pendiente).

### TEMA 8 — Figura del cruce con los 2 hijos (#9)
- Rehacer `fig:cruce` para mostrar Descendiente 1 y Descendiente 2 (herencia
  complementaria por categoría).

### TEMA 9 — README de reproducción (#10)
- Crear un README en el repo con los pasos para lanzar las pruebas y mencionarlo en
  §5 para el tribunal.

### TEMA 10 — Conclusiones: pregunta + contribución al estado del arte (E4)
- Reforzar la respuesta a la pregunta de investigación y **añadir explícitamente la
  contribución al estado del arte** (qué aporta frente a Bjørke & Fludal,
  García-Sánchez, etc.: Standard completo, operadores pack-aware, torneo Swiss).

### TEMA 11 — Acrónimo TFG (#19) y URL a footnote (#5)
- Definir "Trabajo de Fin de Grado (TFG)" en la primera aparición y usar TFG después.
- Pasar el URL del repo a nota a pie.

---

## D. Prioridad sugerida
1. **TEMA 5** (cap. 6: ruta de viaje + diagrama + enlaces) — lo que más pesa para el tutor.
2. **TEMA 3 + TEMA 4** (explicar figuras + desesquematizar) — suben calidad y páginas (E1).
3. **TEMA 10** (conclusiones: contribución al estado del arte).
4. **TEMA 1 + TEMA 2 + TEMA 11** (estilo anti-IA, decimales, TFG, URL) — mecánicos, rápidos.
5. **TEMA 6, 7, 8** (ecuaciones, pesos, figura cruce).
6. **TEMA 9** (README) — fuera de la memoria (en el repo).

**Efecto en páginas (E1):** los temas 3, 4, 5, 6 y 10 añaden texto sustantivo →
deberían llevar de ~46 a ~50+ páginas de forma natural, sin relleno.

**Nota sobre cómputo:** casi todo es redacción (sin ejecutar). La única parte que
se beneficia de experimentos es la justificación de α/β (TEMA 7, prueba de
sensibilidad = T6) — opcional; se puede defender por escrito si no da tiempo.
