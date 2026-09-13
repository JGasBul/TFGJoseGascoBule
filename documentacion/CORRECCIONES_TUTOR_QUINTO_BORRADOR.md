# Correcciones del tutor — 5.º borrador (`TFG_Quinto_Borrador_Jose_Gasco_Bule.pdf`)

Tutor: Juan Miguel Alberola ("Juanmi"). PDF corregido en
`memoria/correcionTutores/TFG_Quinto_Borrador_Jose_Gasco_Bule.pdf` (61 págs, 53 anotaciones,
extraídas con pypdf).

## Resumen ejecutivo

Esta ronda tiene **un tema dominante que copa ~40 de las 53 anotaciones**: eliminar los **dos
puntos (`:`)** —y algún **punto y coma (`;`)**— del cuerpo del texto. La instrucción global la
deja escrita en la pág. 14:

> *"Reescribe esta frase para que no haya dos puntos. **Revisa todo el documento para dejar solo
> los necesarios, así como los punto y coma**."*

Cada marca "reescribe" cae sobre una frase con un `:` explicativo. El tutor es ahora **más
estricto que en la ronda anterior**: quiere fuera incluso los dos puntos apositivos y los punto y
coma de paralelismo que yo había conservado como "usos legítimos". Criterio para esta ronda: **el
tutor manda** → se eliminan todos los `:` de prosa salvo los estrictamente estructurales (los que
introducen una lista `itemize`/`enumerate`).

El resto son **11 cambios estructurales puntuales** (recortes, notas al pie, citas a ecuaciones,
reescrituras concretas).

Inventario medido sobre el fuente actual: **82 dos puntos de prosa a reescribir**, **13
estructurales que se conservan**, más 2 de ecuaciones (4.1/4.2) que el tutor quiere como "tal y
como se observa en…" y ~4 punto y coma pendientes.

---

## BLOQUE A — Cambios estructurales concretos

| # | Pág | Comentario | Ubicación (fuente) | Acción |
|---|-----|------------|--------------------|--------|
| A1 | 2 | "Que no te quede una palabra suelta / recorta el resumen para que quepa" | `00-resumenes.tex` L13 (resumen ES) | Acortar ligeramente el resumen para que "simulación." no quede como palabra huérfana en su propia línea. |
| A2 | 4 | "Lo mismo" | `00-resumenes.tex` L26 (resum CA) | Íd. para "simulació." (huérfana). |
| A3 | 5 | "este resumen déjalo" | `00-resumenes.tex` (abstract EN) | **No tocar** el abstract inglés (visto bueno del tutor). |
| A4 | 12 | "Esto mejor quítalo" | `01-introduccion.tex` L38, última frase | Eliminar "Cierran la memoria la bibliografía y un anexo sobre la relación del trabajo con los Objetivos de Desarrollo Sostenible de la Agenda 2030." |
| A5 | 13 | "Esto mejor quítalo" | `02-marco-teorico.tex` L8 | Eliminar el recap inicial "La introducción ha planteado la construcción de mazos como un problema de optimización costoso y ha formulado la pregunta que vertebra el trabajo." (y arrancar el capítulo directamente). |
| A6 | 14 | "Cita a la ecuación 2.1 en el texto" | `02-marco-teorico.tex` §2.1 (L17–24, `eq:karsten`) | La ecuación 2.1 está referenciada solo en el cap. 4. Añadir una referencia explícita en el texto donde aparece ("…con un mínimo de tres fuentes, tal y como recoge la Ecuación~\ref{eq:karsten}."). |
| A7 | 16 | "Pon nota al pie con la URL" | `02-marco-teorico.tex` L55 (Magarena) | Añadir `\footnote{Disponible en \url{https://github.com/magarena/magarena}.}` en la primera mención de **Magarena** (misma convención que Forge/Scryfall). |
| A8 | 17 | "comenta por qué motivo" | `02-marco-teorico.tex` L70, fin ("…una vía que finalmente se descartó.") | Añadir el motivo del descarte o remitir a §6.4 ("…se descartó, por el sesgo del simulador que se detalla en la sección~\ref{sec:gauntlet}."). |
| A9 | 19 | "Como conclusión, podemos decir que la revisión…" | `02-marco-teorico.tex` L103 | Reformular el arranque "En síntesis, la revisión confirma dos conclusiones." → "Como conclusión, puede afirmarse que la revisión confirma dos ideas." |
| A10 | 25 | "tal y como se observa en la Ecuación 4.1" y "…4.2" | `04-propuesta.tex` L94 y L106 | Sustituir el `:` que antecede a cada ecuación por la referencia en el texto: "…mediante una suma ponderada, tal y como se observa en la Ecuación~\ref{eq:fitness}." (y análogo con `eq:calidad` / 4.2). |
| A11 | 32 | "llevar a cabo los experimentos" | `06-evaluacion.tex` L15 | Reformular "procede ponerlo a prueba" → "procede llevar a cabo los experimentos". |
| A12 | 50 | "por las limitaciones que se han comentado en el estado del arte" | `07-conclusiones.tex` L12 (párrafo E4) | Añadir esa coletilla al justificar por qué no hay comparación empírica directa ("…comparación empírica directa con otros sistemas, por las limitaciones que se han comentado en el estado del arte."). |

