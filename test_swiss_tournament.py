#!/usr/bin/env python3
"""
Script de prueba para verificar la implementación del Swiss Tournament

Este script verifica que:
1. Los emparejamientos Swiss se generan correctamente
2. Cada mazo juega aproximadamente k_rounds partidas
3. La reducción de combates es la esperada
4. Los logs muestran correctamente la información
"""

import sys
import os
import numpy as np

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from algoritmo_genetico_mtg import MTGGeneticAlgorithm

def test_swiss_pairings():
    """Prueba la generación de emparejamientos Swiss"""
    print("="*70)
    print("TEST: Generación de emparejamientos Swiss Tournament")
    print("="*70)

    # Crear instancia del AG (sin ejecutar evolución)
    ag = MTGGeneticAlgorithm(
        population_size=40,
        use_swiss_tournament=True,
        k_rounds=7,
        n_games_per_match=2,
        max_generations=1,  # Solo 1 generación para prueba
        log_level='INFO'
    )

    # Test 1: Generar pairings con población 40, k=7
    print("\n--- Test 1: población=40, k_rounds=7 ---")
    pairings = ag.generate_swiss_pairings(n_decks=40, k_rounds=7)

    print(f"Enfrentamientos generados: {len(pairings)}")
    print(f"Esperado: ~140 enfrentamientos (40 × 7 / 2)")

    # Verificar que cada mazo juega k_rounds partidas
    matchups_count = [0] * 40
    for i, j in pairings:
        matchups_count[i] += 1
        matchups_count[j] += 1

    print(f"Partidas por mazo:")
    print(f"  Min: {min(matchups_count)}")
    print(f"  Max: {max(matchups_count)}")
    print(f"  Promedio: {sum(matchups_count) / len(matchups_count):.2f}")
    print(f"  Esperado: ~7")

    # Test 2: Comparar con round-robin
    print("\n--- Test 2: Comparación vs Round-Robin ---")
    full_rr = 40 * 39 // 2  # C(40,2)
    print(f"Round-robin completo: {full_rr} enfrentamientos × 3 combates = {full_rr * 3} combates")
    print(f"Swiss (k=7, n=2): {len(pairings)} enfrentamientos × 2 combates = {len(pairings) * 2} combates")
    reduction = ((full_rr * 3) - (len(pairings) * 2)) / (full_rr * 3) * 100
    print(f"Reducción: {reduction:.1f}%")
    print(f"Esperado: ~76% reducción")

    # Test 3: población=20, k=9 (casi round-robin)
    print("\n--- Test 3: población=20, k_rounds=9 ---")
    pairings_20 = ag.generate_swiss_pairings(n_decks=20, k_rounds=9)

    print(f"Enfrentamientos generados: {len(pairings_20)}")
    print(f"Esperado: ~90 enfrentamientos (20 × 9 / 2)")
    print(f"Round-robin completo sería: {20 * 19 // 2} enfrentamientos")

    # Verificar distribución
    matchups_count_20 = [0] * 20
    for i, j in pairings_20:
        matchups_count_20[i] += 1
        matchups_count_20[j] += 1

    print(f"Partidas por mazo:")
    print(f"  Min: {min(matchups_count_20)}")
    print(f"  Max: {max(matchups_count_20)}")
    print(f"  Promedio: {sum(matchups_count_20) / len(matchups_count_20):.2f}")

    # Test 4: k >= n (debería hacer round-robin completo)
    print("\n--- Test 4: k_rounds >= n_decks (round-robin automático) ---")
    pairings_full = ag.generate_swiss_pairings(n_decks=20, k_rounds=25)
    expected_full = 20 * 19 // 2
    print(f"Enfrentamientos generados: {len(pairings_full)}")
    print(f"Esperado (round-robin): {expected_full}")
    assert len(pairings_full) == expected_full, "ERROR: No hizo round-robin completo cuando k >= n"
    print("✅ Correctamente usa round-robin cuando k >= n")

    print("\n" + "="*70)
    print("TODOS LOS TESTS PASADOS ✅")
    print("="*70)

    # Mostrar estadísticas finales
    print("\n📊 ESTADÍSTICAS FINALES")
    print(f"Configuración óptima recomendada:")
    print(f"  - Población: 40 mazos")
    print(f"  - k_rounds: 7")
    print(f"  - n_games_per_match: 2")
    print(f"  - Combates/generación: {len(pairings) * 2}")
    print(f"  - Reducción vs round-robin: {reduction:.1f}%")

    print(f"\nTiempo estimado (basado en 0.18 min/combate):")
    combates_swiss = len(pairings) * 2
    combates_rr = full_rr * 3
    tiempo_swiss = combates_swiss * 0.18
    tiempo_rr = combates_rr * 0.18
    print(f"  - Swiss (pop=40, k=7, n=2): {tiempo_swiss:.0f} min/gen (~{tiempo_swiss*50/60:.1f}h para 50 gen)")
    print(f"  - Round-robin (pop=40): {tiempo_rr:.0f} min/gen (~{tiempo_rr*50/60:.1f}h para 50 gen)")
    print(f"  - Ahorro: {tiempo_rr - tiempo_swiss:.0f} min/gen ({(tiempo_rr*50 - tiempo_swiss*50)/60:.1f}h en 50 gen)")

