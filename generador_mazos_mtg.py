import pandas as pd
import numpy as np
import random
import os
import json
import matplotlib.pyplot as plt
from collections import Counter, defaultdict

class MTGDeckGenerator:
    def __init__(self, cards_csv_path="mtg_data/processed_standard_cards.csv", 
                 catalog_path="mtg_data/card_catalog.json",
                 indices_path="mtg_data/card_indices.json",
                 output_dir="mtg_decks"):
        """
        Inicializa el generador de mazos con representación de array
        
        Args:
            cards_csv_path (str): Ruta al archivo CSV con datos de cartas
            catalog_path (str): Ruta al catálogo de cartas
            indices_path (str): Ruta a los índices de cartas
            output_dir (str): Directorio para guardar los mazos generados
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Cargar catálogo de cartas
        print(f"Cargando catálogo de cartas desde: {catalog_path}")
        with open(catalog_path, 'r', encoding='utf-8') as f:
            self.card_catalog = json.load(f)
        
        # Convertir keys a int (JSON las guarda como strings)
        self.card_catalog = {int(k): v for k, v in self.card_catalog.items()}
        
        # Cargar índices
        print(f"Cargando índices desde: {indices_path}")
        with open(indices_path, 'r', encoding='utf-8') as f:
            indices_data = json.load(f)
            self.type_indices = indices_data['type_indices']
            self.color_indices = indices_data['color_indices']
            self.total_cards = indices_data['total_cards']
        
        print(f"Catálogo cargado: {len(self.card_catalog)} cartas")
        
        # Crear índices adicionales para generación eficiente
        self._prepare_generation_indices()
    
    def _prepare_generation_indices(self):
        """Prepara índices adicionales para generación eficiente de mazos"""
        # Índice de tierras básicas
        self.basic_lands_ids = {}
        basic_land_names = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']
        
        for card_id, card in self.card_catalog.items():
            if card['name'] in basic_land_names:
                self.basic_lands_ids[card['name']] = card_id
        
        # Índice de tierras no básicas
        self.nonbasic_lands_ids = []
        for card_id in self.type_indices.get('lands', []):
            if not self.card_catalog[card_id]['is_basic_land']:
                self.nonbasic_lands_ids.append(card_id)
        
        print(f"Índices preparados: {len(self.basic_lands_ids)} tierras básicas")
    
    def array_to_deck(self, deck_array, deck_name="Deck"):
        """
        Convierte un array de mazo a la representación completa
        
        Args:
            deck_array (np.array): Array donde cada posición es el número de copias
            deck_name (str): Nombre del mazo
            
        Returns:
            dict: Mazo en formato completo
        """
        cards = []
        colors = set()
        
        for card_id, count in enumerate(deck_array):
            if count > 0:
                card_data = self.card_catalog[card_id].copy()
                card_data['count'] = int(count)
                cards.append(card_data)
                
                # Acumular colores
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
        
        # CMC promedio (excluyendo tierras)
        nonland_cards = [c for c in cards if not c['is_land']]
        if nonland_cards:
            avg_cmc = sum(c['cmc'] * c['count'] for c in nonland_cards) / sum(c['count'] for c in nonland_cards)
        else:
            avg_cmc = 0.0
        
        return {
            'name': deck_name,
            'colors': sorted(list(colors)),
            'array': deck_array.tolist(),  # Guardar el array para operaciones genéticas
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
    
    def deck_to_array(self, deck):
        """
        Convierte un mazo en formato completo a array
        
        Args:
            deck (dict): Mazo en formato completo
            
        Returns:
            np.array: Array de tamaño fijo
        """
        # Si el mazo ya tiene el array guardado, usarlo
        if 'array' in deck:
            return np.array(deck['array'])
        
        # Si no, reconstruir el array
        deck_array = np.zeros(self.total_cards, dtype=int)
        
        for card in deck['cards']:
            card_id = card['card_id']
            count = card['count']
            deck_array[card_id] = count
        
        return deck_array
    
    def generate_random_deck_array(self, colors=None, num_colors=2):
        """
        Genera un array de mazo aleatorio con las restricciones especificadas
        
        Args:
            colors (list): Lista de colores específicos, o None para aleatorio
            num_colors (int): Número de colores si no se especifican
            
        Returns:
            np.array: Array representando el mazo
        """
        # Inicializar array vacío
        deck_array = np.zeros(self.total_cards, dtype=int)
        
        # Seleccionar colores si no se especifican
        if colors is None:
            all_colors = ['W', 'U', 'B', 'R', 'G']
            colors = random.sample(all_colors, min(num_colors, len(all_colors)))
        
        # Determinar pool de cartas disponibles
        available_cards = set()
        
        # Añadir cartas de los colores seleccionados
        for color in colors:
            available_cards.update(self.color_indices.get(color, []))
        
        # Añadir cartas incoloras
        available_cards.update(self.color_indices.get('colorless', []))
        
        # Añadir cartas multicolor que contengan solo los colores seleccionados
        for card_id in self.color_indices.get('multicolor', []):
            card_colors = self.card_catalog[card_id]['color_identity']
            if all(c in colors for c in card_colors):
                available_cards.add(card_id)
        
        # Convertir a lista para indexación
        available_cards = list(available_cards)
        
        # Separar por tipos
        lands_pool = [c for c in available_cards if c in self.type_indices.get('lands', [])]
        creatures_pool = [c for c in available_cards if c in self.type_indices.get('creatures', [])]
        spells_pool = [c for c in available_cards if c in self.type_indices.get('spells', [])]
        artifacts_pool = [c for c in available_cards if c in self.type_indices.get('artifacts_enchantments', [])]
        planeswalkers_pool = [c for c in available_cards if c in self.type_indices.get('planeswalkers', [])]
        
        # Generar distribución de cartas
        num_lands = random.randint(22, 26)  # 22-26 tierras
        num_nonlands = 60 - num_lands
        
        # Distribución de no-tierras
        num_creatures = random.randint(int(num_nonlands * 0.3), int(num_nonlands * 0.5))
        num_spells = random.randint(int(num_nonlands * 0.2), int(num_nonlands * 0.35))
        num_artifacts = random.randint(0, int(num_nonlands * 0.15))
        num_planeswalkers = random.randint(0, min(3, int(num_nonlands * 0.1)))
        
        # Ajustar para que sume exactamente num_nonlands
        current_total = num_creatures + num_spells + num_artifacts + num_planeswalkers
        if current_total < num_nonlands:
            diff = num_nonlands - current_total
            num_creatures += diff
        elif current_total > num_nonlands:
            diff = current_total - num_nonlands
            if num_creatures > diff:
                num_creatures -= diff
            else:
                num_spells -= (diff - num_creatures)
                num_creatures = 0
        
        # Función auxiliar para añadir cartas
        def add_cards_from_pool(pool, num_cards, max_copies=4):
            cards_added = 0
            attempts = 0
            max_attempts = num_cards * 10
            
            while cards_added < num_cards and pool and attempts < max_attempts:
                card_id = random.choice(pool)
                
                # Tierras básicas pueden tener más de 4 copias
                if self.card_catalog[card_id]['is_basic_land']:
                    max_allowed = 20
                else:
                    max_allowed = max_copies
                
                if deck_array[card_id] < max_allowed:
                    copies_to_add = min(
                        random.randint(1, max_allowed - deck_array[card_id]),
                        num_cards - cards_added
                    )
                    deck_array[card_id] += copies_to_add
                    cards_added += copies_to_add
                
                attempts += 1
            
            return cards_added
        
        # Añadir tierras básicas
        basic_lands_needed = max(15, num_lands - len(lands_pool))
        color_to_basic = {
            'W': 'Plains', 'U': 'Island', 'B': 'Swamp', 
            'R': 'Mountain', 'G': 'Forest'
        }
        
        lands_per_color = basic_lands_needed // len(colors)
        remainder = basic_lands_needed % len(colors)
        
        for i, color in enumerate(colors):
            basic_land_name = color_to_basic.get(color)
            if basic_land_name and basic_land_name in self.basic_lands_ids:
                card_id = self.basic_lands_ids[basic_land_name]
                count = lands_per_color + (1 if i < remainder else 0)
                deck_array[card_id] = count
        
        # Añadir tierras no básicas
        nonbasic_lands_needed = num_lands - basic_lands_needed
        nonbasic_pool = [c for c in lands_pool if not self.card_catalog[c]['is_basic_land']]
        if nonbasic_pool and nonbasic_lands_needed > 0:
            add_cards_from_pool(nonbasic_pool, nonbasic_lands_needed)
        
        # Añadir el resto de cartas
        add_cards_from_pool(creatures_pool, num_creatures)
        add_cards_from_pool(spells_pool, num_spells)
        add_cards_from_pool(artifacts_pool, num_artifacts)
        add_cards_from_pool(planeswalkers_pool, num_planeswalkers)
        
        # Verificar y ajustar a exactamente 60 cartas
        total = np.sum(deck_array)
        if total < 60:
            # Añadir más cartas
            diff = 60 - total
            all_nonlands = creatures_pool + spells_pool
            for _ in range(diff):
                if all_nonlands:
                    card_id = random.choice(all_nonlands)
                    if deck_array[card_id] < 4:
                        deck_array[card_id] += 1
        elif total > 60:
            # Quitar cartas
            diff = total - 60
            nonzero_indices = np.where(deck_array > 0)[0]
            for _ in range(diff):
                if len(nonzero_indices) > 0:
                    card_id = random.choice(nonzero_indices)
                    deck_array[card_id] -= 1
                    if deck_array[card_id] == 0:
                        nonzero_indices = np.where(deck_array > 0)[0]
        
        return deck_array
    
    def generate_strategic_population(self, total_size=50):
        """
        Genera una población inicial estratégica usando arrays
        
        Args:
            total_size (int): Tamaño total de la población
            
        Returns:
            list: Lista de mazos generados
        """
        print(f"Generando población inicial estratégica de {total_size} mazos...")
        population = []
        deck_counter = 0
        
        all_colors = ['W', 'U', 'B', 'R', 'G']
        
        # 1. Mazos mono-color (2 por cada color = 10 mazos)
        print("\n--- Generando mazos mono-color ---")
        for color in all_colors:
            for i in range(2):
                deck_counter += 1
                color_name = {'W': 'Blanco', 'U': 'Azul', 'B': 'Negro', 'R': 'Rojo', 'G': 'Verde'}[color]
                deck_name = f"Mono_{color_name}_{i+1}"
                
                try:
                    deck_array = self.generate_random_deck_array(colors=[color])
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"Mazo {deck_counter} generado: {deck_name}")
                except Exception as e:
                    print(f"Error al generar mazo {deck_name}: {e}")
        
        # 2. Mazos bi-color (20 mazos - 2 por cada combinación)
        print("\n--- Generando mazos bi-color ---")
        for i, color1 in enumerate(all_colors):
            for color2 in all_colors[i+1:]:
                # Solo generar 1 mazo por combinación para mantener el tamaño total
                deck_counter += 1
                color_names = {
                    'W': 'Blanco', 'U': 'Azul', 'B': 'Negro', 'R': 'Rojo', 'G': 'Verde'
                }
                deck_name = f"{color_names[color1]}_{color_names[color2]}_1"
                
                try:
                    deck_array = self.generate_random_deck_array(colors=[color1, color2])
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"Mazo {deck_counter} generado: {deck_name}")
                except Exception as e:
                    print(f"Error al generar mazo {deck_name}: {e}")
        
        # 3. Mazos tri-color (10 mazos)
        print("\n--- Generando mazos tri-color ---")
        tricolor_combinations = [
            ['W', 'U', 'B'], ['U', 'B', 'R'], ['B', 'R', 'G'], 
            ['R', 'G', 'W'], ['G', 'W', 'U'],  # Shards
            ['W', 'B', 'R'], ['U', 'R', 'G'], ['B', 'G', 'W'],
            ['R', 'W', 'U'], ['G', 'U', 'B']   # Wedges
        ]
        
        for colors in tricolor_combinations:
            deck_counter += 1
            deck_name = f"Tri_{''.join(colors)}"
            
            try:
                deck_array = self.generate_random_deck_array(colors=colors)
                deck = self.array_to_deck(deck_array, deck_name)
                population.append(deck)
                print(f"Mazo {deck_counter} generado: {deck_name}")
            except Exception as e:
                print(f"Error al generar mazo {deck_name}: {e}")
        
        # 4. Mazos 4-5 colores (10 mazos)
        print("\n--- Generando mazos de 4-5 colores ---")
        
        # 5 mazos de 4 colores
        for color_to_exclude in all_colors:
            deck_counter += 1
            four_colors = [c for c in all_colors if c != color_to_exclude]
            deck_name = f"4Color_Sin_{color_to_exclude}"
            
            try:
                deck_array = self.generate_random_deck_array(colors=four_colors)
                deck = self.array_to_deck(deck_array, deck_name)
                population.append(deck)
                print(f"Mazo {deck_counter} generado: {deck_name}")
            except Exception as e:
                print(f"Error al generar mazo {deck_name}: {e}")
        
        # 5 mazos de 5 colores
        for i in range(5):
            deck_counter += 1
            deck_name = f"5Color_{i+1}"
            
            try:
                deck_array = self.generate_random_deck_array(colors=all_colors)
                deck = self.array_to_deck(deck_array, deck_name)
                population.append(deck)
                print(f"Mazo {deck_counter} generado: {deck_name}")
            except Exception as e:
                print(f"Error al generar mazo {deck_name}: {e}")
        
        # Guardar la población
        self.save_population(population)
        
        print(f"\nPoblación inicial generada: {len(population)} mazos")
        return population
    
    def save_population(self, population):
        """Guarda una población de mazos"""
        # Guardar en formato JSON
        population_file = os.path.join(self.output_dir, "initial_population.json")
        with open(population_file, 'w', encoding='utf-8') as f:
            json.dump(population, f, ensure_ascii=False, indent=2)
        print(f"Población guardada en: {population_file}")
        
        # Guardar cada mazo en formato .dck
        for deck in population:
            self.save_as_forge_deck(deck)
            
            # Generar estadísticas visuales
            stats_path = os.path.join(self.output_dir, f"{deck['name']}_stats.png")
            self.plot_deck_stats(deck, stats_path)
    
    def save_as_forge_deck(self, deck):
        """
        Guarda el mazo en formato .dck para Forge
        
        Args:
            deck (dict): Diccionario con información del mazo
        """
        # Guardar en el directorio de salida del generador
        filename = os.path.join(self.output_dir, f"{deck['name']}.dck")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"[metadata]\n")
            f.write(f"Name={deck['name']}\n")
            f.write(f"\n[Main]\n")
            
            for card_info in deck['cards']:
                count = card_info['count']
                card_name = card_info['name']
                
                # Forge espera el formato simple "cantidad nombre"
                f.write(f"{count} {card_name}\n")
    
    def plot_deck_stats(self, deck, save_path=None):
        """
        Genera y guarda gráficos de estadísticas del mazo
        
        Args:
            deck (dict): Diccionario con información del mazo
            save_path (str, optional): Ruta donde guardar los gráficos
        """
        # Calcular estadísticas
        stats = self.analyze_deck(deck)
        
        # Crear figura con subplots
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
        
        # 1. Curva de maná
        mana_costs = list(stats['mana_curve'].keys())
        mana_counts = list(stats['mana_curve'].values())
        
        ax1.bar(mana_costs, mana_counts, color='steelblue')
        ax1.set_title('Curva de maná', fontsize=14)
        ax1.set_xlabel('Coste de maná')
        ax1.set_ylabel('Número de cartas')
        ax1.grid(True, alpha=0.3)
        
        # 2. Distribución de tipos
        types = list(stats['type_distribution'].keys())
        type_counts = list(stats['type_distribution'].values())
        
        colors_pie = ['#8B4513', '#1E90FF', '#FF6347', '#FFD700', '#9370DB']
        ax2.pie(type_counts, labels=types, autopct='%1.1f%%', startangle=90, colors=colors_pie)
        ax2.set_title('Distribución por tipo', fontsize=14)
        
        # 3. Distribución de colores
        colors = list(stats['color_distribution'].keys())
        color_counts = list(stats['color_distribution'].values())
        
        # Asignar colores reales para el gráfico
        color_map = {
            'Blanco': '#FFFACD',
            'Azul': '#4169E1',
            'Negro': '#2F4F4F',
            'Rojo': '#DC143C',
            'Verde': '#228B22',
            'Incoloro': '#C0C0C0'
        }
        plot_colors = [color_map.get(color, 'gray') for color in colors]
        
        ax3.bar(colors, color_counts, color=plot_colors)
        ax3.set_title('Distribución por color', fontsize=14)
        ax3.set_xlabel('Color')
        ax3.set_ylabel('Número de cartas')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Añadir título general
        fig.suptitle(f"Estadísticas de {deck['name']}", fontsize=16, y=1.02)
        
        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=150)
            plt.close()
        else:
            plt.show()
    
    def analyze_deck(self, deck):
        """
        Analiza un mazo y genera estadísticas detalladas
        
        Args:
            deck (dict): Diccionario con información del mazo
            
        Returns:
            dict: Estadísticas del mazo
        """
        # Calcular curva de maná
        mana_curve = defaultdict(int)
        type_distribution = defaultdict(int)
        color_distribution = defaultdict(int)
        
        for card in deck['cards']:
            count = card['count']
            
            # Curva de maná (excluyendo tierras)
            if not card['is_land']:
                cmc = int(card['cmc'])
                if cmc >= 7:
                    mana_curve['7+'] += count
                else:
                    mana_curve[str(cmc)] += count
            
            # Distribución de tipos
            if card['is_land']:
                type_distribution['Tierras'] += count
            elif card['is_creature']:
                type_distribution['Criaturas'] += count
            elif card['is_instant']:
                type_distribution['Instantáneos'] += count
            elif card['is_sorcery']:
                type_distribution['Conjuros'] += count
            elif card['is_planeswalker']:
                type_distribution['Planeswalkers'] += count
            elif card['is_artifact'] or card['is_enchantment']:
                type_distribution['Artefactos/Encantamientos'] += count
            
            # Distribución de colores (excluyendo tierras)
            if not card['is_land']:
                if len(card['color_identity']) == 0:
                    color_distribution['Incoloro'] += count
                else:
                    for color in card['color_identity']:
                        color_name = {
                            'W': 'Blanco', 'U': 'Azul', 'B': 'Negro',
                            'R': 'Rojo', 'G': 'Verde'
                        }.get(color, color)
                        color_distribution[color_name] += count
        
        # Ordenar curva de maná
        sorted_curve = {}
        for i in range(7):
            sorted_curve[str(i)] = mana_curve.get(str(i), 0)
        sorted_curve['7+'] = mana_curve.get('7+', 0)
        
        return {
            'mana_curve': sorted_curve,
            'type_distribution': dict(type_distribution),
            'color_distribution': dict(color_distribution)
        }

if __name__ == "__main__":
    generator = MTGDeckGenerator()
    
    # Generar población inicial
    population = generator.generate_strategic_population(50)
    
    # Mostrar estadísticas de la población
    if population:
        print("\nResumen de la población generada:")
        color_combinations = defaultdict(int)
        
        for deck in population:
            colors = ''.join(sorted(deck['colors']))
            if not colors:
                colors = 'Incoloro'
            color_combinations[colors] += 1
        
        print("Distribución por combinaciones de colores:")
        for colors, count in sorted(color_combinations.items()):
            print(f"  {colors}: {count} mazos")