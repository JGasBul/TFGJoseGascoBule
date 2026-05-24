# Plan: Refinamiento de `deck_quality` tras pack-aware

**Fecha de apertura:** 2026-05-24
**Rama:** `feature/ga-quality-rebalance` (creada desde `develop` en `8b42d12e`)
**Motivación:** Tras la implementación de pack-aware (Fases 1/2/2.5), la métrica `deck_quality` perdió poder discriminativo. Auditando los 40 mazos finales de `prueba2`, el CoV de `quality` es 11.6 % y la métrica media de 0.751 ± 0.087 — no diferencia mazos buenos de mediocres. Esto se manifiesta también en `Gauntlet1`: ya en gen 0 hay mazos con fitness 1.0 saturado, sin gradiente para mejorar.

---

## 0. Resumen ejecutivo

`deck_quality` está construida sobre 6 componentes con pesos α/β/γ. Tras pack-aware, 3 de ellos están **saturados** (CoV < 10 %) y 3 todavía **discriminan** (CoV 17 % - 31 %). El plan elimina los 3 saturados, reponderar los 3 supervivientes, y reactivar `deck_quality` en el fitness con peso β = 0.3.

---

## 1. Diagnóstico cuantitativo

Métricas calculadas sobre los 40 mazos de la población final de `prueba2/` (gen 30, pack-aware):

| Componente | Peso actual | Media | StdDev | Rango | **CoV** | Veredicto |
|---|---:|---:|---:|---:|---:|---|
| `structural` | 10 % | 0.999 | 0.005 | 0.03 | **0.5 %** | ❌ saturado total |
| `card_power` | 15 % | 0.438 | 0.031 | 0.16 | **7.1 %** | ❌ saturado bajo |
| `mana_curve` | 20 % | 0.835 | 0.064 | 0.28 | **7.7 %** | ❌ saturado alto |
| `archetype_coherence` | 15 % | 0.886 | 0.153 | 0.51 | **17.3 %** | ✓ moderado |
| `synergy` | 20 % | 0.679 | 0.188 | 0.69 | **27.7 %** | ✅ bueno |
| `card_balance` | 20 % | 0.747 | 0.230 | 0.90 | **30.7 %** | ✅ bueno |
| **`quality` total** | 100 % | 0.751 | 0.087 | 0.32 | **11.6 %** | ⚠️ diluido |

**Lectura clave:** el 45 % del peso de `deck_quality` (structural + card_power + mana_curve) no aporta información. La métrica media (0.751) y baja varianza (11.6 %) son consecuencia directa de que la mitad del cálculo es "ruido constante".

**Por qué saturan:**

- `structural`: mide playsets vs singletons → pack-aware garantiza 4-of, todos sacan ≈ 1.0.
- `mana_curve`: `adjust_deck_size` regulariza la curva tras cada mutación → toda la pop cae en el rango ideal.
- `card_power`: parece mal calibrado (rango 0.38 - 0.53), todos en ≈ 0.44. Probable saturación bajo el rango útil del scorer.

**Por qué los 3 supervivientes sí discriminan:**

- `card_balance`: criaturas vs no-creaturas según arquetipo. Pack-aware no fuerza esta proporción, así que sigue siendo informativa.
- `synergy`: heurística de sinergias entre cartas. Independiente del marco estructural de pack-aware.
- `archetype_coherence`: avg_cmc/creaturas/tierras vs el ideal del arquetipo detectado. Varía con la composición real.

---

## 2. Decisión

Eliminar las 3 componentes saturadas y reponderar las 3 supervivientes. La pondera nueva mantiene `synergy` y `card_balance` empatadas (las dos más discriminativas) por encima de `archetype_coherence`.

```python
WEIGHTS = {
    'synergy':            0.35,   # antes 0.20 — CoV 27.7 %, premia coherencia interna
    'card_balance':       0.35,   # antes 0.20 — CoV 30.7 %, premia ratio criaturas/spells
    'archetype_coherence':0.30,   # antes 0.15 — CoV 17.3 %, premia ajuste al arquetipo detectado
}
# Eliminados: structural (10 %), card_power (15 %), mana_curve (20 %).
```

**Por qué `synergy` = `card_balance` y no `synergy` > `card_balance`:** sus CoV son comparables (27.7 % y 30.7 %), distinguen propiedades distintas (sinergia interna vs balance de roles), y ambas son cualidades que un jugador humano evaluaría al construir un mazo. Empatarlas es la opción más defendible y simple.

**Por qué `archetype_coherence` un poco por debajo:** su CoV es menor (17.3 %), lo que sugiere que pack-aware ya fuerza parcialmente la coherencia (especialmente las cuotas del HoF). Sigue siendo informativa pero no la principal.

---

## 3. Reactivación de `deck_quality` en el fitness

Tras el rebalanceo, `quality` recupera capacidad discriminativa esperada (CoV proyectado ~22-25 %). Eso justifica reactivarla en el fitness multi-componente, pero con peso menor al original (era 50 %, ahora propuesta 30 %):

```python
fitness_alpha=0.7,                # win_rate Swiss (componente principal)
fitness_beta=0.3,                 # deck_quality refinada
enable_quality_metrics=True,
```