---

## BLOQUE B — Eliminación de dos puntos en prosa (82)

**Regla general de transformación** (elegir la más natural en cada caso):

- `X: Y` (Y explica/justifica X) → `X, ya que Y` · `X, dado que Y` · `X. Y` (dos frases).
- `X: a, b y c` (enumeración corta) → `X, a saber, a, b y c` · integrar con "como" / "entre ellos".
- `X: Y` (Y es aposición/definición) → `X, esto es, Y` · `X, es decir, Y` · reestructurar con "consiste en".

### 01-introduccion.tex (3)
- **L9** «…en cada momento): los arquetipos dominantes varían…» → "…en cada momento), de modo que los arquetipos dominantes varían…"
- **L13** «…costosa y estocástica: la evaluación de un mazo exige…» → "…costosa y estocástica, ya que la evaluación de un mazo exige…"
- **L15** «…un reto concreto: cómo hacer evolucionar…» → "…un reto concreto, el de cómo hacer evolucionar…"

### 02-marco-teorico.tex (18)
- **L13** «…cinco colores: blanco, azul, negro, rojo y verde.» → "…cinco colores, que son el blanco, el azul, el negro, el rojo y el verde."
- **L13** «…su inicial en inglés: W (blanco), U (azul)…» → "…su inicial en inglés, de forma que W corresponde al blanco, U al azul…" (o dejar como enumeración con "a saber,").
- **L15** «…proceso de construcción: incluir una carta…» → "…proceso de construcción, ya que incluir una carta…"
- **L17** «…a esas heurísticas: estima las fuentes…» → "…a esas heurísticas y estima las fuentes…"
- **L28** «…una medida formal: se ha demostrado que…» → "…una medida formal, pues se ha demostrado que…"
- **L48** «…un agravante: la función de fitness no es…» → "…un agravante, y es que la función de fitness no es…"
- **L57** «…evaluar la población: cada mazo se enfrenta…» → "…evaluar la población, de modo que cada mazo se enfrenta…"
- **L57** «…relevante para este trabajo: la inteligencia artificial de Forge…» → "…relevante para este trabajo, ya que la inteligencia artificial de Forge…"
- **L59** «…el algoritmo necesita: coste de maná, tipo, colores…» → "…el algoritmo necesita, a saber, el coste de maná, el tipo, los colores…"
- **L68** «…con otras técnicas: estrategias evolutivas y algoritmos…» → "…con otras técnicas, como las estrategias evolutivas y los algoritmos…"
- **L70** «…afecta al formato: Bjørke y Fludal se restringen…» → "…afecta al formato, ya que Bjørke y Fludal se restringen…"
- **L70** «…granularidad de los operadores: su representación admite…» → "…granularidad de los operadores, pues su representación admite…"
- **L70** «…esquema de evaluación: ellos puntúan cada mazo…» → "…esquema de evaluación, dado que ellos puntúan cada mazo…"
- **L72** «…favorece a unos arquetipos sobre otros: en uno de sus experimentos…» → "…favorece a unos arquetipos sobre otros, hasta el punto de que, en uno de sus experimentos…"
- **L76** «…un precedente directo: el TFG de Mira Abad…» → "…un precedente directo, el TFG de Mira Abad…"
- **L76** «…el objeto de la evolución: Mira Abad evoluciona…» → "…el objeto de la evolución, ya que Mira Abad evoluciona…"
- **L76** «…con búsqueda en árbol: Cowling, Ward y Powley…» → "…con búsqueda en árbol, y así Cowling, Ward y Powley…"
- **L103** «…en tres elementos combinados: el uso del formato Standard…» → "…en tres elementos combinados, que son el uso del formato Standard…"

