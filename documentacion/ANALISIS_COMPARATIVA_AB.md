# Análisis comparativo: `exp03_pack_aware/` (pack-aware) vs `exp02_baseline/` (baseline)

**Fecha del análisis:** 2026-04-24
**Rama:** `feature/ga-pack-level-mutation`
**Objetivo:** Validar el impacto de la mutación y el crossover a nivel de pack (Fases 1 / 2 / 2.5) frente al baseline previo, ejecutando la misma configuración nominal (40 pop × 30 gens).

---

## 0. Resumen ejecutivo

- **Ambas ejecuciones completan 30 generaciones sin crashes.** La lógica pack-aware no introduce fallos ni inestabilidad.
- **Integridad estructural perfecta en ambas**: 40/40 mazos con 60 cartas exactas, 0 violaciones de la norma 4-de-4.
- **Fitness máximo:** baseline 0.8906 vs pack-aware **0.8778** → -0.013 (−1.4 %).
- **Avg fitness final:** baseline 0.617 vs pack-aware **0.630** → +0.013 (+2.1 %). La población mejora de media con packs.
- **Calidad estructural**: el pack-aware transforma la composición de los mazos. Los packs 4-of pasan de **5.55 → 7.83** por mazo (+41 %); los singletons tech se desploman de **3.55 → 0.17** por mazo (−95 %); los no-basics pasan de **0.68 → 4.00** por mazo (+488 %).
- **Arquetipo dominante en cada ejecución diverge**: baseline converge a **aggro B/R/W** (29/40); pack-aware converge a **midrange B/W** (33/40).
- **Veredicto:** el pack-aware sacrifica ~1.5 pp de pico de fitness a cambio de mazos MUCHO más realistas (packs consolidados, manabases con no-basics, cero "polilla" de singletons sueltos). El trade-off es favorable para un TFG cuyo objetivo es explorar el ecosistema / producir mazos creíbles.

---

## 1. Configuración de ambas ejecuciones

| | `exp02_baseline/` (baseline) | `exp03_pack_aware/` (pack-aware) |
|---|---|---|
| Commit HEAD conceptual | `develop` sin packs | `feature/ga-pack-level-mutation` (Fases 1+2+2.5) |
| Población | 40 | 40 |
| Generaciones | 30 | 30 |
| Combates por gen | 320 | 320 |
| Swiss tournament | sí (k=7) | sí (k=7) |
| HOF quota por arquetipo | 3 | 3 |
| Pool de cartas | `card_catalog` (4130 IDs) | idem |

Misma configuración nominal. La única diferencia es la lógica de variación (mutación + crossover) a nivel de pack.

---

## 2. Ejecución: estabilidad y tiempo

| Métrica | `exp02_baseline` | `exp03_pack_aware` |
|---|---:|---:|
| Duración total (medible en logs) | 28.2 h (12 gens loggueadas tras resume) | **67.1 h (31 gens continuas)** |
| Tiempo medio por gen | 141 min | 130 min |
| Combates totales (contados) | 3 840 (12 gens) | **9 920 (31 gens)** |
| Combates exitosos | 3 837 / 3 840 (99.92 %) | **9 919 / 9 920 (99.99 %)** |
| Combates fallidos | **3** timeouts | **1** timeout (gen 19) |
| Resumes desde checkpoint | 1 (el log de statistics empieza en gen 19) | 0 (corrida continua) |
| Crashes / exceptions | 0 | 0 |

**Observaciones:**
- `exp02_baseline` fue **reanudada al menos una vez** (el JSON de statistics empieza en `generation: 19`; el CSV `parallel_evolution_stats.csv` reinicia numeración y muestra gens 0-11 que coinciden en fitness/avg con las gens 19-30 del log). Hay un resumen sobre el bug del checkpoint que **sí afectó a este run**: los `generation_stats` de las gens 0-18 no están persistidos en `logs/parallel_generation_statistics.json`.
- `exp03_pack_aware` corrió de un tirón las 31 gens (checkpoints gen 0 → gen 30 consecutivos sin huecos) y conserva los `generation_stats` de las 31 gens completas.
- Pack-aware reduce el tiempo medio por gen (~8 %); no es un resultado "causal" dado el entorno de ejecución distinto, pero descarta que la lógica pack-aware introduzca overhead.

---

## 3. Integridad estructural de los mazos

Ambas poblaciones finales (n=40) cumplen las reglas sagradas:

