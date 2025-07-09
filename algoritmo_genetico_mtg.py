# Algoritmo Genético MTG Mejorado - Recibe configuración de paralelización

import os
import json
import random
import copy
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count, Manager
from collections import defaultdict
import re
from tqdm import tqdm
import logging
import csv
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading
import json
import time
import pickle
from datetime import datetime

class MTGGeneticAlgorithm:
    def __init__(self, 
                 population_file="mtg_decks/initial_population.json",
                 catalog_path="mtg_data/card_catalog.json",
                 indices_path="mtg_data/card_indices.json",
                 output_dir="mtg_evolved_decks",
                 forge_jar_path="./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
                 max_generations=200,
                 population_size=50,
                 mutation_rate=0.05,
                 crossover_rate=0.9,
                 tournament_size=3,
                 elite_size=5,
                 stagnation_limit=20,
                 # NUEVOS PARÁMETROS DE PARALELIZACIÓN
                 max_workers=None,
                 parallel_batch_size=None,
                 base_timeout=120,
                 log_level='INFO',
                 save_forge_outputs=True,
                 headless_mode=False):
        """
        Inicializa el algoritmo genético con parámetros de paralelización
        
        Args:
            max_workers (int): Número de workers paralelos (None = auto-detectar)
            parallel_batch_size (int): Tamaño de lote paralelo (None = auto-calcular)
            base_timeout (int): Timeout base en segundos
            log_level (str): Nivel de logging ('DEBUG', 'INFO', 'WARNING')
            save_forge_outputs (bool): Si guardar outputs completos de Forge
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self.catalog_path = catalog_path      
        self.indices_path = indices_path      
        self.population_file = population_file 
        self.forge_jar_path = forge_jar_path
        self.max_generations = max_generations
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        self.stagnation_limit = stagnation_limit
        
        # CONFIGURACIÓN DE PARALELIZACIÓN
        self.max_workers = max_workers if max_workers else max(2, cpu_count() // 2)
        self.parallel_batch_size = parallel_batch_size if parallel_batch_size else self.max_workers * 3
        self.base_timeout = base_timeout
        self.adaptive_timeout = base_timeout
        self.save_forge_outputs = save_forge_outputs
        
        # Configurar logging
        self.setup_logging(log_level)
        
        # Estructuras para datos (thread-safe)
        self.combat_log = []
        self.generation_stats = []
        self.current_generation = 0
        self.combat_lock = threading.Lock()
        
        # Cargar catálogo e índices
        self.logger.info(f"Cargando catálogo de cartas...")
        with open(catalog_path, 'r', encoding='utf-8') as f:
            self.card_catalog = json.load(f)
        self.card_catalog = {int(k): v for k, v in self.card_catalog.items()}
        
        with open(indices_path, 'r', encoding='utf-8') as f:
            indices_data = json.load(f)
            self.type_indices = indices_data['type_indices']
            self.color_indices = indices_data['color_indices']
            self.total_cards = indices_data['total_cards']
        
        # Cargar población inicial
        self.population = self.load_population(population_file)
        self.logger.info(f"Población inicial: {len(self.population)} mazos")
        self.logger.info(f"Configuración paralela: {self.max_workers} workers, timeout {self.base_timeout}s")
        
        # Convertir población a arrays
        self.population_arrays = []
        for deck in self.population:
            if 'array' in deck:
                self.population_arrays.append(np.array(deck['array']))
            else:
                array = self.deck_to_array(deck)
                self.population_arrays.append(array)
        
        # Estadísticas de evolución
        self.stats = {
            'best_fitness': [],
            'avg_fitness': [],
            'diversity': [],
            'mutation_rate': []
        }
        
        # Mejores individuos históricos
        self.hall_of_fame = []
        
        # Contador de estancamiento
        self.stagnation_counter = 0
        self.best_fitness_ever = 0
        
        # Configurar Forge
        self.setup_forge()
        
        #Modo headless
        self.headless_mode = headless_mode
        self.logger.info(f"Modo: {'Headless (xvfb-run)' if headless_mode else 'GUI normal'}")
        
         #Hall of Fame Global
        self.hall_of_fame_arrays = []  # Lista de (fitness, deck_array)
        self.max_hall_size = max(self.elite_size, 5)  # Al menos 5 mejores históricos

        self.logger.info(f"Hall of Fame configurado: {self.max_hall_size} mejores históricos")
    
    def setup_logging(self, log_level):
        """Configura sistema de logging"""
        self.logs_dir = os.path.join(self.output_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        log_filename = os.path.join(self.logs_dir, f"parallel_ag_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # Configurar nivel de logging
        numeric_level = getattr(logging, log_level.upper())
        
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("=== ALGORITMO GENÉTICO PARALELO INICIADO ===")
        
        # Archivos de logs
        self.combat_log_file = os.path.join(self.logs_dir, "parallel_combat_results.csv")
        self.match_details_file = os.path.join(self.logs_dir, "parallel_match_details.json")
        
        if self.save_forge_outputs:
            self.forge_output_dir = os.path.join(self.logs_dir, "forge_outputs")
            os.makedirs(self.forge_output_dir, exist_ok=True)
        else:
            self.forge_output_dir = None
            self.logger.info("Forge outputs deshabilitados para ahorrar espacio")
        
        # Inicializar CSV
        with open(self.combat_log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Generation', 'Match_ID', 'Deck1_Name', 'Deck2_Name', 
                'Winner', 'Deck1_Wins', 'Deck2_Wins', 'Duration_Seconds',
                'Worker_ID', 'Forge_Output_File', 'Error_Message', 'Timestamp'
            ])
    
    def load_population(self, population_file):
        """Carga la población inicial desde archivo"""
        try:
            with open(population_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            return population
        except Exception as e:
            self.logger.error(f"Error al cargar población: {e}")
            return []
    
    def deck_to_array(self, deck):
        """Convierte un mazo del formato antiguo a array"""
        array = np.zeros(self.total_cards, dtype=int)
        for card in deck.get('cards', []):
            if 'card_id' in card:
                array[card['card_id']] = card['count']
        return array
    
    def array_to_deck(self, array, name="Evolved_Deck"):
        """Convierte un array a formato de mazo completo"""
        cards = []
        colors = set()
        
        for card_id, count in enumerate(array):
            if count > 0:
                card_data = self.card_catalog[card_id].copy()
                card_data['count'] = int(count)
                cards.append(card_data)
                
                for color in card_data['color_identity']:
                    colors.add(color)
        
        # Calcular estadísticas
        total_cards = sum(c['count'] for c in cards)
        lands = sum(c['count'] for c in cards if c['is_land'])
        creatures = sum(c['count'] for c in cards if c['is_creature'])
        spells = sum(c['count'] for c in cards if c['is_instant'] or c['is_sorcery'])
        artifacts_enchantments = sum(c['count'] for c in cards 
                                   if (c['is_artifact'] or c['is_enchantment']) 
                                   and not c['is_creature'])
        planeswalkers = sum(c['count'] for c in cards if c['is_planeswalker'])
        
        # CMC promedio
        nonland_cards = [c for c in cards if not c['is_land']]
        if nonland_cards:
            avg_cmc = sum(c['cmc'] * c['count'] for c in nonland_cards) / sum(c['count'] for c in nonland_cards)
        else:
            avg_cmc = 0.0
        
        return {
            'name': name,
            'colors': sorted(list(colors)),
            'array': array.tolist(),
            'cards': cards,
            'stats': {
                'total_cards': total_cards,
                'lands': lands,
                'creatures': creatures,
                'spells': spells,
                'artifacts_enchantments': artifacts_enchantments,
                'planeswalkers': planeswalkers,
                'avg_cmc': avg_cmc
            }
        }
        
    def save_population_arrays(self, generation):
        """
        Guarda la población actual en formato de arrays para análisis y debugging.
        Este método era crítico y estaba faltando, causando errores.

        Args:
            generation (int): Número de generación actual
        """
        try:
            # Preparar datos para guardar
            population_data = {
                'generation': generation,
                'timestamp': time.time(),
                'population_size': len(self.population_arrays),
                'arrays': [],
                'fitness_values': getattr(self, 'current_fitness_values', []),
                'hall_of_fame_size': len(getattr(self, 'hall_of_fame_arrays', [])),
                'stagnation_counter': getattr(self, 'stagnation_counter', 0)
            }

            # Convertir arrays numpy a listas para JSON
            for i, array in enumerate(self.population_arrays):
                array_data = {
                    'index': i,
                    'array': array.tolist(),
                    'sum': int(np.sum(array)),
                    'non_zero_count': int(np.count_nonzero(array)),
                    'max_value': int(np.max(array)),
                    'min_value': int(np.min(array))
                }
                population_data['arrays'].append(array_data)

            # Agregar información del Hall of Fame si existe
            if hasattr(self, 'hall_of_fame_arrays') and self.hall_of_fame_arrays:
                population_data['hall_of_fame'] = []
                for fitness, hof_array in self.hall_of_fame_arrays[:5]:  # Solo los top 5
                    hof_data = {
                        'fitness': float(fitness),
                        'array': hof_array.tolist(),
                        'sum': int(np.sum(hof_array)),
                        'non_zero_count': int(np.count_nonzero(hof_array))
                    }
                    population_data['hall_of_fame'].append(hof_data)

            # Crear nombres de archivo con timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Guardar archivo detallado (solo cada 5 generaciones para evitar sobrecarga)
            if generation % 5 == 0 or generation == 1:
                detailed_filename = os.path.join(
                    self.output_dir, 
                    f"population_arrays_detailed_gen_{generation:03d}_{timestamp_str}.json"
                )
                with open(detailed_filename, 'w', encoding='utf-8') as f:
                    json.dump(population_data, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Población detallada guardada: {detailed_filename}")

            # Guardar archivo compacto (solo estadísticas básicas) cada generación
            compact_data = {
                'generation': generation,
                'timestamp': time.time(),
                'population_size': len(self.population_arrays),
                'fitness_stats': {
                    'count': len(population_data['fitness_values']),
                    'max': float(max(population_data['fitness_values'])) if population_data['fitness_values'] else 0.0,
                    'min': float(min(population_data['fitness_values'])) if population_data['fitness_values'] else 0.0,
                    'avg': float(np.mean(population_data['fitness_values'])) if population_data['fitness_values'] else 0.0
                },
                'array_stats': {
                    'total_arrays': len(self.population_arrays),
                    'avg_sum': float(np.mean([np.sum(arr) for arr in self.population_arrays])),
                    'avg_non_zero': float(np.mean([np.count_nonzero(arr) for arr in self.population_arrays]))
                },
                'hall_of_fame_size': len(getattr(self, 'hall_of_fame_arrays', [])),
                'stagnation_counter': getattr(self, 'stagnation_counter', 0)
            }

            compact_filename = os.path.join(
                self.output_dir, 
                f"population_summary_gen_{generation:03d}.json"
            )
            with open(compact_filename, 'w', encoding='utf-8') as f:
                json.dump(compact_data, f, indent=2, ensure_ascii=False)

            # Guardar también un archivo histórico que acumule todas las generaciones
            history_filename = os.path.join(self.output_dir, "evolution_history.json")
            if os.path.exists(history_filename):
                with open(history_filename, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {'generations': []}

            history['generations'].append(compact_data)

            with open(history_filename, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"✅ save_population_arrays completado para generación {generation}")

        except Exception as e:
            self.logger.error(f"❌ Error en save_population_arrays: {e}")
            # No reraiseamos el error para evitar que el algoritmo se detenga
            # Solo loggeamos el error y continuamos
            import traceback
            self.logger.error(f"Traceback completo: {traceback.format_exc()}")


    def save_final_population(self):
        """
        Guarda la población final con información completa.
        Método complementario para al final del algoritmo.
        """
        try:
            final_data = {
                'final_generation': self.current_generation,
                'timestamp': time.time(),
                'total_runtime': getattr(self, 'total_runtime', 0),
                'final_population': [],
                'hall_of_fame': [],
                'evolution_summary': {
                    'max_fitness_achieved': float(max(getattr(self, 'current_fitness_values', [0]))),
                    'generations_completed': self.current_generation,
                    'stagnation_final': getattr(self, 'stagnation_counter', 0)
                }
            }

            # Convertir población final a formato completo (arrays + mazos)
            for i, array in enumerate(self.population_arrays):
                deck = self.array_to_deck(array, f"Final_Deck_{i:03d}")
                deck_data = {
                    'index': i,
                    'array': array.tolist(),
                    'deck': deck,
                    'fitness': float(self.current_fitness_values[i]) if i < len(getattr(self, 'current_fitness_values', [])) else 0.0
                }
                final_data['final_population'].append(deck_data)

            # Hall of Fame completo
            if hasattr(self, 'hall_of_fame_arrays'):
                for fitness, hof_array in self.hall_of_fame_arrays:
                    hof_deck = self.array_to_deck(hof_array, f"HOF_Deck_{len(final_data['hall_of_fame'])}")
                    hof_data = {
                        'fitness': float(fitness),
                        'array': hof_array.tolist(),
                        'deck': hof_deck
                    }
                    final_data['hall_of_fame'].append(hof_data)

            # Guardar resultado final
            final_filename = os.path.join(
                self.output_dir, 
                f"final_population_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(final_filename, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"✅ Población final guardada: {final_filename}")
            return final_filename

        except Exception as e:
            self.logger.error(f"❌ Error guardando población final: {e}")
            return None
    
    def setup_forge(self):
        """Configura Forge"""
        if not os.path.exists(self.forge_jar_path):
            self.logger.error(f"ERROR: No se encontró Forge en {self.forge_jar_path}")
            sys.exit(1)

        # Usar rutas fijas y simples
        self.forge_root = os.path.dirname(self.forge_jar_path)
        self.forge_decks_dir = "./user/decks/constructed"
        self.forge_old_winners_dir = "./user/decks/old_winners"

        # Crear directorios si no existen
        os.makedirs(self.forge_decks_dir, exist_ok=True)
        os.makedirs(self.forge_old_winners_dir, exist_ok=True)

        # Limpiar al inicio
        self.clean_forge_decks()

        self.logger.info(f"Forge configurado. Directorio de mazos: {self.forge_decks_dir}")
    
    def clean_forge_decks(self):
        """Limpia TODOS los archivos de ./user/decks/constructed - VERSIÓN SIMPLE"""
        target_dir = "./user/decks/constructed"
        
        print(f"🧹 Limpiando TODO en: {target_dir}")
        
        if not os.path.exists(target_dir):
            print(f"❌ Directorio no existe: {target_dir}")
            return 0
        
        try:
            files = os.listdir(target_dir)
            print(f"   📂 Archivos encontrados: {len(files)}")
            
            if len(files) == 0:
                print("   📭 Directorio ya está vacío")
                return 0
            
            cleaned_count = 0
            for filename in files:
                filepath = os.path.join(target_dir, filename)
                try:
                    if os.path.isfile(filepath):  # Solo archivos, no directorios
                        os.remove(filepath)
                        cleaned_count += 1
                        print(f"   ✅ Eliminado: {filename}")
                except Exception as e:
                    print(f"   ❌ Error eliminando {filename}: {e}")
            
            print(f"✅ Limpieza completada: {cleaned_count} archivos eliminados")
            return cleaned_count
            
        except Exception as e:
            print(f"❌ Error accediendo al directorio: {e}")
            return 0
    
    def save_combat_result_parallel(self, result):
        """Thread-safe: Guarda resultado de combate"""
        with self.combat_lock:
            # Guardar en CSV
            with open(self.combat_log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    result['generation'], result['match_id'], 
                    result['deck1_name'], result['deck2_name'],
                    result['winner'], result['deck1_wins'], result['deck2_wins'], 
                    result['duration'], result['worker_id'],
                    result['forge_output_file'], result['error_message'], 
                    result['timestamp']
                ])
            
            # Guardar en memoria
            self.combat_log.append(result)
    
    def evaluate_population_tournament_parallel(self, population_arrays, generation=0):
        """Evalúa población mediante torneo round-robin paralelo"""
        self.current_generation = generation

        self.logger.info(f"=== EVALUACIÓN PARALELA GENERACIÓN {generation} ===")

        n_decks = len(population_arrays)
        wins = [0] * n_decks
        games = [0] * n_decks

        generation_start_time = time.time()

        self.logger.info(f"Población: {n_decks} mazos")
        self.logger.info(f"Workers paralelos: {self.max_workers}")
        self.logger.info(f"Total de enfrentamientos: {n_decks * (n_decks - 1) // 2}")

        # SOLO limpiar en la primera generación (generación 0)
        if generation == 0:
            self.clean_forge_decks()
        else:
            self.logger.info(f"Manteniendo mazos existentes para generación {generation}")

        deck_names = []
        for i, array in enumerate(population_arrays):
            deck_name = f"Gen{generation}_Deck{i}"
            deck_names.append(deck_name)
            deck = self.array_to_deck(array, deck_name)
            deck_file = os.path.join(self.forge_decks_dir, f"{deck_name}.dck")
            self.save_forge_deck(deck, deck_file)
        
        # Crear lista de todos los combates - OPTIMIZADO
        combat_tasks = []
        match_count = 0
        
        for i in range(n_decks):
            for j in range(i + 1, n_decks):
                # SOLO UN COMBATE por enfrentamiento único
                match_count += 1
                match_id = f"Gen{generation}_Match{match_count}_{int(time.time())}"
                
                # Alternancia determinística del starter
                if self.get_starting_player(i, j, generation):
                    deck1_name, deck2_name = deck_names[i], deck_names[j]
                    deck1_idx, deck2_idx = i, j
                else:
                    deck1_name, deck2_name = deck_names[j], deck_names[i]
                    deck1_idx, deck2_idx = j, i
                
                combat_tasks.append({
                    'deck1_name': deck1_name,
                    'deck2_name': deck2_name,
                    'forge_jar_path': self.forge_jar_path,
                    'forge_root': self.forge_root,
                    'timeout': self.adaptive_timeout,
                    'match_id': match_id,
                    'generation': generation,
                    'forge_output_dir': self.forge_output_dir,
                    'deck1_idx': deck1_idx,
                    'deck2_idx': deck2_idx,
                    'reverse': False,
                    'headless_mode': self.headless_mode
                })
        
        total_combats = len(combat_tasks)
        self.logger.info(f"Ejecutando {total_combats} combates en paralelo... (OPTIMIZADO: 50% menos)")
        
        # EJECUCIÓN PARALELA
        successful_combats = 0
        failed_combats = 0
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Enviar tareas y crear barra de progreso
            with tqdm(total=total_combats, desc=f"Gen {generation} - Combates Paralelos") as pbar:
                # Submit todas las tareas
                future_to_combat = {
                    executor.submit(parallel_forge_combat_worker, task): task 
                    for task in combat_tasks
                }
                
                # Procesar resultados conforme van completándose
                for future in as_completed(future_to_combat):
                    task = future_to_combat[future]
                    
                    try:
                        result = future.result()
                        
                        # Guardar resultado
                        self.save_combat_result_parallel(result)
                        
                        if result['success']:
                            successful_combats += 1
                            # Actualizar contadores de victorias
                            i = task['deck1_idx']
                            j = task['deck2_idx']
                            
                            if result['return_value'] == 1:
                                wins[i] += 1
                            else:
                                wins[j] += 1
                            
                            games[i] += 1
                            games[j] += 1
                        else:
                            failed_combats += 1
                            if result['winner'] == 'TIMEOUT':
                                # Aumentar timeout si hay muchos timeouts
                                self.adaptive_timeout = min(self.base_timeout * 3, self.adaptive_timeout * 1.1)
                            self.logger.warning(f"Combate fallido: {result['error_message']}")
                        
                    except Exception as e:
                        failed_combats += 1
                        self.logger.error(f"Error procesando combate: {e}")
                    
                    pbar.update(1)
        
        # Calcular fitness
        fitness_values = []
        for i in range(n_decks):
            if games[i] > 0:
                win_rate = wins[i] / games[i]
            else:
                win_rate = 0.0
            fitness_values.append(win_rate)
        
        generation_duration = time.time() - generation_start_time
        
        # Log de resultados
        self.logger.info(f"=== RESULTADOS GENERACIÓN {generation} ===")
        self.logger.info(f"Duración total: {generation_duration/60:.1f} minutos")
        self.logger.info(f"Combates exitosos: {successful_combats}/{total_combats}")
        self.logger.info(f"Combates fallidos: {failed_combats}")
        self.logger.info(f"Mejor fitness: {max(fitness_values):.4f}")
        self.logger.info(f"Fitness promedio: {np.mean(fitness_values):.4f}")
        
        # Ranking de mazos
        deck_rankings = [(i, deck_names[i], fitness_values[i], wins[i], games[i]) 
                        for i in range(n_decks)]
        deck_rankings.sort(key=lambda x: x[2], reverse=True)
        
        self.logger.info("Top 5 mazos:")
        for rank, (idx, name, fitness, win_count, game_count) in enumerate(deck_rankings[:5], 1):
            self.logger.info(f"  {rank}. {name}: {fitness:.4f} ({win_count}/{game_count})")
        
        # Guardar estadísticas de generación
        generation_stats = {
            'generation': generation,
            'duration_minutes': generation_duration / 60,
            'total_combats': total_combats,
            'successful_combats': successful_combats,
            'failed_combats': failed_combats,
            'best_fitness': max(fitness_values),
            'avg_fitness': np.mean(fitness_values),
            'deck_rankings': deck_rankings,
            'adaptive_timeout': self.adaptive_timeout,
            'timestamp': datetime.now().isoformat()
        }
        
        self.generation_stats.append(generation_stats)
        
        return fitness_values
    
    def save_forge_deck(self, deck, filepath):
        """Guarda un mazo en formato Forge"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("[metadata]\n")
            f.write(f"Name={deck['name']}\n")
            f.write("\n[Main]\n")
            
            for card in deck['cards']:
                f.write(f"{card['count']} {card['name']}\n")
    
    # [Resto de métodos iguales: crossover, mutación, etc.]
    def crossover_uniform(self, parent1_array, parent2_array):
        """Cruce uniforme entre dos arrays de mazos"""
        if random.random() > self.crossover_rate:
            return parent1_array.copy(), parent2_array.copy()
        
        mask = np.random.randint(0, 2, size=self.total_cards)
        child1 = np.where(mask == 1, parent1_array, parent2_array)
        child2 = np.where(mask == 0, parent1_array, parent2_array)
        
        child1 = self.adjust_deck_size(child1)
        child2 = self.adjust_deck_size(child2)
        
        return child1, child2
    
    def crossover_two_point(self, parent1_array, parent2_array):
        """Cruce de dos puntos entre arrays de mazos"""
        if random.random() > self.crossover_rate:
            return parent1_array.copy(), parent2_array.copy()
        
        points = sorted(random.sample(range(1, self.total_cards), 2))
        
        child1 = np.concatenate([
            parent1_array[:points[0]],
            parent2_array[points[0]:points[1]],
            parent1_array[points[1]:]
        ])
        
        child2 = np.concatenate([
            parent2_array[:points[0]],
            parent1_array[points[0]:points[1]],
            parent2_array[points[1]:]
        ])
        
        child1 = self.adjust_deck_size(child1)
        child2 = self.adjust_deck_size(child2)
        
        return child1, child2
    
    def mutate_swap(self, deck_array):
        """Mutación por intercambio: intercambia cartas entre posiciones"""
        if random.random() > self.mutation_rate:
            return deck_array.copy()
        
        mutated = deck_array.copy()
        num_swaps = random.randint(1, 3)
        
        for _ in range(num_swaps):
            nonzero_positions = np.where(mutated > 0)[0]
            if len(nonzero_positions) < 2:
                continue
            
            pos1, pos2 = random.sample(list(nonzero_positions), 2)
            
            if mutated[pos1] > 0 and mutated[pos2] < 4:
                mutated[pos1] -= 1
                mutated[pos2] += 1
        
        return mutated
    
    def mutate_add_remove(self, deck_array):
        """Mutación por adición/remoción: puede añadir cartas NUEVAS o quitar existentes"""
        if random.random() > self.mutation_rate:
            return deck_array.copy()

        mutated = deck_array.copy()
        num_changes = random.randint(1, 3)

        for _ in range(num_changes):
            if random.random() < 0.5:
                # AÑADIR carta nueva - clave para exploración
                valid_positions = np.where(mutated < 4)[0]
                if len(valid_positions) > 0:
                    pos = random.choice(valid_positions)
                    mutated[pos] += 1
            else:
                # QUITAR carta existente
                nonzero_positions = np.where(mutated > 0)[0]
                if len(nonzero_positions) > 0:
                    pos = random.choice(nonzero_positions)
                    mutated[pos] -= 1

        return self.adjust_deck_size(mutated)
    
    def mutate_categorical(self, deck_array):
        """Mutación por categorías: intercambia cartas dentro del mismo tipo"""
        if random.random() > self.mutation_rate:
            return deck_array.copy()

        mutated = deck_array.copy()

        # Seleccionar una categoría aleatoria para mutar
        available_categories = []

        # Verificar qué categorías están disponibles en los índices
        if hasattr(self, 'type_indices'):
            for category, indices in self.type_indices.items():
                if len(indices) > 1:  # Solo categorías con múltiples cartas
                    available_categories.append(('type', category, indices))

        if hasattr(self, 'color_indices'):
            for color, indices in self.color_indices.items():
                if len(indices) > 1:  # Solo colores con múltiples cartas
                    available_categories.append(('color', color, indices))

        if not available_categories:
            # Si no hay categorías, hacer mutación simple
            return self.mutate_add_remove(mutated)

        # Elegir categoría aleatoria
        category_type, category_name, category_indices = random.choice(available_categories)

        num_swaps = random.randint(1, 2)
        for _ in range(num_swaps):
            # Encontrar cartas de esta categoría que están en el mazo
            current_cards = [i for i in category_indices if mutated[i] > 0]
            # Encontrar cartas de esta categoría que NO están al máximo
            available_cards = [i for i in category_indices if mutated[i] < 4]

            if len(current_cards) > 0 and len(available_cards) > 0:
                # Estrategia 1: Reemplazar una carta por otra (70% del tiempo)
                if random.random() < 0.7 and len(current_cards) > 0:
                    remove_from = random.choice(current_cards)
                    add_to = random.choice([i for i in available_cards if i != remove_from])

                    if add_to:  # Verificar que encontramos una carta válida
                        mutated[remove_from] -= 1
                        mutated[add_to] += 1

                # Estrategia 2: Solo añadir carta nueva de la categoría (30% del tiempo)
                else:
                    add_to = random.choice(available_cards)
                    mutated[add_to] += 1

        return self.adjust_deck_size(mutated)
    
    def mutate_hybrid(self, deck_array):
        """Mutación híbrida que combina las tres estrategias"""
        if random.random() > self.mutation_rate:
            return deck_array.copy()

        # Elegir estrategia de mutación aleatoriamente con pesos
        strategies = ['swap', 'add_remove', 'categorical']
        weights = [0.3, 0.5, 0.2]  # Favorecer add_remove para más exploración

        strategy = random.choices(strategies, weights=weights)[0]

        if strategy == 'swap':
            return self.mutate_swap(deck_array)
        elif strategy == 'add_remove':
            return self.mutate_add_remove(deck_array)
        else:  # categorical
            return self.mutate_categorical(deck_array)
        
    def mutate_adaptive(self, deck_array, generation=0, stagnation_counter=0):
        """Mutación adaptiva que cambia estrategia según el progreso del algoritmo"""
        if random.random() > self.mutation_rate:
            return deck_array.copy()

        # Adaptar estrategia según el estado del algoritmo
        if stagnation_counter > 10:
            # Si hay mucho estancamiento, favorecer exploración agresiva
            strategies = ['add_remove', 'categorical', 'swap']
            weights = [0.6, 0.3, 0.1]
        elif stagnation_counter > 5:
            # Estancamiento moderado, aumentar exploración
            strategies = ['add_remove', 'swap', 'categorical']
            weights = [0.5, 0.3, 0.2]
        elif generation > 50:
            # Generaciones avanzadas, equilibrar exploración y explotación
            strategies = ['swap', 'add_remove', 'categorical']
            weights = [0.4, 0.4, 0.2]
        else:
            # Generaciones iniciales, favorecer exploración
            strategies = ['add_remove', 'categorical', 'swap']
            weights = [0.5, 0.3, 0.2]

        strategy = random.choices(strategies, weights=weights)[0]

        if strategy == 'swap':
            return self.mutate_swap(deck_array)
        elif strategy == 'add_remove':
            return self.mutate_add_remove(deck_array)
        else:  # categorical
            return self.mutate_categorical(deck_array)

    def mutate(self, deck_array, generation=0, stagnation_counter=0):
        """
        Función de mutación principal
        Args:
            deck_array: Array del mazo a mutar
            generation: Generación actual (opcional)
            stagnation_counter: Contador de estancamiento (opcional)

        Returns:
            Array mutado
        """
        # Usar mutación adaptiva si se proporcionan parámetros de control
        if generation > 0 or stagnation_counter > 0:
            return self.mutate_adaptive(deck_array, generation, stagnation_counter)
        else:
            # Usar mutación híbrida estándar
            return self.mutate_hybrid(deck_array)
    
    def adjust_deck_size(self, deck_array):
        """Ajusta el array para que tenga exactamente 60 cartas"""
        total = np.sum(deck_array)
        
        if total == 60:
            return deck_array
        
        adjusted = deck_array.copy()
        
        if total < 60:
            diff = 60 - total
            land_count = sum(adjusted[i] for i in range(self.total_cards) 
                           if self.card_catalog[i]['is_land'])
            
            if land_count < 20:
                basic_lands = [i for i, card in self.card_catalog.items() 
                             if card.get('is_basic_land', False)]
                for _ in range(min(diff, 20 - land_count)):
                    if basic_lands:
                        land_id = random.choice(basic_lands)
                        adjusted[land_id] += 1
                        diff -= 1
            
            while diff > 0:
                valid_positions = np.where(
                    (adjusted < 4) | 
                    np.array([self.card_catalog[i]['is_basic_land'] 
                             for i in range(self.total_cards)])
                )[0]
                
                if len(valid_positions) > 0:
                    pos = random.choice(valid_positions)
                    adjusted[pos] += 1
                    diff -= 1
                else:
                    break
        
        else:  # total > 60
            diff = total - 60
            while diff > 0:
                nonzero_positions = np.where(adjusted > 0)[0]
                if len(nonzero_positions) > 0:
                    pos = random.choice(nonzero_positions)
                    adjusted[pos] -= 1
                    diff -= 1
                else:
                    break
        
        return adjusted
    
    def tournament_selection(self, population_arrays, fitness_values):
        """Selección por torneo"""
        tournament_indices = random.sample(range(len(population_arrays)), 
                                         min(self.tournament_size, len(population_arrays)))
        
        tournament_fitness = [fitness_values[i] for i in tournament_indices]
        winner_idx = tournament_indices[tournament_fitness.index(max(tournament_fitness))]
        
        return population_arrays[winner_idx].copy()
    
    def calculate_diversity(self, population_arrays):
        """Calcula la diversidad de la población"""
        card_frequencies = np.zeros(self.total_cards)
        
        for array in population_arrays:
            card_frequencies += (array > 0).astype(int)
        
        card_frequencies = card_frequencies / len(population_arrays)
        diverse_cards = np.sum((card_frequencies > 0.2) & (card_frequencies < 0.8))
        total_used_cards = np.sum(card_frequencies > 0)
        
        if total_used_cards > 0:
            diversity = diverse_cards / total_used_cards
        else:
            diversity = 0.0
        
        return diversity
    
    def adaptive_mutation_rate(self, generation, stagnation_counter):
        """Ajusta la tasa de mutación según el progreso"""
        base_rate = self.mutation_rate
        
        if stagnation_counter > 5:
            base_rate *= 1.5
        if stagnation_counter > 10:
            base_rate *= 2.0
        
        if generation > 50 and stagnation_counter < 3:
            base_rate *= 0.8
        
        return min(0.3, base_rate)
    
    def update_hall_of_fame(self, fitness_values, population_arrays):
        """
        Actualiza el Hall of Fame global con los mejores individuos históricos

        Args:
            fitness_values (list): Fitness de la generación actual
            population_arrays (list): Arrays de mazos de la generación actual
        """
        # Combinar candidatos actuales con hall of fame existente
        current_candidates = [(fitness_values[i], population_arrays[i].copy()) 
                             for i in range(len(fitness_values))]

        all_candidates = self.hall_of_fame_arrays + current_candidates

        # Ordenar por fitness (mayor a menor)
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        # Eliminar duplicados exactos y mantener solo los mejores únicos
        unique_best = []
        seen_hashes = set()

        for fitness, array in all_candidates:
            # Crear hash único del array para detectar duplicados
            array_hash = hash(array.tobytes())

            if array_hash not in seen_hashes and len(unique_best) < self.max_hall_size:
                unique_best.append((fitness, array))
                seen_hashes.add(array_hash)

        # Actualizar hall of fame
        old_size = len(self.hall_of_fame_arrays)
        self.hall_of_fame_arrays = unique_best
        new_size = len(self.hall_of_fame_arrays)

        # Log de cambios
        if new_size > old_size:
            self.logger.info(f"🏆 Hall of Fame expandido: {old_size} → {new_size}")

        if len(unique_best) > 0:
            best_fitness = unique_best[0][0]
            worst_fitness = unique_best[-1][0]
            self.logger.debug(f"Hall of Fame: Mejor={best_fitness:.4f}, Peor={worst_fitness:.4f}")
    
    def evolve(self):
        """Ejecuta el algoritmo genético completo con paralelización y anti-estancamiento"""
        self.logger.info("=== INICIANDO ALGORITMO GENÉTICO CON ANTI-ESTANCAMIENTO ===")
        self.logger.info(f"Configuración: {self.population_size} mazos, {self.max_generations} generaciones")
        self.logger.info(f"Paralelización: {self.max_workers} workers, timeout {self.base_timeout}s")

        termination_reason = "max_generations_reached"
        best_deck = None

        try:
            # Evaluación inicial mediante torneo paralelo
            self.logger.info("Evaluando población inicial con procesamiento paralelo...")
            fitness_values = self.evaluate_population_tournament_parallel(self.population_arrays, 0)
            self.save_population_arrays(0)  # ← NUEVA LÍNEA

            # Variables de control mejoradas
            best_fitness_ever = max(fitness_values)
            self.stagnation_counter = 0
            generations_since_intervention = 0
            self.current_fitness_values = fitness_values  # ← NUEVA LÍNEA

            # Actualizar Hall of Fame inicial
            self.update_hall_of_fame(fitness_values, self.population_arrays)

            # BUCLE PRINCIPAL CON CONTROL DE TERMINACIÓN MEJORADO
            for generation in range(1, self.max_generations + 1):
                self.current_generation = generation
                self.logger.info(f"\n=== GENERACIÓN {generation} ===")

                # === CREAR NUEVA GENERACIÓN (código existente) ===
                new_population = []

                # Preservar elite del Hall of Fame
                hof_preserved = 0
                if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 0:
                    elite_to_preserve = min(self.elite_size, len(self.hall_of_fame_arrays))
                    for i in range(elite_to_preserve):
                        if hof_preserved < self.elite_size:
                            fitness, elite_array = self.hall_of_fame_arrays[i]
                            new_population.append(elite_array.copy())
                            hof_preserved += 1

                # Calcular tasa de mutación adaptiva
                current_mutation_rate = self.adaptive_mutation_rate(generation, self.stagnation_counter)

                # Generar el resto de la población
                while len(new_population) < self.population_size:
                    # Selección
                    parent1 = self.tournament_selection(self.population_arrays, fitness_values)
                    parent2 = self.tournament_selection(self.population_arrays, fitness_values)

                    # Cruce
                    if random.random() < self.crossover_rate:
                        if random.random() < 0.5:
                            child1, child2 = self.crossover_uniform(parent1, parent2)
                        else:
                            child1, child2 = self.crossover_two_point(parent1, parent2)
                    else:
                        child1, child2 = parent1.copy(), parent2.copy()

                    # Mutación
                    if random.random() < current_mutation_rate:
                        child1 = self.mutate(child1, generation, self.stagnation_counter)

                    if random.random() < current_mutation_rate:
                        child2 = self.mutate(child2, generation, self.stagnation_counter)

                    new_population.append(child1)
                    if len(new_population) < self.population_size:
                        new_population.append(child2)

                # Actualizar población
                self.population_arrays = new_population

                # === EVALUAR NUEVA GENERACIÓN ===
                fitness_values = self.evaluate_population_tournament_parallel(self.population_arrays, generation)
                self.save_population_arrays(generation)  # ← NUEVA LÍNEA
                self.current_fitness_values = fitness_values  # ← NUEVA LÍNEA

                # Actualizar Hall of Fame
                self.update_hall_of_fame(fitness_values, self.population_arrays)

                # === ACTUALIZAR ESTADÍSTICAS ===
                current_best = max(fitness_values)

                if current_best > best_fitness_ever:
                    best_fitness_ever = current_best
                    self.best_fitness_ever = current_best
                    self.stagnation_counter = 0
                    self.logger.info(f"🎉 NUEVO MEJOR FITNESS: {current_best:.4f}")

                    # Restaurar tasa de mutación si había intervención
                    if generations_since_intervention > 0:
                        self.restore_mutation_rate()
                        generations_since_intervention = 0
                else:
                    self.stagnation_counter += 1
                    self.logger.info(f"📊 Sin mejora. Estancamiento: {self.stagnation_counter}/{self.stagnation_limit}")

                # === VERIFICAR CONDICIONES DE TERMINACIÓN ===
                should_continue, reason, apply_intervention = self.handle_termination_conditions(
                    generation, current_best, self.stagnation_counter
                )

                if apply_intervention:
                    # Aplicar intervención anti-estancamiento
                    self.apply_anti_stagnation_intervention(generation)
                    generations_since_intervention = 1
                    # Continuar después de la intervención
                    continue
                
                if not should_continue:
                    termination_reason = reason
                    self.logger.info(f"🏁 TERMINACIÓN CONTROLADA: {termination_reason}")
                    break
                
                # Incrementar contador de generaciones desde intervención
                if generations_since_intervention > 0:
                    generations_since_intervention += 1
                    # Restaurar mutación después de 3 generaciones
                    if generations_since_intervention >= 3:
                        self.restore_mutation_rate()
                        generations_since_intervention = 0

            # === OBTENER MEJOR RESULTADO CON VERIFICACIÓN ===
            best_deck, final_fitness = self.get_final_best_result()

            # VERIFICACIÓN ADICIONAL: Comparar con best_fitness_ever
            if hasattr(self, 'best_fitness_ever'):
                if final_fitness != self.best_fitness_ever:
                    self.logger.warning(f"⚠️ Discrepancia en fitness final:")
                    self.logger.warning(f"   Hall of Fame: {final_fitness:.4f}")
                    self.logger.warning(f"   Best Ever: {self.best_fitness_ever:.4f}")

                    # Usar el mayor de los dos
                    if self.best_fitness_ever > final_fitness:
                        final_fitness = self.best_fitness_ever
                        self.logger.info(f"✅ Usando best_fitness_ever: {final_fitness:.4f}")

            self.logger.info(f"🏆 MEJOR FITNESS ALCANZADO: {final_fitness:.4f}")
            self.logger.info(f"🎯 RAZÓN DE TERMINACIÓN: {termination_reason}")

        except KeyboardInterrupt:
            self.logger.info("=== EJECUCIÓN INTERRUMPIDA POR EL USUARIO ===")
            termination_reason = "user_interrupt"
            # Crear un deck básico si no hay mejor disponible
            if best_deck is None and len(self.population_arrays) > 0:
                best_deck = self.array_to_deck(self.population_arrays[0], "Interrupted_Deck")

        except Exception as e:
            self.logger.error(f"Error durante la evolución: {e}")
            termination_reason = f"error: {str(e)}"
            # Crear un deck básico si no hay mejor disponible
            if best_deck is None and len(self.population_arrays) > 0:
                best_deck = self.array_to_deck(self.population_arrays[0], "Error_Recovery_Deck")

        finally:
            # === GARANTIZAR EJECUCIÓN DE MÉTODOS FINALES ===
            self.logger.info("🔄 Ejecutando métodos de finalización...")

            try:
                self.save_statistics()
                self.logger.info("✅ save_statistics() ejecutado correctamente")
            except Exception as e:
                self.logger.error(f"Error en save_statistics(): {e}")

            try:
                self.save_final_logs()
                self.logger.info("✅ save_final_logs() ejecutado correctamente")
            except Exception as e:
                self.logger.error(f"Error en save_final_logs(): {e}")

            try:
                final_file = self.save_final_population()
                if final_file:
                    self.logger.info(f"✅ save_final_population() ejecutado: {final_file}")
            except Exception as e:
                self.logger.error(f"Error en save_final_population(): {e}")

        return best_deck
    
    def save_final_logs(self):
        """Guarda logs finales de la ejecución paralela"""
        self.logger.info("Guardando logs finales paralelos...")
        
        # Estadísticas de paralelización
        parallelization_stats = {
            'max_workers_used': self.max_workers,
            'parallel_batch_size': self.parallel_batch_size,
            'adaptive_timeout_final': self.adaptive_timeout,
            'base_timeout': self.base_timeout,
            'save_forge_outputs': self.save_forge_outputs
        }
        
        # Guardar estadísticas de generaciones con info de paralelización
        generation_stats_file = os.path.join(self.logs_dir, "parallel_generation_statistics.json")
        with open(generation_stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                'parallelization_config': parallelization_stats,
                'generation_stats': self.generation_stats
            }, f, ensure_ascii=False, indent=2)
        
        # Guardar detalles de combates
        with open(self.match_details_file, 'w', encoding='utf-8') as f:
            json.dump(self.combat_log, f, ensure_ascii=False, indent=2)
        
        # Estadísticas finales
        total_matches = len(self.combat_log)
        successful_matches = len([m for m in self.combat_log if m['winner'] not in ['TIMEOUT', 'ERROR']])
        
        # Análisis de rendimiento por worker
        worker_stats = {}
        for match in self.combat_log:
            worker_id = match.get('worker_id', 'unknown')
            if worker_id not in worker_stats:
                worker_stats[worker_id] = {'total': 0, 'successful': 0, 'avg_duration': 0}
            
            worker_stats[worker_id]['total'] += 1
            if match['winner'] not in ['TIMEOUT', 'ERROR']:
                worker_stats[worker_id]['successful'] += 1
                worker_stats[worker_id]['avg_duration'] += match['duration']
        
        # Calcular promedios
        for worker_id, stats in worker_stats.items():
            if stats['successful'] > 0:
                stats['avg_duration'] = stats['avg_duration'] / stats['successful']
            stats['success_rate'] = stats['successful'] / stats['total'] if stats['total'] > 0 else 0
        
        self.logger.info(f"=== ESTADÍSTICAS FINALES PARALELAS ===")
        self.logger.info(f"Workers utilizados: {self.max_workers}")
        self.logger.info(f"Total de combates: {total_matches}")
        self.logger.info(f"Combates exitosos: {successful_matches}")
        if total_matches > 0:
            self.logger.info(f"Tasa de éxito global: {successful_matches/total_matches*100:.1f}%")
        
        self.logger.info("Rendimiento por worker:")
        for worker_id, stats in worker_stats.items():
            self.logger.info(f"  Worker {worker_id}: {stats['successful']}/{stats['total']} "
                           f"({stats['success_rate']*100:.1f}%) - "
                           f"Promedio: {stats['avg_duration']:.1f}s")
        
        self.logger.info(f"Logs guardados en: {self.logs_dir}")
    
    def save_best_deck(self, deck, generation):
        """Guarda el mejor mazo encontrado en ambos formatos"""
        self.logger.info(f"Guardando mejor mazo de generación {generation}")
        
        # Formato JSON
        json_file = os.path.join(self.output_dir, f"best_deck_gen_{generation}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(deck, f, ensure_ascii=False, indent=2)
        
        # Formato Forge (.dck) - CORREGIDO
        forge_file = os.path.join(self.output_dir, f"best_deck_gen_{generation}.dck")
        try:
            self.save_forge_deck(deck, forge_file)
            self.logger.info(f"Mejor mazo guardado: {json_file} y {forge_file}")
        except Exception as e:
            self.logger.error(f"Error guardando archivo .dck: {e}")
            self.logger.info(f"Mejor mazo guardado solo en JSON: {json_file}")
            
    def analyze_generation_debug(self, generation, fitness_values):
        """Debug detallado de cada generación"""
        print(f"\n🔍 === DEBUG GENERACIÓN {generation} ===")

        # 1. Estadísticas básicas de fitness
        print(f"📊 FITNESS STATS:")
        print(f"   Mejor: {max(fitness_values):.4f}")
        print(f"   Promedio: {np.mean(fitness_values):.4f}")
        print(f"   Peor: {min(fitness_values):.4f}")
        print(f"   Mediana: {np.median(fitness_values):.4f}")

        # 2. Distribución de fitness
        high = len([f for f in fitness_values if f > 0.70])
        medium_high = len([f for f in fitness_values if 0.60 < f <= 0.70])
        medium = len([f for f in fitness_values if 0.50 < f <= 0.60])
        low = len([f for f in fitness_values if f <= 0.50])

        print(f"📈 DISTRIBUCIÓN FITNESS:")
        print(f"   >0.70 (Alto): {high} mazos ({high/len(fitness_values)*100:.1f}%)")
        print(f"   0.60-0.70 (Medio-Alto): {medium_high} mazos ({medium_high/len(fitness_values)*100:.1f}%)")
        print(f"   0.50-0.60 (Medio): {medium} mazos ({medium/len(fitness_values)*100:.1f}%)")
        print(f"   ≤0.50 (Bajo): {low} mazos ({low/len(fitness_values)*100:.1f}%)")

        # 3. Top mazos
        top_indices = np.argsort(fitness_values)[-5:]  # Top 5
        print(f"🏆 TOP 5 MAZOS:")
        for i, idx in enumerate(reversed(top_indices)):
            print(f"   {i+1}. Mazo {idx}: {fitness_values[idx]:.4f}")

        # 4. Análisis de cartas populares
        card_usage = np.zeros(self.total_cards)
        for array in self.population_arrays:
            card_usage += (array > 0).astype(int)

        used_cards = np.sum(card_usage > 0)
        common_cards = np.sum(card_usage > len(self.population_arrays) * 0.5)  # En >50% mazos
        staple_cards = np.sum(card_usage > len(self.population_arrays) * 0.8)  # En >80% mazos

        print(f"🃏 USO DE CARTAS:")
        print(f"   Cartas usadas: {used_cards}/{self.total_cards}")
        print(f"   Cartas comunes (>50% mazos): {common_cards}")
        print(f"   Cartas staple (>80% mazos): {staple_cards}")

        # 5. Verificar propagación genética
        if generation > 0:
            print(f"🧬 PROPAGACIÓN GENÉTICA:")
            improvement = max(fitness_values) - max(self.stats['best_fitness'])
            avg_improvement = np.mean(fitness_values) - self.stats['avg_fitness'][-1] if self.stats['avg_fitness'] else 0

            print(f"   Mejora del mejor: {improvement:+.4f}")
            print(f"   Mejora del promedio: {avg_improvement:+.4f}")

            if improvement <= 0 and avg_improvement <= 0.01:
                print(f"   ⚠️  POSIBLE ESTANCAMIENTO")
            elif avg_improvement > 0.05:
                print(f"   ✅ EVOLUCIÓN SALUDABLE")

        # 6. Calcular diversidad actual
        current_diversity = self.calculate_diversity(self.population_arrays)
        print(f"🌈 DIVERSIDAD: {current_diversity:.4f}")

        if current_diversity < 0.01:
            print(f"   🚨 DIVERSIDAD CRÍTICA - Convergencia prematura")
        elif current_diversity > 0.20:
            print(f"   ⚠️  DIVERSIDAD ALTA - Falta convergencia")
        else:
            print(f"   ✅ DIVERSIDAD SALUDABLE")

        print(f"=" * 50)
        
    def debug_hall_of_fame(self, generation, fitness_values):
        """Debug del estado del Hall of Fame"""
        if not self.hall_of_fame_arrays:
            self.logger.warning(f"Gen {generation}: Hall of Fame vacío!")
            return

        self.logger.info(f"🏆 === HALL OF FAME GEN {generation} ===")
        for i, (fitness, _) in enumerate(self.hall_of_fame_arrays[:3]):  # Top 3
            self.logger.info(f"   {i+1}. Fitness histórico: {fitness:.4f}")

        historical_best = self.hall_of_fame_arrays[0][0]
        current_best = max(fitness_values) if 'fitness_values' in locals() else 0

        self.logger.info(f"   Mejor histórico: {historical_best:.4f}")
        self.logger.info(f"   Mejor actual: {current_best:.4f}")

        if current_best < historical_best - 0.01:
            self.logger.info(f"   ✅ Sin regresión - Hall of Fame funciona")
        else:
            self.logger.info(f"   🎉 Posible mejora o mantenimiento")    
    
    def save_statistics(self):
        """Guarda estadísticas de evolución"""
        # Crear DataFrame
        stats_df = pd.DataFrame({
            'generation': range(len(self.stats['best_fitness'])),
            'best_fitness': self.stats['best_fitness'],
            'avg_fitness': self.stats['avg_fitness'],
            'diversity': self.stats['diversity'],
            'mutation_rate': self.stats['mutation_rate']
        })
        
        # Guardar CSV
        csv_file = os.path.join(self.output_dir, "parallel_evolution_stats.csv")
        stats_df.to_csv(csv_file, index=False)
        
        # Crear gráficos
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # Fitness
        ax1.plot(stats_df['generation'], stats_df['best_fitness'], 'b-', linewidth=2, label='Mejor')
        ax1.plot(stats_df['generation'], stats_df['avg_fitness'], 'r--', linewidth=2, label='Promedio')
        ax1.set_xlabel('Generación')
        ax1.set_ylabel('Fitness')
        ax1.set_title('Evolución del Fitness (Paralelo)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Diversidad
        ax2.plot(stats_df['generation'], stats_df['diversity'], 'g-', linewidth=2)
        ax2.set_xlabel('Generación')
        ax2.set_ylabel('Diversidad')
        ax2.set_title('Evolución de la Diversidad')
        ax2.grid(True, alpha=0.3)
        
        # Tasa de mutación
        ax3.plot(stats_df['generation'], stats_df['mutation_rate'], 'm-', linewidth=2)
        ax3.set_xlabel('Generación')
        ax3.set_ylabel('Tasa de Mutación')
        ax3.set_title('Tasa de Mutación Adaptativa')
        ax3.grid(True, alpha=0.3)
        
        # Hall of Fame
        if self.hall_of_fame:
            hof_gens = [x[0] for x in self.hall_of_fame]
            hof_fitness = [x[1] for x in self.hall_of_fame]
            ax4.scatter(hof_gens, hof_fitness, c='red', s=100, marker='*')
            ax4.set_xlabel('Generación')
            ax4.set_ylabel('Fitness')
            ax4.set_title(f'Hall of Fame (Workers: {self.max_workers})')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "parallel_evolution_stats.png"), dpi=150)
        plt.close()
        
        # Guardar Hall of Fame
        hof_file = os.path.join(self.output_dir, "parallel_hall_of_fame.json")
        hof_data = []
        for gen, fitness, deck in self.hall_of_fame:
            hof_data.append({
                'generation': gen,
                'fitness': fitness,
                'deck_name': deck['name'],
                'colors': deck['colors'],
                'stats': deck['stats'],
                'parallel_workers': self.max_workers
            })
        
        with open(hof_file, 'w', encoding='utf-8') as f:
            json.dump(hof_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Estadísticas paralelas guardadas en {self.output_dir}")
        
    def get_starting_player(self, i, j, generation):
        """
        Determina quién empieza de manera determinística pero balanceada
        """
        seed = hash((i, j, generation)) % 2
        return seed == 0    
    
    def handle_termination_conditions(self, generation, current_best_fitness, stagnation_counter):
        """
        Maneja las condiciones de terminación y anti-estancamiento de forma inteligente.
        Reemplaza los break problemáticos por return controlado.

        Returns:
            tuple: (should_continue, termination_reason, apply_intervention)
        """
        # Verificar condición de fitness objetivo alcanzado
        if current_best_fitness >= 0.95:
            reason = f"Terminando por alcanzar fitness objetivo (95% win rate): {current_best_fitness:.4f}"
            self.logger.info(reason)
            return False, "fitness_target_reached", False

        # Verificar estancamiento crítico
        if stagnation_counter >= self.stagnation_limit:
            if generation < self.max_generations // 2:
                # Si estamos en la primera mitad, aplicar intervención agresiva
                reason = f"Aplicando intervención anti-estancamiento en generación {generation}"
                self.logger.warning(reason)
                return True, "stagnation_intervention", True
            else:
                # Si estamos en la segunda mitad, terminar
                reason = f"Terminando por estancamiento tras {stagnation_counter} generaciones sin mejora"
                self.logger.info(reason)
                return False, "stagnation_limit_reached", False

        # Continuar normalmente
        return True, "continue", False


    def apply_anti_stagnation_intervention(self, generation):
        """
        Sistema Anti-Estancamiento Agresivo 
        Aplica múltiples estrategias para escapar de óptimos locales.
        """
        self.logger.warning(f"🚨 APLICANDO INTERVENCIÓN ANTI-ESTANCAMIENTO en generación {generation}")

        intervention_applied = False

        # ESTRATEGIA 1: IMMIGRATION (30% de la población)
        immigration_size = max(3, self.population_size // 3)
        self.logger.info(f"🌍 Immigration: Inyectando {immigration_size} mazos completamente nuevos")

        # Generar mazos nuevos usando el generador original
        try:
            from generador_mazos_mtg import MTGDeckGenerator

            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(os.path.dirname(self.catalog_path), "..", "processed_standard_cards.csv"),
                catalog_path=self.catalog_path,
                indices_path=self.indices_path,
                output_dir=self.output_dir
            )

            # Generar mazos frescos con diversidad forzada
            new_decks = generator.generate_population_exact_size(immigration_size)
            new_arrays = []

            for deck in new_decks:
                if 'array' in deck:
                    new_arrays.append(np.array(deck['array'], dtype=int))
                else:
                    new_arrays.append(self.deck_to_array(deck))

            # Reemplazar los peores individuos
            if hasattr(self, 'current_fitness_values') and len(self.current_fitness_values) == len(self.population_arrays):
                # Encontrar los índices de los peores
                sorted_indices = np.argsort(self.current_fitness_values)
                worst_indices = sorted_indices[:immigration_size]

                for i, worst_idx in enumerate(worst_indices):
                    if i < len(new_arrays):
                        self.population_arrays[worst_idx] = new_arrays[i].copy()
                        self.logger.debug(f"Mazo {worst_idx} reemplazado por inmigrante {i}")

                intervention_applied = True
                self.logger.info(f"✅ Immigration completada: {len(worst_indices)} mazos reemplazados")

        except Exception as e:
            self.logger.error(f"Error en immigration: {e}")

        # ESTRATEGIA 2: MUTATION BOOST (Incrementar mutación temporalmente)
        if hasattr(self, 'original_mutation_rate'):
            self.mutation_rate = self.original_mutation_rate * 3.0
        else:
            self.original_mutation_rate = self.mutation_rate
            self.mutation_rate = min(0.4, self.mutation_rate * 3.0)

        self.logger.info(f"🧬 Mutation Boost: Tasa de mutación incrementada a {self.mutation_rate:.3f}")
        intervention_applied = True

        # ESTRATEGIA 3: DIVERSITY INJECTION (Forzar diversidad en Hall of Fame)
        if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 3:
            # Seleccionar individuos diversos del Hall of Fame
            diverse_elite = self.select_diverse_elite()

            if len(diverse_elite) > 0:
                # Reemplazar algunos individuos mediocres con elite diverso
                elite_injection_size = min(len(diverse_elite), self.population_size // 4)

                if hasattr(self, 'current_fitness_values'):
                    # Encontrar individuos mediocres (no los mejores ni los peores)
                    fitness_array = np.array(self.current_fitness_values)
                    median_fitness = np.median(fitness_array)

                    # Buscar individuos cerca de la mediana
                    median_tolerance = np.std(fitness_array) * 0.5
                    mediocre_mask = np.abs(fitness_array - median_fitness) <= median_tolerance
                    mediocre_indices = np.where(mediocre_mask)[0]

                    if len(mediocre_indices) >= elite_injection_size:
                        selected_mediocre = np.random.choice(mediocre_indices, elite_injection_size, replace=False)

                        for i, mediocre_idx in enumerate(selected_mediocre):
                            if i < len(diverse_elite):
                                self.population_arrays[mediocre_idx] = diverse_elite[i].copy()
                                self.logger.debug(f"Individuo mediocre {mediocre_idx} reemplazado por elite diverso")

                        intervention_applied = True
                        self.logger.info(f"✅ Diversity Injection: {len(selected_mediocre)} individuos reemplazados")

        # ESTRATEGIA 4: RESET STAGNATION COUNTER (Dar otra oportunidad)
        self.stagnation_counter = 0
        self.logger.info(f"🔄 Stagnation counter reseteado")

        # Marcar que se aplicó intervención
        if intervention_applied:
            # Agregar marca temporal en logs
            if not hasattr(self, 'interventions_applied'):
                self.interventions_applied = []

            self.interventions_applied.append({
                'generation': generation,
                'strategies': ['immigration', 'mutation_boost', 'diversity_injection'],
                'timestamp': time.time()
            })

            self.logger.warning(f"🚀 INTERVENCIÓN ANTI-ESTANCAMIENTO COMPLETADA en generación {generation}")

        return intervention_applied


    def select_diverse_elite(self):
        """
        Selecciona individuos diversos del Hall of Fame basado en distancia genética.
        """
        if not hasattr(self, 'hall_of_fame_arrays') or len(self.hall_of_fame_arrays) < 2:
            return []

        # Extraer solo los arrays del Hall of Fame
        hof_arrays = [hof_array for _, hof_array in self.hall_of_fame_arrays]

        if len(hof_arrays) <= 3:
            return hof_arrays

        # Selección por diversidad usando distancia hamming
        selected = [hof_arrays[0]]  # Siempre incluir el mejor

        for candidate in hof_arrays[1:]:
            # Calcular distancia mínima a los ya seleccionados
            min_distance = float('inf')

            for selected_array in selected:
                # Distancia basada en cartas diferentes
                different_cards = np.sum(candidate != selected_array)
                min_distance = min(min_distance, different_cards)

            # Si es suficientemente diferente, agregarlo
            diversity_threshold = len(candidate) * 0.1  # Al menos 10% de cartas diferentes
            if min_distance >= diversity_threshold and len(selected) < 4:
                selected.append(candidate)

        self.logger.debug(f"Elite diverso seleccionado: {len(selected)} individuos de {len(hof_arrays)} disponibles")
        return selected


    def restore_mutation_rate(self):
        """
        Restaura la tasa de mutación original después de la intervención.
        """
        if hasattr(self, 'original_mutation_rate'):
            old_rate = self.mutation_rate
            self.mutation_rate = self.original_mutation_rate
            self.logger.info(f"🔄 Tasa de mutación restaurada: {old_rate:.3f} → {self.mutation_rate:.3f}")

    def get_final_best_result(self):
        """
        Obtiene el mejor resultado final de forma correcta
        """
        try:
            # OPCIÓN 1: Usar Hall of Fame arrays (más confiable)
            if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 0:
                best_fitness, best_array = self.hall_of_fame_arrays[0]
                best_deck = self.array_to_deck(best_array, "Champion_Deck")

                self.logger.info(f"✅ Mejor resultado obtenido del Hall of Fame:")
                self.logger.info(f"   Fitness: {best_fitness:.4f}")
                self.logger.info(f"   Array sum: {np.sum(best_array)}")

                # VERIFICAR que el fitness es correcto
                if best_fitness < 0.01:  # Si el fitness es sospechosamente bajo
                    self.logger.warning(f"⚠️ Fitness sospechosamente bajo: {best_fitness:.4f}")
                    # Buscar en hall_of_fame alternativo
                    if hasattr(self, 'hall_of_fame') and self.hall_of_fame:
                        _, alt_fitness, alt_deck = max(self.hall_of_fame, key=lambda x: x[1])
                        if alt_fitness > best_fitness:
                            self.logger.info(f"🔄 Usando hall_of_fame alternativo: {alt_fitness:.4f}")
                            return alt_deck, alt_fitness

                return best_deck, best_fitness

            # OPCIÓN 2: Usar hall_of_fame estándar
            elif hasattr(self, 'hall_of_fame') and self.hall_of_fame:
                _, best_fitness, best_deck = max(self.hall_of_fame, key=lambda x: x[1])

                self.logger.info(f"✅ Mejor resultado obtenido del Hall of Fame estándar:")
                self.logger.info(f"   Fitness: {best_fitness:.4f}")

                return best_deck, best_fitness

            # OPCIÓN 3: Usar población actual (último recurso)
            else:
                if hasattr(self, 'current_fitness_values') and self.current_fitness_values:
                    best_idx = np.argmax(self.current_fitness_values)
                    best_fitness = self.current_fitness_values[best_idx]
                    best_deck = self.array_to_deck(self.population_arrays[best_idx], "Final_Best_Deck")

                    self.logger.info(f"✅ Mejor resultado obtenido de población actual:")
                    self.logger.info(f"   Fitness: {best_fitness:.4f}")

                    return best_deck, best_fitness
                else:
                    # Fallback absoluto
                    best_deck = self.array_to_deck(self.population_arrays[0], "Fallback_Deck")
                    self.logger.warning("⚠️ Usando deck de fallback")
                    return best_deck, 0.0

        except Exception as e:
            self.logger.error(f"Error obteniendo resultado final: {e}")
            best_deck = self.array_to_deck(self.population_arrays[0], "Error_Recovery_Deck")
            return best_deck, 0.0

# FUNCIÓN WORKER PARA PARALELIZACIÓN (debe estar fuera de la clase)
def parallel_forge_combat_worker(combat_info):
    """
    Worker function para ejecutar combates en paralelo
    
    Args:
        combat_info (dict): Información del combate
            
    Returns:
        dict: Resultado del combate
    """
    import subprocess
    import time
    import os
    from datetime import datetime
    
    deck1_name = combat_info['deck1_name']
    deck2_name = combat_info['deck2_name']
    forge_jar_path = combat_info['forge_jar_path']
    forge_root = combat_info['forge_root']
    timeout = combat_info['timeout']
    match_id = combat_info['match_id']
    generation = combat_info['generation']
    forge_output_dir = combat_info.get('forge_output_dir')
    worker_id = os.getpid()
    
    start_time = time.time()
    headless_mode = combat_info.get('headless_mode', False)
    
    # Comando para ejecutar Forge
    base_cmd = [
        "java", "-jar", forge_jar_path,
        "sim",
        "-d", deck1_name, deck2_name,
        "-n", "1"
    ]
    
    if headless_mode:
        cmd = ["xvfb-run", "-a"] + base_cmd 
    else:
        cmd = base_cmd 
    
    try:
        # Ejecutar Forge
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=forge_root
        )
        
        duration = time.time() - start_time
        
        # Guardar output de Forge si está habilitado
        forge_output_file = ""
        if forge_output_dir:
            forge_output_file = f"{match_id}.txt"
            output_path = os.path.join(forge_output_dir, forge_output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"=== COMBATE PARALELO: {deck1_name} vs {deck2_name} ===\n")
                f.write(f"Worker ID: {worker_id}\n")
                f.write(f"Comando: {' '.join(cmd)}\n")
                f.write(f"Duración: {duration:.2f} segundos\n")
                f.write(f"Return code: {result.returncode}\n\n")
                f.write("=== STDOUT ===\n")
                f.write(result.stdout)
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr)
        
        # Parsear resultados
        output = result.stdout
        deck1_wins = 0
        deck2_wins = 0
        game_results = []
        
        # Buscar victorias
        for line in output.split('\n'):
            if "has won!" in line:
                if deck1_name in line:
                    deck1_wins += 1
                    game_results.append(f"Victoria: {deck1_name}")
                elif deck2_name in line:
                    deck2_wins += 1
                    game_results.append(f"Victoria: {deck2_name}")
        
        # Determinar ganador
        if deck1_wins > deck2_wins:
            winner = deck1_name
            return_value = 1
        elif deck2_wins > deck1_wins:
            winner = deck2_name
            return_value = 0
        else:
            winner = "EMPATE"
            return_value = 0
        
        return {
            'success': True,
            'match_id': match_id,
            'generation': generation,
            'deck1_name': deck1_name,
            'deck2_name': deck2_name,
            'winner': winner,
            'deck1_wins': deck1_wins,
            'deck2_wins': deck2_wins,
            'duration': duration,
            'worker_id': worker_id,
            'forge_output_file': forge_output_file,
            'error_message': '',
            'game_results': game_results,
            'return_value': return_value,
            'timestamp': datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return {
            'success': False,
            'match_id': match_id,
            'generation': generation,
            'deck1_name': deck1_name,
            'deck2_name': deck2_name,
            'winner': 'TIMEOUT',
            'deck1_wins': 0,
            'deck2_wins': 0,
            'duration': duration,
            'worker_id': worker_id,
            'forge_output_file': '',
            'error_message': f'Timeout después de {timeout}s',
            'game_results': [],
            'return_value': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        duration = time.time() - start_time
        return {
            'success': False,
            'match_id': match_id,
            'generation': generation,
            'deck1_name': deck1_name,
            'deck2_name': deck2_name,
            'winner': 'ERROR',
            'deck1_wins': 0,
            'deck2_wins': 0,
            'duration': duration,
            'worker_id': worker_id,
            'forge_output_file': '',
            'error_message': str(e),
            'game_results': [],
            'return_value': 0,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # EJEMPLO DE USO DIRECTO (normalmente se llamaría desde mtg_main.py)
    config = {
        'population_file': "mtg_decks/test_population.json",
        'catalog_path': "mtg_data/card_catalog.json",
        'indices_path': "mtg_data/card_indices.json",
        'output_dir': "mtg_evolved_decks",
        'forge_jar_path': "./forge-gui-desktop.jar",
        'max_generations': 3,
        'population_size': 8,
        'mutation_rate': 0.05,
        'crossover_rate': 0.9,
        'tournament_size': 3,
        'elite_size': 2,
        'stagnation_limit': 5,
        # PARÁMETROS DE PARALELIZACIÓN (normalmente pasados desde mtg_main.py)
        'max_workers': 4,           # Configurado por hardware analyzer
        'parallel_batch_size': 12,  # Configurado por hardware analyzer
        'base_timeout': 120,        # Configurado por hardware analyzer
        'log_level': 'INFO',        # Configurado por hardware analyzer
        'save_forge_outputs': True  # Configurado por hardware analyzer
    }
    
    print("🚀 === ALGORITMO GENÉTICO MTG PARALELO ===")
    print(f"Configuración: {config['population_size']} mazos, {config['max_generations']} generaciones")
    print(f"Paralelización: {config['max_workers']} workers")
    
    # Ejecutar algoritmo
    ga = MTGGeneticAlgorithm(**config)
    best_deck = ga.evolve()
    
    # Mostrar resultado
    print("\n🏆 ===== MEJOR MAZO ENCONTRADO =====")
    print(f"Nombre: {best_deck['name']}")
    print(f"Colores: {', '.join(best_deck['colors'])}")
    print(f"Estadísticas: {best_deck['stats']}")
    print("\nCartas principales:")
    for card in sorted(best_deck['cards'], key=lambda x: (x['cmc'], x['name']))[:10]:
        print(f"  {card['count']}x {card['name']} ({card.get('mana_cost', 'N/A')})")
    
    print(f"\n✅ Logs paralelos guardados en: mtg_evolved_decks/logs/")