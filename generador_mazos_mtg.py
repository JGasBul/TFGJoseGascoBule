"""
Generador de Mazos de Magic: The Gathering para Algoritmo Genético

Este módulo genera poblaciones de mazos de Magic totalmente aleatorios (sin sesgos estratégicos)
para ser usados como población inicial en un algoritmo genético. Los mazos respetan únicamente:
- 60 cartas exactas
- Colores asignados (mono-color, bi-color, tri-color, etc.)
- Tierras básicas apropiadas

El resto del contenido de cada mazo es completamente aleatorio, permitiendo que el algoritmo
genético descubra qué combinaciones funcionan mejor sin ayudas predefinidas.
"""

import pandas as pd
import numpy as np
import random
import os
import json
import matplotlib.pyplot as plt
import glob
from collections import Counter, defaultdict


class MTGDeckGenerator:
    """
    Generador de mazos aleatorios de Magic: The Gathering

    Este generador crea poblaciones de mazos con diversidad de colores pero sin
    distribuciones estratégicas predefinidas de tipos de cartas.
    """

    def __init__(self,
                 cards_csv_path="mtg_data/processed_standard_cards.csv",
                 catalog_path="mtg_data/card_catalog.json",
                 indices_path="mtg_data/card_indices.json",
                 output_dir="mtg_decks"):
        """
        Inicializa el generador de mazos

        Args:
            cards_csv_path: Ruta al archivo CSV con datos de cartas (no usado actualmente)
            catalog_path: Ruta al catálogo JSON con todas las cartas disponibles
            indices_path: Ruta al archivo JSON con índices de tipos y colores
            output_dir: Directorio donde se guardarán los mazos generados
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Cargar el catálogo completo de cartas
        print(f"Cargando catálogo de cartas desde: {catalog_path}")
        with open(catalog_path, 'r', encoding='utf-8') as f:
            self.card_catalog = json.load(f)

        # JSON guarda las claves como strings, las convertimos a enteros
        self.card_catalog = {int(k): v for k, v in self.card_catalog.items()}

        # Cargar índices que agrupan cartas por tipo y color
        print(f"Cargando índices desde: {indices_path}")
        with open(indices_path, 'r', encoding='utf-8') as f:
            indices_data = json.load(f)
            self.type_indices = indices_data['type_indices']
            self.color_indices = indices_data['color_indices']
            self.total_cards = indices_data['total_cards']

        print(f"Catálogo cargado: {len(self.card_catalog)} cartas")

        # Preparar índices adicionales para generación rápida
        self._prepare_generation_indices()

    def _prepare_generation_indices(self):
        """
        Prepara índices adicionales para acceso rápido a tierras básicas

        Identifica las cinco tierras básicas (Plains, Island, Swamp, Mountain, Forest)
        y crea un diccionario para acceso directo por nombre.
        """
        self.basic_lands_ids = {}
        basic_land_names = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']

        for card_id, card in self.card_catalog.items():
            if card['name'] in basic_land_names:
                self.basic_lands_ids[card['name']] = card_id

        # Identificar tierras no básicas para variedad
        self.nonbasic_lands_ids = []
        for card_id in self.type_indices.get('lands', []):
            if not self.card_catalog[card_id]['is_basic_land']:
                self.nonbasic_lands_ids.append(card_id)

        print(f"Índices preparados: {len(self.basic_lands_ids)} tierras básicas")

    def clean_existing_decks(self):
        """
        Limpia todos los mazos y archivos relacionados antes de generar nuevos

        Elimina archivos .dck (formato Forge), JSONs de población, gráficos estadísticos
        y cualquier otro archivo de mazos previos para empezar con un directorio limpio.

        Returns:
            int: Número de archivos eliminados
        """
        files_removed = 0

        # Patrones de todos los archivos que queremos eliminar
        patterns_to_clean = [
            "*.dck",                    # Mazos en formato Forge
            "*population*.json",        # Archivos de población
            "*_stats.png",              # Gráficos de estadísticas
            "Best_*",                   # Mejores mazos de ejecuciones anteriores
            "Gen*_Deck*.dck",           # Mazos de generaciones del algoritmo genético
            "Mono_*",                   # Mazos mono-color
            "Bi_*",                     # Mazos bi-color
            "Tri_*",                    # Mazos tri-color
            "*Color_*",                 # Mazos multicolor
            "Random_*",                 # Mazos aleatorios
            "Test_*",                   # Mazos de prueba
            "Extra_*"                   # Mazos extra
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

    # ==================================================================================
    # CONVERSIÓN ENTRE FORMATOS
    # ==================================================================================

    def array_to_deck(self, deck_array, deck_name="Deck"):
        """
        Convierte un array numérico a un diccionario de mazo completo

        El array es una representación compacta donde cada posición indica cuántas
        copias de esa carta hay en el mazo. Este método lo convierte a un formato
        completo con toda la información de las cartas y estadísticas calculadas.

        Args:
            deck_array: Array NumPy donde deck_array[i] = número de copias de la carta i
            deck_name: Nombre a asignar al mazo

        Returns:
            dict con claves:
                - name: nombre del mazo
                - colors: lista de colores presentes
                - array: el array original (para operaciones genéticas)
                - cards: lista de cartas con sus datos completos
                - stats: estadísticas calculadas del mazo
        """
        cards = []
        colors = set()

        # Recorrer el array y extraer las cartas presentes (count > 0)
        for card_id, count in enumerate(deck_array):
            if count > 0:
                card_data = self.card_catalog[card_id].copy()
                card_data['count'] = int(count)
                cards.append(card_data)

                # Acumular todos los colores presentes en el mazo
                for color in card_data['color_identity']:
                    colors.add(color)

        # Calcular estadísticas del mazo
        total_cards = sum(c['count'] for c in cards)
        lands = sum(c['count'] for c in cards if c['is_land'])
        creatures = sum(c['count'] for c in cards if c['is_creature'])
        spells = sum(c['count'] for c in cards if c['is_instant'] or c['is_sorcery'])
        artifacts_enchantments = sum(c['count'] for c in cards
                                   if (c['is_artifact'] or c['is_enchantment'])
                                   and not c['is_creature'])
        planeswalkers = sum(c['count'] for c in cards if c['is_planeswalker'])

        # Calcular coste de maná convertido (CMC) promedio, excluyendo tierras
        nonland_cards = [c for c in cards if not c['is_land']]
        if nonland_cards:
            avg_cmc = sum(c['cmc'] * c['count'] for c in nonland_cards) / sum(c['count'] for c in nonland_cards)
        else:
            avg_cmc = 0.0

        return {
            'name': deck_name,
            'colors': sorted(list(colors)),
            'array': deck_array.tolist(),
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
        Convierte un diccionario de mazo a array numérico

        Operación inversa a array_to_deck. Si el mazo ya tiene el array guardado,
        lo devuelve directamente. Si no, lo reconstruye desde la lista de cartas.

        Args:
            deck: Diccionario con información del mazo

        Returns:
            np.array: Array donde cada posición es el número de copias de esa carta
        """
        # Si el mazo ya tiene el array guardado, usarlo directamente
        if 'array' in deck:
            return np.array(deck['array'])

        # Si no, reconstruir el array desde cero
        deck_array = np.zeros(self.total_cards, dtype=int)

        for card in deck['cards']:
            card_id = card['card_id']
            count = card['count']
            deck_array[card_id] = count

        return deck_array

    # ==================================================================================
    # GENERACIÓN DE MAZOS ALEATORIOS
    # ==================================================================================

    def generate_random_deck_array(self, colors=None, num_colors=2):
        """
        Genera un mazo completamente aleatorio respetando solo restricciones mínimas

        FILOSOFÍA: Este método NO impone distribuciones estratégicas de tipos de cartas.
        Solo garantiza:
        1. Exactamente 60 cartas
        2. Cartas que respeten los colores asignados
        3. Tierras básicas apropiadas (15-25 aleatorias)

        El resto del mazo se rellena COMPLETAMENTE AL AZAR, permitiendo que el algoritmo
        genético descubra qué combinaciones funcionan mejor sin sesgos humanos.

        Args:
            colors: Lista de colores específicos ['W', 'U', 'B', 'R', 'G']
                   Si es None, se eligen num_colors colores al azar
            num_colors: Número de colores a elegir si colors es None

        Returns:
            np.array: Array de 60 cartas totalmente aleatorio
        """
        deck_array = np.zeros(self.total_cards, dtype=int)

        # Si no se especifican colores, elegir aleatoriamente
        if colors is None:
            all_colors = ['W', 'U', 'B', 'R', 'G']
            colors = random.sample(all_colors, min(num_colors, len(all_colors)))

        # Paso 1: Filtrar cartas disponibles según los colores permitidos
        available_cards = set()

        for card_id, card in self.card_catalog.items():
            card_colors = set(card['color_identity'])
            allowed_colors = set(colors)

            # Incluir carta si todos sus colores están permitidos
            if card_colors.issubset(allowed_colors):
                available_cards.add(card_id)
            # Las tierras básicas siempre se permiten para sus colores
            elif card.get('is_basic_land', False) and len(card_colors) == 1 and card_colors.issubset(allowed_colors):
                available_cards.add(card_id)

        # Verificación de seguridad: ¿tenemos suficientes cartas?
        if len(available_cards) < 20:
            print(f"⚠️  Advertencia: Solo {len(available_cards)} cartas disponibles para {colors}")
            # Añadir cartas incoloras como fallback
            for card_id, card in self.card_catalog.items():
                if len(card['color_identity']) == 0:
                    available_cards.add(card_id)

        # Separar tierras básicas del resto de cartas
        available_cards = list(available_cards)
        basic_lands = [c for c in available_cards if self.card_catalog[c].get('is_basic_land', False)]
        non_basic_cards = [c for c in available_cards if not self.card_catalog[c].get('is_basic_land', False)]

        # Paso 2: Añadir tierras básicas distribuidas según los colores del mazo
        color_to_basic = {
            'W': 'Plains',
            'U': 'Island',
            'B': 'Swamp',
            'R': 'Mountain',
            'G': 'Forest'
        }

        # Número aleatorio de tierras básicas (entre 15 y 25)
        num_basic_lands = random.randint(15, 25)
        lands_per_color = num_basic_lands // len(colors)
        remainder = num_basic_lands % len(colors)

        # Distribuir tierras entre los colores del mazo
        for i, color in enumerate(colors):
            basic_land_name = color_to_basic.get(color)
            if basic_land_name and basic_land_name in self.basic_lands_ids:
                card_id = self.basic_lands_ids[basic_land_name]
                count = lands_per_color + (1 if i < remainder else 0)
                deck_array[card_id] = count

        # Paso 3: Rellenar el resto del mazo COMPLETAMENTE AL AZAR hasta 60 cartas
        current_total = np.sum(deck_array)

        while current_total < 60 and non_basic_cards:
            # Elegir una carta completamente al azar
            card_id = random.choice(non_basic_cards)

            # Respetar límite de 4 copias (20 para tierras básicas)
            max_copies = 20 if self.card_catalog[card_id].get('is_basic_land', False) else 4

            # Añadir la carta si no hemos llegado al límite
            if deck_array[card_id] < max_copies:
                deck_array[card_id] += 1
                current_total += 1

        # Paso 4: Ajustar si nos pasamos de 60 (muy improbable, pero por seguridad)
        while current_total > 60:
            nonzero_indices = np.where(deck_array > 0)[0]
            if len(nonzero_indices) > 0:
                card_id = random.choice(nonzero_indices)
                deck_array[card_id] -= 1
                current_total -= 1
            else:
                break

        # Paso 5: Si aún no llegamos a 60, añadir más tierras básicas
        while current_total < 60 and basic_lands:
            card_id = random.choice(basic_lands)
            deck_array[card_id] += 1
            current_total += 1

        return deck_array

    # ==================================================================================
    # GENERACIÓN DE POBLACIONES
    # ==================================================================================

    def generate_population_exact_size(self, total_size):
        """
        Genera una población de mazos con diversidad de colores

        Este método genera exactamente el número de mazos solicitado, distribuyendo
        la población en diferentes categorías de colores:
        - Mono-color (25%): un solo color
        - Bi-color (50%): dos colores
        - Tri-color (20%): tres colores
        - Multicolor (5%): 4-5 colores

        IMPORTANTE: Esta distribución solo afecta a los COLORES de los mazos.
        El CONTENIDO de cada mazo sigue siendo completamente aleatorio.

        Args:
            total_size: Número exacto de mazos a generar

        Returns:
            list: Lista de diccionarios de mazos generados
        """
        print(f"Generando población de EXACTAMENTE {total_size} mazos...")

        if total_size < 5:
            print("ERROR: Se necesitan al mínimo 5 mazos para diversidad básica")
            return []

        # Limpiar mazos existentes antes de generar nuevos
        self.clean_existing_decks()

        population = []
        deck_counter = 0
        all_colors = ['W', 'U', 'B', 'R', 'G']

        # Calcular cuántos mazos de cada tipo generar
        distribution = self._calculate_distribution(total_size)

        print(f"\nDistribución calculada para {total_size} mazos:")
        for category, count in distribution.items():
            if count > 0:
                print(f"  {category}: {count} mazos")

        # --- GENERACIÓN DE MAZOS MONO-COLOR ---
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

        # --- GENERACIÓN DE MAZOS BI-COLOR ---
        if distribution['bi'] > 0:
            print(f"\n--- Generando {distribution['bi']} mazos bi-color ---")

            # Generar todas las combinaciones posibles de 2 colores (10 total)
            bi_combinations = []
            for i, color1 in enumerate(all_colors):
                for color2 in all_colors[i+1:]:
                    bi_combinations.append([color1, color2])

            # Distribuir los mazos bi-color entre las combinaciones
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

        # --- GENERACIÓN DE MAZOS TRI-COLOR ---
        if distribution['tri'] > 0:
            print(f"\n--- Generando {distribution['tri']} mazos tri-color ---")

            # Combinaciones clásicas de 3 colores (tienen nombres en MTG)
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

            # Distribuir los mazos tri-color entre las combinaciones
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

                # Salir si ya tenemos suficientes mazos
                if len(population) >= total_size:
                    break

        # --- GENERACIÓN DE MAZOS MULTICOLOR (4-5 colores) ---
        if distribution['multi'] > 0:
            print(f"\n--- Generando {distribution['multi']} mazos multicolor (4-5 colores) ---")

            for i in range(distribution['multi']):
                deck_counter += 1

                # Alternar entre 4 y 5 colores
                if i % 2 == 0:
                    # Mazo de 4 colores (excluir uno)
                    excluded_color = all_colors[i % 5]
                    colors = [c for c in all_colors if c != excluded_color]
                    deck_name = f"4Color_Sin{excluded_color}_{deck_counter}"
                else:
                    # Mazo de 5 colores (todos)
                    colors = all_colors.copy()
                    deck_name = f"5Color_{deck_counter}"

                try:
                    deck_array = self.generate_random_deck_array(colors=colors)
                    deck = self.array_to_deck(deck_array, deck_name)
                    population.append(deck)
                    print(f"  Mazo {deck_counter}: {deck_name}")
                except Exception as e:
                    print(f"  Error al generar {deck_name}: {e}")

        # --- COMPLETAR CON MAZOS ALEATORIOS SI FALTA ALGUNO ---
        remaining = total_size - len(population)
        if remaining > 0:
            print(f"\n--- Generando {remaining} mazos aleatorios para completar ---")

            for i in range(remaining):
                deck_counter += 1

                # Sesgo hacia mazos bi-color (más comunes en MTG competitivo)
                color_distribution = [1, 2, 2, 2, 3]
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

        # --- VERIFICACIÓN FINAL ---
        actual_size = len(population)
        if actual_size != total_size:
            print(f"\n⚠️  ADVERTENCIA: Se generaron {actual_size} mazos en lugar de {total_size}")

            if actual_size > total_size:
                # Eliminar mazos sobrantes
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

        # --- GUARDAR POBLACIÓN EN ARCHIVO JSON ---
        if len(population) <= 20:
            filename = "test_population.json"
        else:
            filename = "initial_population.json"

        population_file = os.path.join(self.output_dir, filename)
        with open(population_file, 'w', encoding='utf-8') as f:
            json.dump(population, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Población final: {len(population)} mazos")
        print(f"   Guardada en: {population_file}")

        # --- GUARDAR MAZOS EN FORMATO FORGE Y GENERAR GRÁFICOS ---
        print(f"\n📊 Generando archivos .dck y gráficos de estadísticas...")
        successful_graphs = 0
        for i, deck in enumerate(population):
            # Guardar cada mazo en formato .dck (para Forge)
            self.save_as_forge_deck(deck)

            # Generar gráfico de estadísticas para cada mazo
            stats_path = os.path.join(self.output_dir, f"{deck['name']}_stats.png")
            try:
                if self.plot_deck_stats(deck, stats_path):
                    successful_graphs += 1

                # Mostrar progreso periódicamente
                if (i + 1) % 10 == 0 or (i + 1) == len(population):
                    print(f"   Procesados: {i + 1}/{len(population)} mazos")

            except Exception as e:
                print(f"   ⚠️  Error con {deck['name']}: {e}")

        print(f"✅ Generados exitosamente: {successful_graphs}/{len(population)} gráficos")

        # Análisis final de la distribución generada
        self._analyze_final_distribution(population)

        return population

    def _calculate_distribution(self, total_size):
        """
        Calcula cuántos mazos de cada tipo de color generar

        Distribuye la población según porcentajes predefinidos, intentando
        mantener al menos 1 mazo de cada categoría importante.

        Args:
            total_size: Tamaño total de la población

        Returns:
            dict: {'mono': X, 'bi': Y, 'tri': Z, 'multi': W}
        """
        # Porcentajes objetivo que suman 100%
        DISTRIBUTION_PERCENTAGES = {
            'mono': 0.25,      # 25% mono-color
            'bi': 0.50,        # 50% bi-color (más competitivos históricamente)
            'tri': 0.20,       # 20% tri-color
            'multi': 0.05      # 5% multicolor (4-5 colores, menos comunes)
        }

        distribution = {}

        # Calcular cantidades según el tamaño de la población
        for category, percentage in DISTRIBUTION_PERCENTAGES.items():
            if total_size >= 20:
                # Poblaciones grandes: usar porcentajes directos
                count = max(1, int(total_size * percentage))
            else:
                # Poblaciones pequeñas: distribución mínima
                if category == 'mono':
                    count = min(5, max(1, total_size // 4))
                elif category == 'bi':
                    count = min(10, max(1, total_size // 2))
                elif category == 'tri':
                    count = min(5, max(0, total_size // 6))
                else:  # multi
                    count = min(2, max(0, total_size // 10))

            distribution[category] = count

        # Ajustar para que la suma sea exactamente total_size
        total_allocated = sum(distribution.values())
        difference = total_size - total_allocated

        if difference > 0:
            # Faltan mazos: añadir a bi-color (categoría más común)
            distribution['bi'] += difference
        elif difference < 0:
            # Sobran mazos: quitar en orden de prioridad
            categories = ['multi', 'tri', 'mono', 'bi']
            remaining_to_remove = abs(difference)

            for category in categories:
                if remaining_to_remove <= 0:
                    break

                # Mantener al menos 1 mazo de categorías importantes
                can_remove = max(0, distribution[category] - (1 if category in ['mono', 'bi'] else 0))
                remove = min(can_remove, remaining_to_remove)
                distribution[category] -= remove
                remaining_to_remove -= remove

        return distribution

    def _analyze_final_distribution(self, population):
        """
        Analiza y muestra estadísticas de la población generada

        Imprime un resumen detallado de la distribución de colores en la población,
        útil para verificar que se generó correctamente.

        Args:
            population: Lista de mazos generados
        """
        print(f"\n📊 ANÁLISIS DE LA POBLACIÓN FINAL:")

        # Contar mazos por número de colores
        color_distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        color_combinations = {}

        for deck in population:
            num_colors = len(deck['colors'])
            color_distribution[num_colors] += 1

            colors_key = ''.join(sorted(deck['colors'])) if deck['colors'] else 'Incoloro'
            color_combinations[colors_key] = color_combinations.get(colors_key, 0) + 1

        # Mostrar distribución por número de colores
        print(f"   Por número de colores:")
        for num_colors, count in color_distribution.items():
            if count > 0:
                color_name = {
                    0: 'Incoloro', 1: 'Mono-color', 2: 'Bi-color',
                    3: 'Tri-color', 4: '4 colores', 5: '5 colores'
                }[num_colors]
                percentage = (count / len(population)) * 100
                print(f"     {color_name}: {count} mazos ({percentage:.1f}%)")

        # Mostrar combinaciones específicas más comunes
        print(f"\n   Combinaciones específicas:")
        sorted_combinations = sorted(color_combinations.items(), key=lambda x: -x[1])
        for colors, count in sorted_combinations[:10]:  # Top 10
            percentage = (count / len(population)) * 100
            print(f"     {colors or 'Incoloro'}: {count} mazos ({percentage:.1f}%)")

        if len(sorted_combinations) > 10:
            others = sum(count for _, count in sorted_combinations[10:])
            percentage = (others / len(population)) * 100
            print(f"     Otros: {others} mazos ({percentage:.1f}%)")

    # ==================================================================================
    # MÉTODOS DE CONVENIENCIA
    # ==================================================================================

    def generate_strategic_population(self, total_size=50):
        """
        Genera población estratégica (wrapper para compatibilidad)

        Args:
            total_size: Número de mazos a generar (por defecto 50)

        Returns:
            list: Población generada
        """
        return self.generate_population_exact_size(total_size)

    def generate_test_population(self, total_size=15):
        """
        Genera población de prueba más pequeña

        Args:
            total_size: Número de mazos a generar (por defecto 15)

        Returns:
            list: Población generada
        """
        return self.generate_population_exact_size(total_size)

    # ==================================================================================
    # GUARDADO Y VISUALIZACIÓN
    # ==================================================================================

    def save_as_forge_deck(self, deck):
        """
        Guarda un mazo en formato .dck compatible con Forge

        Forge es un simulador de Magic que usa archivos .dck con formato:
        [metadata]
        Name=nombre_mazo

        [Main]
        4 Lightning Bolt
        20 Mountain
        ...

        Args:
            deck: Diccionario con información del mazo
        """
        filename = os.path.join(self.output_dir, f"{deck['name']}.dck")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"[metadata]\n")
            f.write(f"Name={deck['name']}\n")
            f.write(f"\n[Main]\n")

            for card_info in deck['cards']:
                count = card_info['count']
                card_name = card_info['name']
                f.write(f"{count} {card_name}\n")

    def plot_deck_stats(self, deck, save_path=None):
        """
        Genera gráficos de estadísticas del mazo

        Crea tres gráficos:
        1. Curva de maná: distribución de costes de maná
        2. Distribución de tipos: porcentaje de tierras, criaturas, hechizos, etc.
        3. Distribución de colores: cartas de cada color

        Args:
            deck: Diccionario con información del mazo
            save_path: Ruta donde guardar el gráfico (None para mostrar en pantalla)

        Returns:
            bool: True si se generó correctamente, False en caso de error
        """
        try:
            # Calcular estadísticas del mazo
            stats = self.analyze_deck(deck)

            # Crear figura con tres subgráficos
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))

            # Gráfico 1: Curva de maná
            mana_costs = list(stats['mana_curve'].keys())
            mana_counts = list(stats['mana_curve'].values())

            if sum(mana_counts) > 0:
                ax1.bar(mana_costs, mana_counts, color='steelblue')
                ax1.set_title('Curva de maná', fontsize=14)
                ax1.set_xlabel('Coste de maná')
                ax1.set_ylabel('Número de cartas')
                ax1.grid(True, alpha=0.3)
            else:
                ax1.text(0.5, 0.5, 'Sin cartas\nno-tierra', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_title('Curva de maná', fontsize=14)

            # Gráfico 2: Distribución de tipos (pie chart)
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

            # Gráfico 3: Distribución de colores
            colors = list(stats['color_distribution'].keys())
            color_counts = list(stats['color_distribution'].values())

            if sum(color_counts) > 0:
                # Filtrar colores con 0 cartas
                filtered_colors = []
                filtered_color_counts = []
                plot_colors = []

                # Colores reales para el gráfico
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

            # Título general
            fig.suptitle(f"Estadísticas de {deck['name']}", fontsize=16, y=1.02)

            # Guardar o mostrar
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
        Analiza un mazo y calcula estadísticas detalladas

        Args:
            deck: Diccionario con información del mazo

        Returns:
            dict con:
                - mana_curve: distribución de costes de maná
                - type_distribution: distribución de tipos de carta
                - color_distribution: distribución de colores
        """
        mana_curve = defaultdict(int)
        type_distribution = defaultdict(int)
        color_distribution = defaultdict(int)

        for card in deck['cards']:
            count = card['count']

            # Curva de maná (solo cartas no-tierra)
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

            # Distribución de colores (solo cartas no-tierra)
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

        # Ordenar curva de maná de 0 a 7+
        sorted_curve = {}
        for i in range(7):
            sorted_curve[str(i)] = mana_curve.get(str(i), 0)
        sorted_curve['7+'] = mana_curve.get('7+', 0)

        return {
            'mana_curve': sorted_curve,
            'type_distribution': dict(type_distribution),
            'color_distribution': dict(color_distribution)
        }


# ==================================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==================================================================================

if __name__ == "__main__":
    # Crear generador
    generator = MTGDeckGenerator()

    # Generar población inicial de 50 mazos
    population = generator.generate_strategic_population(50)

    # Mostrar resumen de la población generada
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
