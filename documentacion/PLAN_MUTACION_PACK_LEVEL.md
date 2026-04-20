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

### 3.1 Mutación

Cuatro estrategias pack-level que **reemplazan** a las actuales:

#### `mutate_pack_add`
Añade una carta nueva (count=0) al mazo como **4-of directo**.

- Elegir `card_id` con `count == 0` del pool apropiado al mazo (respeta colores).
- `mutated[card_id] = 4`.
- Delta: +4 cartas en el mazo (posteriormente `adjust_deck_size` recorta).

#### `mutate_pack_remove`
Elimina un pack entero.

- Elegir `card_id` con `count > 0` (prioritariamente cartas no-tierra).
- `mutated[card_id] = 0`.
- Delta: -N cartas en el mazo (N ∈ [1, 4]).

#### `mutate_pack_swap`
Sustituye un pack por otro.

- Elegir `card_id_out` con `count > 0` no-tierra.
- Elegir `card_id_in` con `count == 0` del pool apropiado.
- `mutated[card_id_out] = 0`; `mutated[card_id_in] = 4`.
- Delta: -N+4. Sesgado por afinidad arquetípica (ver `_archetype_card_affinity`).

#### `mutate_pack_promote`
Completa un pack parcial a 4-of (refuerza la norma sin cambiar identidad).

- Elegir `card_id` con `0 < count < 4` (prioritariamente el de mayor afinidad con el arquetipo).
- `mutated[card_id] = 4`.
- Delta: +N (N ∈ [1, 3]).

### 3.2 Número de operaciones por mutación

**Cambio de rango:** de `num_changes ∈ [3, 8]` (copias) a `num_changes ∈ [1, 3]` (packs).

Justificación: cada operación pack afecta ~4 slots, así que 1-3 ops = 4-12 slots tocados = delta similar al actual (3-8 copias) pero **sin ruido 1-of**.

### 3.3 Archetype-aware

`mutate_archetype_aware` se mantiene como estrategia top del dispatcher, pero las decisiones ADD/REMOVE pasan a ser pack-level. El sesgo por `_archetype_card_affinity` se mantiene: cartas con `aff=2` son prioritarias para `pack_add`/`pack_promote`; cartas con `aff=0` son prioritarias para `pack_remove`.

### 3.4 Dispatcher

`mutate_adaptive` mantiene los mismos regímenes (estancamiento fuerte / moderado / avanzado / inicial) pero con el nuevo catálogo de estrategias:

| Régimen | pack_swap | pack_add | pack_remove | pack_promote |
|---|---|---|---|---|
| Inicial (gen < 50) | 0.40 | 0.25 | 0.20 | 0.15 |
| Avanzado (gen ≥ 50) | 0.50 | 0.15 | 0.20 | 0.15 |
| Estancamiento moderado (>5) | 0.30 | 0.30 | 0.25 | 0.15 |
| Estancamiento fuerte (>10) | 0.25 | 0.35 | 0.30 | 0.10 |

Notas:
- `pack_swap` es el operador exploratorio natural (cambia identidad manteniendo tamaño aproximado).
- `pack_add` sube en estancamiento (más exploración de cartas nuevas).
- `pack_promote` ayuda a cerrar la consolidación cuando quedan packs parciales de PASO 3/4.

### 3.5 `mutate_categorical`

Se retira. Su función (diversidad por tipo/color) queda cubierta por `pack_add`/`pack_swap` con sesgo arquetípico. Mantenerla pack-aware duplicaría esfuerzo sin aporte claro.

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