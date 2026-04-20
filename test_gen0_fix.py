"""
Test de validación de los fixes:
1. Singletons en padding (norma 4-of)
2. Rebalance de manabase (Frank Karsten aprox)

Solo inicializa el GA (dispara _seed_archetypes → adjust_deck_size con ambos fixes)
y analiza la gen 0 resultante. No ejecuta combates Forge.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter
from algoritmo_genetico_mtg import MTGGeneticAlgorithm


def analyze_deck(deck_array, card_catalog, basic_lands_ids):
    """Analiza un mazo: singletons, manabase y demanda de pips."""
    total = int(deck_array.sum())
    uniques = int((deck_array > 0).sum())

    # Distribución de counts
    count_dist = Counter()
    for count in deck_array:
        if count > 0:
            count_dist[int(count)] += 1

    singletons = count_dist.get(1, 0)
    duplets = count_dist.get(2, 0)
    triplets = count_dist.get(3, 0)
    fours = count_dist.get(4, 0)

    # Demanda de pips por color
    pip_demand = {c: 0 for c in 'WUBRG'}
    for cid, cnt in enumerate(deck_array):
        if cnt == 0:
            continue
        card = card_catalog[cid]
        if card['is_land']:
            continue
        mana_cost = card.get('mana_cost', '') or ''
        for color in 'WUBRG':
            pip_demand[color] += int(cnt) * mana_cost.count('{' + color + '}')

    # Fuentes por color (tierras básicas)
    color_to_basic = {'W': 'Plains', 'U': 'Island', 'B': 'Swamp',
                      'R': 'Mountain', 'G': 'Forest'}
    sources = {}
    for color, name in color_to_basic.items():
        if name in basic_lands_ids:
            sources[color] = int(deck_array[basic_lands_ids[name]])
        else:
            sources[color] = 0

    # Tierras totales
    lands = 0
    for cid, cnt in enumerate(deck_array):
        if cnt > 0 and card_catalog[cid]['is_land']:
            lands += int(cnt)

    # Chequeo de suficiencia (heuristica Karsten)
    needed = {c: (max(3, round(0.45 * d)) if d > 0 else 0)
              for c, d in pip_demand.items()}
    deficits = {c: needed[c] - sources[c] for c in 'WUBRG'
                if needed[c] > sources[c]}

    return {
        'total': total,
        'uniques': uniques,
        'singletons': singletons,
        'duplets': duplets,
        'triplets': triplets,
        'fours': fours,
        'lands': lands,
        'pip_demand': pip_demand,
        'sources': sources,
        'needed': needed,
        'deficits': deficits,
    }


def main():
    print("=" * 70)
    print("TEST GEN 0 — FIX DE SINGLETONS Y MANABASE")
    print("=" * 70)

    config = {
        'population_file': "mtg_decks/test_population.json",
        'catalog_path': "mtg_data/card_catalog.json",
        'indices_path': "mtg_data/card_indices.json",
        'output_dir': "mtg_evolved_decks/test_gen0",
        'forge_jar_path': "./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
        'max_generations': 1,
        'population_size': 8,
        'mutation_rate': 0.6,
        'crossover_rate': 0.30,
        'tournament_size': 3,
        'elite_size': 2,
        'max_workers': 4,
        'parallel_batch_size': 4,
        'base_timeout': 60,
        'log_level': 'WARNING',
        'save_forge_outputs': False,
    }

    print("\n[1] Instanciando GA (dispara _seed_archetypes → adjust_deck_size)...")
    ga = MTGGeneticAlgorithm(**config)

    print(f"\n[2] Gen 0 sembrada: {len(ga.population_arrays)} mazos")
    print()

    # Análisis agregado
    total_singletons = 0
    total_duplets = 0
    total_fours = 0
    total_deficit_colors = 0
    decks_with_deficit = 0

    for i, arr in enumerate(ga.population_arrays):
        info = analyze_deck(arr, ga.card_catalog, ga.basic_lands_ids)
        total_singletons += info['singletons']
        total_duplets += info['duplets']
        total_fours += info['fours']
        if info['deficits']:
            decks_with_deficit += 1
            total_deficit_colors += len(info['deficits'])

        colors_present = {c for c, d in info['pip_demand'].items() if d > 0}
        src_str = '/'.join(f"{c}{info['sources'][c]}" for c in sorted(colors_present))
        ned_str = '/'.join(f"{c}{info['needed'][c]}" for c in sorted(colors_present))
        def_str = ('DEFICIT:' + ','.join(f"{c}-{v}" for c, v in info['deficits'].items())
                   if info['deficits'] else 'OK')
        archetype = ga.detect_archetype(arr)['archetype']
        min_lands = ga.ARCHETYPE_MIN_LANDS.get(archetype, 20)
        land_floor = 'OK' if info['lands'] >= min_lands else f'<{min_lands}!'

        print(f"Deck {i} [{archetype[:4]}]: total={info['total']}, únicas={info['uniques']}, "
              f"lands={info['lands']}({land_floor}), "
              f"4of={info['fours']}, 3of={info['triplets']}, "
              f"2of={info['duplets']}, 1of={info['singletons']} | "
              f"fuentes={src_str} nec={ned_str} {def_str}")

    n = len(ga.population_arrays)
    print()
    print("=" * 70)
    print("AGREGADO:")
    print(f"  Singletons/mazo:     {total_singletons/n:.2f}  (antes del fix: ~6.0)")
    print(f"  Duplets/mazo:        {total_duplets/n:.2f}")
    print(f"  4-of/mazo:           {total_fours/n:.2f}")
    print(f"  Mazos con déficit de manabase: {decks_with_deficit}/{n}")
    print(f"  Colores en déficit (total):    {total_deficit_colors}")
    print("=" * 70)


if __name__ == "__main__":
    main()