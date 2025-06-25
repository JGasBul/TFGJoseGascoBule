import requests
import json
import pandas as pd
import os
from tqdm import tqdm
import time
from datetime import datetime

class MTGCardScraper:
    def __init__(self, output_dir="mtg_data", exclude_latest_set=True):
        """
        Inicializa el scraper de cartas de MTG
        
        Args:
            output_dir (str): Directorio para guardar los datos descargados
            exclude_latest_set (bool): Si excluir la última expansión (para compatibilidad con Forge)
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
    
    def get_standard_sets(self):
        """Identifica cuáles de los sets disponibles están en formato Estándar ANTERIOR"""
        sets_df = self.get_sets_from_scryfall()
        if sets_df is None:
            return None
        
        # Obtener fecha actual
        current_date = pd.to_datetime('today')
        
        # Para el formato estándar ANTERIOR, tomamos sets de hace 2-4 años
        # Esto garantiza mejor compatibilidad con Forge
        sets_df['released_at'] = pd.to_datetime(sets_df['released_at'])
        
        # Fecha límite superior: hace 1 año (para excluir sets muy recientes)
        upper_date_limit = current_date - pd.DateOffset(years=2)
        # Fecha límite inferior: hace 3 años
        lower_date_limit = current_date - pd.DateOffset(years=4)
        
        standard_sets = sets_df[
            (sets_df['set_type'] == 'expansion') & 
            (sets_df['released_at'] > lower_date_limit) &
            (sets_df['released_at'] < upper_date_limit)
        ]
        
        # Ordenar por fecha de lanzamiento
        standard_sets = standard_sets.sort_values('released_at', ascending=False)
        
        print(f"Usando formato Estándar ANTERIOR para máxima compatibilidad con Forge")
        print(f"Sets entre {lower_date_limit.strftime('%Y-%m')} y {upper_date_limit.strftime('%Y-%m')}")
        print(f"Sets identificados: {len(standard_sets)}")
        
        # Mostrar los sets seleccionados
        for _, set_data in standard_sets.iterrows():
            print(f"  - {set_data['name']} ({set_data['code']}) - {set_data['released_at'].strftime('%Y-%m')}")
        
        return standard_sets
    
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
            else:
                print(f"Error {response.status_code} al obtener cartas: {response.text}")
                url = None
        
        return cards
    
    def get_all_standard_cards(self):
        """Obtiene todas las cartas del formato Estándar"""
        standard_sets = self.get_standard_sets()
        if standard_sets is None:
            return None
        
        all_cards = []
        for _, set_row in tqdm(standard_sets.iterrows(), total=len(standard_sets)):
            set_code = set_row['code']
            set_cards = self.get_cards_from_set(set_code)
            for card in set_cards:
                card['set_name'] = set_row['name']
            all_cards.extend(set_cards)
            
            # Guardar cada set por separado como backup
            set_filename = os.path.join(self.output_dir, f"set_{set_code}.json")
            with open(set_filename, 'w', encoding='utf-8') as f:
                json.dump(set_cards, f, ensure_ascii=False, indent=2)
        
        # Guardar todas las cartas juntas
        all_cards_filename = os.path.join(self.output_dir, "all_standard_cards.json")
        with open(all_cards_filename, 'w', encoding='utf-8') as f:
            json.dump(all_cards, f, ensure_ascii=False, indent=2)
        
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
        
        for card in cards:
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
        print("Obteniendo cartas del formato Estándar...")
        if self.exclude_latest_set:
            print("(Excluyendo la última expansión para compatibilidad con Forge)")
        
        cards = self.get_all_standard_cards()
        if cards:
            print(f"Se obtuvieron {len(cards)} cartas.")
            
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
        
        print("\nEstadísticas de cartas:")
        print(f"Total de cartas únicas: {len(self.cards_df)}")
        
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
            print(f"  {rarity}: {count}")
        
        print("\nDistribución por CMC:")
        cmc_counts = self.cards_df['cmc'].value_counts().sort_index()
        for cmc, count in cmc_counts.items():
            if cmc <= 7:
                print(f"  CMC {int(cmc)}: {count}")
            else:
                print(f"  CMC 8+: {count}")

if __name__ == "__main__":
    scraper = MTGCardScraper(exclude_latest_set=True)
    cards_df = scraper.run()