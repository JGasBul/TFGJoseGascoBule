import pandas as pd
import numpy as np
import random
import os
import json
import matplotlib.pyplot as plt
import glob
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
    
    def clean_existing_decks(self):
        """
        Limpia todos los mazos existentes (.dck y .json) antes de generar nuevos
        """
        files_removed = 0
        
        # Patrones de archivos a eliminar
        patterns_to_clean = [
            "*.dck",                    # Archivos de mazo de Forge
            "*population*.json",        # Archivos de población
            "*_stats.png",             # Gráficos de estadísticas
            "Best_*",                  # Mejores mazos anteriores
            "Gen*_Deck*.dck",          # Mazos de generaciones del AG
            "Mono_*",                  # Mazos mono-color
            "Bi_*",                    # Mazos bi-color
            "Tri_*",                   # Mazos tri-color
            "*Color_*",                # Mazos multicolor
            "Random_*",                # Mazos aleatorios
            "Test_*",                  # Mazos de prueba
            "Extra_*"                  # Mazos extra
        ]
        
        print(f"\n🧹 Limpiando mazos existentes en {self.output_dir}...")
        
        for pattern in patterns_to_clean:
            file_pattern = os.path.join(self.output_dir, pattern)
            files = glob.glob(file_pattern)
            
            for file_path in files:
                try:
                    os.remove(file_path)
                    files_removed += 1
                    print(f"   Eliminado: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"   Error eliminando {os.path.basename(file_path)}: {e}")
        
        if files_removed > 0:
            print(f"✅ {files_removed} archivos eliminados correctamente")
        else:
            print("ℹ️  No se encontraron archivos para eliminar")
        
        return files_removed
    
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
        
        # NUEVA LÓGICA DE FILTRADO DE CARTAS
        available_cards = set()
        
        # Añadir cartas que SOLO contengan los colores permitidos
        for card_id, card in self.card_catalog.items():
            card_colors = set(card['color_identity'])
            allowed_colors = set(colors)
            
            # Criterios de inclusión:
            # 1. La carta no debe tener colores prohibidos
            # 2. Incluir cartas incoloras SOLO si no tienen color identity problemática
            if card_colors.issubset(allowed_colors):
                available_cards.add(card_id)
            # Casos especiales: tierras básicas siempre permitidas para sus colores
            elif card.get('is_basic_land', False) and len(card_colors) == 1 and card_colors.issubset(allowed_colors):
                available_cards.add(card_id)
        
        # Verificar que tenemos cartas suficientes
        if len(available_cards) < 20:
            print(f"⚠️  Advertencia: Solo {len(available_cards)} cartas disponibles para {colors}")
            # Fallback: añadir cartas incoloras verdaderas
            for card_id, card in self.card_catalog.items():
                if len(card['color_identity']) == 0:  # Verdaderamente incoloras
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
                if self.card_catalog[card_id].get('is_basic_land', False):
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
        basic_lands_needed = max(15, num_lands - len([c for c in lands_pool if not self.card_catalog[c].get('is_basic_land', False)]))
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
        nonbasic_pool = [c for c in lands_pool if not self.card_catalog[c].get('is_basic_land', False)]
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
    
    def generate_population_exact_size(self, total_size):
        """
        Genera una población de exactamente el tamaño especificado 
        manteniendo proporcionalidad estratégica
        
        Args:
            total_size (int): Número exacto de mazos a generar
            
        Returns:
            list: Lista de mazos generados
        """
        print(f"Generando población de EXACTAMENTE {total_size} mazos...")
        
        if total_size < 5:
            print("ERROR: Se necesitan al mínimo 5 mazos para diversidad básica")
            return []
        
        # Limpiar mazos existentes automáticamente
        self.clean_existing_decks()
        
        population = []
        deck_counter = 0
        all_colors = ['W', 'U', 'B', 'R', 'G']
        
        # DISTRIBUCIÓN PROPORCIONAL SEGÚN TAMAÑO
        distribution = self._calculate_distribution(total_size)
        
        print(f"\nDistribución calculada para {total_size} mazos:")
        for category, count in distribution.items():
            if count > 0:
                print(f"  {category}: {count} mazos")
        
        # 1. MAZOS MONO-COLOR
        print(f"\n--- Generando {distribution['mono']} mazos mono-color ---")
        mono_per_color = distribution['mono'] // 5
        extra_mono = distribution['mono'] % 5
        
        for i, color in enumerate(all_colors):
            count = mono_per_color + (1 if i < extra_mono else 0)
            if count > 0:
                deck_counter += 1
                color_name = {'W': 'Blanco', 'U': 'Azul', 'B': 'Negro', 'R': 'Rojo', 'G': 'Verde'}[color]
                deck_name = f"Mono_{color_name}_{deck_counter}"
                
                try:
                    deck_array = self.generate_random_deck_array(colors=[color])
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"  Mazo {deck_counter}: {deck_name}")
                except Exception as e:
                    print(f"  Error al generar {deck_name}: {e}")
        
        # 2. MAZOS BI-COLOR
        if distribution['bi'] > 0:
            print(f"\n--- Generando {distribution['bi']} mazos bi-color ---")
            
            # Todas las combinaciones de 2 colores (10 total)
            bi_combinations = []
            for i, color1 in enumerate(all_colors):
                for color2 in all_colors[i+1:]:
                    bi_combinations.append([color1, color2])
            
            # Distribuir mazos bi-color proporcionalmente
            bi_per_combo = distribution['bi'] // len(bi_combinations)
            extra_bi = distribution['bi'] % len(bi_combinations)
            
            combo_idx = 0
            for colors in bi_combinations:
                count = bi_per_combo + (1 if combo_idx < extra_bi else 0)
                for j in range(count):
                    deck_counter += 1
                    color_names = {
                        'W': 'Blanco', 'U': 'Azul', 'B': 'Negro', 'R': 'Rojo', 'G': 'Verde'
                    }
                    deck_name = f"Bi_{color_names[colors[0]]}_{color_names[colors[1]]}_{j+1}"
                    
                    try:
                        deck_array = self.generate_random_deck_array(colors=colors)
                        deck = self.array_to_deck(deck_array, deck_name)
                        population.append(deck)
                        print(f"  Mazo {deck_counter}: {deck_name}")
                    except Exception as e:
                        print(f"  Error al generar {deck_name}: {e}")
                combo_idx += 1
        
        # 3. MAZOS TRI-COLOR
        if distribution['tri'] > 0:
            print(f"\n--- Generando {distribution['tri']} mazos tri-color ---")
            
            # Combinaciones populares de 3 colores
            tri_combinations = [
                ['W', 'U', 'B'],  # Esper
                ['U', 'B', 'R'],  # Grixis
                ['B', 'R', 'G'],  # Jund
                ['R', 'G', 'W'],  # Naya
                ['G', 'W', 'U'],  # Bant
                ['W', 'B', 'R'],  # Mardu
                ['U', 'R', 'G'],  # Temur
                ['B', 'G', 'W'],  # Abzan
                ['R', 'W', 'U'],  # Jeskai
                ['G', 'U', 'B']   # Sultai
            ]
            
            # Distribuir proporcionalmente
            tri_per_combo = distribution['tri'] // len(tri_combinations)
            extra_tri = distribution['tri'] % len(tri_combinations)
            
            combo_idx = 0
            for colors in tri_combinations:
                count = tri_per_combo + (1 if combo_idx < extra_tri else 0)
                for j in range(count):
                    deck_counter += 1
                    deck_name = f"Tri_{''.join(colors)}_{j+1}"
                    
                    try:
                        deck_array = self.generate_random_deck_array(colors=colors)
                        deck = self.array_to_deck(deck_array, deck_name)
                        population.append(deck)
                        print(f"  Mazo {deck_counter}: {deck_name}")
                    except Exception as e:
                        print(f"  Error al generar {deck_name}: {e}")
                combo_idx += 1
                
                if len(population) >= total_size:
                    break
        
        # 4. MAZOS DE 4+ COLORES
        if distribution['multi'] > 0:
            print(f"\n--- Generando {distribution['multi']} mazos multicolor (4-5 colores) ---")
            
            for i in range(distribution['multi']):
                deck_counter += 1
                
                # Alternar entre 4 y 5 colores
                if i % 2 == 0:
                    # 4 colores (excluir uno)
                    excluded_color = all_colors[i % 5]
                    colors = [c for c in all_colors if c != excluded_color]
                    deck_name = f"4Color_Sin{excluded_color}_{deck_counter}"
                else:
                    # 5 colores
                    colors = all_colors.copy()
                    deck_name = f"5Color_{deck_counter}"
                
                try:
                    deck_array = self.generate_random_deck_array(colors=colors)
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"  Mazo {deck_counter}: {deck_name}")
                except Exception as e:
                    print(f"  Error al generar {deck_name}: {e}")
        
        # 5. MAZOS ALEATORIOS PARA COMPLETAR
        remaining = total_size - len(population)
        if remaining > 0:
            print(f"\n--- Generando {remaining} mazos aleatorios para completar ---")
            
            for i in range(remaining):
                deck_counter += 1
                
                # Número aleatorio de colores (1-3, con sesgo hacia 2)
                color_distribution = [1, 2, 2, 2, 3]  # Sesgo hacia bi-color
                num_colors = random.choice(color_distribution)
                colors = random.sample(all_colors, num_colors)
                deck_name = f"Random_{''.join(sorted(colors))}_{deck_counter}"
                
                try:
                    deck_array = self.generate_random_deck_array(colors=colors)
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"  Mazo {deck_counter}: {deck_name}")
                except Exception as e:
                    print(f"  Error al generar {deck_name}: {e}")
        
        # VERIFICACIÓN FINAL
        actual_size = len(population)
        if actual_size != total_size:
            print(f"\n⚠️  ADVERTENCIA: Se generaron {actual_size} mazos en lugar de {total_size}")
            
            if actual_size > total_size:
                # Eliminar mazos extra (los últimos aleatorios)
                population = population[:total_size]
                print(f"   Recortado a {total_size} mazos")
            elif actual_size < total_size:
                # Generar mazos adicionales simples
                missing = total_size - actual_size
                print(f"   Generando {missing} mazos adicionales...")
                
                for i in range(missing):
                    deck_counter += 1
                    colors = random.sample(all_colors, 2)  # Bi-color por defecto
                    deck_name = f"Extra_{deck_counter}"
                    
                    try:
                        deck_array = self.generate_random_deck_array(colors=colors)
                        deck = self.array_to_deck(deck_array, deck_name)
                        population.append(deck)
                    except Exception as e:
                        print(f"   Error al generar mazo extra: {e}")
        
        # Guardar población
        if len(population) <= 20:
            filename = "test_population.json"
        else:
            filename = "initial_population.json"
        
        population_file = os.path.join(self.output_dir, filename)
        with open(population_file, 'w', encoding='utf-8') as f:
            json.dump(population, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Población final: {len(population)} mazos")
        print(f"   Guardada en: {population_file}")
        
        # Guardar mazos en formato .dck y generar gráficos
        print(f"\n📊 Generando archivos .dck y gráficos de estadísticas...")
        successful_graphs = 0
        for i, deck in enumerate(population):
            # Guardar en formato Forge
            self.save_as_forge_deck(deck)
            
            # Generar gráfico para cada mazo
            stats_path = os.path.join(self.output_dir, f"{deck['name']}_stats.png")
            try:
                if self.plot_deck_stats(deck, stats_path):
                    successful_graphs += 1
                
                # Mostrar progreso cada 10 mazos o al final
                if (i + 1) % 10 == 0 or (i + 1) == len(population):
                    print(f"   Procesados: {i + 1}/{len(population)} mazos")
                    
            except Exception as e:
                print(f"   ⚠️  Error con {deck['name']}: {e}")
        
        print(f"✅ Generados exitosamente: {successful_graphs}/{len(population)} gráficos")
        
        # Análisis final de distribución
        self._analyze_final_distribution(population)
        
        return population
    
    def _calculate_distribution(self, total_size):
        """
        Calcula la distribución proporcional de tipos de mazos
        
        Args:
            total_size (int): Tamaño total de la población
            
        Returns:
            dict: Distribución por categorías
        """
        # Porcentajes objetivo (suman 100%)
        DISTRIBUTION_PERCENTAGES = {
            'mono': 0.25,      # 25% mono-color
            'bi': 0.50,        # 50% bi-color (más común/competitivo)
            'tri': 0.20,       # 20% tri-color 
            'multi': 0.05      # 5% multicolor (4-5 colores)
        }
        
        distribution = {}
        allocated = 0
        
        # Calcular cantidades manteniendo al menos 1 de cada tipo importante
        for category, percentage in DISTRIBUTION_PERCENTAGES.items():
            if total_size >= 20:
                # Para poblaciones grandes, usar porcentajes
                count = max(1, int(total_size * percentage))
            else:
                # Para poblaciones pequeñas, distribución mínima
                if category == 'mono':
                    count = min(5, max(1, total_size // 4))
                elif category == 'bi':
                    count = min(10, max(1, total_size // 2))
                elif category == 'tri':
                    count = min(5, max(0, total_size // 6))
                else:  # multi
                    count = min(2, max(0, total_size // 10))
            
            distribution[category] = count
            allocated += count
        
        # Ajustar si nos pasamos o nos falta
        total_allocated = sum(distribution.values())
        difference = total_size - total_allocated
        
        if difference != 0:
            # Distribuir la diferencia priorizando bi-color
            if difference > 0:
                # Faltan mazos, añadir a bi-color
                distribution['bi'] += difference
            else:
                # Sobran mazos, quitar proporcionalmente
                categories = ['multi', 'tri', 'mono', 'bi']  # Orden de prioridad para quitar
                remaining_to_remove = abs(difference)
                
                for category in categories:
                    if remaining_to_remove <= 0:
                        break
                    
                    can_remove = max(0, distribution[category] - (1 if category in ['mono', 'bi'] else 0))
                    remove = min(can_remove, remaining_to_remove)
                    distribution[category] -= remove
                    remaining_to_remove -= remove
        
        return distribution
    
    def _analyze_final_distribution(self, population):
        """
        Analiza y muestra la distribución final de la población
        
        Args:
            population (list): Lista de mazos generados
        """
        print(f"\n📊 ANÁLISIS DE LA POBLACIÓN FINAL:")
        
        # Contar por número de colores
        color_distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        color_combinations = {}
        
        for deck in population:
            num_colors = len(deck['colors'])
            color_distribution[num_colors] += 1
            
            colors_key = ''.join(sorted(deck['colors'])) if deck['colors'] else 'Incoloro'
            color_combinations[colors_key] = color_combinations.get(colors_key, 0) + 1
        
        print(f"   Por número de colores:")
        for num_colors, count in color_distribution.items():
            if count > 0:
                color_name = {
                    0: 'Incoloro', 1: 'Mono-color', 2: 'Bi-color',
                    3: 'Tri-color', 4: '4 colores', 5: '5 colores'
                }[num_colors]
                percentage = (count / len(population)) * 100
                print(f"     {color_name}: {count} mazos ({percentage:.1f}%)")
        
        print(f"\n   Combinaciones específicas:")
        sorted_combinations = sorted(color_combinations.items(), key=lambda x: -x[1])
        for colors, count in sorted_combinations[:10]:  # Top 10
            percentage = (count / len(population)) * 100
            print(f"     {colors or 'Incoloro'}: {count} mazos ({percentage:.1f}%)")
        
        if len(sorted_combinations) > 10:
            others = sum(count for _, count in sorted_combinations[10:])
            percentage = (others / len(population)) * 100
            print(f"     Otros: {others} mazos ({percentage:.1f}%)")
    
    def generate_strategic_population(self, total_size=50):
        """
        Método principal para generar población estratégica
        Reemplaza al método original con lógica hardcodeada
        """
        return self.generate_population_exact_size(total_size)
    
    def generate_test_population(self, total_size=15):
        """
        Método principal para generar población de prueba
        Reemplaza al método original con lógica hardcodeada
        """
        return self.generate_population_exact_size(total_size)
    
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
        try:
            # Calcular estadísticas
            stats = self.analyze_deck(deck)
            
            # Crear figura con subplots
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
            
            # 1. Curva de maná
            mana_costs = list(stats['mana_curve'].keys())
            mana_counts = list(stats['mana_curve'].values())
            
            if sum(mana_counts) > 0:  # Solo si hay cartas no-tierra
                ax1.bar(mana_costs, mana_counts, color='steelblue')
                ax1.set_title('Curva de maná', fontsize=14)
                ax1.set_xlabel('Coste de maná')
                ax1.set_ylabel('Número de cartas')
                ax1.grid(True, alpha=0.3)
            else:
                ax1.text(0.5, 0.5, 'Sin cartas\nno-tierra', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_title('Curva de maná', fontsize=14)
            
            # 2. Distribución de tipos
            types = list(stats['type_distribution'].keys())
            type_counts = list(stats['type_distribution'].values())
            
            if sum(type_counts) > 0:
                # Filtrar tipos con 0 cartas
                filtered_types = []
                filtered_counts = []
                for t, c in zip(types, type_counts):
                    if c > 0:
                        filtered_types.append(t)
                        filtered_counts.append(c)
                
                if filtered_counts:
                    colors_pie = ['#8B4513', '#1E90FF', '#FF6347', '#FFD700', '#9370DB', '#32CD32']
                    ax2.pie(filtered_counts, labels=filtered_types, autopct='%1.1f%%', 
                           startangle=90, colors=colors_pie[:len(filtered_counts)])
                    ax2.set_title('Distribución por tipo', fontsize=14)
            else:
                ax2.text(0.5, 0.5, 'Sin datos', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('Distribución por tipo', fontsize=14)
            
            # 3. Distribución de colores
            colors = list(stats['color_distribution'].keys())
            color_counts = list(stats['color_distribution'].values())
            
            if sum(color_counts) > 0:
                # Filtrar colores con 0 cartas
                filtered_colors = []
                filtered_color_counts = []
                plot_colors = []
                
                # Asignar colores reales para el gráfico
                color_map = {
                    'Blanco': '#FFFACD',
                    'Azul': '#4169E1',
                    'Negro': '#2F4F4F',
                    'Rojo': '#DC143C',
                    'Verde': '#228B22',
                    'Incoloro': '#C0C0C0'
                }
                
                for color, count in zip(colors, color_counts):
                    if count > 0:
                        filtered_colors.append(color)
                        filtered_color_counts.append(count)
                        plot_colors.append(color_map.get(color, 'gray'))
                
                if filtered_colors:
                    ax3.bar(filtered_colors, filtered_color_counts, color=plot_colors)
                    ax3.set_title('Distribución por color', fontsize=14)
                    ax3.set_xlabel('Color')
                    ax3.set_ylabel('Número de cartas')
                    ax3.tick_params(axis='x', rotation=45)
                    ax3.grid(True, alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'Sin cartas\nde color', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Distribución por color', fontsize=14)
            
            plt.tight_layout()
            
            # Añadir título general
            fig.suptitle(f"Estadísticas de {deck['name']}", fontsize=16, y=1.02)
            
            if save_path:
                plt.savefig(save_path, bbox_inches='tight', dpi=150)
                plt.close()
                return True
            else:
                plt.show()
                return True
                
        except Exception as e:
            print(f"   Error generando gráfico para {deck['name']}: {e}")
            if 'fig' in locals():
                plt.close(fig)
            return False
    
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