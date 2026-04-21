"""Runner minimal para 1 generación completa con combates Forge.
Valida los operadores pack-level en un ciclo evolutivo real."""
import time
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

config = {
    'population_file': "mtg_decks/test_population.json",
    'catalog_path': "mtg_data/card_catalog.json",
    'indices_path': "mtg_data/card_indices.json",
    'output_dir': "mtg_evolved_decks",
    'forge_jar_path': "./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
    'max_generations': 3,
    'population_size': 8,
    'mutation_rate': 0.6,
    'crossover_rate': 0.30,
    'tournament_size': 3,
    'elite_size': 2,
    'max_workers': 4,
    'parallel_batch_size': 12,
    'base_timeout': 120,
    'log_level': 'INFO',
    'save_forge_outputs': False,
}

print("=" * 70)
print("RUN 1-GEN — Validación operadores pack-level (Fase 1)")
print("=" * 70)
t0 = time.time()

ga = MTGGeneticAlgorithm(**config)

land_ids = set(ga.type_indices.get('lands', []))

def stats_line(i, arr):
    arch = ga.detect_archetype(arr)['archetype']
    lands = sum(int(arr[j]) for j in land_ids)
    unique = int((arr > 0).sum())
    ones_land = sum(1 for cid, cnt in enumerate(arr) if cnt == 1 and cid in land_ids)
    ones_noland = sum(1 for cid, cnt in enumerate(arr) if cnt == 1 and cid not in land_ids)
    duplets = int((arr == 2).sum())
    fours = int((arr == 4).sum())
    return (f"  D{i} [{arch[:4]}]: total={int(arr.sum())}, únicas={unique}, "
            f"lands={lands}, 4of={fours}, 2of={duplets}, "
            f"1of_NL={ones_noland}, 1of_L={ones_land}")

print("\n[Gen 0 sembrada] Estadísticas estructurales iniciales:")
for i, arr in enumerate(ga.population_arrays):
    print(stats_line(i, arr))

best = ga.evolve(resume_from_checkpoint=False)

elapsed = time.time() - t0
print(f"\n[Tiempo total] {elapsed:.1f}s ({elapsed/60:.1f} min)")

print("\n[Gen 1 evolucionada] Estadísticas estructurales finales:")
for i, arr in enumerate(ga.population_arrays):
    print(stats_line(i, arr))

print(f"\n🏆 Mejor: {best['name']} ({', '.join(best['colors'])})")
print(f"   Stats: {best.get('stats', {})}")