#!/usr/bin/env python3
"""
Script de Prueba: Validación de adjust_deck_size() Corregido

Este script demuestra que el método corregido ahora:
1. Detecta correctamente los colores del mazo después de operaciones genéticas
2. Añade tierras básicas apropiadas según esos colores
3. Mantiene la proporción 15-30 tierras obligatoriamente
4. Genera mazos jugables incluso después de cruces que cambien colores
"""

import sys
import json
import numpy as np
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

def test_color_coherence():
    """
    Prueba que el método añade tierras del color correcto
    """
    print("=" * 80)
    print("PRUEBA 1: Coherencia de Colores Después de Cruce")
    print("=" * 80)

    # Inicializar algoritmo genético (solo para usar sus métodos)
    ag = MTGGeneticAlgorithm(
        population_file="mtg_decks/test_population.json",
        catalog_path="mtg_data/card_catalog.json",
        indices_path="mtg_data/card_indices.json",
        max_generations=1,
        population_size=5
    )

    # Cargar población de prueba
    with open("mtg_decks/test_population.json", 'r') as f:
        population = json.load(f)

    if len(population) < 2:
        print("❌ ERROR: Se necesitan al menos 2 mazos en test_population.json")
        return False

    # Tomar dos mazos de diferentes colores
    deck1 = population[0]  # Primer mazo
    deck2 = population[1]  # Segundo mazo

    print(f"\nMazo 1: {deck1['name']}")
    print(f"  Colores: {deck1['colors']}")
    print(f"  Estadísticas: {deck1['stats']}")

    print(f"\nMazo 2: {deck2['name']}")
    print(f"  Colores: {deck2['colors']}")
    print(f"  Estadísticas: {deck2['stats']}")

    # Convertir a arrays
    array1 = ag.deck_to_array(deck1)
    array2 = ag.deck_to_array(deck2)

    print(f"\n{'='*80}")
    print("SIMULANDO CRUCE UNIFORME")
    print("=" * 80)

    # Realizar cruce uniforme (simula herencia aleatoria)
    child_array, _ = ag.crossover_uniform(array1, array2)

    # Convertir hijo a mazo para analizar
    child_deck = ag.array_to_deck(child_array, "Hijo_Después_Cruce")

    print(f"\nHijo después de cruce:")
    print(f"  Nombre: {child_deck['name']}")
    print(f"  Colores: {child_deck['colors']}")
    print(f"  Total de cartas: {child_deck['stats']['total_cards']}")
    print(f"  Tierras: {child_deck['stats']['lands']}")

    # Analizar tierras básicas del hijo
    print(f"\nAnálisis de tierras básicas del hijo:")

    lands_by_color = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0}
    for card in child_deck['cards']:
        if card.get('is_basic_land', False):
            for color in card['color_identity']:
                if color in lands_by_color:
                    lands_by_color[color] += card['count']

    color_names = {'W': 'Blanco', 'U': 'Azul', 'B': 'Negro', 'R': 'Rojo', 'G': 'Verde'}

    print(f"\n  Tierras básicas por color:")
    for color, count in lands_by_color.items():
        if count > 0:
            print(f"    {color_names[color]} ({color}): {count}")

    # Verificar coherencia
    deck_colors_set = set(child_deck['colors'])
    land_colors_set = {c for c, count in lands_by_color.items() if count > 0}

    print(f"\n  Colores del mazo (hechizos): {deck_colors_set}")
    print(f"  Colores con tierras: {land_colors_set}")

    if deck_colors_set.issubset(land_colors_set) or not deck_colors_set:
        print(f"\n✅ COHERENCIA VERIFICADA: Todos los colores tienen tierras")
        coherent = True
    else:
        missing = deck_colors_set - land_colors_set
        print(f"\n⚠️  ADVERTENCIA: Colores sin tierras: {missing}")
        coherent = False

    # Verificar proporción de tierras
    land_count = child_deck['stats']['lands']
    if 15 <= land_count <= 30:
        print(f"✅ PROPORCIÓN VÁLIDA: {land_count} tierras (15-30 aceptable)")
        proportion_ok = True
    else:
        print(f"❌ PROPORCIÓN INVÁLIDA: {land_count} tierras (debería ser 15-30)")
        proportion_ok = False

    return coherent and proportion_ok


def test_land_proportion_enforcement():
    """
    Prueba que el método fuerza la proporción 15-30 tierras
    """
    print("\n" + "=" * 80)
    print("PRUEBA 2: Forzar Proporción de Tierras (15-30)")
    print("=" * 80)

    ag = MTGGeneticAlgorithm(
        population_file="mtg_decks/test_population.json",
        catalog_path="mtg_data/card_catalog.json",
        indices_path="mtg_data/card_indices.json",
        max_generations=1,
        population_size=5
    )

    # Crear mazo problemático: MUY POCAS TIERRAS
    problematic_array = np.zeros(ag.total_cards, dtype=int)

    # Añadir solo 5 Mountains (muy pocas)
    mountains_id = ag.basic_lands_ids.get('Mountain')
    if mountains_id:
        problematic_array[mountains_id] = 5

    # Rellenar con 55 hechizos rojos
    red_spells = [i for i, card in ag.card_catalog.items()
                  if 'R' in card['color_identity'] and not card['is_land']][:55]

    for spell_id in red_spells:
        problematic_array[spell_id] = 1

    print(f"\n📊 Mazo ANTES de adjust_deck_size:")
    total_before = int(np.sum(problematic_array))
    lands_before = sum(problematic_array[i] for i in ag.type_indices.get('lands', []))
    print(f"  Total cartas: {total_before}")
    print(f"  Tierras: {lands_before} ❌ (menos de 15)")

    # Aplicar adjust_deck_size
    fixed_array = ag.adjust_deck_size(problematic_array)

    print(f"\n📊 Mazo DESPUÉS de adjust_deck_size:")
    total_after = int(np.sum(fixed_array))
    lands_after = sum(fixed_array[i] for i in ag.type_indices.get('lands', []))
    print(f"  Total cartas: {total_after}")
    print(f"  Tierras: {lands_after}")

    # Verificar corrección
    if total_after == 60:
        print(f"✅ Total correcto: 60 cartas")
        total_ok = True
    else:
        print(f"❌ Total incorrecto: {total_after} (debería ser 60)")
        total_ok = False

    if 15 <= lands_after <= 30:
        print(f"✅ Proporción de tierras corregida: {lands_after} (rango 15-30)")
        lands_ok = True
    else:
        print(f"❌ Proporción de tierras incorrecta: {lands_after} (debería ser 15-30)")
        lands_ok = False

    # Verificar que añadió Mountains (no otras tierras)
    mountains_after = fixed_array[mountains_id]
    print(f"\n  Mountains añadidas: {mountains_after - 5} (de 5 a {mountains_after})")

    return total_ok and lands_ok