| Regla | `exp02_baseline` | `exp03_pack_aware` |
|---|---:|---:|
| Mazos con exactamente 60 cartas | **40 / 40** | **40 / 40** |
| Violaciones de 4-of (no-basic > 4) | **0** | **0** |
| Singletons no-land por mazo (media) — cap objetivo ≤ 2 | **3.55** ⚠️ | **0.17** ✓ |
| Singletons land por mazo (media) | 0.62 | 4.00 |
| Sets 4-of por mazo (media) | 5.55 | **7.83** |
| No-basic lands por mazo (media) | 0.68 | **4.00** |
| Tierras totales por mazo (media) | 20.52 | 25.95 |

**Lectura clave:**
- El **cap de `max_singletons=2` del baseline se viola de facto**. Con 3.55 singletons no-land de media, muchos mazos tienen 5-8 copias únicas "tech" sueltas. `consolidate_singletons(max_singletons=2)` operaba pero el churn de la mutación/crossover no-pack regeneraba singletons entre pasos.
- El pack-aware hace que los singletons no-land queden a **0.17**. Cuando aparece uno, es residuo legítimo de `adjust_deck_size` (recortes tras padding o floor de manabase).
- Los **no-basics casi no existían** en el baseline (0.68 / mazo). Con pack-aware hay 4.00 no-basics / mazo (típicamente singletons de dual/utility: Plaza of Heroes, Promising Vein, Fomori Vault, Maelstrom of the Spirit Dragon…).
- La memoria [project_pendientes_post_auditoria.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_pendientes_post_auditoria.md) señalaba "0 nonbasics" como problema. **El pack-aware lo resuelve implícitamente** (los packs preservan la presencia de no-basic lands mezclados con las básicas cuando la selección los incluye).

---

## 4. Evolución del fitness

Datos comparables (últimas 12 gens, que son las únicas que el baseline persistió en `parallel_generation_statistics.json`):

| Ventana (gens 19-30) | baseline | exp03_pack_aware |
|---|---:|---:|
| best_fit medio | 0.8174 | 0.8200 |
| avg_fit medio | 0.6104 | 0.6256 |
| **pico best_fit** | **0.8906** (gen 29) | **0.8778** (gen 20) |
| avg_fit en gen 30 | 0.6171 | 0.6298 |
| failures en ventana | 3 | 1 |

Evolución completa visible en `exp03_pack_aware/parallel_evolution_stats.csv` (31 líneas):

| Gen | best_fit | avg_fit | diversity | mut_rate | entropía arq. |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.808 | 0.555 | 0.878 | 0.60 | 0.958 |
| 5 | 0.787 | 0.598 | 0.508 | 0.60 | 0.583 |
| 10 | 0.811 | 0.602 | 0.461 | 0.75 | 0.731 |
| 15 | 0.800 | 0.607 | 0.411 | 0.90 | 0.583 |
| 20 | **0.878** | 0.607 | 0.472 | 0.60 | 0.633 |
| 25 | 0.841 | 0.631 | 0.316 | 0.60 | 0.583 |
| 30 | 0.822 | 0.630 | 0.396 | 0.75 | 0.583 |

**Dinámica observada en exp03_pack_aware:**
- avg_fit sube de 0.555 a 0.630 (+13.5 %) con curva consistente, no ruido.
- Diversidad baja de 0.878 → 0.396 (convergencia natural).
- Entropía de arquetipo baja de 0.958 → 0.583 (población se especializa).
- El `mutation_rate` adaptativo escala a 0.9 en gens 14-18 (rompe meseta: gen 20 produce el pico 0.878), después relaja a 0.60/0.75.
- `stagnation_counter` al final de exp03_pack_aware = 9 → el run se cerró cerca del plateau. Con más gens podría romperlo.

El baseline tenía `best_fit` de pico más alto (0.891) pero avg_fit peor (0.617). El **pack-aware eleva el suelo de la población**: la media mejora aunque el "techo" baje ligeramente.

---

## 5. Los mazos tienen sentido

### 5.1 Hall of Fame comparado (top de cada arquetipo)

