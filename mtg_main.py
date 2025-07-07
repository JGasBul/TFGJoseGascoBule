#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal para el TFG: Diseño de un algoritmo genético para la 
construcción de mazos en Magic: The Gathering.

Versión con auto-optimización de hardware integrada en el menú.
"""

import os
import json
import time
import glob
from pathlib import Path
import sys
from datetime import datetime
import psutil
import platform
import multiprocessing as mp
import numpy as np

# Importar nuestros módulos
from obtener_cartas_mtg import MTGCardScraper
from generador_mazos_mtg import MTGDeckGenerator
from algoritmo_genetico_mtg import MTGGeneticAlgorithm

class HardwareAnalyzer:
    """Analizador de hardware para auto-optimización"""
    
    def __init__(self):
        """Analiza el hardware del sistema"""
        print("🔍 === ANALIZANDO HARDWARE DEL SISTEMA ===")
        self.system_info = self.analyze_system()
        self.performance_profile = self.create_performance_profile()
        self.optimization_config = self.generate_optimization_config()
        
    def analyze_system(self):
        """Análisis completo del hardware"""
        print("   💻 Analizando CPU...")
        cpu_info = {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 0,
            'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0
        }
        
        # Test de carga CPU
        cpu_samples = []
        for _ in range(5):
            cpu_samples.append(psutil.cpu_percent(interval=0.2))
        
        cpu_info['baseline_usage'] = sum(cpu_samples) / len(cpu_samples)
        cpu_info['available_capacity'] = 100 - cpu_info['baseline_usage']
        
        print("   🧠 Analizando memoria...")
        memory = psutil.virtual_memory()
        memory_info = {
            'total_gb': memory.total / (1024**3),
            'available_gb': memory.available / (1024**3),
            'used_gb': memory.used / (1024**3),
            'percentage_used': memory.percent
        }
        
        print("   💾 Analizando almacenamiento...")
        disk_usage = psutil.disk_usage('.')
        storage_info = {
            'total_gb': disk_usage.total / (1024**3),
            'used_gb': disk_usage.used / (1024**3),
            'free_gb': disk_usage.free / (1024**3),
            'percentage_used': (disk_usage.used / disk_usage.total) * 100
        }
        
        # Test básico de I/O
        try:
            storage_info.update(self.test_disk_speed())
        except:
            storage_info['read_speed_mb_s'] = 0
            storage_info['write_speed_mb_s'] = 0
        
        print("   ⚙️  Analizando sistema operativo...")
        os_info = {
            'platform': platform.system(),
            'release': platform.release(),
            'architecture': platform.architecture()[0],
            'processor': platform.processor()
        }
        
        return {
            'cpu': cpu_info,
            'memory': memory_info,
            'storage': storage_info,
            'os': os_info
        }
    
    def test_disk_speed(self):
        """Test rápido de velocidad de disco"""
        test_file = "temp_speed_test.dat"
        test_size_mb = 5
        test_data = os.urandom(test_size_mb * 1024 * 1024)
        
        try:
            # Test de escritura
            start_time = time.time()
            with open(test_file, 'wb') as f:
                f.write(test_data)
                f.flush()
                os.fsync(f.fileno())
            write_time = time.time() - start_time
            write_speed = test_size_mb / write_time
            
            # Test de lectura
            start_time = time.time()
            with open(test_file, 'rb') as f:
                _ = f.read()
            read_time = time.time() - start_time
            read_speed = test_size_mb / read_time
            
            os.remove(test_file)
            
            return {
                'read_speed_mb_s': round(read_speed, 1),
                'write_speed_mb_s': round(write_speed, 1)
            }
        except:
            if os.path.exists(test_file):
                os.remove(test_file)
            return {'read_speed_mb_s': 0, 'write_speed_mb_s': 0}
    
    def create_performance_profile(self):
        """Crea perfil de rendimiento del sistema"""
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        storage = self.system_info['storage']
        
        # Clasificar CPU
        if cpu['logical_cores'] >= 16:
            cpu_tier = "high_end"
        elif cpu['logical_cores'] >= 8:
            cpu_tier = "mid_high"
        elif cpu['logical_cores'] >= 4:
            cpu_tier = "mid_range"
        else:
            cpu_tier = "low_end"
        
        # Clasificar RAM
        if memory['total_gb'] >= 32:
            ram_tier = "high_end"
        elif memory['total_gb'] >= 16:
            ram_tier = "mid_high"
        elif memory['total_gb'] >= 8:
            ram_tier = "mid_range"
        else:
            ram_tier = "low_end"
        
        # Clasificar almacenamiento
        read_speed = storage.get('read_speed_mb_s', 0)
        if read_speed >= 500:
            storage_tier = "high_end"  # SSD rápido
        elif read_speed >= 200:
            storage_tier = "mid_high"  # SSD normal
        elif read_speed >= 100:
            storage_tier = "mid_range"  # HDD rápido
        else:
            storage_tier = "low_end"
        
        # Perfil general
        tier_scores = {"high_end": 4, "mid_high": 3, "mid_range": 2, "low_end": 1}
        overall_score = (tier_scores[cpu_tier] + tier_scores[ram_tier] + tier_scores[storage_tier]) / 3
        
        if overall_score >= 3.5:
            system_tier = "high_performance"
        elif overall_score >= 2.5:
            system_tier = "balanced"
        elif overall_score >= 1.5:
            system_tier = "conservative"
        else:
            system_tier = "minimal"
        
        return {
            'cpu_tier': cpu_tier,
            'ram_tier': ram_tier,
            'storage_tier': storage_tier,
            'system_tier': system_tier,
            'overall_score': overall_score,
            'bottlenecks': self.identify_bottlenecks()
        }
    
    def identify_bottlenecks(self):
        """Identifica cuellos de botella"""
        bottlenecks = []
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        storage = self.system_info['storage']
        
        if cpu['logical_cores'] < 4:
            bottlenecks.append("CPU: Pocos cores para paralelización")
        
        if cpu['available_capacity'] < 50:
            bottlenecks.append("CPU: Sistema bajo alta carga")
        
        if memory['available_gb'] < 4:
            bottlenecks.append("RAM: Poca memoria disponible")
        
        if memory['percentage_used'] > 80:
            bottlenecks.append("RAM: Uso muy alto")
        
        if storage['percentage_used'] > 90:
            bottlenecks.append("STORAGE: Disco casi lleno")
        
        if storage.get('read_speed_mb_s', 0) < 50:
            bottlenecks.append("STORAGE: Velocidad muy lenta")
        
        return bottlenecks
    
    def generate_optimization_config(self):
        """Genera configuración optimizada automáticamente"""
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        storage = self.system_info['storage']
        profile = self.performance_profile
        
        # === WORKERS ÓPTIMOS ===
        max_theoretical = cpu['logical_cores']
        load_factor = max(0.1, cpu['available_capacity'] / 100)
        max_by_ram = int(memory['available_gb'] * 1024 / 300)  # ~300MB por worker
        
        optimal_workers = min(
            int(max_theoretical * 0.8 * load_factor),
            max_by_ram,
            16  # Límite razonable
        )
        optimal_workers = max(2, optimal_workers)
        
        # === TIMEOUTS ===
        base_timeout = 300
        
        # === CONFIGURACIÓN DE LOGS ===
        log_level = 'INFO'
        save_forge_outputs = True
        
        # === POBLACIONES RECOMENDADAS ===
        if profile['system_tier'] == "high_performance":
            populations = {'test': 12, 'small': 25, 'medium': 50, 'large': 100}
        elif profile['system_tier'] == "balanced":
            populations = {'test': 8, 'small': 20, 'medium': 35, 'large': 60}
        elif profile['system_tier'] == "conservative":
            populations = {'test': 6, 'small': 15, 'medium': 25, 'large': 40}
        else:
            populations = {'test': 4, 'small': 8, 'medium': 15, 'large': 25}
        
        return {
            'max_workers': optimal_workers,
            'base_timeout': base_timeout,
            'max_timeout': base_timeout * 3,
            'parallel_batch_size': optimal_workers * 3,
            'log_level': log_level,
            'save_forge_outputs': save_forge_outputs,
            'recommended_populations': populations,
            'recommended_generations': {'quick': 3, 'dev': 10, 'research': 25, 'production': 50}
        }
    
    def print_analysis(self):
        """Imprime análisis del sistema"""
        print("\n" + "=" * 70)
        print("🖥️  ANÁLISIS DE HARDWARE COMPLETADO")
        print("=" * 70)
        
        # Sistema
        os_info = self.system_info['os']
        print(f"🏢 Sistema: {os_info['platform']} {os_info['release']} ({os_info['architecture']})")
        
        # CPU
        cpu = self.system_info['cpu']
        print(f"💻 CPU: {cpu['logical_cores']} cores lógicos ({cpu['physical_cores']} físicos)")
        if cpu['max_frequency']:
            print(f"   Frecuencia: {cpu['max_frequency']:.0f} MHz")
        print(f"   Carga actual: {cpu['baseline_usage']:.1f}%")
        print(f"   Capacidad disponible: {cpu['available_capacity']:.1f}%")
        
        # Memoria
        mem = self.system_info['memory']
        print(f"🧠 RAM: {mem['total_gb']:.1f} GB total, {mem['available_gb']:.1f} GB disponible ({mem['percentage_used']:.1f}% usado)")
        
        # Almacenamiento
        storage = self.system_info['storage']
        print(f"💾 Almacenamiento: {storage['free_gb']:.1f} GB libres de {storage['total_gb']:.1f} GB")
        if storage['read_speed_mb_s'] > 0:
            print(f"   Velocidad: {storage['read_speed_mb_s']:.0f} MB/s lectura, {storage['write_speed_mb_s']:.0f} MB/s escritura")
        
        # Perfil de rendimiento
        profile = self.performance_profile
        print(f"\n📊 PERFIL DE RENDIMIENTO:")
        print(f"   CPU: {profile['cpu_tier'].replace('_', ' ').title()}")
        print(f"   RAM: {profile['ram_tier'].replace('_', ' ').title()}")
        print(f"   Storage: {profile['storage_tier'].replace('_', ' ').title()}")
        print(f"   📈 General: {profile['system_tier'].replace('_', ' ').title()} ({profile['overall_score']:.1f}/4.0)")
        
        # Cuellos de botella
        if profile['bottlenecks']:
            print(f"\n⚠️  POSIBLES LIMITACIONES:")
            for bottleneck in profile['bottlenecks']:
                print(f"   • {bottleneck}")
        else:
            print(f"\n✅ No se detectaron limitaciones significativas")
        
        # Configuración optimizada
        config = self.optimization_config
        print(f"\n🚀 CONFIGURACIÓN OPTIMIZADA:")
        print(f"   Workers paralelos: {config['max_workers']}")
        print(f"   Timeout base: {config['base_timeout']} segundos")
        print(f"   Nivel de logging: {config['log_level']}")
        print(f"   Forge outputs: {'✅ Habilitado' if config['save_forge_outputs'] else '❌ Deshabilitado (ahorro espacio)'}")
        
        print("=" * 70)
    
    def estimate_time(self, population, generations, workers=None):
        """Estima tiempo de ejecución"""
        if workers is None:
            workers = self.optimization_config['max_workers']
        
        # Combates por generación
        combats_per_gen = population * (population - 1)
        
        # Tiempo base según sistema
        if self.performance_profile['system_tier'] == "high_performance":
            base_time = 35
        elif self.performance_profile['system_tier'] == "balanced":
            base_time = 45
        elif self.performance_profile['system_tier'] == "conservative":
            base_time = 60
        else:
            base_time = 75
        
        # Tiempo total en paralelo
        total_seconds = (combats_per_gen * base_time * generations) / workers
        total_seconds *= 1.1  # Overhead
        
        if total_seconds < 3600:
            return f"{total_seconds/60:.0f} minutos"
        else:
            return f"{total_seconds/3600:.1f} horas"


class MTGMenuSystem:
    def __init__(self):
        """Inicializa el sistema de menús"""
        self.data_dir = "mtg_data"
        self.decks_dir = "mtg_decks"
        self.evolved_dir = "mtg_evolved_decks"
        self.forge_jar = None
        self.headless_mode = False
        
        # Crear directorios
        Path(self.data_dir).mkdir(exist_ok=True)
        Path(self.decks_dir).mkdir(exist_ok=True)
        Path(self.evolved_dir).mkdir(exist_ok=True)
        
        # Estado del sistema
        self.cards_available = False
        self.population_available = False
        self.forge_configured = False
        
        # NUEVO: Hardware analyzer
        self.hardware_analyzer = None
        
        self.check_system_status()
        self.auto_detect_headless()
    
    def analyze_hardware_if_needed(self):
        """Analiza hardware si no se ha hecho ya"""
        if self.hardware_analyzer is None:
            try:
                self.hardware_analyzer = HardwareAnalyzer()
                return True
            except Exception as e:
                print(f"⚠️  Error analizando hardware: {e}")
                return False
        return True
    
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
        
        # Buscar Forge
        forge_patterns = [
            "./forge-gui-desktop*.jar",
            "./forge*.jar",
            "../forge-gui-desktop*.jar",
            "~/Downloads/forge-gui-desktop*.jar",
            "~/Desktop/forge-gui-desktop*.jar",
            "./forge-gui-desktop-*-jar-with-dependencies.jar"
        ]
        
        for pattern in forge_patterns:
            expanded_pattern = os.path.expanduser(pattern)
            matches = glob.glob(expanded_pattern)
            if matches:
                matches.sort(reverse=True)
                self.forge_jar = matches[0]
                self.forge_configured = True
                break
    def auto_detect_headless(self):
        """Detecta automáticamente si estamos en un entorno headless"""
        try:
            # Método 1: Verificar variable de entorno DISPLAY
            display = os.environ.get('DISPLAY')
            if not display:
                self.headless_mode = True
                return
            
            # Método 2: Verificar SSH_CONNECTION (indica sesión SSH)
            ssh_connection = os.environ.get('SSH_CONNECTION')
            if ssh_connection:
                self.headless_mode = True
                return
            
            # Método 3: Intentar importar tkinter (GUI)
            try:
                import tkinter
                # Intentar crear una ventana temporal
                root = tkinter.Tk()
                root.withdraw()  # Ocultar ventana
                root.destroy()
                self.headless_mode = False
            except:
                self.headless_mode = True
                
        except Exception:
            # Si hay cualquier error, asumir headless por seguridad
            self.headless_mode = True
    
    def print_header(self):
        """Imprime el header del programa"""
        print("\n" + "=" * 80)
        print("    ALGORITMO GENÉTICO PARA MAGIC: THE GATHERING")
        print("    🚀 Versión con Auto-Optimización de Hardware - TFG José Gascó")
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
            print(f"  ✅ Forge: Configurado en {os.path.basename(self.forge_jar)}")
        else:
            print("  ❌ Forge: No encontrado (necesario para algoritmo genético)")
            
        if self.headless_mode:
            print("  🖥️  Modo: Headless (sin interfaz gráfica) - usando xvfb-run")
        else:
            print("  🖥️  Modo: GUI disponible - ejecución estándar")
        
        # Estado del análisis de hardware
        if self.hardware_analyzer:
            config = self.hardware_analyzer.optimization_config
            profile = self.hardware_analyzer.performance_profile
            print(f"  🚀 Hardware: {profile['system_tier'].replace('_', ' ').title()} - {config['max_workers']} workers óptimos")
        else:
            print(f"  🔍 Hardware: Se analizará automáticamente cuando sea necesario")
        
        # Mostrar recomendación si todo está listo
        if self.cards_available and self.population_available and self.forge_configured:
            print(f"  🎯 Sistema listo para algoritmo genético AUTO-OPTIMIZADO")
        
        print()
    
    def show_performance_comparison(self):
        """Muestra comparación de rendimiento con paralelización"""
        if not self.hardware_analyzer:
            return
        
        config = self.hardware_analyzer.optimization_config
        workers = config['max_workers']
        
        print(f"\n📈 COMPARACIÓN DE RENDIMIENTO:")
        print(f"   Tu baseline secuencial: 100 minutos")
        print(f"   Con paralelización ({workers} workers): ~{100/workers:.0f} minutos")
        print(f"   🚀 Aceleración esperada: {workers:.1f}x más rápido")
        print(f"   ⏱️  Tiempo ahorrado: ~{100 - (100/workers):.0f} minutos")
    
    def detect_baseline_performance(self):
        """Detecta si hay datos de rendimiento previo"""
        # Buscar archivos de estadísticas previas
        stats_files = [
            os.path.join(self.evolved_dir, "evolution_stats.csv"),
            os.path.join(self.evolved_dir, "parallel_evolution_stats.csv")
        ]
        
        for stats_file in stats_files:
            if os.path.exists(stats_file):
                try:
                    import pandas as pd
                    df = pd.read_csv(stats_file)
                    if len(df) > 0:
                        return True
                except:
                    pass
        return False
    
    def main_menu(self):
        """Menú principal del sistema"""
        while True:
            self.print_header()
            self.print_status()
            
            # Mostrar comparación de rendimiento si hay baseline
            if self.detect_baseline_performance():
                self.show_performance_comparison()
            
            print("🎯 MENÚ PRINCIPAL:")
            print("  1. 📥 Obtener cartas de Magic (Paso 1)")
            print("  2. 🎴 Generar mazos iniciales (Paso 2)")
            print("  3. 🧬 Ejecutar algoritmo genético AUTO-OPTIMIZADO (Paso 3)")
            print("  4. 🔧 Configurar Forge")
            print("  5. 🖥️  Analizar hardware del sistema")
            print("  6. 📊 Ver estadísticas del sistema")
            print("  7. 🚀 Ejecución automática completa (AUTO-OPTIMIZADA)")
            print("  8. ⚡ Modo de prueba rápida (AUTO-OPTIMIZADO)")
            print("  9. 🖥️  Configurar modo headless")
            print("  0. 🚪 Salir")
            
            try:
                choice = input("\n👉 Selecciona una opción (0-8): ").strip()
                
                if choice == "0":
                    print("\n👋 ¡Hasta luego!")
                    break
                elif choice == "1":
                    self.menu_obtener_cartas()
                elif choice == "2":
                    self.menu_generar_mazos()
                elif choice == "3":
                    self.menu_algoritmo_genetico_optimizado()
                elif choice == "4":
                    self.menu_configurar_forge()
                elif choice == "5":
                    self.menu_analizar_hardware()
                elif choice == "6":
                    self.menu_estadisticas()
                elif choice == "7":
                    self.ejecucion_completa_optimizada()
                elif choice == "8":
                    self.modo_prueba_optimizado()
                elif choice == "9":
                    self.menu_configurar_headless()
                else:
                    print("\n❌ Opción no válida. Por favor, selecciona un número del 0 al 9.")
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
    
    def menu_analizar_hardware(self):
        """Menú para analizar hardware"""
        print("\n" + "=" * 60)
        print("🖥️  ANÁLISIS DE HARDWARE")
        print("=" * 60)
        
        if self.hardware_analyzer:
            print("✅ El hardware ya ha sido analizado.")
            choice = input("¿Realizar nuevo análisis? (s/N): ").strip().lower()
            if choice not in ['s', 'sí', 'si', 'y', 'yes']:
                self.hardware_analyzer.print_analysis()
                input("\nPresiona Enter para continuar...")
                return
        
        try:
            print("🔍 Analizando tu hardware...")
            print("   (Esto tomará 5-10 segundos)")
            
            self.hardware_analyzer = HardwareAnalyzer()
            self.hardware_analyzer.print_analysis()
            
            # Mostrar recomendaciones
            config = self.hardware_analyzer.optimization_config
            print(f"\n📏 RECOMENDACIONES PARA TU SISTEMA:")
            for name, size in config['recommended_populations'].items():
                estimate = self.hardware_analyzer.estimate_time(size, 10)
                print(f"   {name.title()}: {size} mazos (~{estimate} para 10 generaciones)")
            
        except Exception as e:
            print(f"❌ Error durante análisis: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def menu_configurar_headless(self):
        """Menú para configurar modo headless - NUEVO"""
        print("\n" + "=" * 60)
        print("🖥️  CONFIGURAR MODO HEADLESS")
        print("=" * 60)
        
        print(f"Estado actual: {'✅ Headless' if self.headless_mode else '🖼️  GUI disponible'}")
        
        print("\nEl modo headless es necesario en servidores o máquinas sin interfaz gráfica.")
        print("En modo headless, Forge se ejecuta con 'xvfb-run -a' para simular display.")
        print("\n🏫 PERFECTO para la universidad donde usas SSH sin X11 forwarding!")
        
        print("\n🔧 OPCIONES:")
        print("  1. 🔍 Auto-detectar (recomendado)")
        print("  2. ✅ Forzar modo headless (para servidores/universidad)")
        print("  3. 🖼️  Forzar modo GUI (para escritorio)")
        print("  4. 🧪 Probar detección actual")
        print("  5. 📋 Ver información del entorno")
        
        try:
            choice = input("\n👉 Selecciona opción (1-5): ").strip()
            
            if choice == "1":
                print("\n🔍 Ejecutando auto-detección...")
                old_mode = self.headless_mode
                self.auto_detect_headless()
                
                if old_mode != self.headless_mode:
                    print(f"   Modo cambiado: {'GUI → Headless' if self.headless_mode else 'Headless → GUI'}")
                else:
                    print(f"   Modo confirmado: {'Headless' if self.headless_mode else 'GUI'}")
                
                print(f"   ✅ Configuración: {'xvfb-run + java' if self.headless_mode else 'java directo'}")
                
            elif choice == "2":
                self.headless_mode = True
                print("\n✅ Modo headless activado manualmente")
                print("   Forge se ejecutará con: xvfb-run -a java -jar forge.jar")
                print("   🏫 Perfecto para máquinas de universidad!")
                
            elif choice == "3":
                self.headless_mode = False
                print("\n🖼️  Modo GUI activado manualmente")
                print("   Forge se ejecutará con: java -jar forge.jar")
                print("   💻 Perfecto para tu máquina personal!")
                
            elif choice == "4":
                print("\n🧪 PRUEBA DE DETECCIÓN:")
                print(f"   Variable DISPLAY: {os.environ.get('DISPLAY', '❌ No definida')}")
                print(f"   SSH_CONNECTION: {os.environ.get('SSH_CONNECTION', '❌ No definida')}")
                
                try:
                    import tkinter
                    root = tkinter.Tk()
                    root.withdraw()
                    root.destroy()
                    print("   Tkinter: ✅ Disponible")
                except Exception as e:
                    print(f"   Tkinter: ❌ Error - {e}")
                
                print(f"   Modo detectado: {'Headless' if self.headless_mode else 'GUI'}")
                
            elif choice == "5":
                print("\n📋 INFORMACIÓN DEL ENTORNO:")
                print(f"   Sistema: {platform.system()} {platform.release()}")
                print(f"   Usuario: {os.environ.get('USER', 'desconocido')}")
                print(f"   HOME: {os.environ.get('HOME', 'desconocido')}")
                print(f"   TERM: {os.environ.get('TERM', 'desconocido')}")
                print(f"   SSH_CLIENT: {os.environ.get('SSH_CLIENT', '❌ No en SSH')}")
                print(f"   SSH_TTY: {os.environ.get('SSH_TTY', '❌ No en SSH')}")
                
                # Sugerencia automática
                if os.environ.get('SSH_CONNECTION') or not os.environ.get('DISPLAY'):
                    print("\n💡 SUGERENCIA: Parece que estás en un entorno remoto")
                    print("   Se recomienda usar modo headless (Opción 2)")
                else:
                    print("\n💡 SUGERENCIA: Parece que tienes GUI disponible")
                    print("   Puedes usar modo normal (Opción 3)")
                
            else:
                print("❌ Opción no válida.")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def menu_algoritmo_genetico_optimizado(self):
        """Menú para algoritmo genético auto-optimizado"""
        print("\n" + "=" * 60)
        print("🧬 ALGORITMO GENÉTICO AUTO-OPTIMIZADO")
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
        
        # Analizar hardware si no se ha hecho
        if not self.analyze_hardware_if_needed():
            print("❌ No se pudo analizar el hardware. Usando configuración por defecto.")
            input("\nPresiona Enter para continuar...")
            return
        
        # Detectar población disponible
        pop_file = os.path.join(self.decks_dir, "initial_population.json")
        test_pop_file = os.path.join(self.decks_dir, "test_population.json")
        
        if os.path.exists(test_pop_file):
            with open(test_pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            pop_size = len(population)
            population_file = test_pop_file
            pop_type = "Prueba"
        elif os.path.exists(pop_file):
            with open(pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            pop_size = len(population)
            population_file = pop_file
            pop_type = "Completa"
        else:
            print("❌ No se encontró población de mazos.")
            return
        
        # Mostrar configuración optimizada
        config = self.hardware_analyzer.optimization_config
        profile = self.hardware_analyzer.performance_profile
        
        print(f"\n📊 CONFIGURACIÓN AUTO-DETECTADA:")
        print(f"   Sistema: {profile['system_tier'].replace('_', ' ').title()} ({profile['overall_score']:.1f}/4.0)")
        print(f"   Población: {pop_type} ({pop_size} mazos)")
        print(f"   Workers óptimos: {config['max_workers']}")
        print(f"   Timeout base: {config['base_timeout']}s")
        print(f"   Logging: {config['log_level']}")
        
        # Opciones de ejecución basadas en hardware
        print(f"\n🎯 CONFIGURACIONES OPTIMIZADAS PARA TU SISTEMA:")
        
        options = [
            ("Prueba Ultra Rápida", 3, "🏃"),
            ("Desarrollo", 10, "🧪"),
            ("Investigación", 25, "🔬"),
            ("Producción", 50, "🏭")
        ]
        
        for i, (name, gens, emoji) in enumerate(options, 1):
            estimate = self.hardware_analyzer.estimate_time(pop_size, gens)
            print(f"  {i}. {emoji} {name}: {gens} generaciones (~{estimate})")
        
        print(f"  5. 🎛️  Personalizada")
        
        try:
            choice = input("\n👉 Selecciona configuración (1-5): ").strip()
            
            if choice in ["1", "2", "3", "4"]:
                _, max_gens, _ = options[int(choice) - 1]
                config_name = options[int(choice) - 1][0]
            elif choice == "5":
                try:
                    max_gens = int(input("👉 Número de generaciones (3-100): "))
                    if max_gens < 3 or max_gens > 100:
                        print("❌ Número fuera de rango.")
                        return
                    config_name = "Personalizada"
                except ValueError:
                    print("❌ Número no válido.")
                    return
            else:
                print("❌ Opción no válida.")
                return
            
            # Calcular parámetros optimizados
            elite_size = max(2, pop_size // 15)
            stagnation_limit = max(3, max_gens // 4)
            estimated_time = self.hardware_analyzer.estimate_time(pop_size, max_gens)
            
            print(f"\n📋 CONFIGURACIÓN FINAL AUTO-OPTIMIZADA:")
            print(f"   Nombre: {config_name}")
            print(f"   Población: {pop_size} mazos")
            print(f"   Generaciones máximas: {max_gens}")
            print(f"   Elite preservada: {elite_size}")
            print(f"   Límite de estancamiento: {stagnation_limit}")
            print(f"   Workers paralelos: {config['max_workers']}")
            print(f"   Timeout base: {config['base_timeout']}s")
            print(f"   Tiempo estimado: {estimated_time}")
            
            if "horas" in estimated_time and float(estimated_time.split()[0]) > 8:
                print(f"\n⚠️  ADVERTENCIA: Esta ejecución es muy larga ({estimated_time})")
                print("   Considera usar una configuración más pequeña primero.")
            elif "horas" in estimated_time and float(estimated_time.split()[0]) > 3:
                print(f"\n⚠️  NOTA: Esta ejecución tomará {estimated_time}")
            
            confirm = input("\n¿Iniciar algoritmo genético AUTO-OPTIMIZADO? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return
            
            print(f"\n🚀 Iniciando algoritmo genético AUTO-OPTIMIZADO...")
            print(f"   Configuración: {config_name}")
            print(f"   Workers paralelos: {config['max_workers']}")
            print(f"   Tiempo estimado: {estimated_time}")
            print(f"   Inicio: {datetime.now().strftime('%H:%M:%S')}")
            
            start_time = time.time()
            
            # CONFIGURAR Y EJECUTAR ALGORITMO GENÉTICO CON TODOS LOS PARÁMETROS DE PARALELIZACIÓN
            ga = MTGGeneticAlgorithm(
                # Parámetros básicos
                population_file=population_file,
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=max_gens,
                population_size=pop_size,
                mutation_rate=0.12,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=elite_size,
                stagnation_limit=stagnation_limit,
                headless_mode=self.headless_mode,
                # PARÁMETROS DE PARALELIZACIÓN - AQUÍ ESTÁ LA CLAVE
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs']
            )
            
            best_deck = ga.evolve()
            
            elapsed = time.time() - start_time
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            
            print(f"\n✅ ¡Algoritmo genético AUTO-OPTIMIZADO completado!")
            print(f"   Tiempo real: {int(hours)}h {int(minutes)}m")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f} ({ga.best_fitness_ever * 100:.1f}% win rate)")
            print(f"   Workers utilizados: {config['max_workers']}")
            
            # Guardar mejor mazo
            suffix = "_test_parallel" if pop_type == "Prueba" else "_final_parallel"
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
            "./forge-gui-desktop*.jar",
            "./forge*.jar",
            "../forge-gui-desktop*.jar",
            "~/Downloads/forge-gui-desktop*.jar",
            "~/Desktop/forge-gui-desktop*.jar",
            "./forge-gui-desktop-*-jar-with-dependencies.jar"
        ]
        
        found_files = []
        
        for pattern in forge_patterns:
            expanded_pattern = os.path.expanduser(pattern)
            matches = glob.glob(expanded_pattern)
            found_files.extend(matches)
        
        # Eliminar duplicados y ordenar
        found_files = list(set(found_files))
        found_files.sort(reverse=True)
        
        if found_files:
            self.forge_jar = found_files[0]
            self.forge_configured = True
            print(f"✅ Forge encontrado: {self.forge_jar}")
            
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
        
        # Estadísticas de evolución (ahora incluyendo paralelas)
        evolution_files = [
            ("Secuencial", os.path.join(self.evolved_dir, "evolution_stats.csv")),
            ("Paralelo", os.path.join(self.evolved_dir, "parallel_evolution_stats.csv"))
        ]
        
        for mode_name, stats_file in evolution_files:
            if os.path.exists(stats_file):
                try:
                    import pandas as pd
                    df = pd.read_csv(stats_file)
                    
                    print(f"\n🧬 ÚLTIMA EVOLUCIÓN ({mode_name}):")
                    print(f"   Generaciones ejecutadas: {len(df)}")
                    print(f"   Mejor fitness: {df['best_fitness'].max():.4f}")
                    print(f"   Fitness promedio final: {df['avg_fitness'].iloc[-1]:.4f}")
                except:
                    pass
        
        # Estadísticas de hardware si están disponibles
        if self.hardware_analyzer:
            config = self.hardware_analyzer.optimization_config
            profile = self.hardware_analyzer.performance_profile
            print(f"\n🖥️  HARDWARE ANALIZADO:")
            print(f"   Perfil: {profile['system_tier'].replace('_', ' ').title()}")
            print(f"   Workers óptimos: {config['max_workers']}")
            print(f"   Timeout base: {config['base_timeout']}s")
        
        input("\nPresiona Enter para continuar...")
    
    def ejecucion_completa_optimizada(self):
        """Ejecución automática completa con auto-optimización"""
        print("\n" + "=" * 60)
        print("🚀 EJECUCIÓN AUTOMÁTICA COMPLETA AUTO-OPTIMIZADA")
        print("=" * 60)
        
        if not self.forge_configured:
            print("\n❌ Forge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return
        
        # Analizar hardware automáticamente
        if not self.analyze_hardware_if_needed():
            print("❌ No se pudo analizar el hardware.")
            input("\nPresiona Enter para continuar...")
            return
        
        config = self.hardware_analyzer.optimization_config
        profile = self.hardware_analyzer.performance_profile
        
        # Seleccionar tamaño de población basado en hardware
        if profile['system_tier'] in ['high_performance', 'balanced']:
            population_size = config['recommended_populations']['medium']
            generations = 20
        else:
            population_size = config['recommended_populations']['small']
            generations = 15
        
        estimated_time = self.hardware_analyzer.estimate_time(population_size, generations)
        
        print("Esta opción ejecutará todo el proceso AUTO-OPTIMIZADO:")
        print("  1. Obtener cartas (si no están disponibles)")
        print(f"  2. Generar población de {population_size} mazos")
        print(f"  3. Ejecutar algoritmo genético por {generations} generaciones")
        print(f"  4. Usar {config['max_workers']} workers paralelos")
        print(f"\n⏱️  Tiempo estimado total: {estimated_time}")
        print(f"🖥️  Sistema detectado: {profile['system_tier'].replace('_', ' ').title()}")
        
        confirm = input("\n¿Ejecutar proceso completo AUTO-OPTIMIZADO? (s/N): ").strip().lower()
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
            print(f"\n🎴 Paso 2/3: Generando {population_size} mazos...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(population_size)
            self.check_system_status()
            
            # Paso 3: Algoritmo genético AUTO-OPTIMIZADO
            print(f"\n🧬 Paso 3/3: Ejecutando algoritmo genético AUTO-OPTIMIZADO...")
            print(f"   ({generations} generaciones, {config['max_workers']} workers paralelos)")
            
            # CONFIGURACIÓN COMPLETA CON PARÁMETROS DE PARALELIZACIÓN
            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "initial_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=generations,
                population_size=population_size,
                mutation_rate=0.12,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=max(2, population_size // 15),
                stagnation_limit=max(5, generations // 4),
                headless_mode=self.headless_mode,
                # PARÁMETROS DE PARALELIZACIÓN
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs']
            )
            
            best_deck = ga.evolve()
            
            total_elapsed = time.time() - total_start
            hours = total_elapsed // 3600
            minutes = (total_elapsed % 3600) // 60
            
            print(f"\n🎉 ¡EJECUCIÓN COMPLETA AUTO-OPTIMIZADA FINALIZADA!")
            print(f"   Tiempo total: {int(hours)}h {int(minutes)}m")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            print(f"   Workers utilizados: {config['max_workers']}")
            
            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_complete_parallel.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)
            
            self.print_deck_summary(best_deck)
            
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Ejecución interrumpida por el usuario")
        except Exception as e:
            print(f"\n❌ Error en ejecución completa: {e}")
        
        input("\nPresiona Enter para continuar...")
    
    def modo_prueba_optimizado(self):
        """Modo de prueba rápida auto-optimizado"""
        print("\n" + "=" * 60)
        print("⚡ MODO DE PRUEBA RÁPIDA AUTO-OPTIMIZADO")
        print("=" * 60)
        
        if not self.forge_configured:
            print("\n❌ Forge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return
        
        # Analizar hardware automáticamente
        if not self.analyze_hardware_if_needed():
            print("❌ No se pudo analizar el hardware. Usando configuración por defecto.")
            test_size = 8
            test_gens = 3
            workers = 2
            estimated_time = "30-45 minutos"
        else:
            config = self.hardware_analyzer.optimization_config
            profile = self.hardware_analyzer.performance_profile
            test_size = config['recommended_populations']['test']
            test_gens = config['recommended_generations']['quick']
            workers = config['max_workers']
            estimated_time = self.hardware_analyzer.estimate_time(test_size, test_gens)
        
        print("Esta opción ejecutará una prueba rápida AUTO-OPTIMIZADA:")
        print("  1. Usar cartas existentes o descargar si es necesario")
        print(f"  2. Generar población de {test_size} mazos")
        print(f"  3. Ejecutar algoritmo genético por {test_gens} generaciones")
        print(f"  4. Usar {workers} workers paralelos")
        print(f"\n⏱️  Tiempo estimado total: {estimated_time}")
        
        confirm = input("\n¿Ejecutar prueba rápida AUTO-OPTIMIZADA? (S/n): ").strip().lower()
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
            print(f"\n🎴 Generando {test_size} mazos de prueba...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(test_size)
            self.check_system_status()
            
            # Paso 3: Algoritmo genético de prueba AUTO-OPTIMIZADO
            print(f"\n🧬 Ejecutando algoritmo genético de prueba AUTO-OPTIMIZADO...")
            print(f"   ({test_gens} generaciones, {workers} workers paralelos)")
            
            # Configuración optimizada si hay hardware analyzer
            if self.hardware_analyzer:
                config = self.hardware_analyzer.optimization_config
                ga_config = {
                    'max_workers': config['max_workers'],
                    'parallel_batch_size': config['parallel_batch_size'],
                    'base_timeout': config['base_timeout'],
                    'log_level': config['log_level'],
                    'save_forge_outputs': config['save_forge_outputs']
                }
            else:
                # Configuración por defecto
                ga_config = {
                    'max_workers': 2,
                    'parallel_batch_size': 6,
                    'base_timeout': 300,
                    'log_level': 'INFO',
                    'save_forge_outputs': True
                }
            
            # EJECUTAR CON PARÁMETROS DE PARALELIZACIÓN
            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "test_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=test_gens,
                population_size=test_size,
                mutation_rate=0.12,
                crossover_rate=0.9,
                tournament_size=3,
                elite_size=2,
                stagnation_limit=max(2, test_gens // 2),
                headless_mode=self.headless_mode,
                # PARÁMETROS DE PARALELIZACIÓN
                **ga_config
            )
            
            best_deck = ga.evolve()
            
            test_elapsed = time.time() - test_start
            minutes = test_elapsed // 60
            seconds = test_elapsed % 60
            
            print(f"\n🎯 ¡PRUEBA AUTO-OPTIMIZADA COMPLETADA!")
            print(f"   Tiempo total: {int(minutes)}m {int(seconds)}s")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            print(f"   Workers utilizados: {workers}")
            
            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_test_parallel.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)
            
            self.print_deck_summary(best_deck)
            
            print(f"\n✅ Si la prueba funcionó correctamente, puedes ejecutar")
            print(f"   la versión completa con la opción 7 del menú principal.")
            
            if self.hardware_analyzer:
                config = self.hardware_analyzer.optimization_config
                print(f"\n📈 RENDIMIENTO DETECTADO:")
                print(f"   Tu sistema puede manejar hasta {config['recommended_populations']['large']} mazos")
                print(f"   con {config['max_workers']} workers paralelos")
            
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