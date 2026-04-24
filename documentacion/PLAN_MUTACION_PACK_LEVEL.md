# Plan: Mutación y crossover a nivel de "pack" (4-of)

**Fecha:** 2026-04-20
**Base:** commit `4636694e` (norma 4-of sagrada + manabase proporcional + piso arquetípico).
**Motivación:** La directiva "norma de las 4 copias es sagrada" (ver `feedback_norma_cuatro_copias.md` en memoria) debe cumplirse no sólo en `adjust_deck_size`, sino también en los operadores genéticos. Actualmente los operadores tocan **copias individuales**, lo que introduce singletons/duplets como ruido evolutivo.

---

## 1. Problema

Los operadores de mutación actuales (ver [algoritmo_genetico_mtg.py:1051-1256](../algoritmo_genetico_mtg.py#L1051-L1256)) operan en **incrementos de 1 copia**:

```python
# mutate_swap
mutated[pos1] -= 1
mutated[pos2] += 1

# mutate_add_remove
mutated[pos] += 1  # o -= 1
```

Cada operación modifica 1 slot del mazo. Con `num_changes ∈ [3, 8]`, una mutación típica afecta 3-8 copias sueltas. Consecuencias:

1. **Introduce singletons/duplets sistemáticamente** — añadir 1 copia de una carta nueva crea un singleton.
2. **Saltos pequeños en el espacio de mazos** — cambiar 3-8 copias sobre 60 cartas es un <10% de delta estructural.
3. **Contradice la directiva 4-of** — el operador trabaja contra la norma que luego `consolidate_singletons` tiene que limpiar.
4. **Exploración débil** — para probar "¿y si este mazo llevara 4× Lightning Bolt?" hacen falta 4 mutaciones consecutivas que toquen la misma carta; estadísticamente improbable.

---

## 2. Decisión

**Todos los operadores de mutación y crossover pasan a trabajar en packs (unidades de 4 copias).**

Una mutación es una **decisión de inclusión/exclusión de carta**, no de ajuste de copias. El número de copias de una carta en un mazo es binario por defecto: **4 o 0**. Las excepciones (1-2 copias como tech card) las administra exclusivamente `consolidate_singletons(max_singletons=2)`, que se ejecuta dentro de `adjust_deck_size`.

### Lectura TFG

Este cambio se alinea con cómo un jugador humano construye un mazo de constructed: "meto o no meto esta carta; si la meto, van 4 copias". El AG actual toma decisiones al nivel de "1 copia sí/no", que es un nivel de granularidad que **ningún humano usa** y que no existe en el espacio de mazos competitivos de MTG.

---

## 3. Diseño de los operadores

### 3.0 Principio de diseño: todos los operadores son self-balancing

Tras debate (2026-04-20), se descarta tener `pack_add` y `pack_remove` como operadores atómicos. Motivo: cada uno produciría un desbalance de ±N cartas que `adjust_deck_size` resolvería cortando/añadiendo **aleatoriamente**, rompiendo packs 4-of existentes y generando el mismo ruido que estamos intentando eliminar.

**Regla general:** todo operador pack **elimina y añade packs en la misma operación** (siempre net 0 cartas). La limpieza residual de tierras/colores la sigue haciendo `adjust_deck_size` (PASO 2-4), que no altera counts de no-tierras.

### 3.1 Operadores pack (lista definitiva)

Siete operadores pack-level. Cada uno es una **sustitución atómica (swap) con sesgo específico**.

#### 1. `mutate_pack_swap` (genérico, exploratorio)
- Remove: card_id no-tierra con `count > 0`, ponderado por inversa de afinidad arquetípica.
- Add: card_id con `count == 0`, color-compatible, ponderado por afinidad.
- Efecto: swap genérico, base del dispatcher.

#### 2. `mutate_pack_promote_compensated` (conservador, norma 4-of)
- Identifica un pack parcial (card_id con `0 < count < 4`) de alta afinidad.
- Lo completa a 4 (añade `4 − count` copias).
- Compensa eliminando `4 − count` copias de la carta de **peor afinidad** del mazo.
- Efecto: refuerza la norma 4-of sin cambiar identidad estructural.

#### 3. `mutate_pack_curve_shift` (MTG: curva arquetípica)
- Calcula `avg_cmc` actual y lo compara con `ARCHETYPE_COHERENCE_IDEALS[archetype]['avg_cmc']`.
- Si `avg_cmc > ideal_high`: remove pack con CMC alto, add pack con CMC bajo (o viceversa).
- Si está en rango: fallback a `pack_swap`.
- Efecto: empuja la curva de maná hacia el ideal del arquetipo detectado.

#### 4. `mutate_pack_removal_injection` (MTG: respuestas)
- Cuenta cartas del mazo cuyo `oracle_text` coincide con patrones de removal (`destroy target`, `exile target`, `deals \d+ damage to`, `sacrifices a`, `target creature gets -`).
- Target de removal por arquetipo: aggro 2-4, midrange 4-6, control 6-10.
- Si está por debajo: swap no-removal por removal del color del mazo.
- Efecto: imita la decisión humana de "necesito más respuestas".

#### 5. `mutate_pack_splash_prune` (MTG: consolida manabase)
- Calcula demanda de pips por color (como `rebalance_manabase`).
- Si el mazo es 3+ colores y uno tiene demanda ≤ 2 (splash marginal): identifica el color splash.
- Remove: card del color splash. Add: card del color mayoritario.
- Efecto: reduce dispersión de manabase a cambio de consistencia.

#### 6. `mutate_pack_threat_upgrade` (MTG: subir tamaño de criaturas)
- Solo aplica para aggro/midrange.
- Para cada criatura del mazo con `power`/`toughness` numéricos, busca criaturas **de igual CMC** pero con mayor `power + toughness`.
- Remove: pack de criatura con stats bajos. Add: pack de criatura con stats altos (mismo CMC, color-compatible).
- Efecto: optimiza el paquete de amenazas sin alterar la curva.

#### 7. `mutate_pack_tribal_consolidate` (MTG: sinergia tribal)
- Parsea `type_line` de las criaturas del mazo para extraer subtipos (tras el "—").
- Identifica el subtipo más representado.
- Busca criaturas fuera del mazo con ese subtipo y color compatible.
- Remove: criatura de otro subtipo. Add: criatura del subtipo dominante.
- Efecto: empuja hacia un paquete tribal coherente (goblins, elfos, humanos, etc.).

### 3.2 Número de operaciones por mutación

`num_ops ∈ [1, 3]` operaciones pack por llamada a `mutate()`. Cada op toca ~4-8 slots. Total ≤12-24 slots = cambio estructural significativo sin ruido 1-of.

### 3.3 Archetype-aware

Todos los operadores detectan el arquetipo internamente vía `detect_archetype()` y usan `_archetype_card_affinity` para ponderar candidatos. El arquetipo se re-detecta cada op (puede migrar durante la mutación).

### 3.4 Dispatcher

Pesos por régimen evolutivo:

| Régimen | swap | promote | curve | removal | splash | threat | tribal |
|---|---|---|---|---|---|---|---|
| Inicial (gen < 50)            | 25% | 15% | 15% | 10% | 10% | 15% | 10% |
| Avanzado (gen ≥ 50)           | 20% | 20% | 15% | 10% | 10% | 15% | 10% |
| Estancamiento moderado (>5)   | 40% | 10% | 10% | 10% | 10% | 10% | 10% |
| Estancamiento fuerte (>10)    | 50% |  5% | 10% | 10% | 10% | 10% |  5% |

Notas:
- `pack_swap` sube en estancamiento (exploración máxima).
- `pack_promote_compensated` baja en estancamiento (si el mazo está atascado, no es momento de consolidar sino de probar cosas).
- Los operadores MTG-temáticos mantienen pesos estables — su función es sostenida a lo largo de la ejecución.

### 3.5 Fallback

Cada operador MTG-temático comprueba si tiene candidatos viables (mazo ya en rango de curva, sin splash, etc.). Si no los tiene, **cae a `pack_swap` genérico**. Así ningún régimen queda "ciego".

### 3.6 Operadores retirados

Se eliminan del código:
- `mutate_swap`, `mutate_add_remove`, `mutate_categorical`, `mutate_archetype_aware`.

Motivo: todos operaban por copias sueltas y sus funciones quedan subsumidas por los 7 operadores pack.

---

## 4. Crossover

El crossover actual (revisar en `algoritmo_genetico_mtg.py`) también pasa a ser pack-aware: se heredan **packs enteros** de cada padre, no copias sueltas.

Estrategia propuesta: por cada `card_id` presente en al menos uno de los dos padres, decidir probabilísticamente de qué padre heredar el pack entero (50/50, con posible sesgo). El resultado puede superar 60 cartas; `adjust_deck_size` recorta.

Detalle de implementación pendiente hasta leer el crossover actual — puede que ya funcione cercano a esto.

---

## 5. Interacción con `adjust_deck_size`

Todas las mutaciones pack-level terminan llamando a `adjust_deck_size`, que ya:

1. PASO 0.5 consolida singletons (pack-aware via `max_singletons=2`).
2. PASO 1 rellena a 60 priorizando cartas existentes (fix del commit `4636694e`).
3. PASO 2 enforza piso arquetípico de tierras.
4. PASO 3 garantiza ≥1 básica por color.
5. PASO 4 rebalancea manabase proporcional a pips.

**No se necesita cambio en `adjust_deck_size`.** Las mutaciones pack-level rompen menos invariantes que las actuales, así que las correcciones de esta función tendrán menos trabajo.

---

## 6. Plan de implementación

### Fase 1: Mutación pack-level
1. Añadir métodos `mutate_pack_add`, `mutate_pack_remove`, `mutate_pack_swap`, `mutate_pack_promote`.
2. Reescribir `mutate_archetype_aware` para usar packs (add/remove/swap ponderados por afinidad).
3. Actualizar `mutate_adaptive` con los nuevos pesos del dispatcher.
4. Retirar `mutate_swap`, `mutate_add_remove`, `mutate_categorical` (o marcar como deprecated y borrar al siguiente ciclo).

### Fase 2: Crossover pack-level
5. Revisar el crossover actual; si ya opera a nivel de card_id completo, documentar como "ya pack-aware". Si opera por copias sueltas, reescribir para heredar packs.

### Fase 3: Validación
6. Ejecutar `test_gen0_fix.py` tras init — debería dar ≤2 singletons/mazo (techo de `consolidate_singletons`).
7. Ejecutar 1 generación completa con combates. Medir:
   - Singletons/mazo (objetivo: ≤2).
   - Diversidad estructural de la población (objetivo: similar o mayor que ahora).
   - Fitness medio (objetivo: no empeora; idealmente mejora porque los mazos son más coherentes).
8. Si pasa, lanzar run de 10-15 gens para confirmar exploración real.

### Fase 4: Limpieza
9. Actualizar `feedback_norma_cuatro_copias.md` en memoria con la implementación definitiva.
10. Commit por fase (mutación, crossover, validación).

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Saltos pack-level son demasiado grandes y destruyen buenos mazos | `pack_promote` actúa como mutación "conservadora"; la élite protege a los top-k. |
| Exploración se colapsa si el pool de candidatos ADD es pequeño | Sesgo arquetípico con `aff=0,1,2` pesos 1/2/6 — ya mantiene alternativas. |
| Interacción con anti-estancamiento (mut_rate alta) | Los pesos del dispatcher ya suben `pack_add` en estancamiento. |
| Pérdida de cartas útiles "tech" singleton | `consolidate_singletons(max_singletons=2)` sigue dejando 2 slots libres para toolbox. |

---

## 8. Abierto para debate

- ¿Mantener un operador "residual" tipo `mutate_copy_tune` con probabilidad baja (5-10%) para afinar 1-of? Por defecto **NO** (directiva estricta), pero se deja constancia.
- Crossover pack-level exacto depende del código actual — se decide tras revisarlo.
- Eventualmente podría introducirse `mutate_pack_partial_swap` (2-of ↔ 2-of entre dos cartas); por ahora se descarta por ir contra la directiva.