### 03-metodologia.tex (2)
- **L15** «…naturaleza del problema: dado que la calidad…» → "…naturaleza del problema, ya que, dado que la calidad…" (o "…del problema. Dado que la calidad…").
- **L17** «…cuatro pasos: la implementación de un cambio…» → "…cuatro pasos, que son la implementación de un cambio…"

### 04-propuesta.tex (14 + 2 de A10)
- **L13** «…describe la propuesta: un algoritmo genético adaptado…» → "…describe la propuesta, un algoritmo genético adaptado…"
- **L13** «…sus componentes: la representación de un mazo…» → "…sus componentes, esto es, la representación de un mazo…"
- **L47** «…solo una siembra: en cuanto comienza la evolución…» → "…solo una siembra, ya que en cuanto comienza la evolución…"
- **L49** «…se preserva la élite: los mejores mazos históricos…» → "…se preserva la élite, formada por los mejores mazos históricos…"
- **L53** «…cuota estricta por arquetipo: reserva un tercio…» → "…cuota estricta por arquetipo, de modo que reserva un tercio…"
- **L89** «…norma de las cuatro copias: el valor de cada componente…» → "…norma de las cuatro copias, ya que el valor de cada componente…"
- **L102** «…rendimiento real del mazo: la proporción de partidas…» → "…rendimiento real del mazo, esto es, la proporción de partidas…"
- **L123** «…un tercer criterio opcional: el rendimiento frente a…» → "…un tercer criterio opcional, el rendimiento frente a…"
- **L156** «…comparten un principio: cada mutación es una sustitución…» → "…comparten un principio, y es que cada mutación es una sustitución…"
- **L175** «…un jugador que construye un mazo: completar un pack…» → "…un jugador que construye un mazo, como completar un pack…"
- **L175** «…según el régimen evolutivo: durante el estancamiento…» → "…según el régimen evolutivo, de forma que durante el estancamiento…"
- **L182** «…se realiza por torneo: se toma una muestra aleatoria…» → "…se realiza por torneo, tomando una muestra aleatoria…"
- **L184** «…contra todos los demás: para una población de N…» → "…contra todos los demás, de modo que para una población de N…"
- **L195** «…una segunda ventaja: es el sistema con el que…» → "…una segunda ventaja, y es que se trata del sistema con el que…"
- **L202** «…detenga la ejecución: si se acumulan interrupciones…» → "…detenga la ejecución, ya que si se acumulan interrupciones…"
- **L242** «…una decisión deliberada: el generador no introduce…» → "…una decisión deliberada, puesto que el generador no introduce…"

### 05-implementacion.tex (1)
- **L11** «…la propuesta del capítulo anterior: las tecnologías empleadas…» → "…la propuesta del capítulo anterior, esto es, las tecnologías empleadas…"

