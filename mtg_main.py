#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal para el TFG: Diseño de un algoritmo genético para la 
construcción de mazos en Magic: The Gathering.

Versión refactorizada con representación de arrays de tamaño fijo.

Este script integra todos los componentes del proyecto:
1. Obtención de cartas del formato Estándar (excluyendo última expansión)
2. Generación de población inicial de mazos
3. Ejecución del algoritmo genético
4. Visualización de resultados

Autor: José Gascó Bule
"""

import os
import argparse
import json
import time
from pathlib import Path
import sys

# Importar nuestros módulos
from obtener_cartas_mtg import MTGCardScraper
from generador_mazos_mtg import MTGDeckGenerator
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

def parse_arguments():
    """Procesa los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description='Algoritmo Genético para Mazos de Magic: The Gathering (Versión Array)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Directorios y archivos
    parser.add_argument('--data_dir', type=str, default="mtg_data", 
                        help='Directorio para datos de cartas')
    parser.add_argument('--decks_dir', type=str, default="mtg_decks", 
                        help='Directorio para mazos generados')
    parser.add_argument('--evolved_dir', type=str, default="mtg_evolved_decks", 
                        help='Directorio para mazos evolucionados')
    parser.add_argument('--forge_jar', type=str, default="./forge-gui-desktop-2.0.03-jar-with-dependencies.jar", 
                        help='Ruta al ejecutable Forge')
    
    # Parámetros del algoritmo
    parser.add_argument('--population_size', type=int, default=50, 
                        help='Tamaño de la población')
    parser.add_argument('--max_generations', type=int, default=100, 
                        help='Número máximo de generaciones')
    parser.add_argument('--mutation_rate', type=float, default=0.05, 
                        help='Tasa de mutación (0.0-1.0)')
    parser.add_argument('--crossover_rate', type=float, default=0.9, 
                        help='Tasa de cruce (0.0-1.0)')
    parser.add_argument('--tournament_size', type=int, default=3, 
                        help='Tamaño del torneo para selección')
    parser.add_argument('--elite_size', type=int, default=5, 
                        help='Número de mejores individuos a preservar')
    parser.add_argument('--stagnation_limit', type=int, default=20, 
                        help='Generaciones sin mejora antes de terminar')
    parser.add_argument('--exclude_latest_set', action='store_true', default=True,
                        help='Excluir la última expansión para compatibilidad con Forge')
    
    # Modo de ejecución
    parser.add_argument('--mode', type=str, choices=['full', 'cards', 'decks', 'evolve'], 
                        default='full', help='Modo de ejecución del script')
    
    return parser.parse_args()

def print_summary(deck):
    """Imprime un resumen del mazo"""
    print(f"\nNombre: {deck['name']}")
    print(f"Colores: {', '.join(deck['colors']) if deck['colors'] else 'Incoloro'}")
    
    stats = deck['stats']
    print(f"\nEstadísticas:")
    print(f"  Total de cartas: {stats['total_cards']}")
    print(f"  Tierras: {stats['lands']}")
    print(f"  Criaturas: {stats['creatures']}")
    print(f"  Hechizos: {stats['spells']}")
    print(f"  Artefactos/Encantamientos: {stats['artifacts_enchantments']}")
    print(f"  Planeswalkers: {stats['planeswalkers']}")
    print(f"  CMC promedio: {stats['avg_cmc']:.2f}")
    
    # Mostrar algunas cartas clave
    print(f"\nAlgunas cartas del mazo:")
    cards_to_show = sorted(deck['cards'], key=lambda x: (x['cmc'], -x['count']))[:10]
    for card in cards_to_show:
        mana_cost = card.get('mana_cost', 'N/A')
        print(f"  {card['count']}x {card['name']} ({mana_cost})")

