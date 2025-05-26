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
from multiprocessing import Pool, cpu_count
from collections import defaultdict
import re
from tqdm import tqdm

class MTGGeneticAlgorithm:
    def __init__(self, 
                 population_file="mtg_decks/initial_population.json",
                 catalog_path="mtg_data/card_catalog.json",
                 indices_path="mtg_data/card_indices.json",
                 output_dir="mtg_evolved_decks",
                 forge_jar_path="./forge-gui-desktop-2.0.03-jar-with-dependencies.jar",
                 max_generations=200,
                 population_size=50,
                 mutation_rate=0.05,
                 crossover_rate=0.9,
                 tournament_size=3,
                 elite_size=5,
                 stagnation_limit=20):
        """
        Inicializa el algoritmo genético con representación de arrays
        
        Args:
            population_file (str): Ruta al archivo JSON con población inicial
            catalog_path (str): Ruta al catálogo de cartas
            indices_path (str): Ruta a los índices de cartas
            output_dir (str): Directorio para guardar los mazos evolucionados
            forge_jar_path (str): Ruta al ejecutable forge-gui-desktop.jar
            max_generations (int): Número máximo de generaciones
            population_size (int): Tamaño de la población
            mutation_rate (float): Tasa de mutación base
            crossover_rate (float): Tasa de cruce
            tournament_size (int): Tamaño del torneo para selección
            elite_size (int): Número de mejores individuos a preservar
            stagnation_limit (int): Generaciones sin mejora antes de terminar
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self.forge_jar_path = forge_jar_path
        self.max_generations = max_generations
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        self.stagnation_limit = stagnation_limit
        
        # Cargar catálogo e índices
        print(f"Cargando catálogo de cartas...")
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
        print(f"Población inicial cargada: {len(self.population)} mazos")
        
        # Convertir población a arrays
        self.population_arrays = []
        for deck in self.population:
            if 'array' in deck:
                self.population_arrays.append(np.array(deck['array']))
            else:
                # Convertir del formato antiguo si es necesario
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
    
    def load_population(self, population_file):
        """Carga la población inicial desde archivo"""
        try:
            with open(population_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            return population
        except Exception as e:
            print(f"Error al cargar población: {e}")
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
    
    def setup_forge(self):
        """Configura Forge para simulaciones"""
        # Verificar que Forge existe
        if not os.path.exists(self.forge_jar_path):
            print(f"ERROR: No se encontró Forge en {self.forge_jar_path}")
            print("Este algoritmo REQUIERE Forge para las evaluaciones.")
            print("Por favor, descarga forge-gui-desktop.jar y colócalo en la ruta especificada.")
            sys.exit(1)
        
        # Configurar directorios de Forge
        self.forge_root = os.path.dirname(self.forge_jar_path)
        self.forge_decks_dir = os.path.join(self.forge_root, "user", "decks", "constructed")
        self.forge_old_winners_dir = os.path.join(self.forge_root, "user", "decks", "old_winners")
        
        # Crear directorios si no existen
        os.makedirs(self.forge_decks_dir, exist_ok=True)
        os.makedirs(self.forge_old_winners_dir, exist_ok=True)
        
        # Limpiar mazos antiguos de generaciones previas
        self.clean_forge_decks()
        
        print("Forge configurado correctamente para simulaciones.")
        print(f"Directorio de mazos: {self.forge_decks_dir}")
    
    def clean_forge_decks(self):
        """Limpia los mazos antiguos del directorio de Forge"""
        # Buscar archivos que coincidan con nuestro patrón de nombres
        pattern = re.compile(r"Gen\d+_Deck\d+\.dck")
        
        for filename in os.listdir(self.forge_decks_dir):
            if pattern.match(filename):
                filepath = os.path.join(self.forge_decks_dir, filename)
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Advertencia: No se pudo eliminar {filename}: {e}")
        
        print("Mazos antiguos limpiados.")
    
    def save_old_winner(self, deck, generation):
        """Guarda el ganador anterior en la carpeta de old_winners"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"Winner_Gen{generation}_{timestamp}.dck"
        filepath = os.path.join(self.forge_old_winners_dir, filename)
        self.save_forge_deck(deck, filepath)
        print(f"Ganador anterior guardado en: {filename}")
    
    def evaluate_population_tournament(self, population_arrays, generation=0):
        """
        Evalúa toda la población mediante un torneo round-robin
        
        Args:
            population_arrays (list): Lista de arrays representando mazos
            generation (int): Generación actual
            
        Returns:
            list: Lista de valores de fitness (win rates)
        """
        n_decks = len(population_arrays)
        wins = [0] * n_decks
        games = [0] * n_decks
        
        print(f"\nEjecutando torneo round-robin con {n_decks} mazos...")
        print(f"Total de enfrentamientos: {n_decks * (n_decks - 1) // 2}")
        
        # Limpiar mazos antiguos antes de crear los nuevos
        self.clean_forge_decks()
        
        # Convertir todos los arrays a mazos y guardarlos en el directorio de Forge
        deck_files = []
        deck_names = []
        for i, array in enumerate(population_arrays):
            deck_name = f"Gen{generation}_Deck{i}"
            deck_names.append(deck_name)
            deck = self.array_to_deck(array, deck_name)
            deck_file = os.path.join(self.forge_decks_dir, f"{deck_name}.dck")
            self.save_forge_deck(deck, deck_file)
            deck_files.append(deck_file)
        
        # Ejecutar todos los enfrentamientos
        match_count = 0
        total_matches = n_decks * (n_decks - 1) // 2
        
        with tqdm(total=total_matches, desc="Enfrentamientos") as pbar:
            for i in range(n_decks):
                for j in range(i + 1, n_decks):
                    # Cada par juega 2 partidas (una con cada jugador primero)
                    # Partida 1: i vs j
                    wins_i_vs_j = self.simulate_forge_match(
                        deck_names[i], deck_names[j], games=1
                    )
                    wins[i] += wins_i_vs_j
                    wins[j] += (1 - wins_i_vs_j)
                    games[i] += 1
                    games[j] += 1
                    
                    # Partida 2: j vs i (cambiar orden de juego)
                    wins_j_vs_i = self.simulate_forge_match(
                        deck_names[j], deck_names[i], games=1
                    )
                    wins[j] += wins_j_vs_i
                    wins[i] += (1 - wins_j_vs_i)
                    games[i] += 1
                    games[j] += 1
                    
                    match_count += 1
                    pbar.update(1)
        
        # Calcular fitness (win rate) para cada mazo
        fitness_values = []
        for i in range(n_decks):
            if games[i] > 0:
                win_rate = wins[i] / games[i]
            else:
                win_rate = 0.0
            fitness_values.append(win_rate)
        
        # Mostrar estadísticas del torneo
        print(f"\nResultados del torneo:")
        print(f"  Mejor win rate: {max(fitness_values):.2%}")
        print(f"  Peor win rate: {min(fitness_values):.2%}")
        print(f"  Win rate promedio: {np.mean(fitness_values):.2%}")
        
        return fitness_values
    
    def simulate_forge_match(self, deck1_name, deck2_name, games=1):
        """
        Simula una partida entre dos mazos en Forge
        
        Args:
            deck1_name (str): Nombre del primer mazo (sin extensión .dck)
            deck2_name (str): Nombre del segundo mazo (sin extensión .dck)
            games (int): Número de partidas
            
        Returns:
            int: Número de victorias del primer mazo
        """
        # Comando para ejecutar Forge en modo simulación
        # Forge espera solo los nombres de los mazos, no las rutas completas
        cmd = [
            "java", "-jar", self.forge_jar_path,
            "sim",
            "-d", deck1_name, deck2_name,
            "-n", "1"
        ]
        
        try:
            # Ejecutar desde el directorio de Forge
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60,  # Timeout más corto para partidas individuales
                cwd=self.forge_root  # Cambiar al directorio de Forge
            )
            
            # Parsear resultados
            output = result.stdout
            
            # Buscar el patrón de victoria en el formato de Forge
            # Formato: "Ai(X)-NombreMazo has won!"
            # Necesitamos ver si ganó deck1 o deck2
            
            # Contar victorias del deck1
            deck1_wins = 0
            deck2_wins = 0
            
            # Buscar todas las líneas que contienen "has won!"
            for line in output.split('\n'):
                if "has won!" in line:
                    if deck1_name in line:
                        deck1_wins += 1
                    elif deck2_name in line:
                        deck2_wins += 1
            
            # Si se jugó más de una partida, retornar el número de victorias
            if games > 1:
                return deck1_wins
            
            # Si solo se jugó una partida, retornar 1 o 0
            if deck1_wins > 0:
                return 1
            elif deck2_wins > 0:
                return 0
            
            # Si no encontramos un ganador claro, buscar patrones alternativos
            # Patrón alternativo: "Player 1 wins" o similar
            if re.search(r"Player 1 wins?", output, re.IGNORECASE):
                return 1
            elif re.search(r"Player 2 wins?", output, re.IGNORECASE):
                return 0
            
            # Si hay error, imprimir para debugging
            if result.stderr:
                print(f"\nError en simulación: {result.stderr}")
            
            # Si no podemos determinar el ganador, asumimos empate (0)
            print(f"\nNo se pudo determinar ganador entre {deck1_name} y {deck2_name}")
            return 0
            
        except subprocess.TimeoutExpired:
            print(f"\nTimeout en partida {deck1_name} vs {deck2_name}")
            return 0
        except Exception as e:
            print(f"\nError en simulación: {e}")
            return 0
    
    def save_forge_deck(self, deck, filepath):
        """Guarda un mazo en formato Forge"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("[metadata]\n")
            f.write(f"Name={deck['name']}\n")
            f.write("\n[Main]\n")
            
            for card in deck['cards']:
                # Forge espera el formato simple "cantidad nombre"
                f.write(f"{card['count']} {card['name']}\n")
    
    def crossover_uniform(self, parent1_array, parent2_array):
        """
        Cruce uniforme entre dos arrays de mazos
        
        Args:
            parent1_array (np.array): Primer padre
            parent2_array (np.array): Segundo padre
            
        Returns:
            tuple: Dos hijos (np.array)
        """
        if random.random() > self.crossover_rate:
            return parent1_array.copy(), parent2_array.copy()
        
        # Crear máscaras para cruce uniforme
        mask = np.random.randint(0, 2, size=self.total_cards)
        
        # Crear hijos
        child1 = np.where(mask == 1, parent1_array, parent2_array)
        child2 = np.where(mask == 0, parent1_array, parent2_array)
        
        # Ajustar a exactamente 60 cartas
        child1 = self.adjust_deck_size(child1)
        child2 = self.adjust_deck_size(child2)
        
        return child1, child2
    
    def crossover_two_point(self, parent1_array, parent2_array):
        """
        Cruce de dos puntos entre arrays de mazos
        
        Args:
            parent1_array (np.array): Primer padre
            parent2_array (np.array): Segundo padre
            
        Returns:
            tuple: Dos hijos (np.array)
        """
        if random.random() > self.crossover_rate:
            return parent1_array.copy(), parent2_array.copy()
        
        # Seleccionar dos puntos de cruce
        points = sorted(random.sample(range(1, self.total_cards), 2))
        
        # Crear hijos
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
        
        # Ajustar a exactamente 60 cartas
        child1 = self.adjust_deck_size(child1)
        child2 = self.adjust_deck_size(child2)
        
        return child1, child2
    
    def mutate_swap(self, deck_array):
        """
        Mutación por intercambio: intercambia cartas entre posiciones
        
        Args:
            deck_array (np.array): Array del mazo
            
        Returns:
            np.array: Array mutado
        """
        if random.random() > self.mutation_rate:
            return deck_array.copy()
        
        mutated = deck_array.copy()
        
        # Número de intercambios
        num_swaps = random.randint(1, 3)
        
        for _ in range(num_swaps):
            # Encontrar posiciones con cartas
            nonzero_positions = np.where(mutated > 0)[0]
            if len(nonzero_positions) < 2:
                continue
            
            # Seleccionar dos posiciones diferentes
            pos1, pos2 = random.sample(list(nonzero_positions), 2)
            
            # Intercambiar una copia
            if mutated[pos1] > 0 and mutated[pos2] < 4:
                mutated[pos1] -= 1
                mutated[pos2] += 1
        
        return mutated
    
    def mutate_add_remove(self, deck_array):
        """
        Mutación por adición/remoción: añade o quita cartas
        
        Args:
            deck_array (np.array): Array del mazo
            
        Returns:
            np.array: Array mutado
        """
        if random.random() > self.mutation_rate:
            return deck_array.copy()
        
        mutated = deck_array.copy()
        
        # Número de mutaciones
        num_mutations = random.randint(1, 5)
        
        for _ in range(num_mutations):
            if random.random() < 0.5:
                # Añadir una carta
                # Seleccionar carta que no esté al máximo
                valid_positions = np.where((mutated < 4) | 
                                         (np.array([self.card_catalog[i]['is_basic_land'] 
                                                   for i in range(self.total_cards)])))[0]
                if len(valid_positions) > 0:
                    pos = random.choice(valid_positions)
                    mutated[pos] += 1
            else:
                # Quitar una carta
                nonzero_positions = np.where(mutated > 0)[0]
                if len(nonzero_positions) > 0:
                    pos = random.choice(nonzero_positions)
                    mutated[pos] -= 1
        
        # Ajustar a 60 cartas
        mutated = self.adjust_deck_size(mutated)
        
        return mutated
    
    def mutate_color_shift(self, deck_array):
        """
        Mutación de cambio de color: reemplaza cartas por otras del mismo tipo pero diferente color
        
        Args:
            deck_array (np.array): Array del mazo
            
        Returns:
            np.array: Array mutado
        """
        if random.random() > self.mutation_rate * 2:  # Menos frecuente
            return deck_array.copy()
        
        mutated = deck_array.copy()
        
        # Identificar colores actuales del mazo
        current_colors = set()
        for card_id, count in enumerate(mutated):
            if count > 0:
                colors = self.card_catalog[card_id]['color_identity']
                current_colors.update(colors)
        
        # Si el mazo es monocolor, añadir un color
        if len(current_colors) <= 1:
            all_colors = ['W', 'U', 'B', 'R', 'G']
            available_colors = [c for c in all_colors if c not in current_colors]
            if available_colors:
                new_color = random.choice(available_colors)
                current_colors.add(new_color)
        
        # Reemplazar algunas cartas por cartas del mismo tipo pero diferente color
        num_replacements = random.randint(2, 5)
        
        for _ in range(num_replacements):
            # Seleccionar una carta no-tierra para reemplazar
            nonland_positions = []
            for i in range(self.total_cards):
                if mutated[i] > 0 and not self.card_catalog[i]['is_land']:
                    nonland_positions.append(i)
            
            if not nonland_positions:
                continue
            
            old_pos = random.choice(nonland_positions)
            old_card = self.card_catalog[old_pos]
            
            # Buscar cartas similares en otros colores
            candidates = []
            
            # Determinar el tipo de carta a buscar
            if old_card['is_creature']:
                search_pool = self.type_indices.get('creatures', [])
            elif old_card['is_instant'] or old_card['is_sorcery']:
                search_pool = self.type_indices.get('spells', [])
            else:
                continue
            
            # Filtrar por CMC similar (±1)
            target_cmc = old_card['cmc']
            for card_id in search_pool:
                card = self.card_catalog[card_id]
                if (abs(card['cmc'] - target_cmc) <= 1 and
                    card_id != old_pos and
                    any(c in current_colors for c in card['color_identity'])):
                    candidates.append(card_id)
            
            if candidates:
                new_pos = random.choice(candidates)
                # Reemplazar
                count = mutated[old_pos]
                mutated[old_pos] = 0
                mutated[new_pos] = min(4, mutated[new_pos] + count)
        
        return self.adjust_deck_size(mutated)
    
    def adjust_deck_size(self, deck_array):
        """
        Ajusta el array para que tenga exactamente 60 cartas
        
        Args:
            deck_array (np.array): Array del mazo
            
        Returns:
            np.array: Array ajustado
        """
        total = np.sum(deck_array)
        
        if total == 60:
            return deck_array
        
        adjusted = deck_array.copy()
        
        if total < 60:
            # Añadir cartas
            diff = 60 - total
            
            # Priorizar añadir tierras si hay pocas
            land_count = sum(adjusted[i] for i in range(self.total_cards) 
                           if self.card_catalog[i]['is_land'])
            
            if land_count < 20:
                # Añadir tierras básicas
                basic_lands = [i for i, card in self.card_catalog.items() 
                             if card.get('is_basic_land', False)]
                for _ in range(min(diff, 20 - land_count)):
                    if basic_lands:
                        land_id = random.choice(basic_lands)
                        adjusted[land_id] += 1
                        diff -= 1
            
            # Añadir el resto
            while diff > 0:
                # Seleccionar posición válida
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
            # Quitar cartas
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
        """
        Selección por torneo
        
        Args:
            population_arrays (list): Lista de arrays de mazos
            fitness_values (list): Valores de fitness correspondientes
            
        Returns:
            np.array: Array seleccionado
        """
        tournament_indices = random.sample(range(len(population_arrays)), 
                                         min(self.tournament_size, len(population_arrays)))
        
        tournament_fitness = [fitness_values[i] for i in tournament_indices]
        winner_idx = tournament_indices[tournament_fitness.index(max(tournament_fitness))]
        
        return population_arrays[winner_idx].copy()
    
    def calculate_diversity(self, population_arrays):
        """
        Calcula la diversidad de la población
        
        Args:
            population_arrays (list): Lista de arrays
            
        Returns:
            float: Medida de diversidad (0.0-1.0)
        """
        # Calcular frecuencia de cada carta en la población
        card_frequencies = np.zeros(self.total_cards)
        
        for array in population_arrays:
            card_frequencies += (array > 0).astype(int)
        
        # Normalizar
        card_frequencies = card_frequencies / len(population_arrays)
        
        # Diversidad = proporción de cartas que aparecen en 20-80% de los mazos
        diverse_cards = np.sum((card_frequencies > 0.2) & (card_frequencies < 0.8))
        total_used_cards = np.sum(card_frequencies > 0)
        
        if total_used_cards > 0:
            diversity = diverse_cards / total_used_cards
        else:
            diversity = 0.0
        
        return diversity
    
    def adaptive_mutation_rate(self, generation, stagnation_counter):
        """
        Ajusta la tasa de mutación según el progreso
        
        Args:
            generation (int): Generación actual
            stagnation_counter (int): Generaciones sin mejora
            
        Returns:
            float: Tasa de mutación ajustada
        """
        base_rate = self.mutation_rate
        
        # Aumentar mutación si hay estancamiento
        if stagnation_counter > 5:
            base_rate *= 1.5
        if stagnation_counter > 10:
            base_rate *= 2.0
        
        # Disminuir mutación en generaciones tardías si hay progreso
        if generation > 50 and stagnation_counter < 3:
            base_rate *= 0.8
        
        return min(0.3, base_rate)  # Límite máximo del 30%
    
    def evolve(self):
        """
        Ejecuta el algoritmo genético completo
        
        Returns:
            dict: El mejor mazo encontrado
        """
        print("Iniciando evolución...")
        print(f"Población: {self.population_size}, Generaciones: {self.max_generations}")
        print(f"Mutación: {self.mutation_rate}, Cruce: {self.crossover_rate}")
        
        # Evaluación inicial mediante torneo round-robin
        print("\nEvaluando población inicial mediante torneo round-robin...")
        fitness_values = self.evaluate_population_tournament(self.population_arrays, 0)
        
        # Estadísticas iniciales
        best_idx = np.argmax(fitness_values)
        best_fitness = fitness_values[best_idx]
        avg_fitness = np.mean(fitness_values)
        diversity = self.calculate_diversity(self.population_arrays)
        
        self.stats['best_fitness'].append(best_fitness)
        self.stats['avg_fitness'].append(avg_fitness)
        self.stats['diversity'].append(diversity)
        self.stats['mutation_rate'].append(self.mutation_rate)
        
        print(f"Gen 0: Mejor={best_fitness:.4f}, Promedio={avg_fitness:.4f}, Diversidad={diversity:.4f}")
        
        # Guardar mejor inicial
        best_deck = self.array_to_deck(self.population_arrays[best_idx], "Best_Gen_0")
        self.hall_of_fame.append((0, best_fitness, best_deck))
        self.best_fitness_ever = best_fitness
        
        # Evolución
        for generation in range(1, self.max_generations + 1):
            print(f"\n===== Generación {generation} =====")
            
            # Ajustar tasa de mutación
            current_mutation_rate = self.adaptive_mutation_rate(generation, self.stagnation_counter)
            
            # Nueva población
            new_population = []
            
            # Elitismo: preservar los mejores
            elite_indices = np.argsort(fitness_values)[-self.elite_size:]
            for idx in elite_indices:
                new_population.append(self.population_arrays[idx].copy())
            
            # Generar el resto de la población
            while len(new_population) < self.population_size:
                # Selección
                parent1 = self.tournament_selection(self.population_arrays, fitness_values)
                parent2 = self.tournament_selection(self.population_arrays, fitness_values)
                
                # Cruce
                if random.random() < 0.5:
                    child1, child2 = self.crossover_uniform(parent1, parent2)
                else:
                    child1, child2 = self.crossover_two_point(parent1, parent2)
                
                # Mutación
                # Aplicar diferentes tipos de mutación
                if random.random() < current_mutation_rate:
                    mutation_type = random.choice(['swap', 'add_remove', 'color_shift'])
                    if mutation_type == 'swap':
                        child1 = self.mutate_swap(child1)
                    elif mutation_type == 'add_remove':
                        child1 = self.mutate_add_remove(child1)
                    else:
                        child1 = self.mutate_color_shift(child1)
                
                if random.random() < current_mutation_rate:
                    mutation_type = random.choice(['swap', 'add_remove', 'color_shift'])
                    if mutation_type == 'swap':
                        child2 = self.mutate_swap(child2)
                    elif mutation_type == 'add_remove':
                        child2 = self.mutate_add_remove(child2)
                    else:
                        child2 = self.mutate_color_shift(child2)
                
                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)
            
            # Reemplazar población
            self.population_arrays = new_population
            
            # Evaluar nueva población mediante torneo
            print(f"Evaluando generación {generation} mediante torneo round-robin...")
            fitness_values = self.evaluate_population_tournament(self.population_arrays, generation)
            
            # Estadísticas
            best_idx = np.argmax(fitness_values)
            current_best_fitness = fitness_values[best_idx]
            avg_fitness = np.mean(fitness_values)
            diversity = self.calculate_diversity(self.population_arrays)
            
            self.stats['best_fitness'].append(current_best_fitness)
            self.stats['avg_fitness'].append(avg_fitness)
            self.stats['diversity'].append(diversity)
            self.stats['mutation_rate'].append(current_mutation_rate)
            
            print(f"Mejor={current_best_fitness:.4f}, Promedio={avg_fitness:.4f}, Diversidad={diversity:.4f}")
            print(f"Tasa de mutación actual: {current_mutation_rate:.4f}")
            
            # Verificar mejora
            if current_best_fitness > self.best_fitness_ever:
                self.best_fitness_ever = current_best_fitness
                self.stagnation_counter = 0
                best_deck = self.array_to_deck(self.population_arrays[best_idx], 
                                             f"Best_Gen_{generation}")
                self.hall_of_fame.append((generation, current_best_fitness, best_deck))
                print(f"¡Nueva mejor solución encontrada!")
                
                # Guardar el ganador anterior en old_winners si existe uno previo
                if len(self.hall_of_fame) > 1:
                    _, _, previous_best = self.hall_of_fame[-2]
                    self.save_old_winner(previous_best, generation-1)
                
                # Guardar el mejor mazo actual
                self.save_best_deck(best_deck, generation)
            else:
                self.stagnation_counter += 1
                print(f"Sin mejora durante {self.stagnation_counter} generaciones")
            
            # Guardar población cada 10 generaciones
            if generation % 10 == 0:
                self.save_population_arrays(generation)
            
            # Criterios de parada
            if self.stagnation_counter >= self.stagnation_limit:
                print(f"Terminando por estancamiento ({self.stagnation_limit} generaciones sin mejora)")
                break
            
            if current_best_fitness >= 0.95:
                print("Terminando por alcanzar fitness objetivo (95% win rate)")
                break
        
        # Guardar estadísticas finales
        self.save_statistics()
        
        # Retornar el mejor mazo encontrado
        if self.hall_of_fame:
            _, _, best_deck = max(self.hall_of_fame, key=lambda x: x[1])
            return best_deck
        else:
            return self.array_to_deck(self.population_arrays[0], "Final_Deck")
    
    def save_best_deck(self, deck, generation):
        """Guarda el mejor mazo encontrado"""
        # Formato JSON
        json_file = os.path.join(self.output_dir, f"best_deck_gen_{generation}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(deck, f, ensure_ascii=False, indent=2)
        
        # Formato Forge
        forge_file = os.path.join(self.output_dir, f"best_deck_gen_{generation}.dck")
        self.save_forge_deck(deck, forge_file)
    
    def save_population_arrays(self, generation):
        """Guarda la población actual como arrays"""
        arrays_data = {
            'generation': generation,
            'arrays': [arr.tolist() for arr in self.population_arrays]
        }
        
        file_path = os.path.join(self.output_dir, f"population_gen_{generation}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(arrays_data, f)
    
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
        csv_file = os.path.join(self.output_dir, "evolution_stats.csv")
        stats_df.to_csv(csv_file, index=False)
        
        # Crear gráficos
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # Fitness
        ax1.plot(stats_df['generation'], stats_df['best_fitness'], 'b-', label='Mejor')
        ax1.plot(stats_df['generation'], stats_df['avg_fitness'], 'r--', label='Promedio')
        ax1.set_xlabel('Generación')
        ax1.set_ylabel('Fitness')
        ax1.set_title('Evolución del Fitness')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Diversidad
        ax2.plot(stats_df['generation'], stats_df['diversity'], 'g-')
        ax2.set_xlabel('Generación')
        ax2.set_ylabel('Diversidad')
        ax2.set_title('Evolución de la Diversidad')
        ax2.grid(True, alpha=0.3)
        
        # Tasa de mutación
        ax3.plot(stats_df['generation'], stats_df['mutation_rate'], 'm-')
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
            ax4.set_title('Hall of Fame (Mejores Soluciones)')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "evolution_stats.png"), dpi=150)
        plt.close()
        
        # Guardar Hall of Fame
        hof_file = os.path.join(self.output_dir, "hall_of_fame.json")
        hof_data = []
        for gen, fitness, deck in self.hall_of_fame:
            hof_data.append({
                'generation': gen,
                'fitness': fitness,
                'deck_name': deck['name'],
                'colors': deck['colors'],
                'stats': deck['stats']
            })
        
        with open(hof_file, 'w', encoding='utf-8') as f:
            json.dump(hof_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nEstadísticas guardadas en {self.output_dir}")

if __name__ == "__main__":
    # Configuración
    config = {
        'population_file': "mtg_decks/initial_population.json",
        'catalog_path': "mtg_data/card_catalog.json",
        'indices_path': "mtg_data/card_indices.json",
        'output_dir': "mtg_evolved_decks",
        'forge_jar_path': "./forge-gui-desktop.jar",
        'max_generations': 100,
        'population_size': 50,
        'mutation_rate': 0.05,
        'crossover_rate': 0.9,
        'tournament_size': 3,
        'elite_size': 5,
        'stagnation_limit': 20
    }
    
    # Ejecutar algoritmo
    ga = MTGGeneticAlgorithm(**config)
    best_deck = ga.evolve()
    
    # Mostrar resultado
    print("\n===== MEJOR MAZO ENCONTRADO =====")
    print(f"Nombre: {best_deck['name']}")
    print(f"Colores: {', '.join(best_deck['colors'])}")
    print(f"Estadísticas: {best_deck['stats']}")
    print("\nCartas:")
    for card in sorted(best_deck['cards'], key=lambda x: (x['cmc'], x['name'])):
        print(f"  {card['count']}x {card['name']} ({card['mana_cost']})")