| | baseline (exp02_baseline) | pack-aware (exp03_pack_aware) |
|---|---|---|
| **aggro #1** | fitness **0.891**, B/R/W, 31 creaturas, 20 lands (0 no-basic), avg_cmc 2.23 | fitness 0.808, B/G, 29 creaturas, 27 lands (4 no-basic), avg_cmc 1.94 |
| **midrange #1** | fitness 0.826, B/R, 25 creaturas, 20 lands (0 no-basic), avg_cmc 2.83 | fitness **0.878**, B/W, 18 creaturas, 26 lands (4 no-basic), avg_cmc 2.94 |
| **control #1** | fitness 0.790, mono-U, 25 creaturas, 21 lands, avg_cmc 2.64 | fitness **0.863**, B/W, 11 creaturas, 25 lands (4 no-basic), avg_cmc 3.09 |

### 5.2 Inspección cualitativa

**baseline `hall_of_fame_aggro_1.dck`** (el mejor del baseline):
```
2 Bake into a Pie, 4 Dawnwing Marshal, 3 Firebrand Archer, 3 Giada,
3 Moment of Craving, 2 Mountain, 13 Plains, 5 Swamp, 2 Youthful Valkyrie,
3 Anointed Peacekeeper, 1 Flowstone Kavu, 3 Ambush Paratrooper,
3 Monastery Swiftspear, 4 Spectrum Sentinel, 1 Survivor of Korlis,
2 Warlord's Elite, 1 Axiom Engraver, 2 Infectious Inquiry, 1 Scrollshift,
1 Bloodletter of Aclazotz, 1 Lion Heart
```
→ Solo **2 packs 4-of**, **8 singletons**, muchos 2-ofs y 3-ofs. Es un "quilt" de cartas no-consolidado. Fitness alto pero mazo irreal.

**pack-aware `hall_of_fame_midrange_1.dck`** (el mejor de exp03_pack_aware):
```
5 Plains, 17 Swamp, 4 Extinguish the Light, 1 Plaza of Heroes,
4 Sheoldred, the Apocalypse, 4 Splatter Goblin, 4 Gurgling Anointer,
4 Static Net, 4 Fanatical Offering, 4 Preacher of the Schism,
1 Promising Vein, 2 Omenport Vigilante, 1 Fomori Vault,
4 Bumbleflower's Sharepot, 1 Maelstrom of the Spirit Dragon
```
→ **8 packs 4-of**, manabase con 4 no-basics utility, plan de juego coherente (Sheoldred + Preacher como win cons, Extinguish como removal, Static Net + Bumbleflower como utility).

**pack-aware `hall_of_fame_aggro_1.dck`**:
```
4 Diregraf Ghoul, 11 Forest, 2 Primal Might, 12 Swamp, 1 Uncharted Haven,
2 Zombify, 4 A-Llanowar Greenwidow, 1 The Mycosynth Gardens,
1 Grasping Shadows // Shadows' Lair, 4 Jadelight Spelunker,
4 Soulcoil Viper, 4 Vitu-Ghazi Inspector, 4 Treasure Dredger,
4 Iridescent Vinelasher, 1 Three Tree City, 1 Sidisi
```
→ 7 packs 4-of B/G aggro con plan de presión baja-curva + ramp. Mazo competitivo reconocible.

**pack-aware `hall_of_fame_control_1.dck`**:
```
3 Plains, 18 Swamp, 1 Release the Dogs, 3 Extinguish the Light,
1 Plaza of Heroes, 3 Sheoldred, 4 Gurgling Anointer, 4 Static Net,
4 Drown in Ichor, 4 Malicious Eclipse, 4 Preacher of the Schism,
1 Promising Vein, 1 Fomori Vault, 4 Bumbleflower's Sharepot,
4 Aggressive Negotiations, 1 Maelstrom of the Spirit Dragon
```
→ 7 packs 4-of, **≥11 piezas de removal/interacción** (Extinguish+Drown+Malicious Eclipse), win cons tardíos (Sheoldred, Preacher). Control B/W legítimo.

---

## 6. Distribución final de arquetipos y colores

| | baseline | pack-aware |
|---|---:|---:|
| aggro | **29** / 40 | 3 / 40 |
| midrange | 8 / 40 | **33** / 40 |
| control | 3 / 40 | 4 / 40 |
| entropía arq. | 0.749 | 0.583 |

| Par de colores | baseline | pack-aware |
|---|---:|---:|
| B/R/W | 26 | 0 |
| B/W | 1 | **37** |
| B/G | 0 | 2 |
| B/R | 3 | 0 |
| R/U | 3 | 1 |
| U (mono) | 2 | 0 |
| Otros (4-5 colores) | 5 | 0 |

