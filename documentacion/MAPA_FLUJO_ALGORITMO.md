# MAPA DEL FLUJO DE TRABAJO — Algoritmo Genético MTG

> Post-Fase 1. Rama: `feature/ga-archetype-ecosystem`.
> Archivo principal: [algoritmo_genetico_mtg.py](../algoritmo_genetico_mtg.py).

---

## 1. Vista de alto nivel

```
┌──────────────────────────────────────────────────────────────────┐
│                         ENTRADA                                  │
│    population_file (JSON)   +   card_catalog.json                │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│   __init__  →  load_population  →  _seed_archetypes              │
│   (cuotas iguales aggro/midrange/control, consolidación)         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   evolve()  ── bucle principal                   │
│                                                                  │
│   Gen 0: evaluate → update_HoF → checkpoint                      │
│                                                                  │
│   Gen g=1..N:                                                    │
│      1. preservar elite (HoF → new_population)                   │
│      2. adaptive_mutation_rate(g, stagnation)                    │
│      3. WHILE |new_pop| < pop_size:                              │
│            p1, p2 = tournament_selection × 2                     │
│            if rand() < crossover_rate:                           │
│                uniform | two_point                               │
│            if rand() < current_mutation_rate:                    │
│                mutate(child) → adaptive → archetype_aware ∣…     │
│      4. evaluate_population_tournament_parallel (Swiss/Forge)    │
│      5. update_HoF                                               │
│      6. handle_termination + anti-stagnation                     │
│      7. save_checkpoint                                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│   finally:  save_statistics · save_final_logs · save_final_pop   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Fases del pipeline

### 2.1 Inicialización — `__init__` + `load_population`
- Lee `card_catalog.json` e índices auxiliares.
- Carga la población inicial (decks preconstruidos del expansion set).
- Llama a `_seed_archetypes` para asignar cuotas arquetípicas.

### 2.2 Siembra arquetípica — [_seed_archetypes](../algoritmo_genetico_mtg.py#L281-L311)
- Asigna rotativamente `aggro / midrange / control` (cuotas iguales).
- Aplica `consolidate_singletons(target_archetype=...)` para empujar cada mazo hacia su cuota.
- Termina con `adjust_deck_size(...)` para garantizar 60 cartas.
- **Filosofía C**: el arquetipo asignado es sólo una siembra; los descendientes usan `detect_archetype(...)` dinámicamente.

### 2.3 Evaluación — [evaluate_population_tournament_parallel](../algoritmo_genetico_mtg.py#L700)
- Swiss Tournament de K rondas con Forge como simulador.
- Devuelve un fitness por mazo = `puntos_swiss × α + calidad × β` (β=0.4 actualmente; Fase 4 lo sube a 0.5).
- Cada mazo también pasa por `calculate_deck_quality` → 6 componentes ponderados.

### 2.4 Cálculo de calidad — [calculate_deck_quality](../algoritmo_genetico_mtg.py#L2043-L2093)
```
quality =
    0.20 · mana_curve(archetype)         ← coherencia con curva ideal del arq.
  + 0.20 · synergy                        ← sinergias carta-a-carta
  + 0.20 · card_balance(archetype)        ← lands/criaturas/hechizos vs ideal
  + 0.15 · card_power                     ← poder individual (coste/efecto)
  + 0.10 · structural                     ← playsets vs singletons
  + 0.15 · archetype_coherence(arq, info) ← distancia al arquetipo detectado