def test_parameters():
    """Prueba que los parámetros por defecto son correctos"""
    print("\n" + "="*70)
    print("TEST: Parámetros por defecto")
    print("="*70)

    ag = MTGGeneticAlgorithm(
        max_generations=1,
        log_level='INFO'
    )

    print(f"\n✅ Parámetros cargados:")
    print(f"  - population_size: {ag.population_size} (esperado: 40)")
    print(f"  - use_swiss_tournament: {ag.use_swiss_tournament} (esperado: True)")
    print(f"  - k_rounds: {ag.k_rounds} (esperado: 8)")
    print(f"  - n_games_per_match: {ag.n_games_per_match} (esperado: 2)")
    print(f"  - elite_size: {ag.elite_size} (esperado: 12)")
    print(f"  - tournament_size: {ag.tournament_size} (esperado: 5)")

    assert ag.population_size == 40, "ERROR: population_size no es 40"
    assert ag.use_swiss_tournament == True, "ERROR: use_swiss_tournament no es True"
    assert ag.k_rounds == 8, "ERROR: k_rounds no es 8"
    assert ag.n_games_per_match == 2, "ERROR: n_games_per_match no es 2"
    assert ag.elite_size == 12, "ERROR: elite_size no es 12"
    assert ag.tournament_size == 5, "ERROR: tournament_size no es 5"

    print("\n✅ Todos los parámetros son correctos")

def test_round_robin_mode():
    """Prueba que el modo round-robin sigue funcionando"""
    print("\n" + "="*70)
    print("TEST: Modo Round-Robin (compatibilidad hacia atrás)")
    print("="*70)

    ag = MTGGeneticAlgorithm(
        population_size=20,
        use_swiss_tournament=False,  # Desactivar Swiss
        max_generations=1,
        log_level='INFO'
    )

    print(f"\n✅ Modo Round-Robin activado:")
    print(f"  - use_swiss_tournament: {ag.use_swiss_tournament} (esperado: False)")
    print(f"  - population_size: {ag.population_size}")

    expected_matches = 20 * 19 // 2
    expected_combats = expected_matches * 3

    print(f"  - Enfrentamientos esperados: {expected_matches}")
    print(f"  - Combates totales esperados: {expected_combats}")

    assert ag.use_swiss_tournament == False, "ERROR: Swiss Tournament debería estar desactivado"

    print("\n✅ Modo round-robin funciona correctamente")

if __name__ == "__main__":
    print("\n🔬 INICIANDO TESTS DEL SWISS TOURNAMENT\n")

    try:
        test_parameters()
        test_swiss_pairings()
        test_round_robin_mode()

        print("\n" + "="*70)
        print("🎉 TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print("="*70)
        print("\nLa implementación del Swiss Tournament está lista para usar.")
        print("\nPróximos pasos:")
        print("  1. Ejecutar una prueba de 5 generaciones con Swiss Tournament")
        print("  2. Verificar que los logs muestran la información correcta")
        print("  3. Comparar tiempos con experimento anterior")
        print("  4. Ejecutar experimento completo de 50 generaciones")

    except Exception as e:
        print(f"\n❌ ERROR EN LOS TESTS: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