### 06-evaluacion.tex (36)
- **L48** «round-robin completo: cada mazo jugaba contra los otros 19…» → "…round-robin completo, de modo que cada mazo jugaba contra los otros 19…"
- **L61** «…comparten una raíz: el algoritmo estaba explorando…» → "…comparten una raíz, y es que el algoritmo estaba explorando…"
- **L63** «…enfrentamientos por generación: donde el round-robin habría exigido 780…» → "…enfrentamientos por generación, ya que, donde el round-robin habría exigido 780…"
- **L78** «…construcción de mazos: intercambio genérico de cartas…» → "…construcción de mazos, como el intercambio genérico de cartas…"
- **L104** «…se reanudó una vez: los datos de estadísticas…» → "…se reanudó una vez, y por ello los datos de estadísticas…"
- **L108** «…formales del formato: los 40 mazos… tienen 60 cartas…» → "…formales del formato, ya que los 40 mazos… tienen 60 cartas…"
- **L130** «…en sentido formal: ningún mazo tiene más de cuatro copias.» → "…en sentido formal, pues ningún mazo tiene más de cuatro copias."
- **L132** «…de una partida a otra: las piezas que deberían definirlo…» → "…de una partida a otra, ya que las piezas que deberían definirlo…"
- **L134** «…caen a 0.17 por mazo: prácticamente cero, y los que quedan…» → "…caen a 0.17 por mazo, prácticamente cero, y los que quedan…"
- **L196** «…resulta identificable: Sheoldred y Preacher…» → "…resulta identificable, con Sheoldred y Preacher… como amenazas ganadoras, …" (reestructurar la enumeración).
- **L198** «No son ruido: son decisiones de construcción…» → "No son ruido, sino decisiones de construcción…"
- **L204** «…significa incluir cuatro copias: esa es la granularidad…» → "…significa incluir cuatro copias, y esa es la granularidad…"
- **L208** «…objetivo de este TFG: generar mazos que se parezcan…» → "…objetivo de este TFG, que es generar mazos que se parezcan…"
- **L225** «…difícil de anticipar: la mejora estructural…» → "…difícil de anticipar, ya que la mejora estructural…"
- **L253** «…de calibración distinto: toda la población cae en el rango…» → "…de calibración distinto, y es que toda la población cae en el rango…"
- **L255** «…refleja ese ruido: la métrica agregada distingue poco…» → "…refleja ese ruido, pues la métrica agregada distingue poco…"
- **L255** «…con el gauntlet activado: ya en la generación 0…» → "…con el gauntlet activado, ya que en la generación 0…"
- **L281** «…propiedades ortogonales: la sinergia interna del mazo y el equilibrio…» → "…propiedades ortogonales, a saber, la sinergia interna del mazo y el equilibrio…"
- **L287** «…que es lo correcto: un mazo que gana partidas…» → "…que es lo correcto, ya que un mazo que gana partidas…"
- **L291** «…rango [0.38, 0.91]): la dispersión relativa casi se duplica…» → "…rango [0.38, 0.91]), de modo que la dispersión relativa casi se duplica…"
- **L291** «…como cabría suponer: la eliminación de la componente estructural…» → "…como cabría suponer, ya que la eliminación de la componente estructural…"
- **L326** «…fuerza diversidad en la población: un mazo aggro R obtendrá…» → "…fuerza diversidad en la población, ya que un mazo aggro R obtendrá…"
- **L339** «…invalida la comparativa externa: el motor Forge aplica…» → "…invalida la comparativa externa, y es que el motor Forge aplica…"
- **L341** «…de forma subóptima: no reconoce las ventanas…» → "…de forma subóptima, pues no reconoce las ventanas…"
- **L343** «…carece de valor discriminativo: cualquier mazo con mínima coherencia…» → "…carece de valor discriminativo, ya que cualquier mazo con mínima coherencia…"
- **L345** «…no tiene este problema: su estrategia es lineal…» → "…no tiene este problema, pues su estrategia es lineal…"
- **L347** «…ruido en la función de fitness: penaliza correctamente…» → "…ruido en la función de fitness, ya que penaliza correctamente…"
- **L351** «…no es de viabilidad técnica: la implementación funciona…» → "…no es de viabilidad técnica, pues la implementación funciona…"
- **L351** «Es de validez metodológica: incluir un componente…» → "Es de validez metodológica, ya que incluir un componente…"
- **L353** «…se abordó de otra forma: la ejecución definitiva…» → "…se abordó de otra forma, y así la ejecución definitiva…"
- **L411** «…una lectura favorable: el mejor individuo aún mejoraba…» → "…una lectura favorable, ya que el mejor individuo aún mejoraba…"
- **L471** «…es el punto de partida: el sistema no fija la semilla…» → "…es el punto de partida, dado que el sistema no fija la semilla…"
- **L493** «…de una ejecución concreta: las dos ejecuciones…» → "…de una ejecución concreta, ya que las dos ejecuciones…"
- **L493** «…estable entre ejecuciones: 0.9755 y 0.9651 sitúan…» → "…estable entre ejecuciones, pues 0.9755 y 0.9651 sitúan…"
- **L507** «…un plan de juego legible: una base de criaturas blancas…» → "…un plan de juego legible, en el que una base de criaturas blancas…"
- **L511** «…una muestra reducida: sostienen la reproducibilidad…» → "…una muestra reducida, que sostiene la reproducibilidad…"

