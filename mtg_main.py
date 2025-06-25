#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal para el TFG: Diseño de un algoritmo genético para la 
construcción de mazos en Magic: The Gathering.

Versión con menús interactivos y tiempos realistas.
"""

import os
import json
import time
import glob
from pathlib import Path
import sys
from datetime import datetime

# Importar nuestros módulos
from obtener_cartas_mtg import MTGCardScraper
from generador_mazos_mtg import MTGDeckGenerator
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

class MTGMenuSystem:
    def __init__(self):
        """Inicializa el sistema de menús"""
        self.data_dir = "mtg_data"
        self.decks_dir = "mtg_decks"
        self.evolved_dir = "mtg_evolved_decks"
        self.forge_jar = None
        
        # Crear directorios
        Path(self.data_dir).mkdir(exist_ok=True)
        Path(self.decks_dir).mkdir(exist_ok=True)
        Path(self.evolved_dir).mkdir(exist_ok=True)
        
        # Estado del sistema
        self.cards_available = False
        self.population_available = False
        self.forge_configured = False
        
        self.check_system_status()
    
    def check_system_status(self):
        """Verifica el estado actual del sistema"""
        # Verificar cartas
        card_catalog = os.path.join(self.data_dir, "card_catalog.json")
        card_indices = os.path.join(self.data_dir, "card_indices.json")
        cards_csv = os.path.join(self.data_dir, "processed_standard_cards.csv")
        
        if all(os.path.exists(f) for f in [card_catalog, card_indices, cards_csv]):
            self.cards_available = True
            with open(card_catalog, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
                self.num_cards = len(catalog)
        else:
            self.cards_available = False
            self.num_cards = 0
        
        # Verificar población
        pop_file = os.path.join(self.decks_dir, "initial_population.json")
        test_pop_file = os.path.join(self.decks_dir, "test_population.json")
        
        if os.path.exists(pop_file) or os.path.exists(test_pop_file):
            self.population_available = True
        else:
            self.population_available = False
        
        # Buscar Forge usando patrones flexibles para versiones
        import glob
        
        forge_patterns = [
            "./forge-gui-desktop*.jar",                    # Cualquier versión en directorio actual
            "./forge*.jar",                                # Cualquier forge.jar
            "../forge-gui-desktop*.jar",                   # Directorio padre
            "~/Downloads/forge-gui-desktop*.jar",          # Downloads
            "~/Desktop/forge-gui-desktop*.jar",            # Desktop
            "./forge-gui-desktop-*-jar-with-dependencies.jar"  # Patrón específico completo
        ]
        
        for pattern in forge_patterns:
            expanded_pattern = os.path.expanduser(pattern)
            matches = glob.glob(expanded_pattern)
            if matches:
                # Ordenar por versión (más reciente primero)
                matches.sort(reverse=True)
                self.forge_jar = matches[0]
                self.forge_configured = True
                break
    
    def print_header(self):
        """Imprime el header del programa"""
        print("\n" + "=" * 80)
        print("    ALGORITMO GENÉTICO PARA MAGIC: THE GATHERING")
        print("    Versión con representación de arrays - TFG José Gascó")
        print("=" * 80)
    
    def print_status(self):
        """Imprime el estado actual del sistema"""
        print("\n📊 ESTADO ACTUAL DEL SISTEMA:")
        
        if self.cards_available:
            print(f"  ✅ Cartas: {self.num_cards:,} cartas del formato Estándar disponibles")
        else:
            print("  ❌ Cartas: No se han descargado cartas")
        
        if self.population_available:
            print("  ✅ Mazos: Población inicial generada")
        else:
            print("  ❌ Mazos: No se ha generado población inicial")
        
        if self.forge_configured:
            print(f"  ✅ Forge: Configurado en {self.forge_jar}")
        else:
            print("  ❌ Forge: No encontrado (necesario para algoritmo genético)")
        
        print()
    
    def main_menu(self):
        """Menú principal del sistema"""
        while True:
            self.print_header()
            self.print_status()
            
            print("🎯 MENÚ PRINCIPAL:")
            print("  1. 📥 Obtener cartas de Magic (Paso 1)")
            print("  2. 🎴 Generar mazos iniciales (Paso 2)")
            print("  3. 🧬 Ejecutar algoritmo genético (Paso 3)")
            print("  4. 🔧 Configurar Forge")
            print("  5. 📊 Ver estadísticas del sistema")
            print("  6. 🚀 Ejecución automática completa")
            print("  7. ⚡ Modo de prueba rápida")
            print("  0. 🚪 Salir")
            
            try:
                choice = input("\n👉 Selecciona una opción (0-7): ").strip()
                
                if choice == "0":
                    print("\n👋 ¡Hasta luego!")
                    break
                elif choice == "1":
                    self.menu_obtener_cartas()
                elif choice == "2":
                    self.menu_generar_mazos()
                elif choice == "3":
                    self.menu_algoritmo_genetico()
                elif choice == "4":
                    self.menu_configurar_forge()
                elif choice == "5":
                    self.menu_estadisticas()
                elif choice == "6":
                    self.ejecucion_completa()
                elif choice == "7":
                    self.modo_prueba()
                else:
                    print("\n❌ Opción no válida. Por favor, selecciona un número del 0 al 7.")
                    input("\nPresiona Enter para continuar...")
            
            except KeyboardInterrupt:
                print("\n\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}")
                input("\nPresiona Enter para continuar...")
    
    def menu_obtener_cartas(self):
        """Menú para obtener cartas"""
        print("\n" + "=" * 60)
        print("📥 OBTENER CARTAS DE MAGIC")
        print("=" * 60)
        
        if self.cards_available:
            print(f"✅ Ya tienes {self.num_cards:,} cartas descargadas.")
            choice = input("¿Descargar cartas nuevamente? (s/N): ").strip().lower()
            if choice not in ['s', 'sí', 'si', 'y', 'yes']:
                return
        
        print("\n🌐 Descargando cartas del formato Estándar...")
        print("   (Esto puede tardar 2-5 minutos)")
        
        start_time = time.time()
        
        try:
            scraper = MTGCardScraper(
                output_dir=self.data_dir,
                exclude_latest_set=True
            )
            cards_df = scraper.run()
            
            if cards_df is not None and not cards_df.empty:
                elapsed = time.time() - start_time
                print(f"\n✅ ¡Cartas obtenidas exitosamente!")
                print(f"   Tiempo: {elapsed:.1f} segundos")
                print(f"   Cartas únicas: {len(cards_df):,}")
                self.check_system_status()
            else:
                print("\n❌ Error al obtener las cartas.")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def menu_generar_mazos(self):
        """Menú para generar mazos - Con limpieza automática"""
        print("\n" + "=" * 60)
        print("🎴 GENERAR MAZOS INICIALES")
        print("=" * 60)
        
        if not self.cards_available:
            print("❌ Primero necesitas obtener las cartas (Opción 1).")
            input("\nPresiona Enter para continuar...")
            return
        
        # Verificar si hay mazos existentes y mostrar información
        import glob
        existing_files = []
        deck_patterns = [
            os.path.join(self.decks_dir, "*.dck"),
            os.path.join(self.decks_dir, "*population*.json")
        ]
        
        for pattern in deck_patterns:
            existing_files.extend(glob.glob(pattern))
        
        if existing_files:
            print(f"ℹ️  Se encontraron {len(existing_files)} archivos de mazos existentes.")
            print("   Estos serán eliminados automáticamente antes de generar los nuevos.")
        
        print(f"\n🎯 TIPOS DE POBLACIÓN (Tiempos de AG estimados):")
        print("  1. 🏃 Prueba ultra rápida (8 mazos) - AG: ~40 min")
        print("  2. 🚀 Prueba rápida (12 mazos) - AG: ~90 min") 
        print("  3. 💪 Desarrollo (20 mazos) - AG: ~6 horas")
        print("  4. 🔥 Estándar (30 mazos) - AG: ~12 horas")
        print("  5. 🌟 Intensivo (50 mazos) - AG: ~28 horas")
        print("  6. 🎛️  Personalizada")
        
        try:
            choice = input("\n👉 Selecciona tipo de población (1-6): ").strip()
            
            if choice == "1":
                size, name = 8, "prueba ultra rápida"
            elif choice == "2":
                size, name = 12, "prueba rápida"
            elif choice == "3":
                size, name = 20, "desarrollo"
            elif choice == "4":
                size, name = 30, "estándar"
            elif choice == "5":
                size, name = 50, "intensivo"
            elif choice == "6":
                try:
                    size = int(input("👉 Número de mazos (5-100): "))
                    if size < 5 or size > 100:
                        print("❌ Número fuera de rango.")
                        return
                    name = "personalizada"
                except ValueError:
                    print("❌ Número no válido.")
                    return
            else:
                print("❌ Opción no válida.")
                return
            
            # Calcular estimaciones realistas
            tournament_type = "elimination" if size <= 15 else "sampling"
            if tournament_type == "elimination":
                matches_per_gen = size - 1
            else:
                matches_per_gen = size * 5
            
            ag_time_hours = (matches_per_gen * 45 * 20) / 3600  # 20 generaciones promedio
            
            print(f"\n📊 CONFIGURACIÓN SELECCIONADA:")
            print(f"   Mazos: {size}")
            print(f"   Tipo de torneo para AG: {tournament_type}")
            print(f"   Matches por generación: {matches_per_gen}")
            print(f"   Tiempo estimado de AG: {ag_time_hours:.1f} horas")
            if existing_files:
                print(f"   🧹 Se eliminarán {len(existing_files)} archivos existentes")
            
            confirm = input("\n¿Continuar con esta configuración? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return
            
            print(f"\n🔨 Generando población {name} de {size} mazos...")
            start_time = time.time()
            
            # Cargar generador
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            
            # Usar el nuevo método unificado (con limpieza automática)
            population = generator.generate_population_exact_size(size)
            
            elapsed = time.time() - start_time
            print(f"\n✅ ¡Población generada exitosamente!")
            print(f"   Tiempo: {elapsed:.1f} segundos")
            print(f"   Mazos creados: {len(population)}")
            
            self.check_system_status()
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def menu_algoritmo_genetico(self):
        """Menú para algoritmo genético"""
        print("\n" + "=" * 60)
        print("🧬 ALGORITMO GENÉTICO")
        print("=" * 60)
        
        # Verificar prerrequisitos
        missing = []
        if not self.cards_available:
            missing.append("cartas")
        if not self.population_available:
            missing.append("mazos")
        if not self.forge_configured:
            missing.append("Forge")
        
        if missing:
            print(f"❌ Faltan componentes: {', '.join(missing)}")
            print("   Completa los pasos anteriores primero.")
            input("\nPresiona Enter para continuar...")
            return
        
        # Detectar tipo de población
        pop_file = os.path.join(self.decks_dir, "initial_population.json")
        test_pop_file = os.path.join(self.decks_dir, "test_population.json")
        
        if os.path.exists(test_pop_file):
            with open(test_pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            pop_size = len(population)
            is_test = True
            population_file = test_pop_file
        elif os.path.exists(pop_file):
            with open(pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            pop_size = len(population)
            is_test = False
            population_file = pop_file
        else:
            print("❌ No se encontró población de mazos.")
            return
        
        print(f"\n📊 POBLACIÓN DETECTADA:")
        print(f"   Tipo: {'Prueba' if is_test else 'Completa'}")
        print(f"   Mazos: {pop_size}")
        
        # Configuraciones predefinidas con tiempos realistas
        if pop_size <= 15:
            tournament_type = "elimination"
            configs = [
                {"name": "Prueba Ultra Rápida", "gens": 5},
                {"name": "Prueba Rápida", "gens": 8},
                {"name": "Prueba Completa", "gens": 12},
            ]
        else:
            tournament_type = "sampling"
            configs = [
                {"name": "Desarrollo Rápido", "gens": 15},
                {"name": "Desarrollo Completo", "gens": 25},
                {"name": "Investigación", "gens": 40},
            ]
        
        # Calcular tiempos para cada configuración
        if tournament_type == "elimination":
            matches_per_gen = pop_size - 1
        else:  # sampling
            matches_per_gen = pop_size * 5
        
        print(f"   Tipo de torneo: {tournament_type}")
        print(f"   Matches por generación: {matches_per_gen}")
        
        print(f"\n🎯 CONFIGURACIONES DISPONIBLES:")
        for i, config in enumerate(configs, 1):
            time_hours = (matches_per_gen * 45 * config["gens"]) / 3600
            config["time"] = time_hours
            if time_hours < 1:
                time_str = f"{time_hours * 60:.0f} min"
            else:
                time_str = f"{time_hours:.1f} horas"
            print(f"  {i}. {config['name']}: {config['gens']} generaciones (~{time_str})")
        
        print(f"  4. Personalizada")
        
        try:
            choice = input("\n👉 Selecciona configuración (1-4): ").strip()
            
            if choice in ["1", "2", "3"]:
                idx = int(choice) - 1
                max_gens = configs[idx]["gens"]
                estimated_hours = configs[idx]["time"]
                config_name = configs[idx]["name"]
            elif choice == "4":
                try:
                    max_gens = int(input("👉 Número de generaciones (5-100): "))
                    if max_gens < 5 or max_gens > 100:
                        print("❌ Número fuera de rango.")
                        return
                    estimated_hours = (matches_per_gen * 45 * max_gens) / 3600
                    config_name = "Personalizada"
                except ValueError:
                    print("❌ Número no válido.")
                    return
            else:
                print("❌ Opción no válida.")
                return
            
            # Calcular parámetros automáticamente
            elite_size = max(2, pop_size // 15)
            stagnation_limit = max(3, max_gens // 4)
            
            print(f"\n📋 CONFIGURACIÓN FINAL:")
            print(f"   Nombre: {config_name}")
            print(f"   Población: {pop_size} mazos")
            print(f"   Tipo de torneo: {tournament_type}")
            print(f"   Generaciones máximas: {max_gens}")
            print(f"   Elite preservada: {elite_size}")
            print(f"   Límite de estancamiento: {stagnation_limit}")
            print(f"   Tiempo estimado: {estimated_hours:.1f} horas")
            
            if estimated_hours > 8:
                print(f"\n⚠️  ADVERTENCIA: Esta ejecución es muy larga ({estimated_hours:.1f} horas)")
                print("   Considera usar una configuración más pequeña primero.")
            elif estimated_hours > 3:
                print(f"\n⚠️  NOTA: Esta ejecución tomará {estimated_hours:.1f} horas")
            
            confirm = input("\n¿Iniciar algoritmo genético? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return
            
            print(f"\n🚀 Iniciando algoritmo genético...")
            print(f"   Configuración: {config_name}")
            print(f"   Tipo de torneo: {tournament_type}")
            print(f"   Tiempo estimado: {estimated_hours:.1f} horas")
            print(f"   Inicio: {datetime.now().strftime('%H:%M:%S')}")
            
            start_time = time.time()
            
            # Configurar y ejecutar algoritmo genético
            ga = MTGGeneticAlgorithm(
                population_file=population_file,
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=max_gens,
                population_size=pop_size,
                mutation_rate=0.05,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=elite_size,
                stagnation_limit=stagnation_limit
            )
            
            # TODO: Configurar tipo de torneo cuando se implemente en el algoritmo
            # ga.set_tournament_type(tournament_type)
            
            best_deck = ga.evolve()
            
            elapsed = time.time() - start_time
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            
            print(f"\n✅ ¡Algoritmo genético completado!")
            print(f"   Tiempo real: {int(hours)}h {int(minutes)}m")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f} ({ga.best_fitness_ever * 100:.1f}% win rate)")
            
            # Guardar mejor mazo
            suffix = "_test" if is_test else "_final"
            best_deck_file = os.path.join(self.evolved_dir, f"best_deck{suffix}.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)
            
            print(f"   Mejor mazo guardado en: {best_deck_file}")
            
            # Mostrar resumen del mejor mazo
            self.print_deck_summary(best_deck)
            
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Ejecución interrumpida por el usuario")
            print("   Los progresos se han guardado automáticamente")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def menu_configurar_forge(self):
        """Menú para configurar Forge"""
        print("\n" + "=" * 60)
        print("🔧 CONFIGURAR FORGE")
        print("=" * 60)
        
        if self.forge_configured:
            print(f"✅ Forge ya está configurado: {self.forge_jar}")
            choice = input("¿Cambiar configuración? (s/N): ").strip().lower()
            if choice not in ['s', 'sí', 'si', 'y', 'yes']:
                return
        
        print("\n📁 BUSCAR FORGE:")
        print("  1. Buscar automáticamente")
        print("  2. Especificar ruta manualmente")
        print("  3. Descargar Forge (abre navegador)")
        
        try:
            choice = input("\n👉 Selecciona opción (1-3): ").strip()
            
            if choice == "1":
                self.auto_find_forge()
            elif choice == "2":
                self.manual_forge_path()
            elif choice == "3":
                self.download_forge_info()
            else:
                print("❌ Opción no válida.")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def auto_find_forge(self):
        """Busca Forge automáticamente usando patrones flexibles para versiones"""
        print("\n🔍 Buscando Forge...")
        
        forge_patterns = [
            "./forge-gui-desktop*.jar",                    # Cualquier versión en directorio actual
            "./forge*.jar",                                # Cualquier forge.jar simple
            "../forge-gui-desktop*.jar",                   # Directorio padre
            "~/Downloads/forge-gui-desktop*.jar",          # Downloads
            "~/Desktop/forge-gui-desktop*.jar",            # Desktop
            "./forge-gui-desktop-*-jar-with-dependencies.jar"  # Patrón específico completo
        ]
        
        found_files = []
        
        for pattern in forge_patterns:
            expanded_pattern = os.path.expanduser(pattern)
            matches = glob.glob(expanded_pattern)
            found_files.extend(matches)
        
        # Eliminar duplicados y ordenar
        found_files = list(set(found_files))
        found_files.sort(reverse=True)  # Versiones más recientes primero
        
        if found_files:
            self.forge_jar = found_files[0]
            self.forge_configured = True
            print(f"✅ Forge encontrado: {self.forge_jar}")
            
            # Mostrar otras versiones encontradas si las hay
            if len(found_files) > 1:
                print(f"   También se encontraron:")
                for other_file in found_files[1:]:
                    print(f"     - {other_file}")
                print(f"   Usando la versión: {os.path.basename(self.forge_jar)}")
        else:
            print("❌ Forge no encontrado automáticamente.")
            print("   Patrones buscados:")
            for pattern in forge_patterns:
                print(f"     - {pattern}")
            print("   Usa la opción 2 para especificar la ruta manualmente.")
    
    def manual_forge_path(self):
        """Permite especificar la ruta de Forge manualmente"""
        print("\n📂 Especifica la ruta completa al archivo forge-gui-desktop.jar:")
        path = input("👉 Ruta: ").strip().strip('"\'')
        
        if not path:
            print("❌ No se especificó ruta.")
            return
        
        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
            self.forge_jar = expanded_path
            self.forge_configured = True
            print(f"✅ Forge configurado: {expanded_path}")
        else:
            print(f"❌ Archivo no encontrado: {expanded_path}")
    
    def download_forge_info(self):
        """Muestra información para descargar Forge"""
        print("\n📥 DESCARGAR FORGE:")
        print("   1. Ve a: https://www.slightlymagic.net/forum/viewforum.php?f=26")
        print("   2. Descarga: forge-gui-desktop-X.X.XX-jar-with-dependencies.jar")
        print("   3. Colócalo en la carpeta del proyecto")
        print("   4. Usa la opción 1 para detectarlo automáticamente")
        
        try:
            import webbrowser
            choice = input("\n¿Abrir página de descarga en el navegador? (S/n): ").strip().lower()
            if choice not in ['n', 'no']:
                webbrowser.open("https://www.slightlymagic.net/forum/viewforum.php?f=26")
                print("🌐 Página abierta en el navegador")
        except:
            print("No se pudo abrir el navegador automáticamente")
    
    def menu_estadisticas(self):
        """Menú de estadísticas"""
        print("\n" + "=" * 60)
        print("📊 ESTADÍSTICAS DEL SISTEMA")
        print("=" * 60)
        
        # Estadísticas de cartas
        if self.cards_available:
            catalog_file = os.path.join(self.data_dir, "card_catalog.json")
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            print(f"\n🃏 CARTAS:")
            print(f"   Total: {len(catalog):,}")
            
            # Contar por tipos
            lands = sum(1 for card in catalog.values() if card['is_land'])
            creatures = sum(1 for card in catalog.values() if card['is_creature'])
            spells = sum(1 for card in catalog.values() if card['is_instant'] or card['is_sorcery'])
            
            print(f"   Tierras: {lands:,}")
            print(f"   Criaturas: {creatures:,}")
            print(f"   Hechizos: {spells:,}")
            print(f"   Otros: {len(catalog) - lands - creatures - spells:,}")
        
        # Estadísticas de población
        if self.population_available:
            pop_files = []
            if os.path.exists(os.path.join(self.decks_dir, "initial_population.json")):
                pop_files.append(("Completa", os.path.join(self.decks_dir, "initial_population.json")))
            if os.path.exists(os.path.join(self.decks_dir, "test_population.json")):
                pop_files.append(("Prueba", os.path.join(self.decks_dir, "test_population.json")))
            
            print(f"\n🎴 POBLACIONES:")
            for name, file_path in pop_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    population = json.load(f)
                
                print(f"   {name}: {len(population)} mazos")
        
        # Estadísticas de evolución
        evolution_stats = os.path.join(self.evolved_dir, "evolution_stats.csv")
        if os.path.exists(evolution_stats):
            import pandas as pd
            stats_df = pd.read_csv(evolution_stats)
            
            print(f"\n🧬 ÚLTIMA EVOLUCIÓN:")
            print(f"   Generaciones ejecutadas: {len(stats_df)}")
            print(f"   Mejor fitness: {stats_df['best_fitness'].max():.4f}")
            print(f"   Fitness promedio final: {stats_df['avg_fitness'].iloc[-1]:.4f}")
        
        input("\nPresiona Enter para continuar...")
    
    def ejecucion_completa(self):
        """Ejecución automática completa"""
        print("\n" + "=" * 60)
        print("🚀 EJECUCIÓN AUTOMÁTICA COMPLETA")
        print("=" * 60)
        
        print("Esta opción ejecutará todo el proceso automáticamente:")
        print("  1. Obtener cartas (si no están disponibles)")
        print("  2. Generar población de 25 mazos")
        print("  3. Ejecutar algoritmo genético por 20 generaciones")
        print("\n⏱️  Tiempo estimado total: 4-6 horas")
        
        if not self.forge_configured:
            print("\n❌ Forge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return
        
        confirm = input("\n¿Ejecutar proceso completo? (s/N): ").strip().lower()
        if confirm not in ['s', 'sí', 'si', 'y', 'yes']:
            return
        
        total_start = time.time()
        
        try:
            # Paso 1: Cartas
            if not self.cards_available:
                print("\n📥 Paso 1/3: Obteniendo cartas...")
                scraper = MTGCardScraper(output_dir=self.data_dir, exclude_latest_set=True)
                scraper.run()
                self.check_system_status()
            
            # Paso 2: Mazos
            print("\n🎴 Paso 2/3: Generando 25 mazos...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(25)
            self.check_system_status()
            
            # Paso 3: Algoritmo genético
            print("\n🧬 Paso 3/3: Ejecutando algoritmo genético...")
            print("   (20 generaciones, torneo por muestreo, ~4-6 horas)")
            
            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "initial_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=20,
                population_size=25,
                mutation_rate=0.05,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=3,
                stagnation_limit=8
            )
            
            best_deck = ga.evolve()
            
            total_elapsed = time.time() - total_start
            hours = total_elapsed // 3600
            minutes = (total_elapsed % 3600) // 60
            
            print(f"\n🎉 ¡EJECUCIÓN COMPLETA FINALIZADA!")
            print(f"   Tiempo total: {int(hours)}h {int(minutes)}m")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            
            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_complete.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)
            
            self.print_deck_summary(best_deck)
            
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Ejecución interrumpida por el usuario")
        except Exception as e:
            print(f"\n❌ Error en ejecución completa: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def modo_prueba(self):
        """Modo de prueba rápida"""
        print("\n" + "=" * 60)
        print("⚡ MODO DE PRUEBA RÁPIDA")
        print("=" * 60)
        
        print("Esta opción ejecutará una prueba rápida:")
        print("  1. Usar cartas existentes o descargar si es necesario")
        print("  2. Generar población de 8 mazos")
        print("  3. Ejecutar algoritmo genético por 5 generaciones")
        print("\n⏱️  Tiempo estimado total: 40-60 minutos")
        
        if not self.forge_configured:
            print("\n❌ Forge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return
        
        confirm = input("\n¿Ejecutar prueba rápida? (S/n): ").strip().lower()
        if confirm in ['n', 'no']:
            return
        
        test_start = time.time()
        
        try:
            # Paso 1: Cartas (si es necesario)
            if not self.cards_available:
                print("\n📥 Obteniendo cartas...")
                scraper = MTGCardScraper(output_dir=self.data_dir, exclude_latest_set=True)
                scraper.run()
                self.check_system_status()
            
            # Paso 2: Mazos de prueba
            print("\n🎴 Generando 8 mazos de prueba...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(8)
            self.check_system_status()
            
            # Paso 3: Algoritmo genético de prueba
            print("\n🧬 Ejecutando algoritmo genético de prueba...")
            print("   (5 generaciones, torneo eliminación, ~40 minutos)")
            
            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "test_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=5,
                population_size=8,
                mutation_rate=0.05,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=2,
                stagnation_limit=3
            )
            
            best_deck = ga.evolve()
            
            test_elapsed = time.time() - test_start
            minutes = test_elapsed // 60
            seconds = test_elapsed % 60
            
            print(f"\n🎯 ¡PRUEBA COMPLETADA!")
            print(f"   Tiempo total: {int(minutes)}m {int(seconds)}s")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            
            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_test.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)
            
            self.print_deck_summary(best_deck)
            
            print(f"\n✅ Si la prueba funcionó correctamente, puedes ejecutar")
            print(f"   la versión completa con la opción 6 del menú principal.")
            
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Prueba interrumpida por el usuario")
        except Exception as e:
            print(f"\n❌ Error en prueba: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def print_deck_summary(self, deck):
        """Imprime un resumen del mazo"""
        print(f"\n🏆 MEJOR MAZO ENCONTRADO:")
        print(f"   Nombre: {deck['name']}")
        print(f"   Colores: {', '.join(deck['colors']) if deck['colors'] else 'Incoloro'}")
        
        stats = deck['stats']
        print(f"   Total de cartas: {stats['total_cards']}")
        print(f"   Tierras: {stats['lands']}")
        print(f"   Criaturas: {stats['creatures']}")
        print(f"   Hechizos: {stats['spells']}")
        print(f"   CMC promedio: {stats['avg_cmc']:.2f}")
        
        print(f"\n   🃏 Algunas cartas destacadas:")
        cards_to_show = sorted(deck['cards'], key=lambda x: (-x['count'], x['name']))[:8]
        for card in cards_to_show:
            mana_cost = card.get('mana_cost', 'N/A')
            print(f"     {card['count']}x {card['name']} ({mana_cost})")

def main():
    """Función principal"""
    try:
        menu_system = MTGMenuSystem()
        menu_system.main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        print("Por favor, reporta este error si persiste.")

if __name__ == "__main__":
    main()