```
`detect_archetype` se llama **una vez** y se propaga a los 4 componentes arquetipo-aware.

### 2.5 Operadores genéticos (Post-Fase 1)

#### Selección
- [tournament_selection](../algoritmo_genetico_mtg.py#L2097): torneo de K (default=4), devuelve copia del ganador.

#### Cruce — controlado **solo** por `evolve()` (gate único: `random() < crossover_rate`)
- [crossover_uniform](../algoritmo_genetico_mtg.py#L947): sin doble puerta. Swap carta-a-carta 50/50 + `adjust_deck_size`.
- [crossover_two_point](../algoritmo_genetico_mtg.py#L964): sin doble puerta. Dos puntos de corte, fusión por bloques. *Fase 4 añadirá variante arquetipo-aware.*

#### Mutación — controlada **solo** por `evolve()` (gate único: `random() < current_mutation_rate`)
- [mutate_swap](../algoritmo_genetico_mtg.py#L990): intercambia 3–8 cartas *(antes 1–3)*.
- [mutate_add_remove](../algoritmo_genetico_mtg.py#L1012): añade/quita 3–8 unidades *(antes 1–3)*.
- [mutate_categorical](../algoritmo_genetico_mtg.py#L1036): 3–6 swaps intra-categoría *(antes 1–2)*.
- [mutate_archetype_aware](../algoritmo_genetico_mtg.py#L1106) **NUEVO**: pondera añadir/quitar por affinity de carta al arquetipo (verificado: aggro añade 2.5× más affinity=2 que affinity=0).
- [mutate_adaptive](../algoritmo_genetico_mtg.py#L1171): dispatcher ponderado. Tres regímenes según `stagnation_counter`:
  ```
  stagn=0   → {archetype_aware:0.45, swap:0.15, add_remove:0.25, categorical:0.15}
  stagn≤5   → {archetype_aware:0.35, swap:0.15, add_remove:0.30, categorical:0.20}
  stagn>5   → {archetype_aware:0.30, swap:0.20, add_remove:0.30, categorical:0.20}
  ```
  Verificado en tests: 170/400 invocaciones a `archetype_aware` (~43%, coherente con el 45% configurado).
- [mutate_hybrid](../algoritmo_genetico_mtg.py#L1088): *conservada pero no referenciada por `mutate()` actual; candidata a borrado en Fase 3.*

#### Tasa de mutación adaptiva — [adaptive_mutation_rate](../algoritmo_genetico_mtg.py#L2125-L2142)
```
base = self.mutation_rate  (config: 0.9)
if stagnation > 5:  base *= 1.5
if stagnation > 10: base *= 2.0
if gen > 50 and stagnation < 3: base *= 0.8
return min(1.0, base)   ← antes min(0.3, …): cap bug arreglado en Fase 1
```

### 2.6 Hall of Fame — [update_hall_of_fame](../algoritmo_genetico_mtg.py#L2144-L2193)
- Activo desde Gen 0 (retraso eliminado).
- Merge de `hall_of_fame_arrays + generación_actual`, ordena por fitness, deduplica por hash del array, trunca a `max_hall_size`.
- El elite preservado en la siguiente generación sale de aquí (`elite_size` primeros).
- **Pendiente Fase 2**: cuotas arquetípicas (4+4+4) para evitar que un arquetipo monopolice el HoF.

### 2.7 Anti-estancamiento — [apply_anti_stagnation_intervention](../algoritmo_genetico_mtg.py#L3029)
- Dispara cuando `handle_termination_conditions` lo indica.
- Inyecta diversidad (reinyección desde HoF diverso + boost de mutation_rate durante 3 gens).
- `restore_mutation_rate` tras 3 gens sin mejora.

### 2.8 Finalización
- `save_statistics` + `save_final_logs` + `save_final_population` en `finally:`, siempre se ejecutan.
- `get_final_best_result` devuelve el mejor del HoF (cross-check con `best_fitness_ever`).

---

## 3. Invariantes verificados (tests Fase 1)

| Invariante | Dónde se garantiza | Test |
|---|---|---|
| 60 cartas tras cualquier operador | `adjust_deck_size` al final de cada método | `test_60_cartas_invariante_en_cadena` |
| Sin doble gate en cruce/mutación | Gate único en `evolve()` (L2582, L2591, L2594) | `TestPhase1Gates` (7 tests) |
| `mutation_rate=0.9` se respeta | `adaptive_mutation_rate` capa en 1.0 | `TestPhase1AdaptiveRate` (3 tests) |
| `archetype_aware` sesga añadidos hacia affinity alta | `_archetype_card_affinity` + `random.choices(weights=...)` | `test_sesgo_add_hacia_afinidad_alta` (459 vs 184) |
| Hijos distintos de padres tras ciclo completo | Combinación cruce+mutación genera diversidad | `test_end_to_end_hijos_distintos` (95-100%) |
| `mutate_adaptive` usa `archetype_aware` | Dispatcher con peso 0.45 en régimen inicial | `test_mutate_adaptive_usa_archetype_aware` (~43%) |

**19/19 tests pasan** (`/tmp/test_fase1.py`).

---

## 4. Verificación de coherencia global

### ¿El flujo tiene sentido? — Sí, con matices:

**Fortalezas ya logradas (Fase 1):**
1. **Un único gate** por operador evita la supresión compuesta (antes la probabilidad efectiva de mutación era ~(0.9)² = 0.81 con cap 0.3, resultando en mutaciones casi inexistentes).
2. **Magnitud aumentada** (3–8 vs 1–3) permite que una mutación sea perceptible contra el ruido de 60 cartas.
3. **Operador arquetipo-aware** convierte la mutación en **exploración dirigida**, no en drift aleatorio.
4. **`calculate_deck_quality` detecta arquetipo una sola vez** y lo propaga (evita 4 detecciones por mazo/gen).

**Cabos sueltos que justifican Fases 2–5:**
- **Fase 2**: HoF sin cuotas → un arquetipo dominante expulsa a los otros del elite y colapsa la diversidad. Además `best_fitness_ever` duplica información ya presente en `hall_of_fame_arrays[0]`.
- **Fase 3**: `mutate_hybrid` ya no se referencia; la intervención anti-estancamiento usa parámetros frágiles.
- **Fase 4**: `elite_size=12` sobre `pop_size=24` preserva 50% → explora poco. `crossover_rate=0.15` es bajísimo para 60 cartas.
- **Fase 5**: no hay métrica de entropía arquetípica; sin ella no podemos validar la Filosofía C cuantitativamente.
- **Fase 6** (cosmética): el `input()` bloqueante y las tres funciones `save_*` duplicadas son fricción operativa.

### Semáforo por módulo

| Módulo | Estado tras Fase 1 | Siguiente acción |
|---|---|---|
| Siembra (`_seed_archetypes`) | 🟢 Verificado | — |
| Fitness + calidad (6 comp) | 🟢 Verificado | — |
| Operadores genéticos | 🟢 Reparado (Fase 1) | Fase 4: crossover arquetipo-aware |
| Gate en `evolve` | 🟢 Gate único | — |
| HoF | 🟡 Funcional, sin cuotas | **Fase 2** (urgente) |
| Anti-estancamiento | 🟡 Funcional, frágil | Fase 3 |
| Parámetros (elite/cross/β) | 🔴 Subóptimos | Fase 4 |
| Observabilidad arquetípica | 🔴 Sin métrica | Fase 5 |

---

## 5. Resumen ejecutivo

Post-Fase 1 el algoritmo tiene:
- Mutación **efectiva** (antes era casi inerte por doble gate + cap 0.3 + magnitud 1–3).
- Mutación **dirigida** (archetype-aware con peso 0.45 en régimen normal).
- Fitness **arquetipo-aware en 4 de 6 componentes**.
- Siembra **con cuotas** que preserva la Filosofía C (arquetipo libre en descendientes).

La próxima fase (HoF con cuotas) es la que más impacto tendrá en preservar la diversidad que esta fase acaba de habilitar.
