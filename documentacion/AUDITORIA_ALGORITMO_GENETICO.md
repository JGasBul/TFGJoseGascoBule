# Auditoría completa de `algoritmo_genetico_mtg.py`

**Fecha:** 2026-04-16
**Motivo:** Tras la corrida de la noche (pop=40, 30 generaciones, Swiss k=8, n=2) la Gen 1 colapsó a **39 midrange / 1 aggro / 0 control** pese a sembrar Gen 0 de forma equitativa (24 mid / 12 ctrl / 4 agg tras detección real). 31 de los 40 mazos de Gen 1 eran clones exactos de mazos de Gen 0 (fingerprint idéntico en tierras, criaturas, cmc promedio y uniques).

Este documento recoge TODOS los errores, inconsistencias y problemas de diseño detectados en la revisión línea a línea del algoritmo, clasificados por severidad, junto con el plan de reparación en fases.

---

## 1. BUGS CRÍTICOS (rompen la evolución efectiva)

### 1.1. Crossover con doble compuerta ("DOUBLE-GATE")
**Ubicaciones:** [algoritmo_genetico_mtg.py:2505](../algoritmo_genetico_mtg.py#L2505), [algoritmo_genetico_mtg.py:952](../algoritmo_genetico_mtg.py#L952), [algoritmo_genetico_mtg.py:966](../algoritmo_genetico_mtg.py#L966)

El bucle principal `evolve()` decide si aplicar cruce con:
```python
if random.random() < self.crossover_rate:                   # L2505 (gate EXTERNO)
    if random.random() < 0.5:
        child1, child2 = self.crossover_uniform(p1, p2)
    else:
        child1, child2 = self.crossover_two_point(p1, p2)
```

Pero **tanto `crossover_uniform` como `crossover_two_point` vuelven a filtrar internamente**:
```python
def crossover_uniform(self, parent1_array, parent2_array):
    if random.random() > self.crossover_rate:                # L952 (gate INTERNO)
        return parent1_array.copy(), parent2_array.copy()    # ← devuelve clones
    ...
```

**Efecto real:** cruce efectivo = `0.15 × 0.15 = 2.25 %` cuando la configuración intenta 15 %.
**Consecuencia:** 97 % de los "hijos" son copias literales de los padres → explica los 31 clones detectados en Gen 1.

---

### 1.2. Mutación con triple compuerta ("TRIPLE-GATE")
**Ubicaciones:** [algoritmo_genetico_mtg.py:2514](../algoritmo_genetico_mtg.py#L2514), [algoritmo_genetico_mtg.py:2517](../algoritmo_genetico_mtg.py#L2517), [algoritmo_genetico_mtg.py:1105](../algoritmo_genetico_mtg.py#L1105), [algoritmo_genetico_mtg.py:990](../algoritmo_genetico_mtg.py#L990), [algoritmo_genetico_mtg.py:1011](../algoritmo_genetico_mtg.py#L1011), [algoritmo_genetico_mtg.py:1035](../algoritmo_genetico_mtg.py#L1035), [algoritmo_genetico_mtg.py:1087](../algoritmo_genetico_mtg.py#L1087)

Tres niveles de filtro apilados:

1. **Nivel externo (`evolve`)**:
   ```python
   if random.random() < current_mutation_rate:               # L2514 (0.3 tras el cap)
       child1 = self.mutate(...)
   ```
2. **Nivel dispatcher (`mutate_adaptive` / `mutate_hybrid`)**:
   ```python
   if random.random() > self.mutation_rate: return deck_array.copy()  # L1105, L1087 (0.9)
   ```
3. **Nivel sub-estrategia (`mutate_swap`, `mutate_add_remove`, `mutate_categorical`)**:
   ```python
   if random.random() > self.mutation_rate: return deck_array.copy()  # L990, L1011, L1035 (0.9)
   ```

**Efecto real:** mutación efectiva = `0.3 × 0.9 × 0.9 ≈ 24.3 %` cuando la configuración pretende 90 %.

---

### 1.3. Cap oculto en `adaptive_mutation_rate`
**Ubicación:** [algoritmo_genetico_mtg.py:2053-2065](../algoritmo_genetico_mtg.py#L2053)

```python
def adaptive_mutation_rate(self, generation, stagnation_counter):
    base_rate = self.mutation_rate   # 0.9
    if stagnation_counter > 5:  base_rate *= 1.5
    if stagnation_counter > 10: base_rate *= 2.0
    if generation > 50 and stagnation_counter < 3: base_rate *= 0.8
    return min(0.3, base_rate)       # ← TECHO DE 0.3 ¡SIEMPRE!
```

El comentario del `__init__` ya lo reconoce: `mutation_rate=0.9, # Alta exploración (call sites usan este valor; cap real 0.3 en adaptive_mutation_rate)`.
Es una decisión deliberada, pero es lo que arrastra el bug 1.2. Además, es **inconsistente** con `apply_anti_stagnation_intervention` (L3008), que usa `min(0.4, ...)`.

---

### 1.4. `crossover_two_point` semánticamente vacío
**Ubicación:** [algoritmo_genetico_mtg.py:964-986](../algoritmo_genetico_mtg.py#L964)

Los arrays tienen tamaño `total_cards` (~2500) y están indexados por `card_id` (asignado arbitrariamente por el catálogo). Cortar entre `card_id=500` y `card_id=1500` **no preserva ninguna agrupación biológica o de juego** — los IDs no tienen orden jerárquico.

```python
points = sorted(random.sample(range(1, self.total_cards), 2))
child1 = np.concatenate([parent1[:points[0]], parent2[points[0]:points[1]], parent1[points[1]:]])
```

Resultado: mezcla aleatoria sin contenido estructural. Debería sustituirse por un cruce **categoría-consciente** (intercambiar criaturas con criaturas, tierras con tierras, etc.) o eliminarse.

---

### 1.5. Hall of Fame ciego al arquetipo + élite excesivo
**Ubicaciones:** [algoritmo_genetico_mtg.py:2067-2116](../algoritmo_genetico_mtg.py#L2067), [algoritmo_genetico_mtg.py:2486-2493](../algoritmo_genetico_mtg.py#L2486), [algoritmo_genetico_mtg.py:71](../algoritmo_genetico_mtg.py#L71)

El HoF guarda los mejores `max_hall_size = max(elite_size, 5) = 12` por fitness puro, sin cuotas por arquetipo. Luego `evolve` copia **íntegros** los primeros `elite_size = 12` al nuevo `new_population`:

```python
elite_to_preserve = min(self.elite_size, len(self.hall_of_fame_arrays))
for i in range(elite_to_preserve):
    new_population.append(elite_array.copy())       # L2491
```

**Consecuencia en cascada:**
- Si aggro gana los primeros enfrentamientos de Gen 0 (cosa habitual en metas lentos), el HoF se llena de aggro.
- 12 aggro se clonan directamente a Gen 1 (30 % de pop=40).
- Con cruce al 2 % y mutación al 24 %, el resto (28 hijos) son casi clones de padres aggro.
- `adjust_deck_size` + `consolidate_singletons` sin `target_archetype` (ver 2.2) re-clasifican mucho hacia midrange, colapsando la diversidad.

Combinación letal: **12 élites + 2 % cruce + 24 % mutación + HoF ciego** = Gen 1 homogénea.

---

## 2. BUGS SERIOS (degradan calidad)

### 2.1. Magnitud de mutación demasiado pequeña
**Ubicaciones:** [algoritmo_genetico_mtg.py:994](../algoritmo_genetico_mtg.py#L994), [algoritmo_genetico_mtg.py:1015](../algoritmo_genetico_mtg.py#L1015), [algoritmo_genetico_mtg.py:1061](../algoritmo_genetico_mtg.py#L1061)

```python
num_swaps   = random.randint(1, 3)    # mutate_swap
num_changes = random.randint(1, 3)    # mutate_add_remove
num_swaps   = random.randint(1, 2)    # mutate_categorical
```

Sobre un mazo de 60 cartas, 1-3 cambios = **1.6 %–5 %** del mazo. Insuficiente para abandonar óptimos locales. Debería ser `randint(3, 8)` o dinámico según estancamiento.

---

### 2.2. `_seed_archetypes` loguea el objetivo, no el resultado
**Ubicación:** [algoritmo_genetico_mtg.py:281-311](../algoritmo_genetico_mtg.py#L281)

```python
for i, arr in enumerate(population_arrays):
    target = archetypes[i % len(archetypes)]
    arr_seeded = self.consolidate_singletons(arr, target_archetype=target)
    arr_seeded = self.adjust_deck_size(arr_seeded)
    seeded.append(arr_seeded)
    archetype_counts[target] += 1                 # ← cuenta el objetivo asignado
```

El log dice *"Gen0 sembrada con cuotas arquetípicas: {'aggro': 14, 'midrange': 13, 'control': 13}"* pero esas son las etiquetas **pretendidas**. `detect_archetype` real de los mazos ya consolidados da otra distribución (en la corrida: 24 mid / 12 ctrl / 4 agg). La observabilidad es engañosa.

---

### 2.3. Dispatcher `mutate` con rama muerta
**Ubicación:** [algoritmo_genetico_mtg.py:1135-1151](../algoritmo_genetico_mtg.py#L1135)

```python
def mutate(self, deck_array, generation=0, stagnation_counter=0):
    if generation > 0 or stagnation_counter > 0:
        return self.mutate_adaptive(...)
    else:
        return self.mutate_hybrid(...)
```

En la práctica, `evolve` **siempre** llama con `generation >= 1`, así que la rama `mutate_hybrid` nunca se ejecuta en producción. Es código muerto que complica lectura y duplica gates redundantes.

---

### 2.4. `elite_size = 12` sobre `pop = 40` es demasiado (30 %)
**Ubicación:** [algoritmo_genetico_mtg.py:71](../algoritmo_genetico_mtg.py#L71)

Preservar el 30 % de la población sin modificar genera una fuerza homogeneizante muy fuerte. Combinado con el HoF ciego al arquetipo (1.5), es el multiplicador del colapso. Literatura habitual: 10-20 % de élite en GAs.

---

### 2.5. Diversidad sólo mide presencia, no cantidades
**Ubicación:** [algoritmo_genetico_mtg.py:2035-2051](../algoritmo_genetico_mtg.py#L2035)

```python
card_frequencies += (array > 0).astype(int)   # binarización
```

Dos mazos con los mismos 40 IDs únicos pero distintos counts (ej. 4-of vs 1-of) cuentan como idénticos para la métrica. Subestima la homogeneización real.

---

## 3. INCONSISTENCIAS MENORES

### 3.1. Cap distinto en intervención anti-estancamiento
**Ubicación:** [algoritmo_genetico_mtg.py:3008](../algoritmo_genetico_mtg.py#L3008)

```python
self.mutation_rate = min(0.4, self.mutation_rate * 3.0)
```

Mientras `adaptive_mutation_rate` topa en 0.3. El techo efectivo de mutación pasa de 0.3 a 0.4 tras una intervención, introduciendo un salto no documentado.

---

### 3.2. Doble `save_checkpoint` post-intervención
**Ubicaciones:** [algoritmo_genetico_mtg.py:2567](../algoritmo_genetico_mtg.py#L2567), [algoritmo_genetico_mtg.py:2591](../algoritmo_genetico_mtg.py#L2591)

Tras aplicar intervención se guarda checkpoint y luego se hace `continue`, saltando el checkpoint final del bucle. Correcto funcionalmente, pero un poco redundante y confuso al leer el flujo.

---

### 3.3. `input()` bloqueante en `evolve()`
**Ubicación:** [algoritmo_genetico_mtg.py:2417](../algoritmo_genetico_mtg.py#L2417)

```python
response = input(f"\n¿Deseas reanudar desde la generación {checkpoint_gen}? (S/n): ").strip().lower()
```

Si el algoritmo se lanza en background (servidor, nohup, cron, CI), la llamada a `input()` cuelga la ejecución silenciosamente. Debería ser un flag CLI (`--resume` / `--fresh`) o una opción del config.

---

### 3.4. `mutate_hybrid` no propaga `generation`/`stagnation`
**Ubicación:** [algoritmo_genetico_mtg.py:1085-1101](../algoritmo_genetico_mtg.py#L1085)

Acepta sólo `deck_array`. Como la rama hybrid en la práctica está muerta (3.3) no causa daño, pero si alguna vez se reactivara, perdería la información adaptativa.

---

### 3.5. `mutation_rate` del log vs mutation efectiva
**Ubicación:** [algoritmo_genetico_mtg.py:2754](../algoritmo_genetico_mtg.py#L2754), [algoritmo_genetico_mtg.py:3179](../algoritmo_genetico_mtg.py#L3179)

`update_statistics` guarda `self.mutation_rate` (0.9) como "mutation_rate", no el efectivo (0.3). El CSV de evolución reporta valores que no coinciden con lo que realmente aplica el algoritmo.

---

## 4. RESUMEN NUMÉRICO DEL IMPACTO

| Componente     | Config. declarada | Efectivo real      | Pérdida     |
|----------------|-------------------|--------------------|-------------|
| crossover_rate | 0.15              | 0.0225 (0.15²)     | -85 %       |
| mutation_rate  | 0.9               | ~0.243 (0.3·0.9²)  | -73 %       |
| elite clones   | -                 | 12/40 (30 %)       | alto        |
| HoF diversity  | top-12 by fitness | sin cuota arq.     | total       |

Con estos números, la población de la Gen 1 es matemáticamente esperable que sea:
- ~12 clones exactos del HoF (élite).
- ~28 hijos "crossover": 97 % idénticos a padres, 3 % mezclados aleatoriamente.
- De esos 28, ~76 % sin mutar, el 24 % restante mutado con 1-3 cambios (1.6-5 % del mazo).
- `adjust_deck_size` re-normaliza todo, colapsando detecciones arquetípicas a midrange.

Por eso salen 31 clones y 39 mid / 1 agg / 0 ctrl: **el algoritmo está haciendo exactamente lo que el código le pide, pero lo que le pide no es evolucionar**.

---

## 5. REVISIÓN POR FILOSOFÍA ACTUAL — QUÉ FALTA Y QUÉ SOBRA

Los apartados 1-4 detectan bugs dentro del diseño actual. Este apartado examina el código bajo la lente de la **filosofía actual del TFG** (evolución paralela de 3 arquetipos con siembra equitativa, descendientes libres, fitness arquetipo-aware de 6 componentes completada en Tarea 4). Dado que el proyecto comenzó con otra filosofía (evolución genérica monolítica), hay piezas desactualizadas.

---

### 5.1. LO QUE FALTA (la filosofía lo exige, pero no existe)

#### F1 — Mutación arquetipo-aware
**Ubicación:** [algoritmo_genetico_mtg.py:988-1101](../algoritmo_genetico_mtg.py#L988)

Ya tenemos fitness arquetipo-aware y consolidación arquetipo-aware. Pero `mutate_swap`, `mutate_add_remove` y `mutate_categorical` son **totalmente ciegas al arquetipo**: un mazo control muta igual que uno aggro, con igual probabilidad de añadir criaturas baratas o hechizos caros. La mutación degrada el arquetipo detectado generación tras generación.

Hace falta una variante que use `_archetype_card_affinity` como sesgo: quitar preferentemente cartas con `affinity=0`, añadir preferentemente cartas con `affinity=2`.

#### F2 — Cuota arquetípica en Hall of Fame
**Ubicación:** [algoritmo_genetico_mtg.py:2067-2116](../algoritmo_genetico_mtg.py#L2067)

Ya listado como bug 1.5. Subrayado aquí porque **sin esto la filosofía de "3 arquetipos en paralelo" simplemente no existe en operación** — el HoF es top-N puro por fitness, colapsa a lo que gane más, y ese colapso se propaga al élite de la siguiente generación.

#### F3 — Cruce categoría-consciente
**Ubicación:** [algoritmo_genetico_mtg.py:964-986](../algoritmo_genetico_mtg.py#L964)

`crossover_two_point` corta por índice arbitrario de `card_id` (bug 1.4). Lo que debería existir es un cruce que preserve la coherencia del arquetipo del padre dominante: cruzar criaturas con criaturas, tierras con tierras, hechizos con hechizos, de modo que el hijo sea una recombinación jugable y no ruido.

#### F4 — Inmigración arquetipo-aware
**Ubicación:** [algoritmo_genetico_mtg.py:2952-3061](../algoritmo_genetico_mtg.py#L2952)

`apply_anti_stagnation_intervention` inyecta 30 % de mazos nuevos desde `MTGDeckGenerator` **sin pasarlos por `_seed_archetypes`**. Si la filosofía inicial es sembrar con cuotas, la inmigración también debería respetar cuotas. Es una línea: pasar los nuevos inmigrantes por `_seed_archetypes` antes de insertarlos.

#### F5 — Etiqueta de arquetipo en persistencia
**Ubicaciones:** [algoritmo_genetico_mtg.py:372-477](../algoritmo_genetico_mtg.py#L372), [algoritmo_genetico_mtg.py:2881-2912](../algoritmo_genetico_mtg.py#L2881), [algoritmo_genetico_mtg.py:3164-3197](../algoritmo_genetico_mtg.py#L3164)

Ninguna de las funciones de guardado registra el arquetipo detectado:
- `save_population_arrays` guarda sum, non_zero, fitness, pero no `detect_archetype`.
- `save_hall_of_fame_data` igual.
- `update_statistics` no registra la distribución arquetípica por generación.

El análisis post-hoc requiere reparsear los `.dck` con un script externo (como `/tmp/analyze_server_gens.py`). Debería ser nativo.

#### F6 — Métrica de diversidad arquetípica
**Ubicación:** [algoritmo_genetico_mtg.py:2035-2051](../algoritmo_genetico_mtg.py#L2035)

`calculate_diversity` sólo mide presencia binaria de `card_id`. Falta una métrica de diversidad arquetípica — típicamente **entropía de Shannon** sobre la distribución `{aggro, midrange, control}`:

```
H = -Σ p_i · log2(p_i)
```

H = log2(3) ≈ 1.58 con distribución perfecta, H = 0 con colapso total. Indicador directo de si el ecosistema de arquetipos está vivo.

---

### 5.2. LO QUE SOBRA (desactualizado respecto a la filosofía actual)

#### S1 — `stagnation_limit = 999` desactiva casi 200 líneas de código
**Ubicación:** [algoritmo_genetico_mtg.py:72](../algoritmo_genetico_mtg.py#L72)

Con `stagnation_limit=999` nunca se dispara `apply_anti_stagnation_intervention`. Quedan muertos en producción:
- `apply_anti_stagnation_intervention` ([L2952-3061](../algoritmo_genetico_mtg.py#L2952), ~110 líneas)
- `select_diverse_elite` ([L3064-3095](../algoritmo_genetico_mtg.py#L3064))
- `restore_mutation_rate` ([L3098-3105](../algoritmo_genetico_mtg.py#L3098))
- Segunda rama de `handle_termination_conditions` ([L2935-2946](../algoritmo_genetico_mtg.py#L2935))
- Gestión de `generations_since_intervention`, `original_mutation_rate`, `interventions_applied`.

**Decisión pendiente:** si no se va a reactivar → **eliminar todo el bloque**. Si se reactiva → arreglar con F4 (inmigración arq-aware) y unificar cap con el adaptativo.

#### S2 — `mutate_hybrid` + rama muerta del dispatcher
**Ubicación:** [algoritmo_genetico_mtg.py:1085-1151](../algoritmo_genetico_mtg.py#L1085)

`evolve` siempre llama a `self.mutate(child, generation, stagnation_counter)` con `generation >= 1`. La rama `mutate_hybrid` del dispatcher (L1150-1151) nunca se ejecuta en producción. Eliminar `mutate_hybrid` completo y simplificar `mutate` a una sola línea que llame a `mutate_adaptive`.

#### S3 — `crossover_two_point` sin semántica
Ya cubierto (bug 1.4). O se rediseña como F3, o se elimina.

#### S4 — Fallbacks redundantes en `get_final_best_result`
**Ubicación:** [algoritmo_genetico_mtg.py:3107-3162](../algoritmo_genetico_mtg.py#L3107)

Tres opciones de recuperación:
```python
if hasattr(self, 'hall_of_fame_arrays'): ...            # opción 1
elif hasattr(self, 'hall_of_fame') and ...: ...         # opción 2 (atributo inexistente)
else: ...                                               # opción 3
```

El atributo `self.hall_of_fame` nunca se crea en `__init__` (sólo existe `hall_of_fame_arrays`), así que la opción 2 es código muerto. Simplificar a 2 opciones reales.

#### S5 — Solapamiento de funciones de guardado
Funciones que guardan información casi idéntica:
- `save_population_arrays` — por generación, detallado + compacto + histórico
- `save_final_population` — al terminar, contiene lo mismo que `save_population_arrays` con array_to_deck
- `save_statistics` + `save_incremental_statistics` — mismos CSV con nombres diferentes
- `save_hall_of_fame_data` + `save_hall_of_fame_decks` — mismos mazos en JSON y .dck

Bajo la filosofía actual (archivos `.dck` como fuente canónica + `evolution_history.json` como resumen), podrían consolidarse a **3 funciones**: estado-de-generación, estado-final, gráficos.

#### S6 — `headless_mode` y `save_forge_outputs` como complejidad opcional
**Ubicaciones:** [algoritmo_genetico_mtg.py:255-260](../algoritmo_genetico_mtg.py#L255), [algoritmo_genetico_mtg.py:3261-3264](../algoritmo_genetico_mtg.py#L3261)

Si la corrida real siempre es en servidor headless, `headless_mode` podría ser único modo. `save_forge_outputs=True` genera GB de logs que se auto-desactivan al 95 % de disco; si no se auditan, mejor por defecto a `False`.

#### S7 — `best_fitness_ever` duplica el Hall of Fame
**Ubicaciones:** [algoritmo_genetico_mtg.py:2540-2544](../algoritmo_genetico_mtg.py#L2540), [algoritmo_genetico_mtg.py:2596-2606](../algoritmo_genetico_mtg.py#L2596)

Se mantiene `self.best_fitness_ever` aparte del HoF. Termina divergiendo (ver log de la corrida: *"Discrepancia en fitness final: Hall of Fame: X vs Best Ever: Y"*). Con un HoF bien implementado, este atributo es redundante.

---

### 5.3. TABLA RESUMEN POR MÉTODO

| Método                                       | Estado actual          | Acción                       |
|----------------------------------------------|------------------------|------------------------------|
| `_seed_archetypes`                           | ✅ Coherente           | Arreglar log (bug 2.2)       |
| `consolidate_singletons`                     | ✅ Coherente           | —                            |
| `adjust_deck_size`                           | ✅ Coherente           | —                            |
| `detect_archetype`                           | ✅ Coherente           | —                            |
| Fitness (6 componentes)                      | ✅ Coherente           | —                            |
| `crossover_uniform`                          | ⚠️ Con bug 1.1          | Quitar gate interno (Fase 1) |
| `crossover_two_point`                        | ❌ Sin semántica        | **Eliminar o rediseñar (F3)**|
| `mutate_swap/add_remove/categorical`         | ⚠️ Ciegas al arquetipo  | **Añadir arq-aware (F1)**    |
| `mutate_hybrid` + rama muerta dispatcher     | ❌ Código muerto        | **Eliminar (S2)**            |
| `update_hall_of_fame`                        | ❌ Sin cuota arq.       | **F2**                       |
| `tournament_selection`                       | ✅ Neutro, OK          | —                            |
| `apply_anti_stagnation_intervention` y hijos | ❌ Desactivado          | **Decidir: borrar o arreglar (S1)** |
| `calculate_diversity`                        | ⚠️ Sólo binaria         | **F6 (entropía arq.)**       |
| `save_population_arrays`                     | ⚠️ Sin arquetipo        | **F5**                       |
| `save_hall_of_fame_data`                     | ⚠️ Sin arquetipo        | **F5**                       |
| `save_*` (varias)                            | ⚠️ Solapamiento         | **S5 (consolidar)**          |
| `get_final_best_result`                      | ⚠️ Fallbacks muertos    | **S4**                       |
| `best_fitness_ever`                          | ⚠️ Duplicado HoF        | **S7**                       |
| `headless_mode`/`save_forge_outputs`         | ⚠️ Complejidad opcional | **S6 (simplificar)**         |

---

## 6. PLAN DE REPARACIÓN EN FASES (revisado)

Cada fase se implementa y se commitea por separado para poder auditar el efecto de cada cambio.

### Fase 1 — Operadores genéticos (crítica, desbloquea el GA)
- Eliminar el gate interno de `crossover_uniform` (L952-953).
- Eliminar el gate interno de `crossover_two_point` (L966-967) — en esta fase sólo el gate; el rediseño cae en Fase 4.
- Eliminar gates internos de `mutate_swap`, `mutate_add_remove`, `mutate_categorical`, `mutate_hybrid`, `mutate_adaptive` (L990, 1011, 1035, 1087, 1105).
- Eliminar `min(0.3, base_rate)` de `adaptive_mutation_rate` (L2065) — usar `min(1.0, base_rate)`.
- Subir magnitud de mutación: `num_changes = random.randint(3, 8)` en las tres estrategias.
- **F1**: Añadir `mutate_archetype_aware` usando `_archetype_card_affinity` como sesgo para add/remove y categorical.

### Fase 2 — Hall of Fame con cuota arquetípica
- Reescribir `update_hall_of_fame` con cuota 4+4+4 por arquetipo (12 slots totales).
- Si un arquetipo está vacío, rellenar con mejores globales (fallback).
- `save_hall_of_fame_decks` refleja la cuota en el nombre (`hall_of_fame_aggro_1.dck`).
- Eliminar `best_fitness_ever` (S7): derivar siempre del HoF.

### Fase 3 — Limpieza de código muerto
- Eliminar `mutate_hybrid` y la rama muerta del dispatcher `mutate` (S2).
- **Decisión sobre anti-estancamiento (S1)**:
  - Opción A (recomendada): **eliminar** `apply_anti_stagnation_intervention`, `select_diverse_elite`, `restore_mutation_rate`, la segunda rama de `handle_termination_conditions`, y toda la gestión asociada. Mantener `stagnation_counter` sólo para logs/métricas.
  - Opción B: mantener pero reactivar con F4.
- Simplificar `get_final_best_result` a 2 opciones reales (S4).
- Eliminar `headless_mode`/`save_forge_outputs` como flags opcionales si siempre son fijos (S6).

### Fase 4 — Balance de parámetros + cruce arquetípico
- `elite_size`: 12 → **9** (22.5 % de pop=40).
- `crossover_rate`: 0.15 → **0.30** (ahora efectivo, no 0.15²).
- `fitness_beta`: 0.4 → **0.5** (más peso a calidad estructural).
- **F3**: Sustituir `crossover_two_point` por `crossover_archetype` categoría-consciente (cruza criaturas con criaturas, tierras con tierras, hechizos con hechizos). Si se opta por eliminar, dejar sólo `crossover_uniform`.
- **F4** (sólo si Fase 3 optó B): inmigración arquetipo-aware en `apply_anti_stagnation_intervention`.

### Fase 5 — Observabilidad
- Arreglar `_seed_archetypes` para loguear `detect_archetype` real post-consolidación (bug 2.2).
- **F5**: guardar arquetipo detectado de cada mazo en `save_population_arrays`, `save_hall_of_fame_data`, `save_final_population`, y en cada entrada de `evolution_history.json`.
- **F6**: añadir métrica de entropía de Shannon arquetípica en `calculate_diversity` o en `update_statistics`.
- Corregir `update_statistics` para reportar mutación **efectiva**, no `self.mutation_rate`.

### Fase 6 — Consolidación y robustez (opcional)
- **S5**: consolidar funciones de guardado a 3 (estado-generación, estado-final, gráficos).
- Reemplazar `input()` del checkpoint por flag CLI (`--resume` / `--fresh`) para no bloquear en servidor.
- Mejorar `calculate_diversity` para considerar counts, no sólo presencia binaria.

---

## 7. CRITERIOS DE ACEPTACIÓN TRAS LAS FASES

Tras aplicar Fase 1-5, la siguiente corrida Gen 0 → Gen 1 debería cumplir:

- **Clones exactos Gen 0 → Gen 1 ≤ 25 %** (actual: 77.5 %, 31/40).
- **Distribución arquetípica Gen 1** preservada dentro del ±15 % de Gen 0.
- **Entropía de Shannon arquetípica (F6) ≥ 1.3** (máximo teórico 1.58).
- **Diversidad** (métrica actual) crece o se mantiene entre Gen 0 y Gen 1.
- **Fitness promedio** no empeora más del 10 % en Gen 1.
- **`evolution_history.json`** contiene arquetipo detectado por mazo, sin necesidad de scripts externos.

Si se cumple, relanzar la corrida nocturna completa con 30 generaciones.

---

## 8. OBJETIVO DEL ALGORITMO TRAS LA REPARACIÓN

Este apartado fija la narrativa del TFG después de aplicar las 6 fases. El algoritmo deja de ser un GA genérico de "encontrar el mazo más fuerte" y pasa a ser algo conceptualmente distinto.

### 8.1. El giro de objetivo

**Antes (filosofía inicial):**
> *"Encontrar, mediante un GA, el mejor mazo monolítico de MTG según win_rate contra otros candidatos."*

**Después (filosofía actual completa):**
> *"Co-evolucionar un meta estable de tres arquetipos (aggro, midrange, control) en paralelo, donde cada arquetipo desarrolla sus propias mejores listas respetando sus restricciones estructurales y manteniendo un ecosistema diverso."*

Ya no se busca *un* campeón, se busca **un meta-juego en miniatura**: 3 soluciones parejas y competitivas entre sí, análogas a los Tier-1 del meta real.

### 8.2. Pipeline resultante

```
Gen 0 ──────────────────────────────────────────┐
 │ _seed_archetypes (cuotas 1/3 + consolidación)│
 ↓                                               │
 40 mazos etiquetados ~14 agg / 13 mid / 13 ctrl │
 │                                               │
 ↓                                               │
Swiss Tournament (k=8, n=2) — matchups cruzados │
 │                                               │
 ↓                                               │
Fitness arquetipo-aware (6 componentes)          │
 = α·win_rate + β·(mana_curve_arq + balance_arq │
                   + coherencia_arq + …)         │
 │                                               │
 ↓                                               │
update_hall_of_fame ── 4 aggro + 4 mid + 4 ctrl ←─ cuota
 │                                               │
 ↓                                               │
Nueva generación:                                │
  • 9 élites (3 por arquetipo desde HoF)         │
  • 31 hijos:                                    │
    - Selección por torneo                       │
    - crossover_archetype (categoría-consciente) │
    - mutate_archetype_aware (sesgo afinidad)    │
    - adjust_deck_size + consolidate_singletons  │
      (descendientes libres: arq. detectado)     │
 │                                               │
 ↓                                               │
 Métricas: entropía Shannon arquetípica,         │
 diversidad card-level, distribución arq.        │
 │                                               │
 └──── repeat hasta Gen N ────────────────────────┘
```

### 8.3. Qué se puede medir y demostrar

Con F5 + F6 (observabilidad) ya no se mide sólo "¿sube el fitness?", sino:

1. **Estabilidad del ecosistema**: entropía Shannon por generación → ¿se mantienen los 3 arquetipos o colapsa?
2. **Madurez por arquetipo**: mejor fitness dentro de cada cuota del HoF → ¿aggro alcanza antes su techo que control?
3. **Deriva arquetípica**: cuántos mazos cambian de arquetipo entre padre e hijo → ¿la filosofía C (descendientes libres) produce migración natural o se respetan linajes?
4. **Matchups cruzados**: Swiss de mazos de distinto arquetipo → tabla piedra-papel-tijera emergente.
5. **Convergencia intra-arquetipo**: ¿los ~13 aggro convergen a la misma lista o exploran variantes?

### 8.4. Valor académico — framing para la memoria

Lo que antes era *"aplicar GAs a optimización de mazos"* (poco novedoso) pasa a ser:

> **"Preservación de diversidad de nichos en algoritmos genéticos aplicada a la co-evolución de arquetipos en juegos de cartas coleccionables"**

Marcos teóricos que encajan y pueden citarse:
- **Niching methods / speciation** en GAs (Mahfoud 1995; Goldberg–Richardson sharing).
- **Novelty search** (Lehman & Stanley).
- **Co-evolución competitiva** (Rosin & Belew; Hillis).
- **Quality-Diversity algorithms** (MAP-Elites, Mouret & Clune): **el HoF con cuota 4+4+4 es literalmente un MAP-Elites simplificado sobre el eje "arquetipo"**. Éste es el framing más fuerte y el que mejor posiciona el TFG.

### 8.5. Limitaciones honestas que conviene reconocer

Para no sobrevender el trabajo en la memoria:

1. **Pool fijo de cartas** — no se inventan cartas nuevas; la exploración está acotada al catálogo Standard.
2. **Fitness depende de Forge** — si Forge simula mal una interacción, el fitness miente.
3. **Swiss con k=8 tiene varianza** — una muestra pequeña de matchups puede premiar mazos afortunados.
4. **3 arquetipos es una simplificación** — el meta real tiene sub-arquetipos (aggro-boros vs aggro-mono-red) que quedan amalgamados.
5. **No hay sideboard** — partidas únicas, no BO3, por lo que estrategias transformacionales quedan fuera.

### 8.6. Frase síntesis

> *"Un algoritmo Quality-Diversity para MTG que evoluciona en paralelo tres arquetipos competitivos preservándolos como nichos separados, y que mide la salud del ecosistema con entropía arquetípica además del fitness."*

Ese es el "norte" conceptual del algoritmo tras las 6 fases.
