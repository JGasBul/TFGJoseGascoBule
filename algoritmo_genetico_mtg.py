"""
Algoritmo Genético para Optimización de Mazos de Magic: The Gathering

Este módulo implementa un algoritmo genético paralelizado para evolucionar poblaciones
de mazos de Magic hacia estrategias ganadoras. Utiliza Forge como simulador de combates
y aplica operadores genéticos (selección, cruce, mutación) con mecanismos anti-estancamiento.

Características principales:
- Evaluación paralela de fitness mediante torneos round-robin
- Hall of Fame para preservar mejores soluciones históricas
- Mutación adaptativa según el progreso evolutivo
- Sistema anti-estancamiento con immigration y diversity injection
- Guardado incremental de estadísticas y poblaciones

Autor: Proyecto TFG - Algoritmos Genéticos aplicados a MTG
"""

# ==================================================================================
# IMPORTS
# ==================================================================================

# Librería estándar
import os
import json
import random
import subprocess
import sys
import time
import logging
import csv
import threading
from datetime import datetime
from collections import defaultdict

# Librerías de terceros
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# Configuración de matplotlib para entornos sin GUI
matplotlib.use('Agg')


# ==================================================================================
# CLASE PRINCIPAL DEL ALGORITMO GENÉTICO
# ==================================================================================

