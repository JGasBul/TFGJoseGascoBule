#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script Principal del TFG: Algoritmo Genético para Magic: The Gathering

Este módulo implementa el sistema de menús interactivo completo para el proyecto de TFG
sobre diseño de algoritmos genéticos aplicados a la construcción de mazos de MTG.

Características principales:
- Análisis automático de hardware para optimización de rendimiento
- Sistema de menús intuitivo con todas las funcionalidades del proyecto
- Auto-detección de modo headless para ejecución en servidores
- Estimaciones de tiempo basadas en hardware real del usuario
- Configuración automática de parámetros de paralelización

Autor: José Gascó Bule - Universidad de [Nombre]
Fecha: Enero 2025
Versión: 2.0 - Con Auto-Optimización Integrada
"""

# ==================================================================================
# IMPORTS
# ==================================================================================

# Librería estándar
import os
import json
import time
import glob
import sys
import platform
import multiprocessing as mp
from pathlib import Path
from datetime import datetime

# Librerías de terceros
import psutil
import numpy as np

# Módulos del proyecto
from obtener_cartas_mtg import MTGCardScraper
from generador_mazos_mtg import MTGDeckGenerator
from algoritmo_genetico_mtg import MTGGeneticAlgorithm


# ==================================================================================
# CLASE: HARDWARE ANALYZER
# ==================================================================================

class HardwareAnalyzer:
    """
    Analizador de Hardware para Auto-Optimización del Algoritmo Genético

    Esta clase realiza un análisis completo del hardware del sistema y genera
    automáticamente configuraciones optimizadas de paralelización, timeouts y
    tamaños de población basados en las capacidades reales de la máquina.

    Analiza:
    - CPU: cores físicos/lógicos, frecuencia, carga actual
    - Memoria: RAM total, disponible, porcentaje de uso
    - Almacenamiento: espacio disponible, velocidades de lectura/escritura
    - Sistema operativo: plataforma, release, arquitectura

    Genera:
    - Configuración optimizada de workers paralelos
    - Recomendaciones de tamaños de población
    - Estimaciones de tiempo de ejecución
    - Identificación de cuellos de botella
    """

    def __init__(self):
        """
        Inicializa el analizador y ejecuta análisis completo del sistema
        """
        print("🔍 === ANALIZANDO HARDWARE DEL SISTEMA ===")
        self.system_info = self.analyze_system()
        self.performance_profile = self.create_performance_profile()
        self.optimization_config = self.generate_optimization_config()

    # ==============================================================================
    # ANÁLISIS DE HARDWARE
    # ==============================================================================

    def analyze_system(self):
        """
        Realiza análisis completo del hardware del sistema

        Returns:
            dict: Diccionario con información completa de CPU, memoria,
                  almacenamiento y sistema operativo
        """
        print("   💻 Analizando CPU...")
        cpu_info = {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 0,
            'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0
        }

        # Test de carga CPU actual (5 muestras de 200ms cada una)
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

        # Test básico de velocidad de I/O
        try:
            storage_info.update(self.test_disk_speed())
        except Exception:
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
        """
        Realiza test rápido de velocidad de disco (lectura/escritura)

        Crea un archivo temporal de 5MB y mide tiempos de escritura y lectura.

        Returns:
            dict: Velocidades de lectura y escritura en MB/s
        """
        test_file = "temp_speed_test.dat"
        test_size_mb = 5
        test_data = os.urandom(test_size_mb * 1024 * 1024)

        try:
            # Test de escritura con flush completo
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

            # Limpiar archivo de test
            os.remove(test_file)

            return {
                'read_speed_mb_s': round(read_speed, 1),
                'write_speed_mb_s': round(write_speed, 1)
            }
        except Exception:
            if os.path.exists(test_file):
                os.remove(test_file)
            return {'read_speed_mb_s': 0, 'write_speed_mb_s': 0}

    # ==============================================================================
    # PERFILADO Y CLASIFICACIÓN
    # ==============================================================================

    def create_performance_profile(self):
        """
        Crea perfil de rendimiento clasificando componentes por tier

        Clasifica CPU, RAM y almacenamiento en tiers (high_end, mid_high, mid_range, low_end)
        y genera un perfil general del sistema (high_performance, balanced, conservative, minimal).

        Returns:
            dict: Perfil completo con tiers de componentes y sistema general
        """
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        storage = self.system_info['storage']

        # Clasificar CPU por número de cores lógicos
        if cpu['logical_cores'] >= 16:
            cpu_tier = "high_end"
        elif cpu['logical_cores'] >= 8:
            cpu_tier = "mid_high"
        elif cpu['logical_cores'] >= 4:
            cpu_tier = "mid_range"
        else:
            cpu_tier = "low_end"

        # Clasificar RAM por GB totales
        if memory['total_gb'] >= 32:
            ram_tier = "high_end"
        elif memory['total_gb'] >= 16:
            ram_tier = "mid_high"
        elif memory['total_gb'] >= 8:
            ram_tier = "mid_range"
        else:
            ram_tier = "low_end"

        # Clasificar almacenamiento por velocidad de lectura
        read_speed = storage.get('read_speed_mb_s', 0)
        if read_speed >= 500:
            storage_tier = "high_end"  # SSD NVMe
        elif read_speed >= 200:
            storage_tier = "mid_high"  # SSD SATA
        elif read_speed >= 100:
            storage_tier = "mid_range"  # HDD rápido (7200rpm)
        else:
            storage_tier = "low_end"     # HDD lento

        # Calcular perfil general ponderado
        tier_scores = {"high_end": 4, "mid_high": 3, "mid_range": 2, "low_end": 1}
        overall_score = (tier_scores[cpu_tier] + tier_scores[ram_tier] + tier_scores[storage_tier]) / 3

        # Asignar tier de sistema general
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
        """
        Identifica posibles cuellos de botella del sistema

        Detecta limitaciones en CPU (cores, carga), RAM (disponible, uso) y
        almacenamiento (espacio, velocidad) que podrían afectar rendimiento.

        Returns:
            list: Lista de strings describiendo cuellos de botella detectados
        """
        bottlenecks = []
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        storage = self.system_info['storage']

        # Cuellos de botella de CPU
        if cpu['logical_cores'] < 4:
            bottlenecks.append("CPU: Pocos cores para paralelización eficiente")

        if cpu['available_capacity'] < 50:
            bottlenecks.append("CPU: Sistema bajo alta carga (puede afectar rendimiento)")

        # Cuellos de botella de RAM
        if memory['available_gb'] < 4:
            bottlenecks.append("RAM: Poca memoria disponible (< 4GB)")

        if memory['percentage_used'] > 80:
            bottlenecks.append("RAM: Uso muy alto (> 80%)")

        # Cuellos de botella de almacenamiento
        if storage['percentage_used'] > 90:
            bottlenecks.append("STORAGE: Disco casi lleno (> 90%)")

        if storage.get('read_speed_mb_s', 0) < 50:
            bottlenecks.append("STORAGE: Velocidad muy lenta (< 50 MB/s)")

        return bottlenecks

    # ==============================================================================
    # GENERACIÓN DE CONFIGURACIÓN OPTIMIZADA
    # ==============================================================================

    def generate_optimization_config(self):
        """
        Genera configuración optimizada automática para el algoritmo genético

        Calcula número óptimo de workers paralelos, timeouts, tamaños de población
        recomendados y otras configuraciones basándose en el análisis de hardware.

        Returns:
            dict: Configuración completa optimizada con todos los parámetros
        """
        cpu = self.system_info['cpu']
        memory = self.system_info['memory']
        profile = self.performance_profile

        # === CÁLCULO DE WORKERS ÓPTIMOS ===
        # Considerar múltiples factores: cores físicos (mejor para CPU-bound), RAM, carga
        max_theoretical = cpu['physical_cores'] or cpu['logical_cores']
        max_by_ram = int(memory['available_gb'] * 1024 / 400)    # ~400MB por worker (conservador)

        # Calcular workers basado en cores físicos (mejor para tareas CPU-bound)
        # Usamos 100% de cores físicos si carga < 60%, sino reducimos
        if cpu['baseline_usage'] < 60:
            # Sistema con poca carga: usar todos los cores físicos
            optimal_workers = max_theoretical
        else:
            # Sistema con carga alta: usar 70% de cores físicos
            optimal_workers = max(2, int(max_theoretical * 0.7))

        # Aplicar límites por RAM y práctico
        optimal_workers = min(
            optimal_workers,
            max_by_ram,     # Limitado por RAM disponible
            20              # Límite práctico aumentado (antes era 16)
        )
        optimal_workers = max(2, optimal_workers)  # Mínimo 2 workers

        # === CONFIGURACIÓN DE TIMEOUTS ===
        base_timeout = 300  # 5 minutos base para combates de Forge

        # === CONFIGURACIÓN DE LOGS ===
        log_level = 'INFO'  # Balance entre información y rendimiento
        save_forge_outputs = True  # Guardar outputs para debugging

        # === POBLACIONES RECOMENDADAS POR TIER DE SISTEMA ===
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

    # ==============================================================================
    # UTILIDADES Y PRESENTACIÓN
    # ==============================================================================

    def print_analysis(self):
        """
        Imprime análisis completo del sistema de forma legible
        """
        print("\n" + "=" * 70)
        print("🖥️  ANÁLISIS DE HARDWARE COMPLETADO")
        print("=" * 70)

        # Información del sistema operativo
        os_info = self.system_info['os']
        print(f"🏢 Sistema: {os_info['platform']} {os_info['release']} ({os_info['architecture']})")

        # Información de CPU
        cpu = self.system_info['cpu']
        print(f"💻 CPU: {cpu['logical_cores']} cores lógicos ({cpu['physical_cores']} físicos)")
        if cpu['max_frequency']:
            print(f"   Frecuencia: {cpu['max_frequency']:.0f} MHz")
        print(f"   Carga actual: {cpu['baseline_usage']:.1f}%")
        print(f"   Capacidad disponible: {cpu['available_capacity']:.1f}%")

        # Información de memoria
        mem = self.system_info['memory']
        print(f"🧠 RAM: {mem['total_gb']:.1f} GB total, {mem['available_gb']:.1f} GB disponible ({mem['percentage_used']:.1f}% usado)")

        # Información de almacenamiento
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
        print(f"   Forge outputs: {'✅ Habilitado' if config['save_forge_outputs'] else '❌ Deshabilitado'}")

        print("=" * 70)

    def estimate_time(self, population, generations, workers=None):
        """
        Estima tiempo de ejecución del algoritmo genético

        Args:
            population (int): Tamaño de población
            generations (int): Número de generaciones
            workers (int, optional): Workers a usar (por defecto usa óptimo)

        Returns:
            str: Estimación de tiempo en formato legible (minutos u horas)
        """
        if workers is None:
            workers = self.optimization_config['max_workers']

        # Combates por generación (round-robin simplificado)
        combats_per_gen = population * (population - 1)

        # Tiempo base por combate según tier del sistema
        if self.performance_profile['system_tier'] == "high_performance":
            base_time = 35  # segundos por combate
        elif self.performance_profile['system_tier'] == "balanced":
            base_time = 45
        elif self.performance_profile['system_tier'] == "conservative":
            base_time = 60
        else:
            base_time = 75

        # Tiempo total con paralelización
        total_seconds = (combats_per_gen * base_time * generations) / workers
        total_seconds *= 1.1  # 10% overhead para gestión de procesos

        # Formatear salida
        if total_seconds < 3600:
            return f"{total_seconds/60:.0f} minutos"
        else:
            return f"{total_seconds/3600:.1f} horas"


# ==================================================================================
# CLASE: MENU SYSTEM
# ==================================================================================

class MTGMenuSystem:
    """
    Sistema de Menús Interactivo para el Proyecto de TFG

    Esta clase implementa toda la interfaz de usuario basada en menús para
    interactuar con el proyecto completo: descarga de cartas, generación de mazos,
    ejecución del algoritmo genético y análisis de resultados.

    Características:
    - Auto-detección de estado del sistema (cartas, mazos, Forge)
    - Análisis de hardware bajo demanda
    - Auto-detección de modo headless para servidores
    - Múltiples modos de ejecución (prueba rápida, completa, personalizada)
    - Estimaciones de tiempo realistas
    """

    def __init__(self):
        """
        Inicializa el sistema de menús y verifica estado del sistema
        """
        # Directorios del proyecto
        self.data_dir = "mtg_data"
        self.decks_dir = "mtg_decks"
        self.evolved_dir = "mtg_evolved_decks"
        self.forge_jar = None
        self.headless_mode = False

        # Crear directorios si no existen
        Path(self.data_dir).mkdir(exist_ok=True)
        Path(self.decks_dir).mkdir(exist_ok=True)
        Path(self.evolved_dir).mkdir(exist_ok=True)

        # Estado del sistema
        self.cards_available = False
        self.population_available = False
        self.forge_configured = False

        # Hardware analyzer (se inicializa bajo demanda)
        self.hardware_analyzer = None

        # Verificar estado inicial y modo de ejecución
        self.check_system_status()
        self.auto_detect_headless()

    # ==============================================================================
    # VERIFICACIÓN Y DETECCIÓN DE ESTADO
    # ==============================================================================

    def analyze_hardware_if_needed(self):
        """
        Analiza hardware del sistema si no se ha hecho previamente

        Returns:
            bool: True si el análisis fue exitoso o ya estaba hecho
        """
        if self.hardware_analyzer is None:
            try:
                self.hardware_analyzer = HardwareAnalyzer()
                return True
            except Exception as e:
                print(f"⚠️  Error analizando hardware: {e}")
                return False
        return True

    def check_system_status(self):
        """
        Verifica el estado actual del sistema (cartas, mazos, Forge)

        Actualiza los flags de estado para mostrar información correcta en menús
        """
        # Verificar si las cartas están disponibles
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

        # Verificar si hay población de mazos generada
        pop_file = os.path.join(self.decks_dir, "initial_population.json")
        test_pop_file = os.path.join(self.decks_dir, "test_population.json")

        if os.path.exists(pop_file) or os.path.exists(test_pop_file):
            self.population_available = True
        else:
            self.population_available = False

        # Buscar Forge JAR automáticamente
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
                matches.sort(reverse=True)  # Ordenar para usar versión más reciente
                self.forge_jar = matches[0]
                self.forge_configured = True
                break

    def auto_detect_headless(self):
        """
        Detecta automáticamente si el sistema está en modo headless

        Un sistema headless es aquel sin interfaz gráfica (servidores, SSH).
        En modo headless, Forge debe ejecutarse con xvfb-run.
        """
        try:
            # Método 1: Verificar variable DISPLAY
            display = os.environ.get('DISPLAY')
            if not display:
                self.headless_mode = True
                return

            # Método 2: Verificar si es conexión SSH
            ssh_connection = os.environ.get('SSH_CONNECTION')
            if ssh_connection:
                self.headless_mode = True
                return

            # Método 3: Intentar importar tkinter (requiere GUI)
            try:
                import tkinter
                root = tkinter.Tk()
                root.withdraw()
                root.destroy()
                self.headless_mode = False
            except Exception:
                self.headless_mode = True

        except Exception:
            # Por seguridad, asumir headless si hay error
            self.headless_mode = True

    # ==============================================================================
    # PRESENTACIÓN DE ESTADO
    # ==============================================================================

    def print_header(self):
        """
        Imprime el header principal del programa
        """
        print("\n" + "=" * 80)
        print("           ALGORITMO GENÉTICO PARA MAGIC: THE GATHERING")
        print("    Optimización Evolutiva de Mazos con Paralelización Adaptativa")
        print("                    TFG - José Gascó Bulé (2025)")
        print("=" * 80)

    def print_status(self):
        """
        Imprime el estado actual del sistema con información detallada
        """
        print("\nESTADO ACTUAL DEL SISTEMA:")

        # Estado de cartas
        if self.cards_available:
            print(f"  Cartas: {self.num_cards:,} cartas del formato Estándar disponibles")
        else:
            print("  Cartas: No se han descargado cartas")

        # Estado de mazos
        if self.population_available:
            print("  Mazos: Población inicial generada")
        else:
            print("  Mazos: No se ha generado población inicial")

        # Estado de Forge
        if self.forge_configured:
            print(f"  Forge: Configurado en {os.path.basename(self.forge_jar)}")
        else:
            print("  Forge: No encontrado (necesario para algoritmo genético)")

        # Modo de ejecución
        if self.headless_mode:
            print("  Modo: Headless (sin interfaz gráfica) - usando xvfb-run")
        else:
            print("  Modo: GUI disponible - ejecución estándar")

        # Estado del análisis de hardware
        if self.hardware_analyzer:
            config = self.hardware_analyzer.optimization_config
            profile = self.hardware_analyzer.performance_profile
            print(f"  Hardware: {profile['system_tier'].replace('_', ' ').title()} - {config['max_workers']} workers óptimos")
        else:
            print(f"  Hardware: Se analizará automáticamente cuando sea necesario")

        # Mensaje de preparación
        if self.cards_available and self.population_available and self.forge_configured:
            print(f"  Sistema listo para algoritmo genético optimizado")

        print()

    def show_performance_comparison(self):
        """
        Muestra comparación de rendimiento con paralelización
        """
        if not self.hardware_analyzer:
            return

        config = self.hardware_analyzer.optimization_config
        workers = config['max_workers']

        print(f"\n📈 COMPARACIÓN DE RENDIMIENTO:")
        print(f"   Baseline secuencial: 100 minutos")
        print(f"   Con paralelización ({workers} workers): ~{100/workers:.0f} minutos")
        print(f"   🚀 Aceleración esperada: {workers:.1f}x más rápido")
        print(f"   ⏱️  Tiempo ahorrado: ~{100 - (100/workers):.0f} minutos")

    def detect_baseline_performance(self):
        """
        Detecta si hay datos de rendimiento de ejecuciones previas

        Returns:
            bool: True si se encontraron archivos de estadísticas previas
        """
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
                except Exception:
                    pass
        return False

    # ==============================================================================
    # MENÚ PRINCIPAL
    # ==============================================================================

    def main_menu(self):
        """
        Menú principal del sistema - punto de entrada interactivo
        """
        while True:
            self.print_header()
            self.print_status()

            # Mostrar comparación de rendimiento si hay baseline
            if self.detect_baseline_performance():
                self.show_performance_comparison()

            print("MENÚ PRINCIPAL:")
            print("  1. Obtener cartas de Magic (Paso 1)")
            print("  2. Generar mazos iniciales (Paso 2)")
            print("  3. Ejecutar algoritmo genético optimizado (Paso 3)")
            print("  4. Continuar desde checkpoint guardado")
            print("  5. Configurar Forge")
            print("  6. Analizar hardware del sistema")
            print("  7. Ver estadísticas del sistema")
            print("  8. Ejecución automática completa")
            print("  9. Modo de prueba rápida")
            print("  10. Configurar modo headless")
            print("  0. Salir")

            try:
                choice = input("\n👉 Selecciona una opción (0-10): ").strip()

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
                    self.menu_continuar_desde_checkpoint()
                elif choice == "5":
                    self.menu_configurar_forge()
                elif choice == "6":
                    self.menu_analizar_hardware()
                elif choice == "7":
                    self.menu_estadisticas()
                elif choice == "8":
                    self.ejecucion_completa_optimizada()
                elif choice == "9":
                    self.modo_prueba_optimizado()
                elif choice == "10":
                    self.menu_configurar_headless()
                else:
                    print("\n❌ Opción no válida. Por favor, selecciona un número del 0 al 10.")
                    input("\nPresiona Enter para continuar...")

            except KeyboardInterrupt:
                print("\n\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}")
                input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: DESCARGA DE CARTAS
    # ==============================================================================

    def menu_obtener_cartas(self):
        """
        Menú para descargar y procesar cartas de Magic desde Scryfall
        """
        print("\n" + "=" * 60)
        print("OBTENER CARTAS DE MAGIC")
        print("=" * 60)

        if self.cards_available:
            print(f"Estado: {self.num_cards:,} cartas del formato Estándar ya disponibles.")
            choice = input("¿Descargar cartas nuevamente? (s/N): ").strip().lower()
            if choice not in ['s', 'sí', 'si', 'y', 'yes']:
                return

        print("\nDescargando cartas del formato Estándar desde Scryfall API...")
        print("Tiempo estimado: 2-5 minutos")

        start_time = time.time()

        try:
            scraper = MTGCardScraper(
                output_dir=self.data_dir,
                exclude_latest_set=True
            )
            cards_df = scraper.run()

            if cards_df is not None and not cards_df.empty:
                elapsed = time.time() - start_time
                print(f"\nCartas obtenidas exitosamente")
                print(f"Tiempo de descarga: {elapsed:.1f} segundos")
                print(f"Cartas únicas procesadas: {len(cards_df):,}")
                self.check_system_status()
            else:
                print("\nError: No se pudieron obtener las cartas del servidor.")

        except Exception as e:
            print(f"\nError durante la descarga: {e}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: GENERACIÓN DE MAZOS
    # ==============================================================================

    def menu_generar_mazos(self):
        """
        Menú para generar población inicial de mazos con limpieza automática
        """
        print("\n" + "=" * 60)
        print("GENERAR MAZOS INICIALES")
        print("=" * 60)

        if not self.cards_available:
            print("Error: Primero necesitas obtener las cartas (Opción 1).")
            input("\nPresiona Enter para continuar...")
            return

        # Verificar mazos existentes
        existing_files = []
        deck_patterns = [
            os.path.join(self.decks_dir, "*.dck"),
            os.path.join(self.decks_dir, "*population*.json")
        ]

        for pattern in deck_patterns:
            existing_files.extend(glob.glob(pattern))

        if existing_files:
            print(f"Información: Se encontraron {len(existing_files)} archivos de mazos existentes.")
            print("Estos serán eliminados automáticamente antes de generar los nuevos.")

        print(f"\nTIPOS DE POBLACIÓN:")
        print("  1. Prueba ultra rápida (8 mazos)")
        print("  2. Prueba rápida (12 mazos)")
        print("  3. Desarrollo (20 mazos)")
        print("  4. Estándar (30 mazos)")
        print("  5. Intensivo (50 mazos)")
        print("  6. Personalizada")

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
                    size = int(input("Número de mazos (5-100): "))
                    if size < 5 or size > 100:
                        print("Error: Número fuera de rango.")
                        return
                    name = "personalizada"
                except ValueError:
                    print("Error: Número no válido.")
                    return
            else:
                print("Error: Opción no válida.")
                return

            print(f"\nCONFIGURACIÓN SELECCIONADA:")
            print(f"  Mazos a generar: {size}")
            if existing_files:
                print(f"  Archivos a eliminar: {len(existing_files)}")

            confirm = input("\n¿Continuar con esta configuración? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return

            print(f"\nGenerando población {name} de {size} mazos...")
            start_time = time.time()

            # Cargar generador (incluye limpieza automática)
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )

            population = generator.generate_population_exact_size(size)

            elapsed = time.time() - start_time
            print(f"\nPoblación generada exitosamente")
            print(f"Tiempo de generación: {elapsed:.1f} segundos")
            print(f"Mazos creados: {len(population)}")

            self.check_system_status()

        except Exception as e:
            print(f"\nError durante la generación: {e}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: ANÁLISIS DE HARDWARE
    # ==============================================================================

    def menu_analizar_hardware(self):
        """
        Menú para análisis detallado de hardware del sistema
        """
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

            # Mostrar recomendaciones personalizadas
            config = self.hardware_analyzer.optimization_config
            print(f"\n📏 RECOMENDACIONES PARA TU SISTEMA:")
            for name, size in config['recommended_populations'].items():
                estimate = self.hardware_analyzer.estimate_time(size, 10)
                print(f"   {name.title()}: {size} mazos (~{estimate} para 10 generaciones)")

        except Exception as e:
            print(f"❌ Error durante análisis: {e}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: CONFIGURACIÓN HEADLESS
    # ==============================================================================

    def menu_configurar_headless(self):
        """
        Menú para configurar modo headless (sin GUI) para servidores
        """
        print("\n" + "=" * 60)
        print("🖥️  CONFIGURAR MODO HEADLESS")
        print("=" * 60)

        print(f"Estado actual: {'✅ Headless' if self.headless_mode else '🖼️  GUI disponible'}")

        print("\nEl modo headless es necesario en servidores o máquinas sin interfaz gráfica.")
        print("En modo headless, Forge se ejecuta con 'xvfb-run -a' para simular display.")

        print("\n🔧 OPCIONES:")
        print("  1. 🔍 Auto-detectar (recomendado)")
        print("  2. ✅ Forzar modo headless (para servidores)")
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

            elif choice == "3":
                self.headless_mode = False
                print("\n🖼️  Modo GUI activado manualmente")
                print("   Forge se ejecutará con: java -jar forge.jar")

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

    # ==============================================================================
    # SUBMENÚS: ALGORITMO GENÉTICO
    # ==============================================================================

    def menu_algoritmo_genetico_optimizado(self):
        """
        Menú principal para ejecutar algoritmo genético auto-optimizado
        """
        print("\n" + "=" * 60)
        print("ALGORITMO GENÉTICO OPTIMIZADO")
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
            print(f"Error: Faltan componentes requeridos: {', '.join(missing)}")
            print("Completa los pasos anteriores primero.")
            input("\nPresiona Enter para continuar...")
            return

        # Analizar hardware si no se ha hecho
        if not self.analyze_hardware_if_needed():
            print("Advertencia: No se pudo analizar el hardware. Usando configuración por defecto.")
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
            print("Error: No se encontró población de mazos.")
            return

        # Mostrar configuración optimizada
        config = self.hardware_analyzer.optimization_config
        profile = self.hardware_analyzer.performance_profile

        print(f"\nCONFIGURACIÓN AUTO-DETECTADA:")
        print(f"  Sistema: {profile['system_tier'].replace('_', ' ').title()} ({profile['overall_score']:.1f}/4.0)")
        print(f"  Población: {pop_type} ({pop_size} mazos)")
        print(f"  Workers óptimos: {config['max_workers']}")
        print(f"  Timeout base: {config['base_timeout']}s")
        print(f"  Nivel de logging: {config['log_level']}")

        # Opciones de ejecución
        print(f"\nCONFIGURACIONES OPTIMIZADAS PARA TU SISTEMA:")

        options = [
            ("Prueba Ultra Rápida", 3),
            ("Desarrollo", 10),
            ("Investigación", 25),
            ("Producción", 50)
        ]

        for i, (name, gens) in enumerate(options, 1):
            estimate = self.hardware_analyzer.estimate_time(pop_size, gens)
            print(f"  {i}. {name}: {gens} generaciones (tiempo estimado: {estimate})")

        print(f"  5. Personalizada")

        try:
            choice = input("\nSelecciona configuración (1-5): ").strip()

            if choice in ["1", "2", "3", "4"]:
                _, max_gens = options[int(choice) - 1]
                config_name = options[int(choice) - 1][0]
            elif choice == "5":
                try:
                    max_gens = int(input("Número de generaciones (3-200): "))
                    if max_gens < 3 or max_gens > 200:
                        print("Error: Número fuera de rango.")
                        return
                    config_name = "Personalizada"
                except ValueError:
                    print("Error: Número no válido.")
                    return
            else:
                print("Error: Opción no válida.")
                return

            # Calcular parámetros optimizados
            # OPTIMIZADO: Elite = 40% de población (antes: ~7%), stagnation desactivado
            elite_size = max(2, int(pop_size * 0.4))  # 40% de población para mayor presión selectiva
            stagnation_limit = 999  # Desactivado: evita inyección contraproducente de mazos aleatorios
            estimated_time = self.hardware_analyzer.estimate_time(pop_size, max_gens)

            print(f"\nCONFIGURACIÓN FINAL OPTIMIZADA:")
            print(f"  Nombre: {config_name}")
            print(f"  Población: {pop_size} mazos")
            print(f"  Generaciones máximas: {max_gens}")
            print(f"  Elite preservada: {elite_size}")
            print(f"  Límite de estancamiento: {stagnation_limit}")
            print(f"  Workers paralelos: {config['max_workers']}")
            print(f"  Timeout base: {config['base_timeout']}s")
            print(f"  Tiempo estimado: {estimated_time}")

            if "horas" in estimated_time and float(estimated_time.split()[0]) > 8:
                print(f"\nAdvertencia: Esta ejecución es muy larga ({estimated_time})")
                print("Considera usar una configuración más pequeña primero.")

            confirm = input("\n¿Iniciar algoritmo genético optimizado? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return

            print(f"\nIniciando algoritmo genético optimizado...")
            print(f"Configuración: {config_name}")
            print(f"Workers paralelos: {config['max_workers']}")
            print(f"Tiempo estimado: {estimated_time}")
            print(f"Hora de inicio: {datetime.now().strftime('%H:%M:%S')}")

            start_time = time.time()

            # Ejecutar algoritmo genético con configuración optimizada
            ga = MTGGeneticAlgorithm(
                population_file=population_file,
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=max_gens,
                population_size=pop_size,
                mutation_rate=0.15,              # Incrementado de 0.12 (+25% exploración)
                crossover_rate=0.9,
                tournament_size=4,               # Incrementado de 3 (+33% presión de selección)
                elite_size=elite_size,
                stagnation_limit=stagnation_limit,
                headless_mode=self.headless_mode,
                # Parámetros de paralelización optimizados
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs'],
                # Parámetros de fitness multi-componente (MÁS PESO A CALIDAD)
                fitness_alpha=0.6,               # Reducido de 0.7 (win rate 60%)
                fitness_beta=0.4,                # Incrementado de 0.3 (calidad 40%)
                enable_quality_metrics=True
            )

            best_deck = ga.evolve()

            elapsed = time.time() - start_time
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60

            print(f"\nAlgoritmo genético optimizado completado exitosamente")
            print(f"Tiempo de ejecución: {int(hours)}h {int(minutes)}m")
            print(f"Mejor fitness alcanzado: {ga.best_fitness_ever:.4f} ({ga.best_fitness_ever * 100:.1f}% win rate)")
            print(f"Workers utilizados: {config['max_workers']}")

            # Guardar mejor mazo
            suffix = "_test_parallel" if pop_type == "Prueba" else "_final_parallel"
            best_deck_file = os.path.join(self.evolved_dir, f"best_deck{suffix}.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            print(f"   Mejor mazo guardado en: {best_deck_file}")
            self.print_deck_summary(best_deck)

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Ejecución interrumpida por el usuario")
            print("   Los progresos se han guardado automáticamente")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        input("\nPresiona Enter para continuar...")

    def menu_continuar_desde_checkpoint(self):
        """
        Menú para buscar y continuar ejecuciones desde checkpoints guardados
        """
        print("\n" + "=" * 80)
        print("CONTINUAR DESDE CHECKPOINT GUARDADO")
        print("=" * 80)

        # Buscar checkpoints disponibles
        checkpoint_dir = os.path.join(self.evolved_dir, "checkpoints")

        if not os.path.exists(checkpoint_dir):
            print("\n❌ No se encontró directorio de checkpoints.")
            print(f"   Ruta buscada: {checkpoint_dir}")
            input("\nPresiona Enter para continuar...")
            return

        # Listar todos los checkpoints
        import glob
        checkpoint_files = sorted(glob.glob(os.path.join(checkpoint_dir, "checkpoint_gen_*.json")))

        if not checkpoint_files:
            print("\n❌ No se encontraron checkpoints guardados.")
            print(f"   Directorio verificado: {checkpoint_dir}")
            input("\nPresiona Enter para continuar...")
            return

        # Mostrar checkpoints disponibles
        print(f"\n📁 CHECKPOINTS DISPONIBLES ({len(checkpoint_files)} encontrados):")
        print("=" * 80)

        checkpoints_info = []
        for cp_file in checkpoint_files:
            try:
                with open(cp_file, 'r') as f:
                    data = json.load(f)

                gen = data['generation']
                timestamp = data['timestamp']
                best_fitness = data.get('best_fitness_ever', 0.0)
                pop_size = data.get('population_size', 0)
                max_gens = data.get('max_generations', 0)
                mut_rate = data.get('mutation_rate', 0.0)
                orig_mut = data.get('original_mutation_rate', 0.0)
                gens_since = data.get('generations_since_intervention', 0)

                checkpoints_info.append({
                    'file': cp_file,
                    'gen': gen,
                    'timestamp': timestamp,
                    'best_fitness': best_fitness,
                    'pop_size': pop_size,
                    'max_gens': max_gens,
                    'mut_rate': mut_rate,
                    'orig_mut': orig_mut,
                    'gens_since': gens_since,
                    'data': data
                })
            except Exception as e:
                print(f"⚠️  Error leyendo {os.path.basename(cp_file)}: {e}")

        if not checkpoints_info:
            print("\n❌ No se pudieron leer los checkpoints.")
            input("\nPresiona Enter para continuar...")
            return

        # Ordenar por generación (más reciente primero)
        checkpoints_info.sort(key=lambda x: x['gen'], reverse=True)

        # Mostrar información detallada
        for i, cp_info in enumerate(checkpoints_info, 1):
            gen = cp_info['gen']
            timestamp = cp_info['timestamp'].split('T')
            date = timestamp[0]
            time_str = timestamp[1].split('.')[0] if len(timestamp) > 1 else "N/A"

            print(f"\n{i}. Generación {gen}/{cp_info['max_gens']}")
            print(f"   📅 Fecha: {date} {time_str}")
            print(f"   🏆 Best fitness: {cp_info['best_fitness']:.4f} ({cp_info['best_fitness']*100:.1f}% win rate)")
            print(f"   👥 Población: {cp_info['pop_size']} mazos")
            print(f"   📊 Progreso: {gen}/{cp_info['max_gens']} generaciones ({gen*100//cp_info['max_gens']}%)")

            # Mostrar estado de mutación adaptativa
            if cp_info['mut_rate'] != cp_info['orig_mut']:
                print(f"   ⚡ Mutación adaptativa ACTIVA: {cp_info['mut_rate']:.3f} (original: {cp_info['orig_mut']:.3f})")
                print(f"   🔄 Generaciones desde intervención: {cp_info['gens_since']}")
            else:
                print(f"   🔧 Mutación: {cp_info['mut_rate']:.3f} (normal)")

        # Seleccionar checkpoint
        print("\n" + "=" * 80)
        print("Selecciona el checkpoint desde el cual continuar:")

        try:
            choice = input(f"\nOpción (1-{len(checkpoints_info)}) o 0 para cancelar: ").strip()

            if choice == "0":
                print("\n❌ Cancelado.")
                input("\nPresiona Enter para continuar...")
                return

            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(checkpoints_info):
                print("\n❌ Opción no válida.")
                input("\nPresiona Enter para continuar...")
                return

            selected_cp = checkpoints_info[choice_idx]

            # Mostrar resumen y confirmar
            print("\n" + "=" * 80)
            print("RESUMEN DE LA CONTINUACIÓN:")
            print("=" * 80)
            print(f"Generación inicial: {selected_cp['gen'] + 1}")
            print(f"Generaciones restantes: {selected_cp['max_gens'] - selected_cp['gen']}")
            print(f"Best fitness actual: {selected_cp['best_fitness']:.4f}")
            print(f"Población: {selected_cp['pop_size']} mazos")

            # Analizar hardware si es necesario
            if not self.analyze_hardware_if_needed():
                print("\n⚠️  Advertencia: No se pudo analizar el hardware.")
                print("   Usando configuración por defecto.")

            config = self.hardware_analyzer.optimization_config
            remaining_gens = selected_cp['max_gens'] - selected_cp['gen']
            estimated_time = self.hardware_analyzer.estimate_time(selected_cp['pop_size'], remaining_gens)

            print(f"\nCONFIGURACIÓN:")
            print(f"  Workers: {config['max_workers']}")
            print(f"  Timeout base: {config['base_timeout']}s")
            print(f"  Tiempo estimado: {estimated_time}")

            confirm = input("\n¿Continuar desde este checkpoint? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                print("\n❌ Cancelado.")
                input("\nPresiona Enter para continuar...")
                return

            # EJECUTAR CONTINUACIÓN
            print("\n" + "=" * 80)
            print("REANUDANDO EJECUCIÓN DESDE CHECKPOINT")
            print("=" * 80)

            # Preparar archivos de población
            pop_file = os.path.join(self.decks_dir, "initial_population.json")
            if not os.path.exists(pop_file):
                # Intentar con test_population
                pop_file = os.path.join(self.decks_dir, "test_population.json")
                if not os.path.exists(pop_file):
                    print("\n❌ Error: No se encontró archivo de población inicial.")
                    print("   Asegúrate de tener initial_population.json o test_population.json")
                    input("\nPresiona Enter para continuar...")
                    return

            start_time = time.time()

            # Ejecutar algoritmo genético (continuará automáticamente desde checkpoint)
            ga = MTGGeneticAlgorithm(
                population_file=pop_file,
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=selected_cp['max_gens'],
                population_size=selected_cp['pop_size'],
                mutation_rate=0.15,
                crossover_rate=0.9,
                tournament_size=4,
                elite_size=max(2, int(selected_cp['pop_size'] * 0.4)),  # OPTIMIZADO: 40% de población
                stagnation_limit=999,  # Desactivado
                max_workers=config['max_workers'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=False,
                headless_mode=self.headless_mode,
                fitness_alpha=0.6,
                fitness_beta=0.4,
                enable_quality_metrics=True
            )

            print("\n⏳ Ejecutando algoritmo genético (continuación desde checkpoint)...\n")

            best_deck, final_fitness = ga.evolve()

            elapsed = time.time() - start_time

            print("\n" + "=" * 80)
            print("✅ CONTINUACIÓN COMPLETADA")
            print("=" * 80)
            print(f"Tiempo de ejecución: {elapsed / 60:.1f} minutos")
            print(f"Generaciones procesadas: {remaining_gens}")
            print(f"Mejor fitness final: {final_fitness:.4f} ({final_fitness * 100:.1f}% win rate)")
            print(f"Best fitness histórico: {ga.best_fitness_ever:.4f} ({ga.best_fitness_ever * 100:.1f}% win rate)")

            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_continued.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            print(f"\n📁 Mejor mazo guardado en: {best_deck_file}")
            self.print_deck_summary(best_deck)

        except ValueError:
            print("\n❌ Error: Opción no válida.")
        except KeyboardInterrupt:
            print("\n\n⏹️  Ejecución interrumpida por el usuario")
            print("   Los progresos se han guardado automáticamente en checkpoints")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: CONFIGURACIÓN DE FORGE
    # ==============================================================================

    def menu_configurar_forge(self):
        """
        Menú para configurar ruta de Forge JAR
        """
        print("\n" + "=" * 60)
        print("CONFIGURAR FORGE")
        print("=" * 60)

        if self.forge_configured:
            print(f"Forge ya configurado: {self.forge_jar}")
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
        """
        Busca Forge automáticamente en ubicaciones comunes
        """
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
            print("   Usa la opción 2 para especificar la ruta manualmente.")

    def manual_forge_path(self):
        """
        Permite al usuario especificar ruta de Forge manualmente
        """
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
        """
        Muestra información para descargar Forge
        """
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
        except Exception:
            print("No se pudo abrir el navegador automáticamente")

    # ==============================================================================
    # SUBMENÚS: ESTADÍSTICAS
    # ==============================================================================

    def menu_estadisticas(self):
        """
        Muestra estadísticas completas del sistema y ejecuciones previas
        """
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

            # Contar por tipos principales
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
                except Exception:
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

    # ==============================================================================
    # MODOS DE EJECUCIÓN AUTOMÁTICA
    # ==============================================================================

    def ejecucion_completa_optimizada(self):
        """
        Ejecuta pipeline completo: cartas → mazos → algoritmo genético
        """
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

        # Seleccionar tamaño basado en hardware
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

            # Paso 3: Algoritmo genético
            print(f"\n🧬 Paso 3/3: Ejecutando algoritmo genético AUTO-OPTIMIZADO...")
            print(f"   ({generations} generaciones, {config['max_workers']} workers paralelos)")

            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "initial_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=generations,
                population_size=population_size,
                mutation_rate=0.15,              # Incrementado de 0.12 (+25% exploración)
                crossover_rate=0.9,              # Mantener (óptimo demostrado)
                tournament_size=4,               # Incrementado de 3 (+33% presión de selección)
                elite_size=max(2, population_size // 15),
                stagnation_limit=max(5, generations // 4),
                headless_mode=self.headless_mode,
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs'],
                # Parámetros de fitness multi-componente (optimizados)
                fitness_alpha=0.6,               # Reducido de 0.7 (win rate 60%)
                fitness_beta=0.4,                # Incrementado de 0.3 (calidad 40%)
                enable_quality_metrics=True
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
        """
        Modo de prueba rápida con población pequeña
        """
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
            # Paso 1: Cartas
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

            # Paso 3: Algoritmo genético de prueba
            print(f"\n🧬 Ejecutando algoritmo genético de prueba AUTO-OPTIMIZADO...")
            print(f"   ({test_gens} generaciones, {workers} workers paralelos)")

            # Configuración optimizada
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
                ga_config = {
                    'max_workers': 2,
                    'parallel_batch_size': 6,
                    'base_timeout': 300,
                    'log_level': 'INFO',
                    'save_forge_outputs': True
                }

            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "test_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=test_gens,
                population_size=test_size,
                mutation_rate=0.15,              # Incrementado de 0.12 (+25% exploración)
                crossover_rate=0.9,              # Mantener (óptimo demostrado)
                tournament_size=4,               # Incrementado de 3 (+33% presión de selección)
                elite_size=2,                    # Mantener (mínimo estable)
                stagnation_limit=max(2, test_gens // 2),
                headless_mode=self.headless_mode,
                # Parámetros de fitness multi-componente (optimizados)
                fitness_alpha=0.6,               # Reducido de 0.7 (win rate 60%)
                fitness_beta=0.4,                # Incrementado de 0.3 (calidad 40%)
                enable_quality_metrics=True,
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

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Prueba interrumpida por el usuario")
        except Exception as e:
            print(f"\n❌ Error en prueba: {e}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # UTILIDADES
    # ==============================================================================

    def print_deck_summary(self, deck):
        """
        Imprime resumen detallado de un mazo

        Args:
            deck (dict): Diccionario con información completa del mazo
        """
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


# ==================================================================================
# FUNCIÓN PRINCIPAL
# ==================================================================================

def main():
    """
    Función principal del programa - punto de entrada
    """
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