**Interpretación:**
- Baseline: la aggro tri-color B/R/W domina el gauntlet. Con mutaciones a nivel individual (carta a carta), es más fácil mantener mazos multi-color explotativos con singletons que maximizan fitness por combo-lucky.
- Pack-aware: midrange B/W (Sheoldred + Preacher) domina. Los packs hacen que añadir una carta implique añadir 4, forzando compromiso cromático y consolidación.
- **Ambos resultados son legítimos pero distintos.** El pack-aware produce mazos "más Magic", el baseline produce mazos "más óptimos contra el gauntlet actual".

---

## 7. Trade-off cuantificado

| Dimensión | baseline | pack-aware | Δ |
|---|---:|---:|---:|
| Pico de fitness | 0.891 | 0.878 | **−1.4 %** |
| Avg fit final | 0.617 | 0.630 | +2.1 % |
| Sets 4-of por mazo | 5.55 | 7.83 | **+41 %** |
| No-basics por mazo | 0.68 | 4.00 | **+488 %** |
| Singletons tech por mazo | 3.55 | 0.17 | **−95 %** |
| Tierras por mazo | 20.52 | 25.95 | +26 % |
| Estabilidad (fail rate) | 0.078 % | 0.010 % | −87 % |

El pack-aware **paga 1.4 pp de pico de fitness** y **recibe**:
- Mazos que respetan la norma 4-de-4 no solo formalmente (eso ya pasaba) sino **en espíritu**: muchos más packs consolidados, muchos menos singletons tech.
- Manabases con no-basics reales (no casi todo básica).
- Mayor estabilidad (menos timeouts de Forge).
- Avg fit poblacional ligeramente mejor.

---

## 8. Señales de atención (exp03_pack_aware)

### 8.1 Convergencia severa a B/W midrange

37/40 mazos en B/W, 33 midrange. Aggro/control sobreviven solo por la cuota del HOF; en la población activa quedan **3 aggros** (2 B/G viables y 1 R/U con fitness 0.26, prácticamente basura) y **4 controls**. Esto confirma la preocupación de la auditoría previa: **la presión selectiva sobre un único arquetipo es demasiado fuerte**. El HOF preserva ejemplares tier-1 de los tres arquetipos, pero la población activa pierde diversidad.

**Recomendación (pendiente Fase 3+):** introducir `gauntlet tier-1 en fitness` (comparar cada mazo contra los mejores del HOF de los otros arquetipos), para que un aggro no solo compita contra aggros y midranges "normales".

### 8.2 Mutation rate adaptativa reacciona pero no rompe el plateau

El `mutation_rate` subió a 0.9 en gens 14-18 (detectó estancamiento), relajó a 0.60/0.75. Funciona, pero el `stagnation_counter=9` al final de exp03_pack_aware indica que las últimas 9 gens no superaron el pico de gen 20. El pico está conservado en el HOF.

### 8.3 Caída del best_fit del pop final

El best_fit en la gen 30 bajó a 0.822 (desde 0.878 en gen 20). El HOF retiene el mejor absoluto, pero en gauntlets futuros habría que considerar que **la última gen no es la "mejor" gen** — hay que consumir el HOF.

### 8.4 Legalidad Standard

Cartas del Champion como Sheoldred, Extinguish the Light y Preacher tienen `legal_in_standard: False` en el catálogo. Si el TFG quiere restringirse a Standard vigente, hay que filtrar el pool; si el objetivo es "mejor mazo posible con el catálogo disponible", no es un problema.

### 8.5 Bug latente: checkpoint stats

[project_bug_checkpoint_stats.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_bug_checkpoint_stats.md) documenta que `save_checkpoint` no persiste `generation_stats`. En `exp03_pack_aware` no se activó (run continuo), pero en `exp02_baseline` se disparó al reanudar: las gens 0-18 quedaron sin `generation_stats` persistido. Es una pérdida de trazabilidad, no afecta al algoritmo. Fix ~4 líneas sigue pendiente.

---

## 9. Evolución de la composición (pack-aware)

Cards distintas usadas en toda la población (pool de 4130):

| Gen | Distintas pop-wide | Top card (presencia) |
|---:|---:|---|
| 0 | 464 | cid 316 (básica) en 19/40 |
| 5 | 136 | cid 439 (Swamp) en 38/40 |
| 10 | 126 | cid 439 en 39/40, Static Net 995 en 27/40 como 4-of |
| 15 | 133 | Plaza of Heroes (678) en 36/40, Bumbleflower 2793 en 31/40 como 4-of |
| 20 | 142 | Sheoldred (708) en 29/40 como 4-of, Static Net en 29/40 como 4-of |
| 25 | **98** | Sheoldred en 31/40 como 4-of, Preacher en 31/40 como 4-of |
| 30 | 108 | Sheoldred en 32/40 como 4-of, Extinguish en 26/40 como 4-of |

