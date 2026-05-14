"""Test corto Fase 7: valida que el gauntlet tier-1 aporta gradiente real.

Objetivo: confirmar que el winrate vs gauntlet no es uniforme (0 ni 1 para todos)
en gens iniciales. Con 5 anchors diversos en arquetipo, debería haber variación
ya en gen 0. Si todos los candidatos sacan 0/5, activamos plan B (métricas
parciales). Coste estimado: ~100 min en portátil con 4 workers.
"""
import time
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

config = {
    'population_file': "mtg_decks/test_population.json",
    'catalog_path': "mtg_data/card_catalog.json",
    'indices_path': "mtg_data/card_indices.json",
    'output_dir': "prueba_gauntlet_test",
    'forge_jar_path': "./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
    # === Tamaños del test ===
    'max_generations': 3,
    'population_size': 15,
    # === Ajustados a pop=15 ===
    'elite_size': 3,                   # 20% de pop (default 9 sería >50%)
    'tournament_size': 3,              # default 5 sería 33% — bajar
    'k_rounds': 6,                     # ceil(log2(15))+2 = 6 (default 8)
    'n_games_per_match': 2,
    'mutation_rate': 0.6,
    'crossover_rate': 0.30,
    # === Paralelismo y timeout ===
    'max_workers': 4,
    'parallel_batch_size': 12,
    'base_timeout': 120,
    'save_forge_outputs': False,
    'log_level': 'INFO',
    # === Gauntlet tier-1 (Fase 7) ===
    'gauntlet_path': 'gauntlet/tier1',
    'gauntlet_gamma_min': 0.05,
    'gauntlet_gamma_max': 0.30,
}

print("=" * 70)
print("TEST GAUNTLET — Fase 7 validación de gradiente")
print(f"  pop={config['population_size']} × gens={config['max_generations']}")
print(f"  anchors en {config['gauntlet_path']}, γ {config['gauntlet_gamma_min']} → {config['gauntlet_gamma_max']}")
print("=" * 70)

t0 = time.time()
ga = MTGGeneticAlgorithm(**config)
best = ga.evolve(resume_from_checkpoint=False)
elapsed = time.time() - t0

print(f"\n[Tiempo total] {elapsed:.1f}s ({elapsed/60:.1f} min)")

# Reporte rápido del gauntlet
wr = getattr(ga, 'last_gauntlet_winrates', None)
if wr:
    n_zeros = sum(1 for w in wr if w == 0.0)
    n_perfect = sum(1 for w in wr if w == 1.0)
    print(f"\n[Gauntlet — última gen] winrates por mazo:")
    for i, w in enumerate(wr):
        print(f"  D{i:2d}: {w:.2f} ({int(round(w * len(ga.gauntlet_decks)))}/{len(ga.gauntlet_decks)})")
    print(f"\n  → {n_zeros}/{len(wr)} con winrate=0, {n_perfect}/{len(wr)} con winrate=1")
    if n_zeros == len(wr):
        print("  ⚠️  GRADIENTE PLANO: todos pierden contra todos los anchors. Activar plan B.")
    else:
        print("  ✓ Gradiente real: hay variación entre candidatos.")

print(f"\n🏆 Mejor: {best['name']} ({', '.join(best.get('colors', []))})")