def main():
    """Función principal del programa"""
    args = parse_arguments()
    
    # Crear directorios si no existen
    Path(args.data_dir).mkdir(exist_ok=True)
    Path(args.decks_dir).mkdir(exist_ok=True)
    Path(args.evolved_dir).mkdir(exist_ok=True)
    
    # Variables para archivos importantes
    card_catalog_file = os.path.join(args.data_dir, "card_catalog.json")
    card_indices_file = os.path.join(args.data_dir, "card_indices.json")
    cards_csv_file = os.path.join(args.data_dir, "processed_standard_cards.csv")
    population_file = os.path.join(args.decks_dir, "initial_population.json")
    
    print("=" * 80)
    print("ALGORITMO GENÉTICO PARA MAGIC: THE GATHERING")
    print("Versión con representación de arrays")
    print("=" * 80)
    
    # PASO 1: Obtener cartas
    if args.mode in ['full', 'cards']:
        print("\n===== PASO 1: Obtener cartas del formato Estándar =====")
        start_time = time.time()
        
        scraper = MTGCardScraper(
            output_dir=args.data_dir,
            exclude_latest_set=args.exclude_latest_set
        )
        cards_df = scraper.run()
        
        elapsed = time.time() - start_time
        print(f"\nObtención de cartas completada en {elapsed:.2f} segundos")
        
        if cards_df is None or cards_df.empty:
            print("ERROR: No se pudieron obtener las cartas. Abortando.")
            return 1
        
        # Verificar que se generaron los archivos necesarios
        if not os.path.exists(card_catalog_file):
            print(f"ERROR: No se generó el catálogo de cartas en {card_catalog_file}")
            return 1
            
        if not os.path.exists(card_indices_file):
            print(f"ERROR: No se generaron los índices en {card_indices_file}")
            return 1
    
    # PASO 2: Generar población inicial
    if args.mode in ['full', 'decks']:
        print("\n===== PASO 2: Generar población inicial de mazos =====")
        start_time = time.time()
        
        # Verificar archivos necesarios
        required_files = [cards_csv_file, card_catalog_file, card_indices_file]
        for file in required_files:
            if not os.path.exists(file):
                print(f"ERROR: No se encontró el archivo requerido: {file}")
                return 1
        
        generator = MTGDeckGenerator(
            cards_csv_path=cards_csv_file,
            catalog_path=card_catalog_file,
            indices_path=card_indices_file,
            output_dir=args.decks_dir
        )
        
        population = generator.generate_strategic_population(args.population_size)
        
        elapsed = time.time() - start_time
        print(f"\nGeneración de mazos completada en {elapsed:.2f} segundos")
        
        if not population:
            print("ERROR: No se pudo generar la población inicial. Abortando.")
            return 1
        
        # Mostrar resumen de un mazo de ejemplo
        print("\n--- Ejemplo de mazo generado ---")
        print_summary(population[0])
    
    # PASO 3: Ejecutar algoritmo genético
    if args.mode in ['full', 'evolve']:
        print("\n===== PASO 3: Ejecutar algoritmo genético =====")
        start_time = time.time()
        
        # Verificar archivos necesarios
        required_files = [population_file, card_catalog_file, card_indices_file]
        for file in required_files:
            if not os.path.exists(file):
                print(f"ERROR: No se encontró el archivo requerido: {file}")
                return 1
        
        # Verificar Forge (OBLIGATORIO)
        if not os.path.exists(args.forge_jar):
            print(f"ERROR: No se encontró Forge en {args.forge_jar}")
            print("Forge es OBLIGATORIO para ejecutar el algoritmo genético.")
            print("Por favor, descarga forge-gui-desktop.jar de:")
            print("https://www.slightlymagic.net/forum/viewforum.php?f=26")
            print("Y colócalo en la ruta especificada.")
            return 1
        
        # Configurar algoritmo genético
        ga = MTGGeneticAlgorithm(
            population_file=population_file,
            catalog_path=card_catalog_file,
            indices_path=card_indices_file,
            output_dir=args.evolved_dir,
            forge_jar_path=args.forge_jar,
            max_generations=args.max_generations,
            population_size=args.population_size,
            mutation_rate=args.mutation_rate,
            crossover_rate=args.crossover_rate,
            tournament_size=args.tournament_size,
            elite_size=args.elite_size,
            stagnation_limit=args.stagnation_limit
        )
        
        # Ejecutar evolución
        best_deck = ga.evolve()
        
        elapsed = time.time() - start_time
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        print(f"\nEvolución completada en {int(hours)}h {int(minutes)}m {seconds:.2f}s")
        
        # Guardar mejor mazo
        best_deck_file = os.path.join(args.evolved_dir, "best_deck_final.json")
        with open(best_deck_file, 'w', encoding='utf-8') as f:
            json.dump(best_deck, f, ensure_ascii=False, indent=2)
        
        print(f"\nMejor mazo guardado en: {best_deck_file}")
        
        # Mostrar resumen del mejor mazo
        print("\n===== MEJOR MAZO ENCONTRADO =====")
        print_summary(best_deck)
        
        # Mostrar estadísticas finales
        if hasattr(ga, 'hall_of_fame') and ga.hall_of_fame:
            print(f"\nHall of Fame: {len(ga.hall_of_fame)} mejores soluciones guardadas")
            print(f"Mejor fitness alcanzado: {ga.best_fitness_ever:.4f}")
            print(f"Esto representa un {ga.best_fitness_ever * 100:.1f}% de win rate en el torneo")
    
    print("\n" + "=" * 80)
    print("¡PROCESO COMPLETADO CON ÉXITO!")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())