import requests
import json
import pandas as pd
import os
from tqdm import tqdm
import time
from datetime import datetime

class MTGCardScraper:
    def __init__(self, output_dir="mtg_data", exclude_latest_set=False):
        """
        Inicializa el scraper de cartas de MTG
        
        Args:
            output_dir (str): Directorio para guardar los datos descargados
            exclude_latest_set (bool): Parámetro mantenido por compatibilidad, pero no usado
        """
        self.output_dir = output_dir
        self.exclude_latest_set = exclude_latest_set
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 MTG Card Collector (academic/research project)'
        })
        self.cards_df = None
        self.card_catalog = {}  # Diccionario {card_id: card_data}
        
        # Lista específica de códigos de expansiones a obtener
        # Esto es mucho más confiable que buscar por nombres
        self.target_set_codes = {
            'FDN': 'Magic: The Gathering Foundations',
            'DMU': 'Dominaria United', 
            'BRO': 'The Brothers\' War',
            'ONE': 'Phyrexia: All Will Be One',
            'MOM': 'March of the Machine',
            'MAT': 'March of the Machine: The Aftermath',
            'WOE': 'Wilds of Eldraine',
            'LCI': 'The Lost Caverns of Ixalan',
            'MKM': 'Murders at Karlov Manor',
            'OTJ': 'Outlaws of Thunder Junction',
            'BIG': 'Outlaws of Thunder Junction/The Big Score',
            'BLB': 'Bloomburrow',
            'DSK': 'Duskmourn: House of Horror',
            'DFT': 'Aetherdrift',
            'TDM': 'Tarkir: Dragonstorm',
            'FIN': 'Final Fantasy'
        }
    
    def get_sets_from_scryfall(self):
        """Obtiene la lista de colecciones (sets) disponibles en Scryfall"""
        url = "https://api.scryfall.com/sets"
        response = self.session.get(url)
        if response.status_code == 200:
            sets_data = response.json()
            sets_list = []
            for set_data in sets_data['data']:
                sets_list.append({
                    'code': set_data['code'],
                    'name': set_data['name'],
                    'released_at': set_data.get('released_at', None),
                    'set_type': set_data.get('set_type', None),
                    'card_count': set_data.get('card_count', 0)
                })
            return pd.DataFrame(sets_list)
        else:
            print(f"Error {response.status_code} al obtener sets: {response.text}")
            return None
    
    def get_target_sets(self):
        """Identifica los sets objetivo por sus códigos específicos"""
        sets_df = self.get_sets_from_scryfall()
        if sets_df is None:
            return None
        
        print(f"Buscando {len(self.target_set_codes)} expansiones por código...")
        
        target_sets_found = []
        not_found_codes = []
        
        for code, expected_name in self.target_set_codes.items():
            # Buscar por código exacto (case insensitive)
            matching_sets = sets_df[
                sets_df['code'].str.upper() == code.upper()
            ]
            
            if len(matching_sets) > 0:
                set_data = matching_sets.iloc[0]
                target_sets_found.append(set_data)
                print(f"✓ {code}: {set_data['name']} - {set_data.get('card_count', 0)} cartas")
            else:
                not_found_codes.append((code, expected_name))
                print(f"✗ {code}: No encontrado (esperaba: {expected_name})")
        
        # Para códigos no encontrados, mostrar información de debugging
        if not_found_codes:
            print(f"\nCódigos no encontrados: {len(not_found_codes)}")
            
            # Buscar códigos similares para debugging
            for code, expected_name in not_found_codes:
                print(f"\nBuscando información para {code} ({expected_name}):")
                
                # Buscar por partes del nombre
                name_parts = expected_name.replace(":", "").replace("/", " ").split()
                similar_sets = []
                
                for part in name_parts:
                    if len(part) > 3:  # Solo palabras significativas
                        matches = sets_df[
                            sets_df['name'].str.contains(part, case=False, na=False, regex=False)
                        ]
                        for _, match in matches.iterrows():
                            if match['code'] not in [found['code'] for found in target_sets_found]:
                                similar_sets.append(match)
                
                if similar_sets:
                    print(f"  Sets similares encontrados:")
                    # Eliminar duplicados y mostrar los primeros 5
                    seen_codes = set()
                    for match in similar_sets[:10]:
                        if match['code'] not in seen_codes:
                            seen_codes.add(match['code'])
                            print(f"    - {match['name']} ({match['code']}) [{match.get('set_type', 'unknown')}] - {match.get('card_count', 0)} cartas")
                else:
                    print(f"  No se encontraron sets similares")
        
        if not target_sets_found:
            print("No se encontraron expansiones objetivo.")
            return None
        
        target_sets_df = pd.DataFrame(target_sets_found)
        
        print(f"\n" + "="*80)
        print(f"EXPANSIONES ENCONTRADAS: {len(target_sets_df)} de {len(self.target_set_codes)}")
        print("="*80)
        for _, set_data in target_sets_df.iterrows():
            print(f"  {set_data['code'].upper()}: {set_data['name']} - {set_data.get('card_count', 0)} cartas - {set_data.get('released_at', 'Fecha desconocida')}")
        print("="*80)
        
        return target_sets_df
    
    def get_cards_from_set(self, set_code):
        """
        Obtiene todas las cartas de un set específico
        
        Args:
            set_code (str): Código del set
        
        Returns:
            list: Lista de diccionarios con la información de las cartas
        """
        print(f"Obteniendo cartas del set: {set_code}")
        cards = []
        url = f"https://api.scryfall.com/cards/search?q=set:{set_code}"
        
        while url:
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                cards.extend(data['data'])
                
                if data.get('has_more', False):
                    url = data.get('next_page', None)
                    time.sleep(0.1)  # Respetar rate limits
                else:
                    url = None
            elif response.status_code == 404:
                print(f"Set {set_code} no encontrado en Scryfall")
                url = None
            else:
                print(f"Error {response.status_code} al obtener cartas: {response.text}")
                url = None
        
        print(f"  Obtenidas {len(cards)} cartas del set {set_code}")
        return cards
    
    def get_all_target_cards(self):
        """Obtiene todas las cartas de las expansiones objetivo"""
        target_sets = self.get_target_sets()
        if target_sets is None or len(target_sets) == 0:
            print("No se encontraron expansiones objetivo válidas.")
            return None
        
        all_cards = []
        successful_sets = []
        
        for _, set_row in tqdm(target_sets.iterrows(), total=len(target_sets), desc="Procesando sets"):
            set_code = set_row['code']
            set_name = set_row['name']
            
            set_cards = self.get_cards_from_set(set_code)
            
            if set_cards:
                for card in set_cards:
                    card['set_name'] = set_name
                all_cards.extend(set_cards)
                successful_sets.append((set_code, set_name))
                
                # Guardar cada set por separado como backup
                set_filename = os.path.join(self.output_dir, f"set_{set_code.lower()}.json")
                with open(set_filename, 'w', encoding='utf-8') as f:
                    json.dump(set_cards, f, ensure_ascii=False, indent=2)
            else:
                print(f"No se pudieron obtener cartas del set: {set_name} ({set_code})")
        
        if not all_cards:
            print("No se obtuvieron cartas de ninguna expansión.")
            return None
        
        # Guardar todas las cartas juntas
        all_cards_filename = os.path.join(self.output_dir, "all_target_cards.json")
        with open(all_cards_filename, 'w', encoding='utf-8') as f:
            json.dump(all_cards, f, ensure_ascii=False, indent=2)
        
        print(f"\n" + "="*80)
        print("RESUMEN DE OBTENCIÓN")
        print("="*80)
        print(f"Sets procesados exitosamente: {len(successful_sets)}")
        for code, name in successful_sets:
            print(f"  {code}: {name}")
        print(f"Total de cartas obtenidas: {len(all_cards)}")
        print("="*80)
        
        return all_cards
    
    def process_card_data(self, cards):
        """
        Procesa las cartas para extraer información relevante y crear catálogo
        
        Args:
            cards (list): Lista de datos de cartas obtenidos de Scryfall
        
        Returns:
            pandas.DataFrame: DataFrame con información procesada de las cartas
        """
        processed_cards = []
        card_id = 0
        
        # Usar un set para evitar duplicados por nombre
        seen_cards = set()
        
        print(f"Procesando {len(cards)} cartas...")
        
        for card in tqdm(cards, desc="Procesando cartas"):
            try:
                card_name = card['name']
                
                # Saltar si ya procesamos esta carta (por nombre)
                if card_name in seen_cards:
                    continue
                
                seen_cards.add(card_name)
                
                # Extraer información relevante
                card_data = {
                    'card_id': card_id,  # ID único para el array
                    'name': card_name,
                    'mana_cost': card.get('mana_cost', ''),
                    'cmc': card.get('cmc', 0),
                    'type_line': card.get('type_line', ''),
                    'oracle_text': card.get('oracle_text', ''),
                    'colors': card.get('colors', []),
                    'color_identity': card.get('color_identity', []),
                    'rarity': card.get('rarity', ''),
                    'set': card.get('set', ''),
                    'set_name': card.get('set_name', ''),
                    'power': card.get('power', None),
                    'toughness': card.get('toughness', None),
                    'loyalty': card.get('loyalty', None),
                    'legal_in_standard': card.get('legalities', {}).get('standard', 'not_legal') == 'legal',
                    'is_land': 'Land' in card.get('type_line', ''),
                    'is_creature': 'Creature' in card.get('type_line', ''),
                    'is_artifact': 'Artifact' in card.get('type_line', ''),
                    'is_enchantment': 'Enchantment' in card.get('type_line', ''),
                    'is_planeswalker': 'Planeswalker' in card.get('type_line', ''),
                    'is_instant': 'Instant' in card.get('type_line', ''),
                    'is_sorcery': 'Sorcery' in card.get('type_line', ''),
                    'is_basic_land': 'Basic' in card.get('type_line', ''),
                    'image_uri': card.get('image_uris', {}).get('normal', '') if 'image_uris' in card else '',
                    'scryfall_uri': card.get('scryfall_uri', ''),
                }
                
                # Añadir al catálogo
                self.card_catalog[card_id] = card_data
                processed_cards.append(card_data)
                card_id += 1
                
            except Exception as e:
                print(f"Error procesando carta {card.get('name', 'desconocida')}: {e}")
        
        # Convertir a DataFrame
        df = pd.DataFrame(processed_cards)
        
        # Guardar el DataFrame procesado
        csv_filename = os.path.join(self.output_dir, "processed_standard_cards.csv")
        df.to_csv(csv_filename, index=False)
        
        # Guardar el catálogo de cartas
        catalog_filename = os.path.join(self.output_dir, "card_catalog.json")
        with open(catalog_filename, 'w', encoding='utf-8') as f:
            json.dump(self.card_catalog, f, ensure_ascii=False, indent=2)
        
        print(f"Catálogo de cartas guardado con {len(self.card_catalog)} cartas únicas")
        
        return df
    
    def create_array_mapping(self):
        """
        Crea archivos de mapeo para facilitar la conversión entre arrays y cartas
        """
        # Crear índices por tipo de carta para optimizar búsquedas
        type_indices = {
            'lands': [],
            'creatures': [],
            'spells': [],
            'artifacts_enchantments': [],
            'planeswalkers': []
        }
        
        # Crear índices por color
        color_indices = {
            'W': [],
            'U': [],
            'B': [],
            'R': [],
            'G': [],
            'colorless': [],
            'multicolor': []
        }
        
        for card_id, card in self.card_catalog.items():
            # Clasificar por tipo
            if card['is_land']:
                type_indices['lands'].append(card_id)
            elif card['is_creature']:
                type_indices['creatures'].append(card_id)
            elif card['is_instant'] or card['is_sorcery']:
                type_indices['spells'].append(card_id)
            elif card['is_artifact'] or card['is_enchantment']:
                type_indices['artifacts_enchantments'].append(card_id)
            elif card['is_planeswalker']:
                type_indices['planeswalkers'].append(card_id)
            
            # Clasificar por color
            if len(card['color_identity']) == 0:
                color_indices['colorless'].append(card_id)
            elif len(card['color_identity']) == 1:
                color = card['color_identity'][0]
                if color in color_indices:
                    color_indices[color].append(card_id)
            else:
                color_indices['multicolor'].append(card_id)
                # También añadir a cada color individual para búsquedas
                for color in card['color_identity']:
                    if color in color_indices:
                        color_indices[color].append(card_id)
        
        # Guardar índices
        indices_filename = os.path.join(self.output_dir, "card_indices.json")
        with open(indices_filename, 'w', encoding='utf-8') as f:
            json.dump({
                'type_indices': type_indices,
                'color_indices': color_indices,
                'total_cards': len(self.card_catalog)
            }, f, ensure_ascii=False, indent=2)
        
        print("Índices de cartas creados y guardados")
    
    def run(self):
        """Ejecuta el proceso completo de obtención y procesamiento de cartas"""
        print("=" * 60)
        print("OBTENCIÓN DE CARTAS POR CÓDIGOS DE EXPANSIÓN")
        print("=" * 60)
        print("Expansiones objetivo:")
        for i, (code, name) in enumerate(self.target_set_codes.items(), 1):
            print(f"  {i:2d}. {code}: {name}")
        print("=" * 60)
        
        cards = self.get_all_target_cards()
        if cards:
            print(f"\nSe obtuvieron {len(cards)} cartas en total.")
            
            print("Procesando datos de cartas...")
            self.cards_df = self.process_card_data(cards)
            print(f"Procesamiento completado. Cartas únicas: {len(self.cards_df)}")
            
            # Crear archivos de mapeo
            self.create_array_mapping()
            
            # Mostrar estadísticas
            self.print_statistics()
            
            return self.cards_df
        else:
            print("No se pudieron obtener cartas.")
            return None
    
    def print_statistics(self):
        """Imprime estadísticas sobre las cartas obtenidas"""
        if self.cards_df is None:
            return
        
        print("\n" + "=" * 50)
        print("ESTADÍSTICAS DE CARTAS OBTENIDAS")
        print("=" * 50)
        print(f"Total de cartas únicas: {len(self.cards_df)}")
        
        print("\nDistribución por expansión:")
        set_counts = self.cards_df['set_name'].value_counts()
        for set_name, count in set_counts.items():
            print(f"  {set_name}: {count} cartas")
        
        print("\nDistribución por tipo:")
        type_counts = {
            'Tierras': self.cards_df['is_land'].sum(),
            'Criaturas': self.cards_df['is_creature'].sum(),
            'Artefactos': self.cards_df['is_artifact'].sum(),
            'Encantamientos': self.cards_df['is_enchantment'].sum(),
            'Planeswalkers': self.cards_df['is_planeswalker'].sum(),
            'Instantáneos': self.cards_df['is_instant'].sum(),
            'Conjuros': self.cards_df['is_sorcery'].sum()
        }
        for tipo, count in type_counts.items():
            print(f"  {tipo}: {count}")
        
        print("\nDistribución por rareza:")
        rarity_counts = self.cards_df['rarity'].value_counts()
        for rarity, count in rarity_counts.items():
            print(f"  {rarity.capitalize()}: {count}")
        
        print("\nDistribución por colores:")
        color_stats = {
            'Blanco (W)': 0,
            'Azul (U)': 0, 
            'Negro (B)': 0,
            'Rojo (R)': 0,
            'Verde (G)': 0,
            'Incoloro': 0,
            'Multicolor': 0
        }
        
        for _, card in self.cards_df.iterrows():
            colors = card['color_identity']
            if len(colors) == 0:
                color_stats['Incoloro'] += 1
            elif len(colors) == 1:
                color_map = {'W': 'Blanco (W)', 'U': 'Azul (U)', 'B': 'Negro (B)', 
                           'R': 'Rojo (R)', 'G': 'Verde (G)'}
                if colors[0] in color_map:
                    color_stats[color_map[colors[0]]] += 1
            else:
                color_stats['Multicolor'] += 1
        
        for color, count in color_stats.items():
            print(f"  {color}: {count}")
        
        print("\nDistribución por CMC:")
        cmc_counts = self.cards_df['cmc'].value_counts().sort_index()
        for cmc, count in cmc_counts.items():
            if cmc <= 7:
                print(f"  CMC {int(cmc)}: {count}")
            elif cmc > 7:
                # Agrupar CMC 8+ 
                cmc_8_plus = self.cards_df[self.cards_df['cmc'] > 7].shape[0]
                print(f"  CMC 8+: {cmc_8_plus}")
                break
        
        print("=" * 50)

if __name__ == "__main__":
    scraper = MTGCardScraper()
    cards_df = scraper.run()