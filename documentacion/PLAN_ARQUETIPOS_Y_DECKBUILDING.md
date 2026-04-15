# Plan de acción: Deck building realista + Arquetipos

**Fecha inicio:** 2026-04-15
**Base:** commit 2080dc0c (Swiss Tournament validado)
**Objetivo:** Eliminar el problema de "pila aleatoria" (36 singletons) y hacer que el AG genere mazos coherentes con arquetipos reconocibles.

---

## Contexto del problema

Los mazos evolucionados actualmente presentan:
- **36 cartas únicas no-tierra** (vs 13-16 en meta real)
- Mayoría como singletons (1 copia) en lugar de playsets (4 copias)
- Sin coherencia de arquetipo (mezcla criaturas agresivas con hechizos de control)

**Causa raíz:** El AG no tiene presión selectiva hacia la estructura canónica de un mazo competitivo ni hacia un arquetipo definido.

---

## Datos de referencia (estudio empírico Standard)

### Estructura común a todos los arquetipos
- 13-16 cartas únicas no-tierra
- 60-75% de las cartas no-tierra en playsets de 4
- 0-2 singletons máximo
- 60 cartas totales

### Ratios por arquetipo

| Arquetipo | Criaturas | Hechizos no-criatura | CMC medio | Tierras |
|-----------|-----------|----------------------|-----------|---------|
| Aggro     | 24-28     | 8-12                 | 1.8-2.2   | 20-22   |
| Midrange  | 16-22     | 10-14                | 2.5-3.0   | 23-25   |
| Control   | 4-10      | 20-26                | 3.0-3.5   | 25-27   |
| Combo/Ramp| 10-16     | 12-18                | 2.2-3.2   | 22-26   |

### Decisión TFG
Soportar inicialmente **3 arquetipos**: Aggro, Midrange, Control.
Combo/Ramp se aplaza a segunda iteración (clasificación automática más compleja).

---

## Arquitectura de la solución: 4 capas

### Capa 0: Clasificador de arquetipo (NUEVO — paso previo)
**Qué:** Dado un mazo, detectar su arquetipo dominante.

**Cómo:**
- Calcular curva de maná (CMC medio, distribución)
- Calcular ratio criaturas / hechizos no-criatura
- Heurísticas sobre tipos de carta (counter, removal, haste, etc.) — opcional en v1
- Devolver etiqueta: `aggro` | `midrange` | `control`

**Dónde:** Nueva función `detect_archetype(deck) -> str` en `algoritmo_genetico_mtg.py`.

**Criterio de clasificación v1 (simple):**
```
if CMC_medio < 2.3 and criaturas >= 22: "aggro"
elif CMC_medio > 2.9 and criaturas <= 12: "control"
else: "midrange"
```

---

### Capa 1: Constraint de consolidación (en `adjust_deck_size`)
**Qué:** Al reparar un mazo tras cruce/mutación, consolidar singletons respetando el arquetipo.

**Cómo:**
1. Detectar arquetipo actual del mazo
2. Si hay >2 singletons no-tierra: consolidar subiendo a 4 las cartas coherentes con el arquetipo
3. Respetar ratios objetivo del arquetipo (criaturas vs hechizos)

**Dónde:** Modificar `adjust_deck_size()` en `algoritmo_genetico_mtg.py`.

---

### Capa 2: Fitness con componente de calidad estructural
**Qué:** Penalizar/premiar la estructura del mazo relativa a su arquetipo.

**Cómo:** Añadir a `deck_quality`:
- **Penalización:** Número de singletons > 2 (escalado)
- **Penalización:** Cartas únicas no-tierra > 18
- **Bonus:** % de cartas en playsets de 4 (objetivo 60-75%)
- **Penalización:** Desviación de ratios del arquetipo detectado (criaturas/hechizos, CMC)

**Peso propuesto:** `fitness = 0.7 * win_rate + 0.3 * deck_quality`
(actualmente existe `deck_quality` pero con pesos distintos — a revisar)

---

### Capa 3: Operador de mutación "consolidación"
**Qué:** Mutación dirigida que convierte singletons en playsets.

**Cómo:** Con cierta probabilidad, elegir una carta con 1 copia y subirla a 4, descartando otras cartas singletons del mazo.

**Dónde:** Nuevo método en clase `MTGGeneticAlgorithm`, añadir a la selección de operadores de mutación.

**Prioridad:** Baja — solo si Capas 0-2 no bastan.

---

## Orden de implementación

1. **[TAREA 1]** Implementar `detect_archetype()` (Capa 0) — función pura, testeable
2. **[TAREA 2]** Modificar `adjust_deck_size()` con consolidación arquetipo-aware (Capa 1)
3. **[TAREA 3]** Test unitario: generar 10 mazos, verificar que ninguno tiene >3 singletons
4. **[TAREA 4]** Añadir métricas estructurales a `deck_quality` (Capa 2)
5. **[TAREA 5]** Ejecutar prueba corta (5 generaciones) y verificar:
   - Número medio de singletons por mazo ↓
   - Número medio de cartas únicas no-tierra ↓ (hacia 13-16)
   - Distribución de arquetipos en la población
6. **[TAREA 6]** Si hace falta, implementar mutación de consolidación (Capa 3)
7. **[TAREA 7]** Ejecutar experimento completo (50 generaciones) y documentar resultados

---

## Notas pendientes de la libreta (estado)

- **Nota 1** — `fitness = 0.5*win_rate_vs_population + 0.5*vs_tier1_reales`: **PENDIENTE** (requiere mazos tier1 reales como referencia)
- **Nota 2** — Restricciones 4-of: **EN CURSO** (este plan)
- **Nota 3** — Adaptive Operator Selection (AOS): **PENDIENTE** (posterior)

---

## Riesgos y decisiones abiertas

- **Riesgo:** Clasificador de arquetipo v1 demasiado simple → puede fallar en mazos transicionales. Mitigación: aceptar cierto error en v1, refinar tras primer experimento.
- **Decisión abierta:** ¿Forzar arquetipo al inicializar la población (cada mazo nace con arquetipo asignado) o dejar que emerja? → Propuesta: **dejar emerger** para no sesgar, pero verificar que emergen todos los arquetipos.
- **Decisión abierta:** Pesos exactos de `deck_quality` → ajustar empíricamente.

---

## Criterio de éxito

Un experimento de 50 generaciones debe producir mazos donde:
- ✅ Cartas únicas no-tierra: 13-18 (actualmente 36)
- ✅ Singletons: ≤ 3
- ✅ Arquetipo identificable (criaturas/hechizos/CMC coherentes)
- ✅ Win rate ≥ al del base actual (no degradar competitividad)