**Por qué β=0.3 y no 0.5:** el componente Swiss sigue siendo el más informativo del rendimiento real. Quality refinada es un ancla estructural que rompe empates entre mazos con win_rate idéntico, no un determinante principal. Con β=0.3:

- Si dos mazos empatan en Swiss (e.g., ambos 6/8), el de mejor quality discrimina.
- Si un mazo gana 7/8 con quality 0.4 vs otro 5/8 con quality 0.9 → el primero gana (`0.7·0.875 + 0.3·0.4 = 0.732` vs `0.7·0.625 + 0.3·0.9 = 0.708`). Razonable.

**Mantenemos el gauntlet desactivado** (`GAUNTLET_ENABLED_BY_DEFAULT = False` en `mtg_main.py`). El plan de la Fase 7 sigue como trabajo futuro pendiente de un motor con AI más sofisticada.

---

## 4. Cambios técnicos concretos

### 4.1 `algoritmo_genetico_mtg.py`

- En `calculate_deck_quality()` (línea ~2751):
  - Borrar el cálculo de `mana_curve_score`, `structural_score`, `card_power_score`.
  - Actualizar `WEIGHTS` a los 3 supervivientes con la nueva ponderación.
  - Actualizar el log.debug para reflejar 3 componentes en lugar de 6.
  - Actualizar el docstring.
- Defaults del constructor (`__init__` ~líneas 90-95):
  - `fitness_alpha`: 1.0 → 0.7.
  - `fitness_beta`: 0.0 → 0.3.
  - `enable_quality_metrics`: False → True.
  - Comentario explica la motivación.

### 4.2 `mtg_main.py`

- Las 5 llamadas a `MTGGeneticAlgorithm(...)` con los defaults antiguos pasan a los nuevos.
- Texto del submenú avanzado actualizado:
  - antes: "Fitness = win_rate del Swiss (deck_quality descartada)"
  - ahora: "Fitness multi-componente: α=0.7·win_rate + β=0.3·calidad refinada"

### 4.3 Sin tocar

- `evaluate_synergy`, `evaluate_card_balance`, `evaluate_archetype_coherence`: el código se queda igual, solo se reponderan en el agregado.
- `evaluate_mana_curve`, `evaluate_structural`, `evaluate_card_power`: el código se conserva (no se borra) porque puede servir para análisis posteriores o reactivación futura. Solo se descuelga del cálculo de `quality`.

---

## 5. Validación esperada

Tras los cambios, repetir la auditoría de la sección 1 sobre los mismos 40 mazos de prueba2:

- CoV de `quality` total debería pasar de **11.6 %** a **~22-25 %**.
- Media de `quality` debería bajar de **0.751** a **~0.65** (deja de estar dominada por las 3 constantes ≈ 0.85-1.0).
- Rango debería ampliarse de 0.32 a **~0.45-0.55**.

Esto confirma que `quality` vuelve a discriminar y que el fitness combinado tendrá gradiente significativo en todos los rangos de la pop.

---

## 6. Bitácora de tareas

- [ ] Editar `calculate_deck_quality()` (eliminar 3 componentes, reponderar 3 supervivientes).
- [ ] Cambiar defaults del constructor (`fitness_alpha=0.7, fitness_beta=0.3, enable_quality_metrics=True`).
- [ ] Actualizar las 5 llamadas en `mtg_main.py`.
- [ ] Actualizar texto del submenú avanzado.
- [ ] Smoke test: auditoría CoV sobre los 40 mazos de prueba2.
- [ ] Si CoV ≥ 20 % → commit y considerar el camino A completado.
- [ ] Si CoV < 20 % → reconsiderar (camino B: añadir Karsten manabase / win-condition density / removal density).

---

## 7. Trabajo futuro (camino B opcional)

Si el camino A no alcanza CoV ≥ 20 %, añadir métricas nuevas que pack-aware no toca:

1. **Manabase Karsten** — ratio `fuentes_color_C / demanda_pip_color_C` por color. Penalizar mazos con CMC pesado en color sin fuentes suficientes (e.g., 4× Sheoldred BB con solo 10 fuentes negras).
2. **Win condition density** — número de cartas que pueden cerrar el juego (criaturas ≥ 4 power, planeswalkers, encantamientos win-cond).
3. **Removal density adaptada al arquetipo** — aggro 4-8 piezas, midrange 8-12, control 12-16. Penalizar desviación.

Cada métrica entre 20-40 líneas de código. Solo abordar si el camino A resulta insuficiente.

---

## 8. Coherencia con runs previos

- **`prueba2` mantiene su validez como entrega final.** Se ejecutó con `α=β=0.5` y `enable_quality_metrics=True` (configuración Fase 4). Su fitness reportado refleja el sistema multi-componente original.
- **Runs futuros con este refinamiento** (e.g., `prueba3/`) usarán `α=0.7, β=0.3` con quality refinada — no son directamente comparables en fitness absoluto con prueba2, pero sí comparables en métricas estructurales, evolución y composición.
- El TFG puede reportar la simplificación de `deck_quality` como **iteración de calibración**: "tras pack-aware se detectaron componentes saturados; se refinó la métrica para mantener su capacidad discriminativa".
