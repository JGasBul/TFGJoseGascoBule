# Plan para llevar el TFG de 8,25 a Sobresaliente (9+)

**Nota de partida (memoria escrita):** 8,25 / 10 — Notable alto.
**Objetivo:** ≥ 9, atacando las tres críticas de rigor de validación.

## Restricción de cómputo y cómo la sorteamos

No se puede ejecutar durante muchas horas seguidas. **No hace falta**: el
sistema guarda un checkpoint por generación y sabe reanudar
(`evolve(resume_from_checkpoint=True)`, `find_latest_checkpoint`). Así que
cada experimento se **trocea en sesiones cortas** y se retoma donde se quedó.

Además, la **métrica de calidad es estructural** (no juega partidas): se
recalcula sobre mazos ya guardados sin simular. Eso permite resolver dos
puntos con **cero cómputo nuevo**, solo análisis de datos existentes.

## Reparto: qué necesita simular y qué no

| Tarea | Ataca | Impacto en nota | Cómputo | Quién |
|---|---|---|---|---|
| **T1. CoV post-refinamiento REAL** | Crítica 3 | Alto | **Cero** (datos exp07 ya existen) | Yo (analizo) |
| **T5. Formalizar métricas + engordar Metodología** | Crítica 5 | Medio | Cero (redacción) | Yo |
| **T7. Redacción: afirmaciones prudentes + amenazas a la validez + orden bib.** | Críticas 7 y menores | Medio | Cero (redacción) | Yo |
| **T2. Distribución de fitness del campeón** | Crítica 1 (interna) | Alto | Bajo (decenas de partidas, reanudable) | Tú ejecutas, yo analizo |
| **T3. Contraste externo: campeón vs 3 anchors fiables** | Crítica 1 (externa) | Alto | Bajo-medio (reanudable) | Tú ejecutas, yo analizo |
| **T4. Repeticiones con semillas (3-5)** | Crítica 2 | **El más alto** | Alto pero troceable | Tú ejecutas por sesiones, yo preparo/analizo |
| **T6. Análisis de sensibilidad α/β (opcional)** | Crítica 4 | Medio | Medio | Tú ejecutas corto, yo analizo |

## Orden recomendado (barato y sin cómputo primero)

1. **T1** — ahora mismo, gratis. Convierte un "confía en mí" en un dato medido.
2. **T5 y T7** — redacción, gratis, mientras preparas las ejecuciones.
3. **T2** — primera ejecución corta: reevaluar el campeón N veces.
4. **T3** — campeón contra los 3 anchors fiables.
5. **T4** — la cola larga: repeticiones con semillas, en sesiones sueltas.
6. **T6** — opcional, si sobra tiempo.

Con **T1 + T2 + T3 + parte de T4** ya se desactivan las críticas 1, 2 y 3, que
son las que frenan la nota. T5/T7 rematan.

---

## Detalle de cada tarea

### T1 — CoV post-refinamiento REAL (cero cómputo)
**Problema:** §6.3.3 dice que el CoV tras el refinamiento es "de aproximadamente
22-25 %" y la media "0,60-0,65". Son proyecciones, no medidas.
**Plan:** recalcular la métrica refinada (sinergia 35 %, equilibrio 35 %,
coherencia 30 %) sobre la **población final real de exp07** (40 mazos, ya
guardada en `final_population_20260526_100730.json`) usando
`evaluate_synergy` / `evaluate_card_balance` / `evaluate_archetype_coherence`.
Obtener media, desviación y CoV reales. Sustituir en §6.3.3 el rango proyectado
por el valor medido y añadir una tabla "antes (11,6 %) vs después (medido)".
**Resultado:** el capítulo de refinamiento pasa de argumentado a demostrado.

### T2 — Distribución de fitness del campeón (cómputo bajo)
**Problema:** 0,9755 es una medición única de un fitness que tú mismo declaras
estocástico.
**Plan:** reevaluar el mazo campeón N≈20-30 veces (partidas contra la misma
referencia) y reportar **media ± desviación** e intervalo. Sesión corta y
reanudable.
**Resultado:** "el campeón rinde 0,9X ± 0,0Y" sustituye a un número aislado;
además valida empíricamente la frase de Limitaciones sobre el rendimiento
esperado real.

### T3 — Contraste externo con los 3 anchors fiables (cómputo bajo-medio)
**Problema:** ninguna validación externa (el gauntlet se descartó entero).
**Plan:** enfrentar el campeón a los **3 anchors que sí ejecuta bien Forge**
(Mono-Red, Boros Equipment, Dimir Midrange) — no a Izzet/Azorius, con sesgo.
N partidas cada uno, reportar win-rate con las cautelas debidas.
**Resultado:** una referencia externa modesta pero real, que era justo lo que
faltaba para la afirmación central. Se enmarca honestamente ("3 de 5 anchors,
los fiables").

### T4 — Repeticiones con semillas (cómputo alto, troceable)
**Problema:** todo son ejecuciones únicas; sin repeticiones ni estadística.
**Plan:** repetir el experimento clave con 3-5 semillas distintas. Para que
sea viable con sesiones cortas:
- Elegir la configuración más informativa (probablemente el A/B pack-aware, o
  una versión reducida del run final a ~20-25 generaciones).
- Ejecutar por tandas cortas apoyándose en el checkpoint; retomar cada sesión.
- Reportar **media ± desviación** del pico de fitness, el fitness medio y la
  reducción de singletons **entre semillas**.
**Resultado:** el resultado deja de ser anecdótico; se puede afirmar robustez.
Es el que más sube la nota.

### T5 — Formalizar métricas + engordar Metodología (cero cómputo)
**Plan:** (a) definir formalmente las seis componentes de la métrica de calidad
(fórmula o descripción precisa de cada una) en Propuesta o Metodología; (b)
ampliar el capítulo 3 con el protocolo de evaluación (cómo se mide el fitness,
número de partidas, criterio de parada, tratamiento del ruido).
**Resultado:** cierra la crítica de "capítulo de metodología fino" y da soporte
formal a la función de fitness.

### T6 — Análisis de sensibilidad α/β (opcional, cómputo medio)
**Plan:** dos-tres ejecuciones cortas variando el peso del fitness (0,6/0,4 vs
0,7/0,3 vs 0,8/0,2) y comparar la tendencia. Justifica empíricamente la
elección de 0,7/0,3.

### T7 — Redacción de rigor (cero cómputo)
- Sustituir afirmaciones especulativas ("con más generaciones superaría
  previsiblemente ese valor") por formulaciones prudentes.
- Añadir una subsección explícita de **"Amenazas a la validez"** (aunque
  Limitaciones ya cubre parte).
- Valorar reordenar la bibliografía por orden de aparición.

---

## Estado (se va marcando)

- [x] T1 — CoV post-refinamiento real **(HECHO)**. Medido sobre los 40 mazos de exp03: la métrica original reproduce la tabla 6.4 (CoV 11,4 %), la refinada mide **CoV 19,4 %** (media 0,765, rango [0,38, 0,91]). Se confirma que el refinamiento casi duplica la dispersión; se corrigió la sub-afirmación falsa de que la media bajaba a 0,60-0,65. Script: `scratchpad/t1_cov.py`.
- [ ] T2 — Distribución de fitness del campeón
- [ ] T3 — Contraste externo con 3 anchors
- [ ] T4 — Repeticiones con semillas
- [ ] T5 — Formalizar métricas + Metodología
- [ ] T6 — Sensibilidad α/β (opcional)
- [ ] T7 — Redacción de rigor