**Colons ante decklist/bloque ("es el siguiente:")** — L171, L495, L433, L445: valorar reescritura suave ("El del baseline se muestra a continuación." / "…se recoge a continuación."). Prioridad menor.

### 07-conclusiones.tex (2)
- **L37** «…granularidad del espacio de búsqueda: cambiar los operadores…» → "…granularidad del espacio de búsqueda, ya que cambiar los operadores…"
- **L61** «…la línea más inmediata: lanzar varias ejecuciones…» → "…la línea más inmediata, que consiste en lanzar varias ejecuciones…"

### 09-anexo-ods.tex (1)
- **L67** «…innovación tecnológica: adapta una metaheurística clásica…» → "…innovación tecnológica, ya que adapta una metaheurística clásica…"

---

## BLOQUE C — Punto y coma pendientes

El tutor vuelve a marcar en la pág. 43 los **paralelismos con `;` que yo había conservado**. Hay
que reescribirlos también:

- `06-evaluacion.tex` L326 «…contra Mono-Red; un control U/W hará lo opuesto.» → punto y "En cambio, un control U/W…".
- `06-evaluacion.tex` L343 (gauntlet) «…no gana porque sea mejor; gana porque su oponente…» → "…no gana porque sea mejor, sino porque su oponente…".
- `06-evaluacion.tex` L347 «…competitividad real; mide en parte explotación…» → "…competitividad real, sino que mide en parte…".
- Repasar los `;` restantes de `02` (L46 paralelismo) y `03` (L37) por si el tutor los quiere fuera igualmente (no marcados explícitamente, pero coherente con la instrucción global).

---

## BLOQUE D — Dos puntos estructurales que SE CONSERVAN (13)

Los que introducen una lista `itemize`/`enumerate` son necesarios y se mantienen:
`01` L26 · `03` L21 · `04` L113 · `06` L52 · `07` L14, L28. (Los de `04` L94/L106 antes de
ecuación pasan a Bloque A10; los de decklist quedan a criterio, arriba.)

---

## Prioridad sugerida

1. **Bloque B + C** (dos puntos y punto y coma) — es el 75 % de las marcas y la queja central. Mecánico pero extenso (~85 reescrituras).
2. **Bloque A** — cambios puntuales (recortes A1/A2/A4/A5, notas al pie A7, citas a ecuaciones A6/A10, coletillas A8/A9/A11/A12).
3. Recompilar, verificar numeración y generar el **6.º borrador**.

Todo es redacción, sin cómputo. Relacionado con la ronda anterior:
`documentacion/CORRECCIONES_TUTOR_RONDA3.md`.