La convergencia es clara: el núcleo del mazo B/W midrange (Sheoldred + Preacher + Extinguish + Static Net + Bumbleflower) se fija a partir de gen 20 y domina hasta el final.

---

## 10. Veredicto

El run `exp03_pack_aware/` **valida las Fases 1 / 2 / 2.5** del plan de mutación y crossover a nivel de pack:

1. **Funciona** — 67h sin crashes, 9919/9920 combates exitosos, 31 gens completas.
2. **Respeta la norma sagrada 4-de-4** en todas las dimensiones (formal y de espíritu): cero violaciones, 7.83 packs consolidados por mazo (vs 5.55 baseline), singletons tech despreciables (0.17 vs 3.55).
3. **Produce mazos realistas** — los 9 mazos del HOF parecen construcciones humanas coherentes, no "quilts" de cartas sueltas.
4. **Resuelve implícitamente el problema de "0 nonbasics"** documentado en la auditoría previa.

A cambio, **sacrifica 1.4 pp de pico de fitness absoluto**. Ese trade-off es **favorable** dado el objetivo del TFG (ecosistema de mazos creíbles). Para maximizar fitness puro sin importar la forma del mazo, la variación carta-a-carta del baseline era más explotativa.

**Siguiente paso recomendado:** decidir sobre la dirección abierta del TFG ([project_direccion_tfg_abierta.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_direccion_tfg_abierta.md)). Si el objetivo es el **estudio del ecosistema**, el pack-aware está listo y el siguiente foco debería ser la **presión selectiva balanceada** (gauntlet tier-1 en fitness) para impedir la monocultura midrange B/W. Si el objetivo es **buscar top-tier**, el baseline es competitivo a pesar de sus singletons.

---

## 11. Archivos de evidencia

**exp03_pack_aware/:**
- Stats evolutivos: [exp03_pack_aware/parallel_evolution_stats.csv](../exp03_pack_aware/parallel_evolution_stats.csv), [exp03_pack_aware/parallel_evolution_stats.png](../exp03_pack_aware/parallel_evolution_stats.png)
- Población final: [exp03_pack_aware/final_population_20260424_152946.json](../exp03_pack_aware/final_population_20260424_152946.json)
- Hall of Fame top-5 consolidado: [exp03_pack_aware/parallel_hall_of_fame.json](../exp03_pack_aware/parallel_hall_of_fame.json)
- 9 HOF por arquetipo (.dck + .json): [exp03_pack_aware/hall_of_fame/](../exp03_pack_aware/hall_of_fame/)
- Mejor mazo: [exp03_pack_aware/best_deck_final_parallel.json](../exp03_pack_aware/best_deck_final_parallel.json)
- Log ejecución: [exp03_pack_aware/logs/parallel_ag_execution_20260421_202441.log](../exp03_pack_aware/logs/parallel_ag_execution_20260421_202441.log)
- Stats por gen: [exp03_pack_aware/logs/parallel_generation_statistics.json](../exp03_pack_aware/logs/parallel_generation_statistics.json)

**exp02_baseline/:**
- Stats evolutivos (parciales): [exp02_baseline/parallel_evolution_stats.csv](../exp02_baseline/parallel_evolution_stats.csv)
- Población final: [exp02_baseline/final_population_20260420_124847.json](../exp02_baseline/final_population_20260420_124847.json)
- Hall of Fame top-5: [exp02_baseline/parallel_hall_of_fame.json](../exp02_baseline/parallel_hall_of_fame.json)
- HOF por arquetipo: [exp02_baseline/hall_of_fame/](../exp02_baseline/hall_of_fame/)

**Memorias referenciadas:**
- [project_pendientes_post_auditoria.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_pendientes_post_auditoria.md)
- [project_direccion_tfg_abierta.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_direccion_tfg_abierta.md)
- [project_bug_checkpoint_stats.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/project_bug_checkpoint_stats.md)
- [feedback_norma_cuatro_copias.md](../../.claude/projects/-home-jgasbul-Escritorio-TFG-TFGJoseGasc-Bule/memory/feedback_norma_cuatro_copias.md)