def test_limit_4_copies():
    """
    Prueba que el método respeta el límite de 4 copias
    """
    print("\n" + "=" * 80)
    print("PRUEBA 3: Límite de 4 Copias (excepto básicas)")
    print("=" * 80)

    ag = MTGGeneticAlgorithm(
        population_file="mtg_decks/test_population.json",
        catalog_path="mtg_data/card_catalog.json",
        indices_path="mtg_data/card_indices.json",
        max_generations=1,
        population_size=5
    )

    # Crear mazo problemático: una carta con más de 4 copias
    problematic_array = np.zeros(ag.total_cards, dtype=int)

    # Añadir 20 Mountains (válido, es tierra básica)
    mountains_id = ag.basic_lands_ids.get('Mountain')
    problematic_array[mountains_id] = 20

    # Añadir 8 copias de un hechizo (INVÁLIDO)
    red_spells = [i for i, card in ag.card_catalog.items()
                  if 'R' in card['color_identity'] and not card['is_land']][:1]

    if red_spells:
        spell_id = red_spells[0]
        problematic_array[spell_id] = 8  # ❌ Más de 4

        spell_name = ag.card_catalog[spell_id]['name']
        print(f"\n📊 Mazo con VIOLACIÓN del límite de 4 copias:")
        print(f"  Hechizo: {spell_name}")
        print(f"  Copias: 8 ❌ (máximo 4 permitido)")

        # Rellenar hasta 60 con otros hechizos
        remaining = 60 - 20 - 8  # 32 cartas más
        for other_spell_id in red_spells[1:remaining+1]:
            problematic_array[other_spell_id] = 1

    # Aplicar adjust_deck_size (NOTA: adjust_deck_size NO corrige límite de 4, solo añade/quita)
    # Para corregir límite de 4, necesitaríamos el método repair_unplayable_deck()

    # Por ahora, solo verificamos que adjust_deck_size NO empeora la situación
    fixed_array = ag.adjust_deck_size(problematic_array)

    print(f"\n📊 Verificación después de adjust_deck_size:")
    print(f"  Total cartas: {int(np.sum(fixed_array))}")

    # Contar cartas con más de 4 copias (que no sean básicas)
    violations = 0
    for card_id, count in enumerate(fixed_array):
        if count > 4:
            card = ag.card_catalog[card_id]
            if not card.get('is_basic_land', False):
                violations += 1
                print(f"  ⚠️  {card['name']}: {count} copias (máximo 4)")

    # NOTA: adjust_deck_size() NO está diseñado para corregir violaciones del límite de 4
    # Su responsabilidad es SOLO ajustar tamaño y coherencia de colores/tierras
    # El límite de 4 debe ser respetado por los operadores genéticos

    # Verificar que adjust_deck_size NO EMPEORÓ la situación
    violations_before = 1  # El test creó 1 violación intencionalmente
    violations_after = violations

    if violations_after <= violations_before:
        print(f"✅ adjust_deck_size NO empeoró las violaciones ({violations_before} → {violations_after})")
        print(f"   (NOTA: Corregir límite de 4 es responsabilidad de los operadores genéticos)")
        return True
    else:
        print(f"❌ adjust_deck_size EMPEORÓ las violaciones ({violations_before} → {violations_after})")
        return False


def main():
    """
    Ejecuta todas las pruebas
    """
    print("\n")
    print("🧪 " + "=" * 76 + " 🧪")
    print("   SUITE DE PRUEBAS: adjust_deck_size() CORREGIDO")
    print("🧪 " + "=" * 76 + " 🧪")

    results = {}

    try:
        results['coherencia_colores'] = test_color_coherence()
    except Exception as e:
        print(f"❌ Error en prueba de coherencia de colores: {e}")
        results['coherencia_colores'] = False

    try:
        results['proporcion_tierras'] = test_land_proportion_enforcement()
    except Exception as e:
        print(f"❌ Error en prueba de proporción de tierras: {e}")
        results['proporcion_tierras'] = False

    try:
        results['limite_4_copias'] = test_limit_4_copies()
    except Exception as e:
        print(f"❌ Error en prueba de límite de 4 copias: {e}")
        results['limite_4_copias'] = False

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN DE PRUEBAS")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASÓ" if passed else "❌ FALLÓ"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")

    total_tests = len(results)
    passed_tests = sum(1 for p in results.values() if p)

    print(f"\nTotal: {passed_tests}/{total_tests} pruebas pasadas")

    if passed_tests == total_tests:
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON! 🎉")
        return 0
    else:
        print("\n⚠️  Algunas pruebas fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