class MTGGeneticAlgorithm:
    """
    Algoritmo Genético Paralelo para Optimización de Mazos de Magic: The Gathering

    Esta clase implementa un algoritmo genético completo que evoluciona poblaciones de
    mazos de MTG utilizando Forge como simulador de combates. Incluye características
    avanzadas como paralelización, hall of fame, mutación adaptativa y anti-estancamiento.
    """
    def __init__(self,
                 population_file="mtg_decks/initial_population.json",
                 catalog_path="mtg_data/card_catalog.json",
                 indices_path="mtg_data/card_indices.json",
                 output_dir="mtg_evolved_decks",
                 forge_jar_path="./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
                 max_generations=200,
                 population_size=40,              # OPTIMIZADO: Aumentado de 20 a 40 para mejor exploración
                 mutation_rate=0.9,               # Alta exploración (call sites usan este valor; cap real 0.3 en adaptive_mutation_rate)
                 crossover_rate=0.15,             # Bajo cruce: prioriza diversidad sobre homogeneización
                 tournament_size=5,               # Optimizado: ~12% de población de 40 (antes 4 de 20)
                 elite_size=12,                   # OPTIMIZADO: 30% de población de 40 (antes 8 de 20)
                 stagnation_limit=999,            # DESACTIVADO: Evita inyección contraproducente de mazos aleatorios
                 # PARÁMETROS SWISS TOURNAMENT
                 use_swiss_tournament=True,       # Activar Swiss Tournament (False = round-robin completo)
                 k_rounds=8,                      # Rondas Swiss (fórmula: ceil(log2(pop)) + 2 = 8 para pop=40, 9 para pop=100)
                 n_games_per_match=2,             # Partidas por enfrentamiento (balance entre precisión y tiempo)
                 # PARÁMETROS DE PARALELIZACIÓN
                 max_workers=None,
                 parallel_batch_size=None,
                 base_timeout=120,
                 log_level='INFO',
                 save_forge_outputs=True,
                 headless_mode=False,
                 # PARÁMETROS DE FITNESS MULTI-COMPONENTE (optimizados)
                 fitness_alpha=0.6,               # Optimizado: win rate 60% (antes 0.7)
                 fitness_beta=0.4,                # Optimizado: calidad 40% (antes 0.3)
                 enable_quality_metrics=True):
        """
        Inicializa el algoritmo genético con todos sus parámetros

        Args:
            population_file: Ruta al archivo JSON con la población inicial
            catalog_path: Ruta al catálogo de cartas
            indices_path: Ruta a los índices de tipos y colores
            output_dir: Directorio para guardar resultados
            forge_jar_path: Ruta al archivo JAR de Forge
            max_generations: Número máximo de generaciones a evolucionar
            population_size: Tamaño de la población en cada generación
            mutation_rate: Probabilidad de mutación (0.0-1.0)
            crossover_rate: Probabilidad de cruce (0.0-1.0)
            tournament_size: Tamaño del torneo para selección
            elite_size: Número de mejores individuos a preservar
            stagnation_limit: Generaciones sin mejora antes de aplicar anti-estancamiento
            use_swiss_tournament: Usar Swiss Tournament (True) o round-robin completo (False)
            k_rounds: Número de rondas en Swiss Tournament (recomendado: ceil(log2(pop))+2)
            n_games_per_match: Partidas por enfrentamiento (1-3, recomendado: 2)
            max_workers: Workers paralelos (None = auto-detectar según CPU)
            parallel_batch_size: Tamaño de lote paralelo (None = auto-calcular)
            base_timeout: Timeout base en segundos para combates
            log_level: Nivel de logging ('DEBUG', 'INFO', 'WARNING')
            save_forge_outputs: Si guardar outputs completos de Forge
            headless_mode: Ejecutar Forge en modo headless (con xvfb-run)
            fitness_alpha: Peso del win_rate en fitness multi-componente (0.0-1.0)
            fitness_beta: Peso de la calidad del mazo en fitness multi-componente (0.0-1.0)
            enable_quality_metrics: Activar fitness multi-componente (True) o usar solo win_rate (False)
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

        # CONFIGURACIÓN SWISS TOURNAMENT
        self.use_swiss_tournament = use_swiss_tournament
        self.k_rounds = k_rounds
        self.n_games_per_match = n_games_per_match

        # CONFIGURACIÓN DE FITNESS MULTI-COMPONENTE
        self.fitness_alpha = fitness_alpha
        self.fitness_beta = fitness_beta
        self.enable_quality_metrics = enable_quality_metrics

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

        # Preparar diccionario de tierras básicas para adjust_deck_size()
        self.basic_lands_ids = {}
        basic_land_names = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']
        for card_id, card in self.card_catalog.items():
            if card['name'] in basic_land_names:
                self.basic_lands_ids[card['name']] = card_id

        self.logger.debug(f"Tierras básicas identificadas: {list(self.basic_lands_ids.keys())}")

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

        # Contador de estancamiento
        self.stagnation_counter = 0
        self.best_fitness_ever = 0

        # Hall of Fame Global - Preserva mejores soluciones históricas
        self.hall_of_fame_arrays = []  # Lista de tuplas (fitness, deck_array)
        self.max_hall_size = max(self.elite_size, 5)  # Al menos 5 mejores históricos

        # Configurar Forge
        self.setup_forge()

        # Modo de ejecución
        self.headless_mode = headless_mode
        self.logger.info(f"Modo: {'Headless (xvfb-run)' if headless_mode else 'GUI normal'}")
        self.logger.info(f"Hall of Fame configurado: {self.max_hall_size} mejores históricos")

    # ==============================================================================
    # CONFIGURACIÓN Y CARGA INICIAL
    # ==============================================================================

    def setup_logging(self, log_level):
        """Configura sistema de logging completo"""
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

    # ==============================================================================
    # CONVERSIÓN ENTRE FORMATOS (Array ↔ Deck)
    # ==============================================================================

    def deck_to_array(self, deck):
        """Convierte un mazo del formato de diccionario a array NumPy"""
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

        # NO limpiar aquí - se limpiará solo al empezar Gen 0 (nueva ejecución)
        # Si recuperamos checkpoint, queremos mantener los mazos existentes

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

    def generate_swiss_pairings(self, n_decks, k_rounds):
        """
        Genera emparejamientos estilo Swiss Tournament

        En un Swiss Tournament, cada mazo juega exactamente k_rounds partidas contra
        oponentes diferentes. Esto reduce significativamente el número de combates
        comparado con round-robin completo.

        Args:
            n_decks: Número de mazos en la población
            k_rounds: Número de rondas Swiss (cada mazo juega k partidas)

        Returns:
            Lista de tuplas (i, j) donde i < j, representando enfrentamientos

        Ejemplo:
            population_size=40, k_rounds=8
            → 160 enfrentamientos (vs 780 en round-robin completo)
            → Cada mazo juega exactamente 8 partidas
        """
        if k_rounds >= n_decks:
            # Si k >= n, hacer round-robin completo
            self.logger.warning(
                f"k_rounds={k_rounds} >= n_decks={n_decks}. "
                f"Usando round-robin completo."
            )
            return [(i, j) for i in range(n_decks) for j in range(i+1, n_decks)]

        pairings = []
        matchups_count = [0] * n_decks  # Cuántas partidas ha jugado cada mazo
        played_against = [set() for _ in range(n_decks)]  # Contra quién ha jugado cada mazo

        for round_num in range(k_rounds):
            round_pairings = []
            available = list(range(n_decks))
            random.shuffle(available)  # Aleatorizar para evitar patrones

            # Emparejar mazos en esta ronda
            while len(available) >= 2:
                # Tomar el primer mazo disponible
                deck_i = available.pop(0)

                # Buscar mejor oponente: que no haya jugado contra deck_i
                best_opponent = None
                for candidate in available:
                    if candidate not in played_against[deck_i]:
                        best_opponent = candidate
                        break

                # Si no hay oponente sin jugar, tomar cualquiera
                if best_opponent is None:
                    if len(available) > 0:
                        best_opponent = available[0]

                if best_opponent is not None:
                    available.remove(best_opponent)

                    # Registrar emparejamiento (siempre i < j)
                    deck_j = best_opponent
                    if deck_i > deck_j:
                        deck_i, deck_j = deck_j, deck_i

                    round_pairings.append((deck_i, deck_j))

                    # Actualizar contadores
                    matchups_count[deck_i] += 1
                    matchups_count[deck_j] += 1
                    played_against[deck_i].add(deck_j)
                    played_against[deck_j].add(deck_i)

            # Si queda un mazo impar, espera a siguiente ronda
            # (esto es normal en Swiss Tournament con población impar)

            pairings.extend(round_pairings)

            self.logger.debug(
                f"Swiss Round {round_num+1}/{k_rounds}: {len(round_pairings)} enfrentamientos"
            )

        # Verificar distribución
        min_games = min(matchups_count)
        max_games = max(matchups_count)
        avg_games = sum(matchups_count) / len(matchups_count)

        self.logger.info(
            f"Swiss Tournament generado: {len(pairings)} enfrentamientos totales "
            f"(min={min_games}, max={max_games}, avg={avg_games:.1f} partidas/mazo)"
        )

        return pairings

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

        # Determinar enfrentamientos según configuración
        if self.use_swiss_tournament:
            self.logger.info(f"=== SWISS TOURNAMENT MODE ===")
            self.logger.info(f"k_rounds: {self.k_rounds}")
            self.logger.info(f"n_games_per_match: {self.n_games_per_match}")
            matchups = self.generate_swiss_pairings(n_decks, self.k_rounds)
            total_enfrentamientos = len(matchups)
            total_combates = total_enfrentamientos * self.n_games_per_match
            self.logger.info(
                f"Swiss: {total_enfrentamientos} enfrentamientos × {self.n_games_per_match} combates = "
                f"{total_combates} combates totales"
            )
        else:
            self.logger.info(f"=== ROUND-ROBIN COMPLETO MODE ===")
            matchups = [(i, j) for i in range(n_decks) for j in range(i+1, n_decks)]
            total_enfrentamientos = len(matchups)
            # Por compatibilidad, mantener 3 combates en round-robin
            total_combates = total_enfrentamientos * 3
            self.logger.info(
                f"Round-robin: {total_enfrentamientos} enfrentamientos × 3 combates = "
                f"{total_combates} combates totales"
            )

        # NO limpiar mazos aquí - queremos acumular todos los mazos de todas las generaciones
        # La limpieza solo se hace manualmente al inicio de una NUEVA ejecución completa
        self.logger.info(f"Guardando mazos para generación {generation}...")

        deck_names = []
        for i, array in enumerate(population_arrays):
            deck_name = f"Gen{generation}_Deck{i}"
            deck_names.append(deck_name)
            deck = self.array_to_deck(array, deck_name)
            deck_file = os.path.join(self.forge_decks_dir, f"{deck_name}.dck")
            self.save_forge_deck(deck, deck_file)

        # Crear lista de todos los combates
        combat_tasks = []
        match_count = 0

        # Determinar número de combates por enfrentamiento
        n_games = self.n_games_per_match if self.use_swiss_tournament else 3

        for i, j in matchups:
            # Crear n_games combates para este enfrentamiento
            for game_num in range(n_games):
                match_count += 1
                match_id = f"Gen{generation}_Match{match_count}_{int(time.time())}"

                # Alternancia determinística del starter
                if self.get_starting_player(i, j, generation + game_num):
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
        if self.use_swiss_tournament:
            # Calcular reducción vs round-robin completo
            full_rr_combats = (n_decks * (n_decks - 1) // 2) * 3
            reduction_pct = ((full_rr_combats - total_combats) / full_rr_combats) * 100
            self.logger.info(
                f"Ejecutando {total_combats} combates en paralelo "
                f"({reduction_pct:.1f}% reducción vs round-robin completo)"
            )
        else:
            self.logger.info(f"Ejecutando {total_combats} combates en paralelo...")
        
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
        
        # Calcular fitness (multi-componente si está habilitado)
        fitness_values = []
        quality_values = []  # Para logging

        for i in range(n_decks):
            # Componente 1: Win rate del torneo
            if games[i] > 0:
                win_rate = wins[i] / games[i]
            else:
                win_rate = 0.0

            # Componente 2: Calidad del mazo (si está habilitado)
            if self.enable_quality_metrics:
                deck_quality = self.calculate_deck_quality(self.population_arrays[i])
                quality_values.append(deck_quality)

                # Fitness combinado: α * win_rate + β * deck_quality
                fitness = (self.fitness_alpha * win_rate) + (self.fitness_beta * deck_quality)

                self.logger.debug(
                    f"Mazo {i} ({deck_names[i]}): fitness={fitness:.4f} "
                    f"(win_rate={win_rate:.4f} [α={self.fitness_alpha}], "
                    f"quality={deck_quality:.4f} [β={self.fitness_beta}])"
                )
            else:
                # Modo legacy: solo win_rate
                fitness = win_rate
                quality_values.append(0.0)  # Placeholder

            fitness_values.append(fitness)
        
        generation_duration = time.time() - generation_start_time

        # Log de resultados
        self.logger.info(f"=== RESULTADOS GENERACIÓN {generation} ===")
        self.logger.info(f"Duración total: {generation_duration/60:.1f} minutos")
        self.logger.info(f"Combates exitosos: {successful_combats}/{total_combats}")
        self.logger.info(f"Combates fallidos: {failed_combats}")
        self.logger.info(f"Mejor fitness: {max(fitness_values):.4f}")
        self.logger.info(f"Fitness promedio: {np.mean(fitness_values):.4f}")

        # Log adicional para fitness multi-componente
        if self.enable_quality_metrics and quality_values:
            avg_quality = np.mean(quality_values)
            max_quality = max(quality_values)
            self.logger.info(
                f"Calidad de mazos: promedio={avg_quality:.4f}, máxima={max_quality:.4f} "
                f"(pesos: α={self.fitness_alpha}, β={self.fitness_beta})"
            )
        
        # Ranking de mazos
        deck_rankings = [(i, deck_names[i], fitness_values[i], wins[i], games[i])
                        for i in range(n_decks)]
        deck_rankings.sort(key=lambda x: x[2], reverse=True)

        # Mostrar Top 5 de la generación actual
        self.logger.info("📊 Top 5 de esta generación:")
        for rank, (idx, name, fitness, win_count, game_count) in enumerate(deck_rankings[:5], 1):
            self.logger.info(f"  {rank}. {name}: {fitness:.4f} ({win_count}/{game_count})")

        # Mostrar Top 5 GLOBAL (Hall of Fame)
        self.logger.info("🏆 Top 5 GLOBAL (Hall of Fame histórico):")
        if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 0:
            for rank, (fitness, array) in enumerate(self.hall_of_fame_arrays[:5], 1):
                self.logger.info(f"  {rank}. HoF #{rank}: {fitness:.4f}")
        else:
            self.logger.info("  (Hall of Fame aún vacío)")
        
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

    # ==============================================================================
    # OPERADORES GENÉTICOS (Cruce y Mutación)
    # ==============================================================================

    def crossover_uniform(self, parent1_array, parent2_array):
        """
        Cruce uniforme: cada posición del hijo se hereda aleatoriamente
        de uno de los padres con probabilidad 50/50
        """
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
    
    def _archetype_card_affinity(self, card, archetype):
        """
        Puntúa 0..2 cuánto encaja una carta con un arquetipo dado.
        Usado para decidir qué singletons consolidar a playset vs eliminar.
        """
        if card['is_land']:
            return 0
        cmc = card.get('cmc', 0)
        is_creature = card['is_creature']
        is_spell = card['is_instant'] or card['is_sorcery']

        if archetype == 'aggro':
            if is_creature and cmc <= 3:
                return 2
            if cmc <= 2:
                return 1
            return 0
        if archetype == 'control':
            if is_spell and cmc >= 2:
                return 2
            if not is_creature and cmc >= 3:
                return 1
            return 0
        # midrange
        if 2 <= cmc <= 4:
            return 2
        if cmc <= 5:
            return 1
        return 0

    def consolidate_singletons(self, deck_array, max_singletons=2):
        """
        Reduce singletons excesivos respetando el arquetipo detectado.

        Mantiene el total de cartas estable: cada promoción 1->4 añade +3,
        compensada por 3 eliminaciones 1->0. Si no hay suficientes
        singletons sobrantes para compensar, reduce el nº de promociones.

        Estrategia:
        1. Detectar arquetipo actual.
        2. Identificar singletons no-tierra y puntuarlos por afinidad.
        3. Priorizar promociones en los de mayor afinidad; eliminaciones en
           los de menor afinidad.
        4. Ajustar nº de promociones/eliminaciones para conservar el total.

        Args:
            deck_array: Array del mazo.
            max_singletons: máximo de singletons que se permite conservar
                            tras la consolidación.

        Returns:
            np.array: Mazo con menos singletons y total conservado.
        """
        archetype = self.detect_archetype(deck_array)['archetype']

        singletons = []
        for card_id, count in enumerate(deck_array):
            if count != 1:
                continue
            card = self.card_catalog[card_id]
            if card['is_land']:
                continue
            singletons.append((card_id, self._archetype_card_affinity(card, archetype)))

        if len(singletons) <= max_singletons:
            return deck_array

        # Ordenar: mayor afinidad primero (candidatos a promoción),
        # menor afinidad al final (candidatos a eliminación).
        singletons.sort(key=lambda x: -x[1])

        excess = len(singletons) - max_singletons  # singletons a resolver

        # Calcular nº de promociones sostenible.
        # Invariante: 3 * n_promote + n_promote <= excess  (cada promoción se
        # come 1 singleton propio + 3 singletons adicionales como fuente).
        # => n_promote <= excess // 4
        # Además, solo promover singletons con afinidad >= 1.
        promotable_count = sum(1 for _, score in singletons if score >= 1)
        n_promote = min(excess // 4, promotable_count)

        adjusted = deck_array.copy()

        promoted_ids = [sid for sid, _ in singletons[:n_promote]]
        # Los singletons a eliminar son los de peor afinidad, en cantidad
        # justa: 3 por cada promoción + los que sobran del max_singletons.
        n_remove = 3 * n_promote + max(0, excess - 4 * n_promote)
        remove_ids = [sid for sid, _ in singletons[-n_remove:]] if n_remove > 0 else []

        for sid in promoted_ids:
            adjusted[sid] = 4
        for sid in remove_ids:
            adjusted[sid] = 0

        return adjusted

    def adjust_deck_size(self, deck_array):
        """
        Ajusta el array para que tenga exactamente 60 cartas y cumpla reglas MTG

        VERSIÓN CORREGIDA: Ahora añade tierras básicas según los colores del mazo actual,
        garantizando jugabilidad después de operaciones genéticas que cambien colores.

        Garantiza:
        - Exactamente 60 cartas
        - 15-30 tierras (proporción jugable)
        - Coherencia de colores: las tierras producen el maná necesario
        - Límite de 4 copias (excepto tierras básicas)
        - Consolidación arquetipo-aware: <=2 singletons no-tierra

        Args:
            deck_array: Array del mazo a ajustar

        Returns:
            np.array: Mazo ajustado y jugable
        """
        # PASO 0.5: Consolidar singletons respetando el arquetipo detectado.
        # Conserva el total de cartas (promociones compensadas con eliminaciones).
        deck_array = self.consolidate_singletons(deck_array)

        total = int(np.sum(deck_array))

        # PASO 0: Identificar colores del mazo ACTUAL (crítico después de cruce/mutación)
        deck_colors = set()
        for card_id, count in enumerate(deck_array):
            if count > 0:
                card = self.card_catalog[card_id]
                if not card['is_land']:  # Solo contar hechizos/criaturas
                    deck_colors.update(card['color_identity'])

        # Mapeo de colores a tierras básicas
        color_to_basic = {
            'W': 'Plains',
            'U': 'Island',
            'B': 'Swamp',
            'R': 'Mountain',
            'G': 'Forest'
        }

        # Crear pool de tierras básicas apropiadas según colores del mazo
        appropriate_basic_lands = []
        if deck_colors:
            for color in deck_colors:
                land_name = color_to_basic.get(color)
                if land_name and land_name in self.basic_lands_ids:
                    appropriate_basic_lands.append(self.basic_lands_ids[land_name])
        else:
            # Mazo incoloro: permitir cualquier tierra básica
            appropriate_basic_lands = [i for i, card in self.card_catalog.items()
                                       if card.get('is_basic_land', False)]

        # Fallback de seguridad
        if not appropriate_basic_lands:
            appropriate_basic_lands = [i for i, card in self.card_catalog.items()
                                       if card.get('is_basic_land', False)]

        adjusted = deck_array.copy()

        # PASO 1: Ajustar total de cartas a 60
        if total < 60:
            diff = 60 - total
            land_count = sum(adjusted[i] for i in self.type_indices.get('lands', []))

            # Priorizar añadir tierras si hay menos de 20
            if land_count < 20 and appropriate_basic_lands:
                lands_to_add = min(diff, 20 - land_count)

                for _ in range(lands_to_add):
                    # Añadir tierra básica del color correcto
                    land_id = random.choice(appropriate_basic_lands)
                    adjusted[land_id] += 1
                    diff -= 1

            # Si aún faltan cartas, añadir hechizos del pool correcto
            while diff > 0:
                # Crear pool de hechizos válidos (del color correcto)
                valid_spells = []
                for card_id, card in self.card_catalog.items():
                    if adjusted[card_id] < 4 and not card['is_land']:
                        card_colors = set(card['color_identity'])
                        # Incluir si: incoloro O todos sus colores están en el mazo
                        if not card_colors or card_colors.issubset(deck_colors):
                            valid_spells.append(card_id)

                if valid_spells:
                    spell_id = random.choice(valid_spells)
                    adjusted[spell_id] += 1
                    diff -= 1
                elif appropriate_basic_lands:
                    # Fallback: añadir más tierras
                    land_id = random.choice(appropriate_basic_lands)
                    adjusted[land_id] += 1
                    diff -= 1
                else:
                    # Fallback final: cualquier carta válida
                    valid_positions = np.where(adjusted < 4)[0]
                    if len(valid_positions) > 0:
                        adjusted[random.choice(valid_positions)] += 1
                        diff -= 1
                    else:
                        break

        elif total > 60:
            # Sobran cartas: quitar aleatoriamente
            diff = total - 60
            while diff > 0:
                nonzero_positions = np.where(adjusted > 0)[0]
                if len(nonzero_positions) > 0:
                    adjusted[random.choice(nonzero_positions)] -= 1
                    diff -= 1
                else:
                    break

        # PASO 2: Verificar y corregir proporción de tierras (15-30)
        land_count = sum(adjusted[i] for i in self.type_indices.get('lands', []))

        if land_count < 15:
            # Muy pocas tierras: convertir hechizos en tierras
            needed = 15 - land_count

            non_land_positions = [i for i in range(len(adjusted))
                                 if adjusted[i] > 0 and not self.card_catalog[i]['is_land']]

            for _ in range(min(needed, len(non_land_positions))):
                if non_land_positions and appropriate_basic_lands:
                    # Quitar un hechizo
                    spell_id = random.choice(non_land_positions)
                    adjusted[spell_id] -= 1
                    if adjusted[spell_id] == 0:
                        non_land_positions.remove(spell_id)

                    # Añadir una tierra del color correcto
                    land_id = random.choice(appropriate_basic_lands)
                    adjusted[land_id] += 1

        elif land_count > 30:
            # Demasiadas tierras: convertir tierras en hechizos del color correcto
            excess = land_count - 30

            land_positions = [i for i in self.type_indices.get('lands', [])
                             if adjusted[i] > 0]

            # Crear pool de hechizos del color correcto
            valid_spells = []
            for card_id, card in self.card_catalog.items():
                if adjusted[card_id] < 4 and not card['is_land']:
                    card_colors = set(card['color_identity'])
                    if not card_colors or card_colors.issubset(deck_colors):
                        valid_spells.append(card_id)

            for _ in range(min(excess, len(land_positions))):
                if land_positions:
                    # Quitar tierra
                    land_id = random.choice(land_positions)
                    adjusted[land_id] -= 1
                    if adjusted[land_id] == 0:
                        land_positions.remove(land_id)

                    # Añadir hechizo del color correcto
                    if valid_spells:
                        spell_id = random.choice(valid_spells)
                        adjusted[spell_id] += 1
                        if adjusted[spell_id] >= 4:
                            valid_spells.remove(spell_id)

        # PASO 3: Verificar coherencia de colores (SIEMPRE, incluso si total=60 y tierras OK)
        # Esto es crítico después de cruce/mutación que cambien los colores del mazo

        # Identificar colores del mazo actual (de cartas NO-tierra)
        current_deck_colors = set()
        for card_id, count in enumerate(adjusted):
            if count > 0:
                card = self.card_catalog[card_id]
                if not card['is_land']:
                    current_deck_colors.update(card['color_identity'])

        # Identificar qué tierras básicas tiene actualmente el mazo
        current_land_colors = set()
        for card_id, count in enumerate(adjusted):
            if count > 0:
                card = self.card_catalog[card_id]
                if card.get('is_basic_land', False):
                    current_land_colors.update(card['color_identity'])

        # Verificar si hay colores sin tierras
        colors_without_lands = current_deck_colors - current_land_colors

        if colors_without_lands and len(current_deck_colors) > 0:
            # Hay colores que necesitan tierras
            # Convertir algunas tierras existentes en las tierras que faltan

            # Identificar qué tierras básicas necesitamos añadir
            color_to_basic = {
                'W': 'Plains', 'U': 'Island', 'B': 'Swamp',
                'R': 'Mountain', 'G': 'Forest'
            }

            needed_lands = []
            for color in colors_without_lands:
                land_name = color_to_basic.get(color)
                if land_name and land_name in self.basic_lands_ids:
                    needed_lands.append(self.basic_lands_ids[land_name])

            if needed_lands:
                # ESTRATEGIA 1: Convertir tierras de colores NO usados en el mazo
                unused_land_colors = current_land_colors - current_deck_colors

                excess_lands_unused = []
                for card_id, count in enumerate(adjusted):
                    if count > 0:
                        card = self.card_catalog[card_id]
                        if card.get('is_basic_land', False):
                            land_color_identity = set(card['color_identity'])
                            if land_color_identity.issubset(unused_land_colors):
                                for _ in range(count):
                                    excess_lands_unused.append(card_id)

                # ESTRATEGIA 2: Si no hay suficientes tierras no usadas, convertir tierras de colores usados
                # pero manteniendo al menos 1/3 de las tierras para cada color que SÍ se usa
                available_lands = []
                if len(excess_lands_unused) < len(colors_without_lands) * 2:
                    # Necesitamos más tierras para convertir
                    # Calcular distribución actual de tierras por color
                    land_distribution = {}
                    for card_id, count in enumerate(adjusted):
                        if count > 0:
                            card = self.card_catalog[card_id]
                            if card.get('is_basic_land', False):
                                for color in card['color_identity']:
                                    land_distribution[color] = land_distribution.get(color, 0) + count

                    # Identificar tierras que podemos quitar manteniendo balance
                    for card_id, count in enumerate(adjusted):
                        if count > 0:
                            card = self.card_catalog[card_id]
                            if card.get('is_basic_land', False):
                                land_color = list(card['color_identity'])[0] if card['color_identity'] else None
                                if land_color and land_color in current_deck_colors:
                                    # Solo quitar si hay más de 3 de este color
                                    if land_distribution.get(land_color, 0) > 3:
                                        # Podemos quitar algunas (pero no todas)
                                        can_remove = min(count, land_distribution[land_color] - 3)
                                        for _ in range(can_remove):
                                            available_lands.append(card_id)

                # Combinar ambas fuentes
                all_convertible_lands = excess_lands_unused + available_lands

                # Convertir tierras para garantizar todos los colores
                colors_to_add = list(colors_without_lands)
                lands_per_color = max(2, len(all_convertible_lands) // len(colors_to_add)) if colors_to_add else 0
                conversions = 0

                for color in colors_to_add:
                    color_to_basic = {
                        'W': 'Plains', 'U': 'Island', 'B': 'Swamp',
                        'R': 'Mountain', 'G': 'Forest'
                    }
                    land_name = color_to_basic.get(color)
                    if land_name and land_name in self.basic_lands_ids:
                        needed_land_id = self.basic_lands_ids[land_name]

                        # Añadir al menos 2-3 tierras de cada color faltante
                        for _ in range(min(lands_per_color, len(all_convertible_lands))):
                            if all_convertible_lands:
                                # Quitar una tierra convertible
                                source_land_id = all_convertible_lands.pop(0)
                                adjusted[source_land_id] -= 1

                                # Añadir la tierra necesaria
                                adjusted[needed_land_id] += 1
                                conversions += 1

                if conversions > 0:
                    self.logger.debug(f"Coherencia de colores: {conversions} tierras convertidas para {colors_without_lands}")

        return adjusted

    # ========================================================================
    # MÉTODOS DE EVALUACIÓN DE CALIDAD DEL MAZO (FITNESS MULTI-COMPONENTE)
    # ========================================================================

    def evaluate_mana_curve(self, deck_array):
        """
        Evalúa la curva de maná del mazo comparándola con una distribución óptima

        Distribución objetivo (basada en teoría de construcción de mazos MTG):
        - 0 CMC: 0%    (solo tierras, excluidas del cálculo)
        - 1 CMC: 15%   (early game spells/creatures)
        - 2 CMC: 25%   (desarrollo temprano)
        - 3 CMC: 25%   (mid-game dominante)
        - 4 CMC: 20%   (mid-game fuerte)
        - 5 CMC: 10%   (late game threats)
        - 6+ CMC: 5%   (finishers)

        Args:
            deck_array: Array del mazo a evaluar

        Returns:
            float: Score de 0.0 a 1.0 (1.0 = curva perfecta)
        """
        # Distribución ideal (porcentajes para cartas no-tierra)
        ideal_curve = {
            1: 0.15,
            2: 0.25,
            3: 0.25,
            4: 0.20,
            5: 0.10,
            6: 0.05  # 6+ agrupado
        }

        # Contar cartas por CMC (excluyendo tierras)
        cmc_distribution = {}
        total_nonland = 0

        for card_id, count in enumerate(deck_array):
            if count > 0:
                card = self.card_catalog[card_id]
                if not card['is_land']:
                    cmc = int(card['cmc'])
                    cmc_key = min(cmc, 6)  # Agrupar 6+ como 6
                    cmc_distribution[cmc_key] = cmc_distribution.get(cmc_key, 0) + count
                    total_nonland += count

        if total_nonland == 0:
            return 0.0  # Deck sin hechizos (inválido)

        # Calcular distribución real
        actual_curve = {}
        for cmc in range(1, 7):
            actual_curve[cmc] = cmc_distribution.get(cmc, 0) / total_nonland

        # Calcular diferencia cuadrática media con la distribución ideal
        mse = sum((actual_curve.get(cmc, 0) - ideal_curve.get(cmc, 0)) ** 2
                  for cmc in ideal_curve.keys())

        # Convertir MSE a score (0-1): menor MSE = mejor score
        # MSE máximo teórico ≈ 0.5, normalizamos
        score = max(0.0, 1.0 - (mse / 0.5))

        return score

    def evaluate_synergy(self, deck_array):
        """
        Evalúa sinergias del mazo: tribales, keywords y consistencia de color

        Componentes:
        - Tribal synergy: Mazos con muchas criaturas del mismo tipo (Ángeles, Dragones, etc.)
        - Keyword density: Proporción de criaturas con habilidades clave (Flying, Trample, etc.)
        - Color consistency: Penalización por demasiados colores o identidad fragmentada

        Args:
            deck_array: Array del mazo a evaluar

        Returns:
            float: Score de 0.0 a 1.0
        """
        creature_types = {}
        keyword_count = 0
        total_creatures = 0
        colors_used = set()
        total_nonland = 0

        # Keywords de interés para MTG
        VALUABLE_KEYWORDS = [
            'Flying', 'Trample', 'Haste', 'First strike', 'Double strike',
            'Deathtouch', 'Lifelink', 'Vigilance', 'Hexproof', 'Indestructible',
            'Menace', 'Reach'
        ]

        for card_id, count in enumerate(deck_array):
            if count > 0:
                card = self.card_catalog[card_id]

                # Contar tipos de criaturas (tribal synergy)
                if card['is_creature']:
                    total_creatures += count
                    # Extraer tipo tribal del type_line (formato: "Creature — Angel Warrior")
                    if '—' in card['type_line']:
                        creature_type = card['type_line'].split('—')[1].strip().split()[0]
                        creature_types[creature_type] = creature_types.get(creature_type, 0) + count

                    # Contar keywords
                    oracle_text = card.get('oracle_text', '')
                    for keyword in VALUABLE_KEYWORDS:
                        if keyword in oracle_text:
                            keyword_count += count
                            break  # Contar cada criatura solo una vez

                # Analizar consistencia de color
                if not card['is_land']:
                    total_nonland += count
                    colors_used.update(card['color_identity'])

        # COMPONENTE 1: Tribal Synergy (0-0.4 puntos)
        tribal_score = 0.0
        if total_creatures > 0:
            # Encontrar tribu dominante
            if creature_types:
                dominant_tribe_count = max(creature_types.values())
                tribal_ratio = dominant_tribe_count / total_creatures
                # Recompensar mazos con >40% del mismo tipo tribal
                tribal_score = min(0.4, tribal_ratio * 0.8) if tribal_ratio > 0.4 else 0.0

        # COMPONENTE 2: Keyword Density (0-0.3 puntos)
        keyword_score = 0.0
        if total_creatures > 0:
            keyword_ratio = keyword_count / total_creatures
            # Recompensar mazos con >50% criaturas con keywords
            keyword_score = min(0.3, keyword_ratio * 0.5)

        # COMPONENTE 3: Color Consistency (0-0.3 puntos)
        color_score = 0.3  # Empezar en máximo
        num_colors = len(colors_used)
        if num_colors == 0:
            color_score = 0.0  # Mazo sin hechizos
        elif num_colors == 1:
            color_score = 0.3  # Monocolor (óptimo)
        elif num_colors == 2:
            color_score = 0.25  # Bicolor (muy bueno)
        elif num_colors == 3:
            color_score = 0.15  # Tricolor (jugable pero inconsistente)
        else:
            color_score = 0.05  # 4-5 colores (muy inconsistente)

        total_synergy = tribal_score + keyword_score + color_score
        return min(1.0, total_synergy)  # Cap en 1.0

    def evaluate_card_balance(self, deck_array):
        """
        Evalúa el balance entre criaturas, hechizos y otros permanentes

        Un mazo equilibrado típicamente tiene:
        - 15-20 criaturas (25-33% de no-tierras)
        - 10-15 hechizos instantáneos/conjuros (17-25%)
        - 2-8 artefactos/encantamientos/planeswalkers (3-13%)
        - 22-26 tierras (37-43% del total)

        Args:
            deck_array: Array del mazo a evaluar

        Returns:
            float: Score de 0.0 a 1.0
        """
        creatures = 0
        spells = 0  # Instants + Sorceries
        artifacts_enchantments = 0
        planeswalkers = 0
        lands = 0

        for card_id, count in enumerate(deck_array):
            if count > 0:
                card = self.card_catalog[card_id]

                if card['is_land']:
                    lands += count
                elif card['is_creature']:
                    creatures += count
                elif card['is_instant'] or card['is_sorcery']:
                    spells += count
                elif card['is_planeswalker']:
                    planeswalkers += count
                elif card['is_artifact'] or card['is_enchantment']:
                    artifacts_enchantments += count

        total_cards = creatures + spells + artifacts_enchantments + planeswalkers + lands
        nonland_cards = total_cards - lands

        if total_cards == 0 or nonland_cards == 0:
            return 0.0

        # Calcular proporciones
        land_ratio = lands / total_cards
        creature_ratio = creatures / nonland_cards
        spell_ratio = spells / nonland_cards

        # EVALUACIÓN 1: Tierras (objetivo 37-43%, óptimo ~40%)
        land_score = 0.0
        if 0.37 <= land_ratio <= 0.43:
            land_score = 0.4  # Perfecto
        elif 0.33 <= land_ratio <= 0.47:
            land_score = 0.3  # Aceptable
        elif 0.25 <= land_ratio <= 0.50:
            land_score = 0.1  # Marginal
        else:
            land_score = 0.0  # Malo

        # EVALUACIÓN 2: Criaturas (objetivo 25-33% de no-tierras)
        creature_score = 0.0
        if 0.25 <= creature_ratio <= 0.33:
            creature_score = 0.3  # Perfecto
        elif 0.20 <= creature_ratio <= 0.40:
            creature_score = 0.2  # Aceptable
        elif 0.15 <= creature_ratio <= 0.50:
            creature_score = 0.1  # Marginal
        else:
            creature_score = 0.0  # Malo

        # EVALUACIÓN 3: Hechizos (objetivo 17-25% de no-tierras)
        spell_score = 0.0
        if 0.17 <= spell_ratio <= 0.25:
            spell_score = 0.3  # Perfecto
        elif 0.10 <= spell_ratio <= 0.30:
            spell_score = 0.2  # Aceptable
        else:
            spell_score = 0.1  # Marginal

        total_balance = land_score + creature_score + spell_score
        return min(1.0, total_balance)

    def evaluate_card_power(self, deck_array):
        """
        Evalúa el poder bruto de las cartas basándose en rareza y eficiencia

        Criterios:
        - Rareza: Mythic > Rare > Uncommon > Common
        - Eficiencia de criaturas: Ratio poder+resistencia / CMC
        - Penalización por cartas muy costosas sin impacto

        Args:
            deck_array: Array del mazo a evaluar

        Returns:
            float: Score de 0.0 a 1.0
        """
        # Pesos de rareza (ajustados empíricamente)
        RARITY_WEIGHTS = {
            'mythic': 4.0,
            'rare': 3.0,
            'uncommon': 2.0,
            'common': 1.0
        }

        total_rarity_score = 0
        total_cards = 0
        efficiency_scores = []

        for card_id, count in enumerate(deck_array):
            if count > 0:
                card = self.card_catalog[card_id]

                # COMPONENTE 1: Rareza
                rarity = card.get('rarity', 'common').lower()
                rarity_weight = RARITY_WEIGHTS.get(rarity, 1.0)
                total_rarity_score += rarity_weight * count
                total_cards += count

                # COMPONENTE 2: Eficiencia de criaturas
                if card['is_creature'] and not card['is_land']:
                    try:
                        power = int(card.get('power', 0)) if card.get('power') else 0
                        toughness = int(card.get('toughness', 0)) if card.get('toughness') else 0
                        cmc = max(1, int(card.get('cmc', 1)))  # Evitar división por 0

                        # Eficiencia = (P+T) / CMC (vanilla test)
                        efficiency = (power + toughness) / cmc
                        # Normalizar: eficiencia >2.5 es excelente, <1.0 es mala
                        normalized_efficiency = min(1.0, efficiency / 2.5)
                        efficiency_scores.append(normalized_efficiency)
                    except (ValueError, TypeError):
                        pass  # Ignorar criaturas con power/toughness no numéricos (ej: */*)

        # Calcular score de rareza (normalizado)
        if total_cards > 0:
            avg_rarity = total_rarity_score / total_cards
            # Normalizar: common=1.0, mythic=4.0 → score 0-1
            rarity_score = (avg_rarity - 1.0) / 3.0  # Rango [0, 1]
        else:
            rarity_score = 0.0

        # Calcular score de eficiencia
        if efficiency_scores:
            efficiency_score = sum(efficiency_scores) / len(efficiency_scores)
        else:
            efficiency_score = 0.5  # Neutral si no hay criaturas

        # Combinar componentes (60% rareza, 40% eficiencia)
        total_power = (rarity_score * 0.6) + (efficiency_score * 0.4)
        return min(1.0, max(0.0, total_power))

    def detect_archetype(self, deck_array):
        """
        Detecta el arquetipo dominante de un mazo (aggro / midrange / control).

        Filosofía híbrida (Opción C del plan): el arquetipo es una propiedad
        CALCULADA, no persistente. Se re-evalúa cada vez que se necesita, de
        modo que un mazo puede "cambiar" de arquetipo por mutación/cruce y
        ser juzgado contra las normas del arquetipo que actualmente exhibe.

        Criterios v1 (heurística simple sobre CMC medio y número de criaturas):
            - aggro:    avg_cmc < 2.3  y  criaturas >= 22
            - control:  avg_cmc > 2.9  y  criaturas <= 12
            - midrange: resto (incluye temporalmente combo/ramp en v1)

        Args:
            deck_array: Array NumPy del mazo (counts por card_id)

        Returns:
            dict con:
                'archetype': str — 'aggro' | 'midrange' | 'control'
                'avg_cmc':   float — CMC medio de cartas no-tierra
                'creatures': int   — nº total de criaturas (con repeticiones)
                'nonland':   int   — nº total de cartas no-tierra
        """
        creatures = 0
        nonland_count = 0
        nonland_cmc_sum = 0.0

        for card_id, count in enumerate(deck_array):
            if count <= 0:
                continue
            card = self.card_catalog[card_id]
            if card['is_land']:
                continue
            nonland_count += count
            nonland_cmc_sum += card.get('cmc', 0) * count
            if card['is_creature']:
                creatures += count

        avg_cmc = (nonland_cmc_sum / nonland_count) if nonland_count > 0 else 0.0

        if nonland_count == 0:
            archetype = 'midrange'
        elif avg_cmc < 2.3 and creatures >= 22:
            archetype = 'aggro'
        elif avg_cmc > 2.9 and creatures <= 12:
            archetype = 'control'
        else:
            archetype = 'midrange'

        return {
            'archetype': archetype,
            'avg_cmc': avg_cmc,
            'creatures': creatures,
            'nonland': nonland_count,
        }

    def calculate_deck_quality(self, deck_array):
        """
        Calcula la calidad global del mazo combinando todas las métricas

        Componentes y pesos:
        - Mana curve:     25% (crítico para jugabilidad)
        - Synergy:        25% (sinergias tribales y keywords)
        - Card balance:   30% (balance tierra/criatura/hechizo)
        - Card power:     20% (rareza y eficiencia)

        Args:
            deck_array: Array del mazo a evaluar

        Returns:
            float: Score de calidad de 0.0 a 1.0
        """
        # Pesos de cada componente (deben sumar 1.0)
        WEIGHTS = {
            'mana_curve': 0.25,
            'synergy': 0.25,
            'card_balance': 0.30,
            'card_power': 0.20
        }

        # Calcular cada métrica
        mana_curve_score = self.evaluate_mana_curve(deck_array)
        synergy_score = self.evaluate_synergy(deck_array)
        balance_score = self.evaluate_card_balance(deck_array)
        power_score = self.evaluate_card_power(deck_array)

        # Combinar con pesos
        quality = (
            mana_curve_score * WEIGHTS['mana_curve'] +
            synergy_score * WEIGHTS['synergy'] +
            balance_score * WEIGHTS['card_balance'] +
            power_score * WEIGHTS['card_power']
        )

        # Log detallado (DEBUG level)
        self.logger.debug(
            f"Calidad del mazo: {quality:.3f} "
            f"(Curva:{mana_curve_score:.2f}, "
            f"Sinergia:{synergy_score:.2f}, "
            f"Balance:{balance_score:.2f}, "
            f"Poder:{power_score:.2f})"
        )

        return quality

    # ========================================================================

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

        HALL OF FAME TARDÍO: No se activa hasta la Generación 5 para evitar
        preservar mazos aleatorios de generaciones tempranas que ralenticen
        la exploración inicial.

        Args:
            fitness_values (list): Fitness de la generación actual
            population_arrays (list): Arrays de mazos de la generación actual
        """
        # Hall of Fame activo desde Gen 0 (eliminado retraso)
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

        # Guardar mazos del Hall of Fame como archivos .dck
        self.save_hall_of_fame_decks()

    def save_hall_of_fame_decks(self):
        """
        Guarda los mazos del Hall of Fame como archivos .dck y .json
        Borra los archivos viejos y guarda los nuevos en cada actualización
        """
        import glob

        # Crear directorio para Hall of Fame si no existe
        hof_dir = os.path.join(self.output_dir, "hall_of_fame")
        os.makedirs(hof_dir, exist_ok=True)

        # Borrar todos los archivos viejos del Hall of Fame
        # Esto se hace en cada actualización para mantener solo los mejores actuales
        old_files = glob.glob(os.path.join(hof_dir, "hall_of_fame_*.dck")) + \
                   glob.glob(os.path.join(hof_dir, "hall_of_fame_*.json"))
        for old_file in old_files:
            try:
                os.remove(old_file)
            except Exception as e:
                self.logger.warning(f"No se pudo borrar {old_file}: {e}")

        # Guardar los mazos actuales del Hall of Fame
        for rank, (fitness, array) in enumerate(self.hall_of_fame_arrays, 1):
            deck_name = f"hall_of_fame_{rank}"
            deck = self.array_to_deck(array, deck_name)

            # Guardar como archivo .dck (para Forge)
            deck_file = os.path.join(hof_dir, f"{deck_name}.dck")
            self.save_forge_deck(deck, deck_file)

            # También guardar en formato JSON con metadatos
            json_file = os.path.join(hof_dir, f"{deck_name}.json")
            deck_metadata = {
                'rank': rank,
                'fitness': fitness,
                'deck_name': deck_name,
                'deck': deck,
                'array': array.tolist()
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(deck_metadata, f, indent=2, ensure_ascii=False)

        if len(self.hall_of_fame_arrays) > 0:
            self.logger.debug(f"💾 Guardados {len(self.hall_of_fame_arrays)} mazos del Hall of Fame en {hof_dir}")

    def clean_hall_of_fame_directory(self):
        """
        Limpia el directorio del Hall of Fame al inicio de una nueva ejecución
        NO se llama al continuar desde checkpoint
        """
        import glob
        import shutil

        hof_dir = os.path.join(self.output_dir, "hall_of_fame")

        if os.path.exists(hof_dir):
            try:
                shutil.rmtree(hof_dir)
                self.logger.info(f"🗑️  Directorio Hall of Fame limpiado: {hof_dir}")
            except Exception as e:
                self.logger.warning(f"No se pudo limpiar directorio Hall of Fame: {e}")

        os.makedirs(hof_dir, exist_ok=True)

    # ==============================================================================
    # SISTEMA DE CHECKPOINTS Y RECUPERACIÓN
    # ==============================================================================

    def check_disk_space(self, min_gb_required=5):
        """
        Verifica que haya suficiente espacio en disco disponible

        Args:
            min_gb_required (float): Espacio mínimo requerido en GB

        Raises:
            RuntimeError: Si el espacio disponible es insuficiente
        """
        import psutil

        disk = psutil.disk_usage(self.output_dir)
        free_gb = disk.free / (1024**3)

        self.logger.info(f"Espacio en disco: {free_gb:.1f} GB libres ({disk.percent:.1f}% usado)")

        if free_gb < min_gb_required:
            error_msg = f"Espacio en disco insuficiente: {free_gb:.1f} GB libres (mínimo {min_gb_required} GB)"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Advertencia si está al 95%
        if disk.percent > 95:
            self.logger.warning(f"ADVERTENCIA: Disco casi lleno ({disk.percent:.1f}%) - Desactivando guardado de outputs de Forge")
            self.save_forge_outputs = False

        return free_gb

    def save_checkpoint(self, generation, fitness_values):
        """
        Guarda un checkpoint completo del estado actual del algoritmo

        Este checkpoint permite reanudar la ejecución exactamente desde esta generación
        si el programa se interrumpe.

        Args:
            generation (int): Número de generación actual
            fitness_values (list): Valores de fitness de la población actual
        """
        checkpoint_dir = os.path.join(self.output_dir, "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)

        checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_gen_{generation}.json")

        try:
            checkpoint_data = {
                'generation': generation,
                'population_size': self.population_size,
                'max_generations': self.max_generations,
                'fitness_values': fitness_values,
                'best_fitness_ever': self.best_fitness_ever if hasattr(self, 'best_fitness_ever') else max(fitness_values),
                'stagnation_counter': self.stagnation_counter if hasattr(self, 'stagnation_counter') else 0,
                'mutation_rate': self.mutation_rate,
                'original_mutation_rate': self.original_mutation_rate if hasattr(self, 'original_mutation_rate') else self.mutation_rate,
                'adaptive_timeout': self.adaptive_timeout,
                'generations_since_intervention': self.generations_since_intervention if hasattr(self, 'generations_since_intervention') else 0,
                # Nuevos parámetros Swiss Tournament
                'use_swiss_tournament': self.use_swiss_tournament,
                'k_rounds': self.k_rounds,
                'n_games_per_match': self.n_games_per_match,
                'timestamp': datetime.now().isoformat(),
                'hall_of_fame': []
            }

            # Guardar Hall of Fame si existe
            if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 0:
                checkpoint_data['hall_of_fame'] = [
                    {'fitness': float(fitness), 'array': array.tolist()}
                    for fitness, array in self.hall_of_fame_arrays
                ]

            # Guardar población actual
            checkpoint_data['population_arrays'] = [
                array.tolist() for array in self.population_arrays
            ]

            # Escritura atómica usando archivo temporal
            temp_file = checkpoint_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            # Mover atómicamente (reemplaza si existe)
            os.replace(temp_file, checkpoint_file)

            self.logger.info(f"Checkpoint guardado: {os.path.basename(checkpoint_file)}")

            # Limpiar checkpoints antiguos (mantener solo los últimos 3)
            self.cleanup_old_checkpoints(checkpoint_dir, keep_last=3)

        except Exception as e:
            self.logger.error(f"Error guardando checkpoint: {e}")

    def cleanup_old_checkpoints(self, checkpoint_dir, keep_last=3):
        """
        Elimina checkpoints antiguos para ahorrar espacio

        Args:
            checkpoint_dir (str): Directorio de checkpoints
            keep_last (int): Número de checkpoints recientes a mantener
        """
        try:
            checkpoint_files = sorted(
                [f for f in os.listdir(checkpoint_dir) if f.startswith('checkpoint_gen_') and f.endswith('.json')],
                key=lambda x: int(x.split('_')[2].split('.')[0])
            )

            # Eliminar todos excepto los últimos N
            for old_checkpoint in checkpoint_files[:-keep_last]:
                old_path = os.path.join(checkpoint_dir, old_checkpoint)
                os.remove(old_path)
                self.logger.debug(f"Checkpoint antiguo eliminado: {old_checkpoint}")

        except Exception as e:
            self.logger.warning(f"Error limpiando checkpoints antiguos: {e}")

    def load_checkpoint(self, checkpoint_file):
        """
        Carga un checkpoint y restaura el estado del algoritmo

        Args:
            checkpoint_file (str): Ruta al archivo de checkpoint

        Returns:
            dict: Datos del checkpoint o None si hay error
        """
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)

            # Restaurar estado del algoritmo
            self.population_arrays = [
                np.array(array, dtype=int) for array in checkpoint_data['population_arrays']
            ]

            self.best_fitness_ever = checkpoint_data.get('best_fitness_ever', 0.0)
            self.stagnation_counter = checkpoint_data.get('stagnation_counter', 0)
            self.mutation_rate = checkpoint_data.get('mutation_rate', self.mutation_rate)
            self.original_mutation_rate = checkpoint_data.get('original_mutation_rate', self.mutation_rate)
            self.adaptive_timeout = checkpoint_data.get('adaptive_timeout', self.base_timeout)
            self.generations_since_intervention = checkpoint_data.get('generations_since_intervention', 0)

            # Restaurar parámetros Swiss Tournament si existen
            if 'use_swiss_tournament' in checkpoint_data:
                self.use_swiss_tournament = checkpoint_data['use_swiss_tournament']
                self.k_rounds = checkpoint_data.get('k_rounds', 8)
                self.n_games_per_match = checkpoint_data.get('n_games_per_match', 2)

            # Restaurar Hall of Fame si existe
            if 'hall_of_fame' in checkpoint_data and len(checkpoint_data['hall_of_fame']) > 0:
                self.hall_of_fame_arrays = [
                    (entry['fitness'], np.array(entry['array'], dtype=int))
                    for entry in checkpoint_data['hall_of_fame']
                ]

            self.logger.info(f"Checkpoint cargado: Generación {checkpoint_data['generation']}")
            self.logger.info(f"  Best fitness: {self.best_fitness_ever:.4f}")
            self.logger.info(f"  Stagnation counter: {self.stagnation_counter}")
            self.logger.info(f"  Mutation rate: {self.mutation_rate:.3f} (original: {self.original_mutation_rate:.3f})")
            self.logger.info(f"  Generations since intervention: {self.generations_since_intervention}")
            self.logger.info(f"  Population size: {len(self.population_arrays)}")
            if hasattr(self, 'use_swiss_tournament'):
                self.logger.info(f"  Swiss Tournament: {self.use_swiss_tournament} (k={self.k_rounds}, n={self.n_games_per_match})")

            return checkpoint_data

        except Exception as e:
            self.logger.error(f"Error cargando checkpoint: {e}")
            return None

    def find_latest_checkpoint(self):
        """
        Busca el checkpoint más reciente disponible

        Returns:
            tuple: (checkpoint_file, generation) o (None, None) si no hay checkpoints
        """
        checkpoint_dir = os.path.join(self.output_dir, "checkpoints")

        if not os.path.exists(checkpoint_dir):
            return None, None

        try:
            checkpoint_files = [
                f for f in os.listdir(checkpoint_dir)
                if f.startswith('checkpoint_gen_') and f.endswith('.json')
            ]

            if not checkpoint_files:
                return None, None

            # Obtener el más reciente por número de generación
            latest = max(
                checkpoint_files,
                key=lambda x: int(x.split('_')[2].split('.')[0])
            )

            generation = int(latest.split('_')[2].split('.')[0])
            checkpoint_file = os.path.join(checkpoint_dir, latest)

            return checkpoint_file, generation

        except Exception as e:
            self.logger.error(f"Error buscando checkpoints: {e}")
            return None, None

    def evolve(self):
        """Ejecuta el algoritmo genético completo con paralelización y anti-estancamiento"""
        self.logger.info("=== INICIANDO ALGORITMO GENÉTICO CON ANTI-ESTANCAMIENTO ===")
        self.logger.info(f"Configuración: {self.population_size} mazos, {self.max_generations} generaciones")
        self.logger.info(f"Paralelización: {self.max_workers} workers, timeout {self.base_timeout}s")

        termination_reason = "max_generations_reached"
        best_deck = None
        start_generation = 0

        try:
            # === VERIFICAR ESPACIO EN DISCO ===
            self.logger.info("=== VERIFICANDO ESPACIO EN DISCO ===")
            try:
                free_gb = self.check_disk_space(min_gb_required=5)
                self.logger.info(f"Verificación OK: {free_gb:.1f} GB disponibles")
            except RuntimeError as e:
                self.logger.error(f"No se puede iniciar: {e}")
                raise

            # === BUSCAR CHECKPOINT EXISTENTE ===
            checkpoint_file, checkpoint_gen = self.find_latest_checkpoint()

            if checkpoint_file and checkpoint_gen is not None:
                self.logger.info(f"=== CHECKPOINT ENCONTRADO: Generación {checkpoint_gen} ===")
                response = input(f"\n¿Deseas reanudar desde la generación {checkpoint_gen}? (S/n): ").strip().lower()

                if response in ['s', 'si', 'sí', 'y', 'yes', '']:
                    checkpoint_data = self.load_checkpoint(checkpoint_file)
                    if checkpoint_data:
                        start_generation = checkpoint_data['generation'] + 1
                        fitness_values = checkpoint_data['fitness_values']
                        best_fitness_ever = checkpoint_data['best_fitness_ever']
                        self.best_fitness_ever = best_fitness_ever

                        self.logger.info(f"REANUDANDO desde generación {start_generation}")
                        self.logger.info(f"Best fitness recuperado: {best_fitness_ever:.4f}")
                    else:
                        self.logger.warning("Error cargando checkpoint. Iniciando desde cero.")
                        start_generation = 0
                else:
                    self.logger.info("Iniciando nueva ejecución desde generación 0")
                    start_generation = 0

            # === EVALUACIÓN INICIAL (solo si no se reanuda) ===
            if start_generation == 0:
                # Limpiar directorios de ejecuciones anteriores
                self.logger.info("🧹 Limpiando archivos de ejecuciones anteriores...")
                self.clean_hall_of_fame_directory()
                self.clean_forge_decks()

                self.logger.info("Evaluando población inicial con procesamiento paralelo...")
                fitness_values = self.evaluate_population_tournament_parallel(self.population_arrays, 0)
                self.save_population_arrays(0)

                # Variables de control mejoradas
                best_fitness_ever = max(fitness_values)
                self.best_fitness_ever = best_fitness_ever
                self.update_statistics(0, fitness_values)

                self.stagnation_counter = 0
                self.generations_since_intervention = 0
                self.current_fitness_values = fitness_values

                # Actualizar Hall of Fame inicial
                self.update_hall_of_fame(fitness_values, self.population_arrays)

                # Guardar checkpoint inicial
                self.save_checkpoint(0, fitness_values)
            else:
                # Restaurar variables de control desde checkpoint
                # stagnation_counter, generations_since_intervention ya restaurados en load_checkpoint
                self.current_fitness_values = fitness_values

            # BUCLE PRINCIPAL CON CONTROL DE TERMINACIÓN MEJORADO
            for generation in range(start_generation + 1 if start_generation > 0 else 1, self.max_generations + 1):
                self.current_generation = generation
                self.logger.info(f"\n=== GENERACIÓN {generation} ===")

                # === VERIFICAR ESPACIO EN DISCO CADA 5 GENERACIONES ===
                if generation % 5 == 0:
                    try:
                        free_gb = self.check_disk_space(min_gb_required=2)
                    except RuntimeError as e:
                        self.logger.error(f"Deteniendo ejecución: {e}")
                        termination_reason = "disk_space_exhausted"
                        break

                # === CREAR NUEVA GENERACIÓN (código existente) ===
                new_population = []

                # Preservar elite del Hall of Fame (siempre activo desde Gen 0)
                hof_preserved = 0

                if hasattr(self, 'hall_of_fame_arrays') and len(self.hall_of_fame_arrays) > 0:
                    elite_to_preserve = min(self.elite_size, len(self.hall_of_fame_arrays))
                    for i in range(elite_to_preserve):
                        if hof_preserved < self.elite_size:
                            fitness, elite_array = self.hall_of_fame_arrays[i]
                            new_population.append(elite_array.copy())
                            hof_preserved += 1
                    self.logger.debug(f"Preservados {hof_preserved} individuos del Hall of Fame")

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
                
                self.update_statistics(generation, fitness_values)  # <-- NUEVA LÍNEA
                
                # Actualizar Hall of Fame
                self.update_hall_of_fame(fitness_values, self.population_arrays)

                # === ACTUALIZAR ESTADÍSTICAS ===
                current_best = max(fitness_values)

                if current_best > best_fitness_ever:
                    best_fitness_ever = current_best
                    self.best_fitness_ever = best_fitness_ever
                    self.stagnation_counter = 0
                    self.logger.info(f"🎉 NUEVO MEJOR FITNESS: {current_best:.4f} (Gen {generation})")
                    
                    # Restaurar tasa de mutación si había intervención
                    if self.generations_since_intervention > 0:
                        self.restore_mutation_rate()
                        self.generations_since_intervention = 0
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
                    self.generations_since_intervention = 1

                    # GUARDAR CHECKPOINT DESPUÉS DE LA INTERVENCIÓN
                    # Es crítico guardar aquí porque el continue saltará el save_checkpoint normal
                    self.logger.info("Guardando checkpoint post-intervención...")
                    self.save_checkpoint(generation, fitness_values)

                    # Continuar después de la intervención
                    continue
                
                if not should_continue:
                    termination_reason = reason
                    self.logger.info(f"🏁 TERMINACIÓN CONTROLADA: {termination_reason}")

                    # GUARDAR CHECKPOINT FINAL ANTES DE TERMINAR
                    self.logger.info("Guardando checkpoint final antes de terminar...")
                    self.save_checkpoint(generation, fitness_values)

                    break
                
                # Incrementar contador de generaciones desde intervención
                if self.generations_since_intervention > 0:
                    self.generations_since_intervention += 1
                    # Restaurar mutación después de 3 generaciones
                    if self.generations_since_intervention >= 3:
                        self.restore_mutation_rate()
                        self.generations_since_intervention = 0

                # === GUARDAR CHECKPOINT AL FINAL DE CADA GENERACIÓN ===
                self.save_checkpoint(generation, fitness_values)

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

            # GUARDAR CHECKPOINT DE EMERGENCIA antes de terminar
            if hasattr(self, 'current_generation') and self.current_generation > 0:
                try:
                    self.logger.info(f"Guardando checkpoint de emergencia en generación {self.current_generation}...")
                    # Usar fitness_values si existe, sino usar los actuales
                    checkpoint_fitness = fitness_values if 'fitness_values' in locals() else self.current_fitness_values
                    self.save_checkpoint(self.current_generation, checkpoint_fitness)
                    self.logger.info(f"✅ Checkpoint guardado: puedes reanudar desde generación {self.current_generation + 1}")
                except Exception as e:
                    self.logger.error(f"Error guardando checkpoint de emergencia: {e}")

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
            
    def save_statistics(self):
        """Guarda estadísticas de evolución con verificación de datos"""
        try:
            # Verificar que hay datos
            if not self.stats['best_fitness']:
                self.logger.warning("⚠️ No hay estadísticas para guardar - creando estadísticas de emergencia")

                # Crear estadísticas básicas si no existen
                if hasattr(self, 'current_fitness_values') and self.current_fitness_values:
                    self.stats['best_fitness'] = [max(self.current_fitness_values)]
                    self.stats['avg_fitness'] = [np.mean(self.current_fitness_values)]
                    self.stats['diversity'] = [self.calculate_diversity(self.population_arrays)]
                    self.stats['mutation_rate'] = [getattr(self, 'mutation_rate', 0.9)]
                else:
                    # Estadísticas de fallback absoluto
                    self.stats['best_fitness'] = [0.0]
                    self.stats['avg_fitness'] = [0.0]
                    self.stats['diversity'] = [0.0]
                    self.stats['mutation_rate'] = [0.9]

            # Verificar longitudes consistentes
            lengths = [len(self.stats[key]) for key in self.stats.keys()]
            if len(set(lengths)) > 1:
                self.logger.warning(f"⚠️ Longitudes inconsistentes en estadísticas: {dict(zip(self.stats.keys(), lengths))}")

                # Truncar a la longitud mínima
                min_length = min(lengths)
                for key in self.stats.keys():
                    self.stats[key] = self.stats[key][:min_length]

            # Crear DataFrame
            stats_df = pd.DataFrame({
                'generation': range(len(self.stats['best_fitness'])),
                'best_fitness': self.stats['best_fitness'],
                'avg_fitness': self.stats['avg_fitness'],
                'diversity': self.stats['diversity'],
                'mutation_rate': self.stats['mutation_rate']
            })

            self.logger.info(f"📊 Guardando estadísticas: {len(stats_df)} generaciones")

            # Guardar CSV
            csv_file = os.path.join(self.output_dir, "parallel_evolution_stats.csv")
            stats_df.to_csv(csv_file, index=False)
            self.logger.info(f"✅ CSV guardado: {csv_file}")

            # Crear gráficos solo si hay datos suficientes
            if len(stats_df) > 0:
                self.create_evolution_plots(stats_df)
            else:
                self.logger.warning("⚠️ No hay suficientes datos para crear gráficos")

            # Guardar Hall of Fame
            self.save_hall_of_fame_data()

            self.logger.info(f"✅ Estadísticas paralelas guardadas en {self.output_dir}")

        except Exception as e:
            self.logger.error(f"❌ Error en save_statistics(): {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
    def create_evolution_plots(self, stats_df):
        """
        Crea gráficos de evolución con manejo de errores
        """
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

            # Gráfico 1: Fitness
            if len(stats_df) > 1:  # Solo si hay múltiples puntos
                ax1.plot(stats_df['generation'], stats_df['best_fitness'], 'b-', linewidth=2, label='Mejor')
                ax1.plot(stats_df['generation'], stats_df['avg_fitness'], 'r--', linewidth=2, label='Promedio')
            else:
                # Para un solo punto, usar scatter
                ax1.scatter(stats_df['generation'], stats_df['best_fitness'], c='blue', s=100, label='Mejor')
                ax1.scatter(stats_df['generation'], stats_df['avg_fitness'], c='red', s=100, label='Promedio')

            ax1.set_xlabel('Generación')
            ax1.set_ylabel('Fitness')
            ax1.set_title('Evolución del Fitness (Paralelo)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Gráfico 2: Diversidad
            if len(stats_df) > 1:
                ax2.plot(stats_df['generation'], stats_df['diversity'], 'g-', linewidth=2)
            else:
                ax2.scatter(stats_df['generation'], stats_df['diversity'], c='green', s=100)

            ax2.set_xlabel('Generación')
            ax2.set_ylabel('Diversidad')
            ax2.set_title('Evolución de la Diversidad')
            ax2.grid(True, alpha=0.3)

            # Gráfico 3: Tasa de mutación
            if len(stats_df) > 1:
                ax3.plot(stats_df['generation'], stats_df['mutation_rate'], 'm-', linewidth=2)
            else:
                ax3.scatter(stats_df['generation'], stats_df['mutation_rate'], c='magenta', s=100)

            ax3.set_xlabel('Generación')
            ax3.set_ylabel('Tasa de Mutación')
            ax3.set_title('Tasa de Mutación Adaptativa')
            ax3.grid(True, alpha=0.3)

            # Gráfico 4: Hall of Fame
            if hasattr(self, 'hall_of_fame_arrays') and self.hall_of_fame_arrays:
                # Crear datos de Hall of Fame por generación
                hof_generations = list(range(len(stats_df)))
                hof_fitness = [max(stats_df['best_fitness'][:i+1]) for i in range(len(stats_df))]

                ax4.plot(hof_generations, hof_fitness, 'r*-', markersize=8, linewidth=2)
                ax4.set_xlabel('Generación')
                ax4.set_ylabel('Mejor Fitness Histórico')
                ax4.set_title(f'Hall of Fame (Workers: {self.max_workers})')
                ax4.grid(True, alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'Hall of Fame\nno disponible', 
                        ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Hall of Fame')

            plt.tight_layout()

            # Guardar gráfico
            plot_file = os.path.join(self.output_dir, "parallel_evolution_stats.png")
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            plt.close()

            self.logger.info(f"✅ Gráficos guardados: {plot_file}")

        except Exception as e:
            self.logger.error(f"❌ Error creando gráficos: {e}")
            # Cerrar figura si existe para evitar warnings
            try:
                plt.close('all')
            except:
                pass    
            
    def save_hall_of_fame_data(self):
        """
        Guarda datos del Hall of Fame con verificación
        """
        try:
            hof_file = os.path.join(self.output_dir, "parallel_hall_of_fame.json")
            hof_data = []

            for i, (fitness, array) in enumerate(self.hall_of_fame_arrays[:5]):  # Top 5
                deck = self.array_to_deck(array, f"HOF_Deck_{i}")
                hof_data.append({
                    'rank': i + 1,
                    'fitness': float(fitness),
                    'deck_name': deck['name'],
                    'colors': deck.get('colors', []),
                    'stats': deck.get('stats', {}),
                    'parallel_workers': self.max_workers,
                    'total_cards': int(np.sum(array)),
                    'unique_cards': int(np.count_nonzero(array))
                })

            # Guardar datos
            with open(hof_file, 'w', encoding='utf-8') as f:
                json.dump(hof_data, f, ensure_ascii=False, indent=2)

            if hof_data:
                self.logger.info(f"✅ Hall of Fame guardado: {len(hof_data)} entradas en {hof_file}")
            else:
                self.logger.warning(f"⚠️ Hall of Fame vacío guardado en {hof_file}")

        except Exception as e:
            self.logger.error(f"❌ Error guardando Hall of Fame: {e}")        
        
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
                    if hasattr(self, 'hall_of_fame') and self.hall_of_fame_arrays:
                        _, alt_fitness, alt_deck = max(self.hall_of_fame_arrays, key=lambda x: x[1])
                        if alt_fitness > best_fitness:
                            self.logger.info(f"🔄 Usando hall_of_fame alternativo: {alt_fitness:.4f}")
                            return alt_deck, alt_fitness

                return best_deck, best_fitness

            # OPCIÓN 2: Usar hall_of_fame estándar
            elif hasattr(self, 'hall_of_fame') and self.hall_of_fame_arrays:
                _, best_fitness, best_deck = max(self.hall_of_fame_arrays, key=lambda x: x[1])

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
        
    def update_statistics(self, generation, fitness_values):
        """
        Actualiza las estadísticas de evolución en cada generación

        Args:
            generation (int): Número de generación actual
            fitness_values (list): Lista de fitness de todos los individuos
        """
        try:
            # Calcular estadísticas básicas
            best_fitness = max(fitness_values)
            avg_fitness = np.mean(fitness_values)
            diversity = self.calculate_diversity(self.population_arrays)

            # Obtener tasa de mutación actual
            current_mutation_rate = getattr(self, 'mutation_rate', 0.9)

            # Actualizar listas de estadísticas
            self.stats['best_fitness'].append(best_fitness)
            self.stats['avg_fitness'].append(avg_fitness)
            self.stats['diversity'].append(diversity)
            self.stats['mutation_rate'].append(current_mutation_rate)

            # Log debug cada 5 generaciones
            if generation % 5 == 0:
                self.logger.debug(f"Stats Gen {generation}: Best={best_fitness:.4f}, "
                                f"Avg={avg_fitness:.4f}, Div={diversity:.4f}")

            # Guardar estadísticas incrementales cada 10 generaciones
            if generation % 10 == 0:
                self.save_incremental_statistics(generation)

        except Exception as e:
            self.logger.error(f"Error actualizando estadísticas en generación {generation}: {e}")
            
    def save_incremental_statistics(self, generation):
        """
        Guarda estadísticas incrementales para no perder datos si hay interrupción
        """
        try:
            # Crear DataFrame con datos actuales
            stats_df = pd.DataFrame({
                'generation': range(len(self.stats['best_fitness'])),
                'best_fitness': self.stats['best_fitness'],
                'avg_fitness': self.stats['avg_fitness'],
                'diversity': self.stats['diversity'],
                'mutation_rate': self.stats['mutation_rate']
            })

            # Guardar CSV incremental
            incremental_file = os.path.join(self.output_dir, f"evolution_stats_gen_{generation}.csv")
            stats_df.to_csv(incremental_file, index=False)

            self.logger.debug(f"Estadísticas incrementales guardadas: {incremental_file}")

        except Exception as e:
            self.logger.error(f"Error guardando estadísticas incrementales: {e}")

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
    # OPTIMIZADO: 3 combates por enfrentamiento para reducir ruido ~58% (antes: 1)
    # Cada enfrentamiento ejecuta 3 combates, victoria = mejor de 3
    base_cmd = [
        "java", "-jar", forge_jar_path,
        "sim",
        "-d", deck1_name, deck2_name,
        "-n", "3"
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
        'mutation_rate': 0.9,
        'crossover_rate': 0.15,
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