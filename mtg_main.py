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
import subprocess
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
        print("=== ANALIZANDO HARDWARE DEL SISTEMA ===")
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
        print("   Analizando CPU...")
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

        print("   Analizando memoria...")
        memory = psutil.virtual_memory()
        memory_info = {
            'total_gb': memory.total / (1024**3),
            'available_gb': memory.available / (1024**3),
            'used_gb': memory.used / (1024**3),
            'percentage_used': memory.percent
        }

        print("   Analizando almacenamiento...")
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

        print("    Analizando sistema operativo...")
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

        # === CÁLCULO DE WORKERS ÓPTIMOS (MODO AGRESIVO) ===
        # Estrategia: usar todos los cores lógicos disponibles (incluye SMT/HyperThreading).
        # Forge tiene I/O wait y JVM warmup, beneficia de sobre-suscripción ligera.
        logical = cpu['logical_cores']
        physical = cpu['physical_cores'] or logical
        max_theoretical = logical if logical > physical else physical

        # RAM realista para Forge (~250-300MB típico, no 400 conservador)
        max_by_ram = int(memory['available_gb'] * 1024 / 300)

        # Usar 100% de cores si carga baja, 80% si carga alta (antes 70%)
        if cpu['baseline_usage'] < 60:
            optimal_workers = max_theoretical
        else:
            optimal_workers = max(2, int(max_theoretical * 0.8))

        # Límite práctico absoluto (evita explosiones en servidores extremos)
        optimal_workers = min(
            optimal_workers,
            max_by_ram,     # Limitado por RAM disponible
            64              # Cap absoluto de seguridad (antes 20)
        )
        optimal_workers = max(2, optimal_workers)  # Mínimo 2 workers

        # === CONFIGURACIÓN DE TIMEOUTS ===
        # 600s (10 min) cubre mirrors control-control sin penalizar aggro.
        # El adaptive timeout escala hasta 3x (1800s) si hace falta.
        base_timeout = 600

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
            'parallel_batch_size': optimal_workers * 5,
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
        print(" ANÁLISIS DE HARDWARE COMPLETADO")
        print("=" * 70)

        # Información del sistema operativo
        os_info = self.system_info['os']
        print(f"Sistema: {os_info['platform']} {os_info['release']} ({os_info['architecture']})")

        # Información de CPU
        cpu = self.system_info['cpu']
        print(f"CPU: {cpu['logical_cores']} cores lógicos ({cpu['physical_cores']} físicos)")
        if cpu['max_frequency']:
            print(f"   Frecuencia: {cpu['max_frequency']:.0f} MHz")
        print(f"   Carga actual: {cpu['baseline_usage']:.1f}%")
        print(f"   Capacidad disponible: {cpu['available_capacity']:.1f}%")

        # Información de memoria
        mem = self.system_info['memory']
        print(f"RAM: {mem['total_gb']:.1f} GB total, {mem['available_gb']:.1f} GB disponible ({mem['percentage_used']:.1f}% usado)")

        # Información de almacenamiento
        storage = self.system_info['storage']
        print(f"Almacenamiento: {storage['free_gb']:.1f} GB libres de {storage['total_gb']:.1f} GB")
        if storage['read_speed_mb_s'] > 0:
            print(f"   Velocidad: {storage['read_speed_mb_s']:.0f} MB/s lectura, {storage['write_speed_mb_s']:.0f} MB/s escritura")

        # Perfil de rendimiento
        profile = self.performance_profile
        print(f"\nPERFIL DE RENDIMIENTO:")
        print(f"   CPU: {profile['cpu_tier'].replace('_', ' ').title()}")
        print(f"   RAM: {profile['ram_tier'].replace('_', ' ').title()}")
        print(f"   Storage: {profile['storage_tier'].replace('_', ' ').title()}")
        print(f"   General: {profile['system_tier'].replace('_', ' ').title()} ({profile['overall_score']:.1f}/4.0)")

        # Cuellos de botella
        if profile['bottlenecks']:
            print(f"\n POSIBLES LIMITACIONES:")
            for bottleneck in profile['bottlenecks']:
                print(f"   • {bottleneck}")
        else:
            print(f"\nNo se detectaron limitaciones significativas")

        # Configuración optimizada
        config = self.optimization_config
        print(f"\nCONFIGURACIÓN OPTIMIZADA:")
        print(f"   Workers paralelos: {config['max_workers']}")
        print(f"   Timeout base: {config['base_timeout']} segundos")
        print(f"   Nivel de logging: {config['log_level']}")
        print(f"   Forge outputs: {'Habilitado' if config['save_forge_outputs'] else 'Deshabilitado'}")

        print("=" * 70)

    def estimate_time(self, population, generations, workers=None, use_swiss=True,
                      with_gauntlet=False, gauntlet_size=5):
        """
        Estima tiempo de ejecución del algoritmo genético.

        Calibración basada en datos reales medidos:
          - prueba2 (40 pop x 30 gen, pack-aware, sin gauntlet, 8 workers):
            9920 combates en 67.1 h --> ~195 s/combate por worker.
          - prueba_gauntlet_test (8-15 pop x 4 gen, con gauntlet, 4 workers):
            609 combates en 5.29 h --> ~125 s/combate por worker.
          - Pop más pequeña tiende a dar combates más cortos; las cifras
            se ponderan para reflejar el caso de uso típico (pop>=20).

        Args:
            population (int): Tamaño de población
            generations (int): Número de generaciones
            workers (int, optional): Workers a usar (por defecto usa óptimo)
            use_swiss (bool): Usar Swiss Tournament (True) o round-robin (False)
            with_gauntlet (bool): Si se activa el gauntlet tier-1 (Fase 7).
                Cada candidato juega K partidas BO1 extra contra los anchors.
            gauntlet_size (int): Número de anchors del gauntlet (default 5).

        Returns:
            str: Estimación de tiempo en formato legible (minutos u horas)
        """
        if workers is None:
            workers = self.optimization_config['max_workers']

        # Combates del torneo interno.
        # Una "invocación de combate" = un `forge sim -n 3` = 3 partidas
        # internas con starter aleatorio. n_games_per_match=1 invocación es
        # suficiente: ya cubre BO3 por matchup. No multiplicar más.
        if use_swiss and population >= 20:
            import math
            k_rounds = min(12, max(5, math.ceil(math.log2(population)) + 2))
            n_games_per_match = 1
            enfrentamientos = (population * k_rounds) // 2
            combats_swiss = enfrentamientos * n_games_per_match
        else:
            enfrentamientos = population * (population - 1) // 2
            combats_swiss = enfrentamientos  # 1 invocación = 3 partidas

        # Combates del gauntlet tier-1 (Fase 7): cada candidato vs cada anchor (BO1)
        combats_gauntlet = population * gauntlet_size if with_gauntlet else 0

        combats_per_gen = combats_swiss + combats_gauntlet

        # Segundos por combate por worker — datos reales medidos
        # Base: ~195 s/combate (prueba2). Ajustado por tier.
        if self.performance_profile['system_tier'] == "high_performance":
            base_seconds_per_combat = 160
        elif self.performance_profile['system_tier'] == "balanced":
            base_seconds_per_combat = 195
        elif self.performance_profile['system_tier'] == "conservative":
            base_seconds_per_combat = 240
        else:
            base_seconds_per_combat = 300

        # Tiempo total con paralelización (ya incluye overhead razonable
        # en el 195s base, no añadir multiplicadores artificiales)
        total_seconds = (combats_per_gen * base_seconds_per_combat * generations) / workers
        total_seconds *= 1.05  # 5% overhead para gestión y timeouts ocasionales

        # Formatear salida
        if total_seconds < 3600:
            return f"{total_seconds/60:.0f} minutos"
        elif total_seconds < 86400:
            return f"{total_seconds/3600:.1f} horas"
        else:
            return f"{total_seconds/86400:.1f} días"


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
        self.gauntlet_dir = "gauntlet/tier1"          # Fase 7: anchors tier-1
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
        self.gauntlet_available = False               # Fase 7
        self.gauntlet_n_anchors = 0
        self.gauntlet_anchors = []                    # Lista de dicts con metadata

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
                print(f" Error analizando hardware: {e}")
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

        # Verificar gauntlet tier-1 (Fase 7)
        self.gauntlet_available = False
        self.gauntlet_n_anchors = 0
        self.gauntlet_anchors = []
        if os.path.isdir(self.gauntlet_dir):
            dck_files = sorted(f for f in os.listdir(self.gauntlet_dir) if f.endswith('.dck'))
            if dck_files:
                self.gauntlet_available = True
                self.gauntlet_n_anchors = len(dck_files)
                manifest_path = os.path.join(self.gauntlet_dir, 'manifest.json')
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                        for fname in dck_files:
                            meta = manifest.get(fname, {})
                            self.gauntlet_anchors.append({
                                'file': fname,
                                'name': meta.get('name', fname.removesuffix('.dck')),
                                'archetype': meta.get('archetype', 'unknown'),
                                'colors': meta.get('colors', []),
                            })
                    except Exception:
                        pass

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
        print("       Coevolución de Mazos con Pack-Aware + Gauntlet Tier-1")
        print("                 TFG — José Gascó Bulé (2025-2026)")
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

        # Estado del gauntlet tier-1 (Fase 7) — desactivado por defecto en esta release
        if self.gauntlet_available:
            archs = sorted({a['archetype'] for a in self.gauntlet_anchors}) if self.gauntlet_anchors else []
            arch_summary = ', '.join(archs) if archs else 'metadata no disponible'
            estado = "ACTIVADO" if self.GAUNTLET_ENABLED_BY_DEFAULT else "desactivado por defecto"
            print(f"  Gauntlet: {self.gauntlet_n_anchors} anchors en {self.gauntlet_dir}/ ({arch_summary}) — {estado}")
        else:
            print(f"  Gauntlet: no configurado")

        # Mensaje de preparación
        if self.cards_available and self.population_available and self.forge_configured:
            print(f"  Sistema listo para algoritmo genético optimizado")

        print()

    def show_performance_comparison(self):
        """
        Muestra estimación de aceleración por paralelización vs ejecución serial.
        Cifras basadas en prueba2 (~195 s/combate por worker, run completo).
        """
        if not self.hardware_analyzer:
            return

        config = self.hardware_analyzer.optimization_config
        workers = config['max_workers']

        # Run estándar pop=40 x 30 gen sin gauntlet: 320 combates/gen x 30 gen = 9600
        combats = 320 * 30
        sequential_h = (combats * 195) / 3600
        parallel_h = sequential_h / workers

        print(f"\nCOMPARACIÓN DE RENDIMIENTO (run estándar 40 pop x 30 gen, sin gauntlet):")
        print(f"   Total combates: {combats}")
        print(f"   Ejecución serial:                ~{sequential_h:.0f} horas")
        print(f"   Con paralelización ({workers} workers): ~{parallel_h:.1f} horas")
        print(f"   Aceleración esperada: {workers:.1f}x")

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
            print("  3. Ejecutar algoritmo genético (Pack-Aware + Gauntlet)")
            print("  4. Continuar desde checkpoint guardado")
            print("  5. Configurar Forge")
            print("  6. Analizar hardware del sistema")
            print("  7. Ver estadísticas del sistema")
            print("  8. Ejecución automática completa (pipeline cartas → mazos → algoritmo)")
            print("  9. Modo de prueba rápida")
            print("  10. Configurar modo headless")
            print("  11. Opciones avanzadas")
            print("  0. Salir")

            try:
                choice = input("\nSelecciona una opción (0-11): ").strip()

                if choice == "0":
                    print("\n¡Hasta luego!")
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
                elif choice == "11":
                    self.menu_opciones_avanzadas()
                else:
                    print("\nOpción no válida. Por favor, selecciona un número del 0 al 11.")
                    input("\nPresiona Enter para continuar...")

            except KeyboardInterrupt:
                print("\n\n¡Hasta luego!")
                break
            except Exception as e:
                print(f"\nError inesperado: {e}")
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
            choice = input("\nSelecciona tipo de población (1-6): ").strip()

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
        print(" ANÁLISIS DE HARDWARE")
        print("=" * 60)

        if self.hardware_analyzer:
            print("El hardware ya ha sido analizado.")
            choice = input("¿Realizar nuevo análisis? (s/N): ").strip().lower()
            if choice not in ['s', 'sí', 'si', 'y', 'yes']:
                self.hardware_analyzer.print_analysis()
                input("\nPresiona Enter para continuar...")
                return

        try:
            print("Analizando tu hardware...")
            print("   (Esto tomará 5-10 segundos)")

            self.hardware_analyzer = HardwareAnalyzer()
            self.hardware_analyzer.print_analysis()

            # Mostrar recomendaciones personalizadas
            config = self.hardware_analyzer.optimization_config
            print(f"\nRECOMENDACIONES PARA TU SISTEMA:")
            for name, size in config['recommended_populations'].items():
                estimate = self.hardware_analyzer.estimate_time(size, 10)
                print(f"   {name.title()}: {size} mazos (~{estimate} para 10 generaciones)")

        except Exception as e:
            print(f"Error durante análisis: {e}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # SUBMENÚS: CONFIGURACIÓN HEADLESS
    # ==============================================================================

    def menu_configurar_headless(self):
        """
        Menú para configurar modo headless (sin GUI) para servidores
        """
        print("\n" + "=" * 60)
        print(" CONFIGURAR MODO HEADLESS")
        print("=" * 60)

        print(f"Estado actual: {'Headless' if self.headless_mode else ' GUI disponible'}")

        print("\nEl modo headless es necesario en servidores o máquinas sin interfaz gráfica.")
        print("En modo headless, Forge se ejecuta con 'xvfb-run -a' para simular display.")

        print("\nOPCIONES:")
        print("  1. Auto-detectar (recomendado)")
        print("  2. Forzar modo headless (para servidores)")
        print("  3.  Forzar modo GUI (para escritorio)")
        print("  4. Probar detección actual")
        print("  5. Ver información del entorno")

        try:
            choice = input("\nSelecciona opción (1-5): ").strip()

            if choice == "1":
                print("\nEjecutando auto-detección...")
                old_mode = self.headless_mode
                self.auto_detect_headless()

                if old_mode != self.headless_mode:
                    print(f"   Modo cambiado: {'GUI → Headless' if self.headless_mode else 'Headless → GUI'}")
                else:
                    print(f"   Modo confirmado: {'Headless' if self.headless_mode else 'GUI'}")

                print(f"   Configuración: {'xvfb-run + java' if self.headless_mode else 'java directo'}")

            elif choice == "2":
                self.headless_mode = True
                print("\nModo headless activado manualmente")
                print("   Forge se ejecutará con: xvfb-run -a java -jar forge.jar")

            elif choice == "3":
                self.headless_mode = False
                print("\n Modo GUI activado manualmente")
                print("   Forge se ejecutará con: java -jar forge.jar")

            elif choice == "4":
                print("\nPRUEBA DE DETECCIÓN:")
                print(f"   Variable DISPLAY: {os.environ.get('DISPLAY', 'No definida')}")
                print(f"   SSH_CONNECTION: {os.environ.get('SSH_CONNECTION', 'No definida')}")

                try:
                    import tkinter
                    root = tkinter.Tk()
                    root.withdraw()
                    root.destroy()
                    print("   Tkinter: Disponible")
                except Exception as e:
                    print(f"   Tkinter: Error - {e}")

                print(f"   Modo detectado: {'Headless' if self.headless_mode else 'GUI'}")

            elif choice == "5":
                print("\nINFORMACIÓN DEL ENTORNO:")
                print(f"   Sistema: {platform.system()} {platform.release()}")
                print(f"   Usuario: {os.environ.get('USER', 'desconocido')}")
                print(f"   HOME: {os.environ.get('HOME', 'desconocido')}")
                print(f"   TERM: {os.environ.get('TERM', 'desconocido')}")
                print(f"   SSH_CLIENT: {os.environ.get('SSH_CLIENT', 'No en SSH')}")
                print(f"   SSH_TTY: {os.environ.get('SSH_TTY', 'No en SSH')}")

                # Sugerencia automática
                if os.environ.get('SSH_CONNECTION') or not os.environ.get('DISPLAY'):
                    print("\nSUGERENCIA: Parece que estás en un entorno remoto")
                    print("   Se recomienda usar modo headless (Opción 2)")
                else:
                    print("\nSUGERENCIA: Parece que tienes GUI disponible")
                    print("   Puedes usar modo normal (Opción 3)")

            else:
                print("Opción no válida.")

        except Exception as e:
            print(f"\nError: {e}")

        input("\nPresiona Enter para continuar...")

    def menu_opciones_avanzadas(self):
        """
        Menú de opciones avanzadas: inspección del gauntlet, tests, estimaciones,
        documentación y experimentos.
        """
        while True:
            print("\n" + "=" * 70)
            print("OPCIONES AVANZADAS")
            print("=" * 70)

            print("\nCONFIGURACIÓN POR DEFECTO DEL ALGORITMO:")
            print("  - Swiss Tournament: pop=40, k=8 rondas, n=1 invocación/match (`forge sim -n 3`)")
            print("  - Cada invocación = 3 partidas internas Forge con starter aleatorio")
            print("  - Pack-aware mutación + crossover (norma 4-of)")
            print("  - Fitness multi-componente: α=0.7·win_rate Swiss + β=0.3·deck_quality refinada")
            print("    (quality reponderada a 3 componentes discriminativos: synergy, balance, coherence)")
            if self.gauntlet_available:
                estado = "activado" if self.GAUNTLET_ENABLED_BY_DEFAULT else "DESACTIVADO por defecto"
                print(f"  - Gauntlet tier-1: {self.gauntlet_n_anchors} anchors en disco — {estado}")
                if not self.GAUNTLET_ENABLED_BY_DEFAULT:
                    print("    (Forge AI sesga contra arquetipos complejos — ver Trabajo futuro)")
            else:
                print("  - Gauntlet tier-1: no configurado")
            print("  - Tiempo estimado (pop=40 x 30 gen, 8 workers, datos calibrados):")
            print("    ~68 min/gen sin gauntlet (34 h total) ; ~155 min/gen con gauntlet (77 h total)")

            print("\nOPCIONES:")
            print("  1. Inspeccionar gauntlet tier-1 (anchors cargados)")
            print("  2. Ejecutar tests de validación del algoritmo")
            print("  3. Ver estimaciones de tiempo por configuración")
            print("  4. Ver documentación técnica")
            print("  5. Experimento: punto dulce mutation/crossover (sin gauntlet)")
            print("  0. Volver al menú principal")

            try:
                choice = input("\nSelecciona opción (0-5): ").strip()

                if choice == "0":
                    break

                elif choice == "1":
                    # Inspeccionar gauntlet
                    print("\n" + "=" * 70)
                    print("GAUNTLET TIER-1")
                    print("=" * 70)
                    if not self.gauntlet_available:
                        print("\nGauntlet no configurado.")
                        print(f"Para activarlo, coloca .dck en {self.gauntlet_dir}/")
                        print("y un manifest.json con metadata por anchor.")
                    else:
                        print(f"\nUbicación: {self.gauntlet_dir}/")
                        print(f"Anchors cargados: {self.gauntlet_n_anchors}")
                        print(f"γ(t) lineal: 0.05 (gen 0) → 0.30 (última gen)")
                        print()
                        for i, a in enumerate(self.gauntlet_anchors):
                            colors = '/'.join(a.get('colors', [])) or '—'
                            print(f"  A{i}  {a['name']:<32} [{a['archetype']:<10}] {colors}")
                            print(f"      archivo: {a['file']}")

                elif choice == "2":
                    # Tests de validación
                    print("\nEJECUTANDO TESTS DE VALIDACIÓN...")
                    test_files = ['test_swiss_tournament.py', 'test_gen0_fix.py',
                                  'test_adjust_deck_corregido.py']
                    for tf in test_files:
                        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), tf)
                        if not os.path.exists(path):
                            print(f"  [skip] {tf} no encontrado")
                            continue
                        print(f"\n  Ejecutando {tf}...")
                        try:
                            result = subprocess.run(
                                ['python3', tf],
                                cwd=os.path.dirname(os.path.abspath(__file__)),
                                capture_output=True, text=True, timeout=60
                            )
                            status = "OK" if result.returncode == 0 else "FAIL"
                            print(f"  [{status}] {tf}")
                            if result.returncode != 0:
                                print(result.stderr[-400:] if result.stderr else result.stdout[-400:])
                        except Exception as e:
                            print(f"  [ERROR] {tf}: {e}")

                elif choice == "3":
                    # Estimaciones de tiempo (recalibradas con datos reales)
                    print("\nESTIMACIONES DE TIEMPO")
                    print("Calibradas con prueba2 (~195 s/combate por worker, 8 workers).")
                    print("Con menos workers el tiempo escala aproximadamente lineal.\n")

                    configs = [
                        # (nombre, pop, k_rounds, n_games, gauntlet, gen objetivo)
                        # n_games = invocaciones de Forge por matchup. n=1 ya da BO3 (sim -n 3).
                        ("Prueba rápida (pop=15, sin gauntlet)",   15, 6, 1, False, 3),
                        ("Prueba rápida + gauntlet (pop=15, K=5)", 15, 6, 1, True,  3),
                        ("Run estándar (pop=40, sin gauntlet)",    40, 8, 1, False, 30),
                        ("Run estándar + gauntlet (pop=40, K=5)",  40, 8, 1, True,  30),
                        ("Run grande (pop=40, gen=50, +gauntlet)", 40, 8, 1, True,  50),
                    ]

                    print("┌──────────────────────────────────────────────┬──────────┬─────────┬─────────┐")
                    print("│ Configuración                                │ Cmb/gen  │ Min/gen │ Total   │")
                    print("├──────────────────────────────────────────────┼──────────┼─────────┼─────────┤")

                    # Asumimos sistema 'balanced' (195 s/combate) + 8 workers
                    s_per_combat = 195
                    workers = 8
                    for name, pop, k, n, with_gnt, gens in configs:
                        swiss = (pop * k // 2) * n
                        gnt = pop * 5 if with_gnt else 0
                        cmb = swiss + gnt
                        min_per_gen = (cmb * s_per_combat * 1.05) / workers / 60
                        total_min = min_per_gen * gens
                        if total_min < 60:
                            total_str = f"{total_min:.0f} min"
                        elif total_min < 1440:
                            total_str = f"{total_min/60:.1f} h"
                        else:
                            total_str = f"{total_min/1440:.1f} días"
                        print(f"│ {name:44} │  {cmb:5}   │  {min_per_gen:5.0f}  │ {total_str:>7} │")

                    print("└──────────────────────────────────────────────┴──────────┴─────────┴─────────┘")
                    print("\nFórmula k_rounds Swiss: k = ceil(log₂(pop)) + 2")
                    print("Combates Swiss = (pop · k / 2) · n_games_per_match")
                    print("Combates gauntlet = pop · K_anchors (BO1)")

                elif choice == "4":
                    # Documentación
                    print("\nDOCUMENTACIÓN TÉCNICA")
                    docs = [
                        ("documentacion/AUDITORIA_ALGORITMO_GENETICO.md",
                         "Auditoría completa del algoritmo (Fases 1-6)"),
                        ("documentacion/MAPA_FLUJO_ALGORITMO.md",
                         "Diagramas del flujo evolutivo"),
                        ("documentacion/PLAN_ARQUETIPOS_Y_DECKBUILDING.md",
                         "Diseño de detección de arquetipos y siembra"),
                        ("documentacion/PLAN_MUTACION_PACK_LEVEL.md",
                         "Pack-aware mutation + crossover (Fases 1, 2, 2.5)"),
                        ("documentacion/PLAN_FASE_7_GAUNTLET_TIER1.md",
                         "Plan del gauntlet tier-1 (Fase 7, 14 decisiones)"),
                        ("documentacion/ANALISIS_PRUEBA2_VS_PRUEBANOCTURNA.md",
                         "Análisis comparativo pack-aware vs baseline"),
                    ]
                    print("\nArchivos disponibles:\n")
                    base = os.path.dirname(os.path.abspath(__file__))
                    for filename, desc in docs:
                        path = os.path.join(base, filename)
                        mark = "[OK] " if os.path.exists(path) else "[NO] "
                        print(f"  {mark}{filename}")
                        print(f"        {desc}\n")

                elif choice == "5":
                    # Experimento mutation/crossover (no usa gauntlet)
                    self.experimento_mutation_crossover()

                else:
                    print("\nOpción no válida.")

                if choice != "0":
                    input("\nPresiona Enter para continuar...")

            except KeyboardInterrupt:
                print("\n\nVolviendo...")
                break
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
                input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # HELPERS DEL GAUNTLET TIER-1 (Fase 7)
    # ==============================================================================

    # Flag de activación del gauntlet (Fase 7).
    # Desactivado por defecto: la exploración mostró que el motor Forge presenta
    # un sesgo medible contra arquetipos de jugabilidad compleja (Azorius Omniscience
    # se derrotaba en >70% de los matches), comprometiendo la interpretabilidad de
    # la métrica vs meta. La infraestructura del gauntlet se mantiene en el código
    # como trabajo futuro. Para activarlo en runs experimentales, pon True aquí o
    # pasa gauntlet_path explícitamente al constructor del GA.
    GAUNTLET_ENABLED_BY_DEFAULT = False

    def _gauntlet_kwargs(self):
        """
        Devuelve los kwargs del gauntlet listos para MTGGeneticAlgorithm.

        Por defecto devuelve dict vacío → GA opera sin componente γ
        (fitness = α·swiss + β·calidad, configuración estable de prueba2).
        """
        if not self.GAUNTLET_ENABLED_BY_DEFAULT or not self.gauntlet_available:
            return {}
        return {
            'gauntlet_path': self.gauntlet_dir,
            'gauntlet_gamma_min': 0.05,
            'gauntlet_gamma_max': 0.30,
        }

    def _print_gauntlet_config(self, indent="   "):
        """Imprime el bloque de configuración del gauntlet (o aviso de desactivado)."""
        if not self.GAUNTLET_ENABLED_BY_DEFAULT:
            if self.gauntlet_available:
                print(f"{indent}Gauntlet tier-1: desactivado por defecto ({self.gauntlet_n_anchors} anchors en disco)")
            else:
                print(f"{indent}Gauntlet tier-1: desactivado por defecto")
            return
        if not self.gauntlet_available:
            print(f"{indent}Gauntlet tier-1: no configurado (γ_t = 0, sin presión externa)")
            return
        print(f"{indent}Gauntlet tier-1: {self.gauntlet_n_anchors} anchors fijos durante el run")
        print(f"{indent}   γ(t) lineal: 0.05 (gen 0) → 0.30 (última gen)")
        for i, a in enumerate(self.gauntlet_anchors):
            colors = '/'.join(a.get('colors', [])) or '—'
            print(f"{indent}   A{i}  {a['name']:<32} [{a['archetype']:<10}] {colors}")

    def _print_gauntlet_report(self, ga, indent="   "):
        """Imprime el reporte final del gauntlet (winrates de la última gen)."""
        if not self.gauntlet_available:
            return
        wr = getattr(ga, 'last_gauntlet_winrates', None)
        if not wr:
            print(f"\n{indent}Gauntlet tier-1: sin datos finales (gauntlet desactivado o run interrumpido antes de gen 0)")
            return
        n_anch = len(getattr(ga, 'gauntlet_decks', [])) or self.gauntlet_n_anchors
        avg = sum(wr) / len(wr)
        zeros = sum(1 for w in wr if w == 0.0)
        perfect = sum(1 for w in wr if w == 1.0)
        best = max(wr)
        gamma = getattr(ga, 'last_gauntlet_gamma', 0.0)
        print(f"\n{indent}GAUNTLET TIER-1 (última generación, γ_t = {gamma:.3f}):")
        print(f"{indent}   Win-rate medio población vs gauntlet: {avg:.3f}")
        print(f"{indent}   Mejor candidato: {best:.2f}  ({int(round(best * n_anch))}/{n_anch} anchors derrotados)")
        print(f"{indent}   Distribución: {zeros} con 0/{n_anch}, {perfect} con {n_anch}/{n_anch}, "
              f"resto {len(wr) - zeros - perfect}")

    # ==============================================================================
    # SUBMENÚS: ALGORITMO GENÉTICO
    # ==============================================================================

    def menu_algoritmo_genetico_optimizado(self):
        """
        Menú principal para ejecutar algoritmo genético auto-optimizado
        """
        print("\n" + "=" * 60)
        print("ALGORITMO GENÉTICO (Pack-Aware + Gauntlet Tier-1)")
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

        if os.path.exists(pop_file):
            with open(pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            available_pop_size = len(population)
            population_file = pop_file
            pop_type = "Completa"
        elif os.path.exists(test_pop_file):
            with open(test_pop_file, 'r', encoding='utf-8') as f:
                population = json.load(f)
            available_pop_size = len(population)
            population_file = test_pop_file
            pop_type = "Prueba"
        else:
            print("Error: No se encontró población de mazos.")
            return

        # ELEGIR TAMAÑO DE POBLACIÓN: mazos generados o 40 por defecto
        print(f"\nCONFIGURACIÓN DE POBLACIÓN:")
        print(f"  Mazos generados: {available_pop_size}")
        print(f"  Recomendado Swiss Tournament: 40 mazos")

        usar_generados = input(f"\n¿Usar los {available_pop_size} mazos generados? (S/n, 'n' generará 40 nuevos mazos): ").strip().lower()

        if usar_generados in ['s', 'sí', 'si', 'y', 'yes', '']:
            # Usar todos los mazos generados
            pop_size = available_pop_size
            print(f"Usando los {pop_size} mazos generados")
        else:
            # Generar 40 mazos nuevos (Swiss Tournament óptimo)
            pop_size = 40
            print(f"Generando {pop_size} mazos nuevos para Swiss Tournament...")

            from generador_mazos_mtg import MTGDeckGenerator
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(pop_size)
            population_file = os.path.join(self.decks_dir, "initial_population.json")
            pop_type = "Completa"
            print(f"{pop_size} mazos nuevos generados")

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
            estimate = self.hardware_analyzer.estimate_time(
                pop_size, gens, with_gauntlet=(self.GAUNTLET_ENABLED_BY_DEFAULT and self.gauntlet_available),
                gauntlet_size=self.gauntlet_n_anchors or 5,
            )
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

            # Calcular parámetros optimizados dinámicamente
            elite_size = max(2, int(pop_size * 0.225))  # Fase 4: 22.5% (antes 30%)
            tournament_size = max(3, int(pop_size * 0.125))  # ~12% de población

            # Parámetros Swiss Tournament (por defecto activado)
            import math
            use_swiss = True
            k_rounds = min(12, max(5, math.ceil(math.log2(pop_size)) + 2))  # Fórmula óptima
            n_games_per_match = 1   # 1 invocación de Forge = `sim -n 3` = 3 partidas internas

            # Calcular enfrentamientos para estimación de tiempo
            if use_swiss:
                enfrentamientos = (pop_size * k_rounds) // 2
                combates_totales = enfrentamientos * n_games_per_match
            else:
                enfrentamientos = (pop_size * (pop_size - 1)) // 2
                combates_totales = enfrentamientos * 3

            estimated_time = self.hardware_analyzer.estimate_time(
                pop_size, max_gens, with_gauntlet=(self.GAUNTLET_ENABLED_BY_DEFAULT and self.gauntlet_available),
                gauntlet_size=self.gauntlet_n_anchors or 5,
            )

            print(f"\nCONFIGURACIÓN FINAL OPTIMIZADA:")
            print(f"  Nombre: {config_name}")
            print(f"  Población: {pop_size} mazos")
            print(f"  Generaciones máximas: {max_gens}")
            print(f"  Elite preservada: {elite_size} ({int(elite_size/pop_size*100)}%)")
            print(f"  Tournament selection: {tournament_size} mazos ({int(tournament_size/pop_size*100)}%)")
            print(f"  ")
            print(f"  Swiss Tournament: {'Activado' if use_swiss else 'Desactivado'}")
            if use_swiss:
                print(f"     - k_rounds: {k_rounds} (cada mazo juega {k_rounds} partidas)")
                print(f"     - n_games_per_match: {n_games_per_match}")
                print(f"     - Enfrentamientos: {enfrentamientos}")
                print(f"     - Combates totales: {combates_totales}")
                full_rr = (pop_size * (pop_size - 1) // 2) * 3
                reduction = ((full_rr - combates_totales) / full_rr) * 100
                print(f"     - Reducción vs round-robin: {reduction:.1f}%")
            print(f"  ")
            print(f"  Workers paralelos: {config['max_workers']}")
            print(f"  Timeout base: {config['base_timeout']}s")
            print(f"  Tiempo estimado: {estimated_time}")
            print(f"  ")
            self._print_gauntlet_config(indent="  ")

            if "horas" in estimated_time and float(estimated_time.split()[0]) > 8:
                print(f"\nAdvertencia: Esta ejecución es muy larga ({estimated_time})")
                print("Considera usar una configuración más pequeña primero.")

            confirm = input("\n¿Iniciar algoritmo genético Swiss Tournament? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                return

            print(f"\nIniciando algoritmo genético Swiss Tournament...")
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
                mutation_rate=0.6,
                crossover_rate=0.30,
                tournament_size=tournament_size,     # Calculado dinámicamente (~12% de pop)
                elite_size=elite_size,               # Calculado dinámicamente (22.5% de pop — Fase 4)
                # Parámetros Swiss Tournament
                use_swiss_tournament=use_swiss,
                k_rounds=k_rounds,
                n_games_per_match=n_games_per_match,
                # Parámetros de paralelización optimizados
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs'],
                headless_mode=self.headless_mode,
                # Parámetros de fitness multi-componente
                fitness_alpha=0.7,               # win_rate Swiss = 70% del fitness
                fitness_beta=0.3,                # deck_quality refinada = 30% del fitness
                enable_quality_metrics=True,
                # Gauntlet tier-1 (Fase 7) — vacío si no hay anchors
                **self._gauntlet_kwargs(),
            )

            best_deck = ga.evolve()

            elapsed = time.time() - start_time
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60

            print(f"\nAlgoritmo genético Swiss Tournament completado exitosamente")
            print(f"Tiempo de ejecución: {int(hours)}h {int(minutes)}m")
            print(f"Mejor fitness alcanzado: {ga.best_fitness_ever:.4f}")
            print(f"Modo: Swiss Tournament (k={k_rounds}, n={n_games_per_match})")
            print(f"Workers utilizados: {config['max_workers']}")
            self._print_gauntlet_report(ga, indent="   ")

            # Guardar mejor mazo
            suffix = "_test_parallel" if pop_type == "Prueba" else "_final_parallel"
            best_deck_file = os.path.join(self.evolved_dir, f"best_deck{suffix}.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            print(f"   Mejor mazo guardado en: {best_deck_file}")
            self.print_deck_summary(best_deck, ga=ga)

        except KeyboardInterrupt:
            print(f"\n\n Ejecución interrumpida por el usuario")
            print("   Los progresos se han guardado automáticamente")
        except Exception as e:
            print(f"\nError: {e}")

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
            print("\nNo se encontró directorio de checkpoints.")
            print(f"   Ruta buscada: {checkpoint_dir}")
            input("\nPresiona Enter para continuar...")
            return

        # Listar todos los checkpoints
        import glob
        checkpoint_files = sorted(glob.glob(os.path.join(checkpoint_dir, "checkpoint_gen_*.json")))

        if not checkpoint_files:
            print("\nNo se encontraron checkpoints guardados.")
            print(f"   Directorio verificado: {checkpoint_dir}")
            input("\nPresiona Enter para continuar...")
            return

        # Mostrar checkpoints disponibles
        print(f"\nCHECKPOINTS DISPONIBLES ({len(checkpoint_files)} encontrados):")
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

                checkpoints_info.append({
                    'file': cp_file,
                    'gen': gen,
                    'timestamp': timestamp,
                    'best_fitness': best_fitness,
                    'pop_size': pop_size,
                    'max_gens': max_gens,
                    'mut_rate': mut_rate,
                    'data': data
                })
            except Exception as e:
                print(f" Error leyendo {os.path.basename(cp_file)}: {e}")

        if not checkpoints_info:
            print("\nNo se pudieron leer los checkpoints.")
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
            print(f"   Fecha: {date} {time_str}")
            print(f"   Best fitness: {cp_info['best_fitness']:.4f} ({cp_info['best_fitness']*100:.1f}% win rate)")
            print(f"   Población: {cp_info['pop_size']} mazos")
            print(f"   Progreso: {gen}/{cp_info['max_gens']} generaciones ({gen*100//cp_info['max_gens']}%)")
            print(f"   Mutación: {cp_info['mut_rate']:.3f}")

        # Seleccionar checkpoint
        print("\n" + "=" * 80)
        print("Selecciona el checkpoint desde el cual continuar:")

        try:
            choice = input(f"\nOpción (1-{len(checkpoints_info)}) o 0 para cancelar: ").strip()

            if choice == "0":
                print("\nCancelado.")
                input("\nPresiona Enter para continuar...")
                return

            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(checkpoints_info):
                print("\nOpción no válida.")
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
                print("\n Advertencia: No se pudo analizar el hardware.")
                print("   Usando configuración por defecto.")

            config = self.hardware_analyzer.optimization_config
            remaining_gens = selected_cp['max_gens'] - selected_cp['gen']
            estimated_time = self.hardware_analyzer.estimate_time(
                selected_cp['pop_size'], remaining_gens,
                with_gauntlet=(self.GAUNTLET_ENABLED_BY_DEFAULT and self.gauntlet_available),
                gauntlet_size=self.gauntlet_n_anchors or 5,
            )

            print(f"\nCONFIGURACIÓN:")
            print(f"  Workers: {config['max_workers']}")
            print(f"  Timeout base: {config['base_timeout']}s")
            print(f"  Tiempo estimado: {estimated_time}")

            confirm = input("\n¿Continuar desde este checkpoint? (S/n): ").strip().lower()
            if confirm in ['n', 'no']:
                print("\nCancelado.")
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
                    print("\nError: No se encontró archivo de población inicial.")
                    print("   Asegúrate de tener initial_population.json o test_population.json")
                    input("\nPresiona Enter para continuar...")
                    return

            start_time = time.time()

            # Calcular parámetros dinámicamente (por si el checkpoint es antiguo)
            import math
            pop_size = selected_cp['pop_size']
            elite_size = max(2, int(pop_size * 0.225))  # Fase 4: 22.5%
            tournament_size = max(3, int(pop_size * 0.125))

            # Parámetros Swiss (el checkpoint puede sobrescribirlos si los tiene guardados)
            use_swiss = True
            k_rounds = min(12, max(5, math.ceil(math.log2(pop_size)) + 2))
            n_games_per_match = 1   # 1 invocación de Forge = `sim -n 3` = 3 partidas internas

            # Ejecutar algoritmo genético (continuará automáticamente desde checkpoint)
            # NOTA: Los parámetros del checkpoint (si existen) sobrescribirán estos valores
            ga = MTGGeneticAlgorithm(
                population_file=pop_file,
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=selected_cp['max_gens'],
                population_size=pop_size,
                mutation_rate=0.6,
                crossover_rate=0.30,
                tournament_size=tournament_size,     # Calculado dinámicamente
                elite_size=elite_size,               # Calculado dinámicamente
                # Swiss Tournament (checkpoint puede sobrescribir)
                use_swiss_tournament=use_swiss,
                k_rounds=k_rounds,
                n_games_per_match=n_games_per_match,
                # Gauntlet tier-1 (Fase 7) — se recarga aunque sea un resume
                **self._gauntlet_kwargs(),
                # Paralelización
                max_workers=config['max_workers'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=False,
                headless_mode=self.headless_mode,
                # Fitness
                fitness_alpha=0.7,
                fitness_beta=0.3,
                enable_quality_metrics=True
            )

            print("\nEjecutando algoritmo genético (continuación desde checkpoint)...\n")

            best_deck, final_fitness = ga.evolve()

            elapsed = time.time() - start_time

            print("\n" + "=" * 80)
            print("CONTINUACIÓN COMPLETADA")
            print("=" * 80)
            print(f"Tiempo de ejecución: {elapsed / 60:.1f} minutos")
            print(f"Generaciones procesadas: {remaining_gens}")
            print(f"Mejor fitness final: {final_fitness:.4f} ({final_fitness * 100:.1f}% win rate)")
            print(f"Best fitness histórico: {ga.best_fitness_ever:.4f} ({ga.best_fitness_ever * 100:.1f}% win rate)")
            self._print_gauntlet_report(ga, indent="")

            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_continued.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            print(f"\nMejor mazo guardado en: {best_deck_file}")
            self.print_deck_summary(best_deck, ga=ga)

        except ValueError:
            print("\nError: Opción no válida.")
        except KeyboardInterrupt:
            print("\n\n Ejecución interrumpida por el usuario")
            print("   Los progresos se han guardado automáticamente en checkpoints")
        except Exception as e:
            print(f"\nError: {e}")
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

        print("\nBUSCAR FORGE:")
        print("  1. Buscar automáticamente")
        print("  2. Especificar ruta manualmente")
        print("  3. Descargar Forge (abre navegador)")

        try:
            choice = input("\nSelecciona opción (1-3): ").strip()

            if choice == "1":
                self.auto_find_forge()
            elif choice == "2":
                self.manual_forge_path()
            elif choice == "3":
                self.download_forge_info()
            else:
                print("Opción no válida.")

        except Exception as e:
            print(f"\nError: {e}")

        input("\nPresiona Enter para continuar...")

    def auto_find_forge(self):
        """
        Busca Forge automáticamente en ubicaciones comunes
        """
        print("\nBuscando Forge...")

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
            print(f"Forge encontrado: {self.forge_jar}")

            if len(found_files) > 1:
                print(f"   También se encontraron:")
                for other_file in found_files[1:]:
                    print(f"     - {other_file}")
                print(f"   Usando la versión: {os.path.basename(self.forge_jar)}")
        else:
            print("Forge no encontrado automáticamente.")
            print("   Usa la opción 2 para especificar la ruta manualmente.")

    def manual_forge_path(self):
        """
        Permite al usuario especificar ruta de Forge manualmente
        """
        print("\nEspecifica la ruta completa al archivo forge-gui-desktop.jar:")
        path = input("Ruta: ").strip().strip('"\'')

        if not path:
            print("No se especificó ruta.")
            return

        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
            self.forge_jar = expanded_path
            self.forge_configured = True
            print(f"Forge configurado: {expanded_path}")
        else:
            print(f"Archivo no encontrado: {expanded_path}")

    def download_forge_info(self):
        """
        Muestra información para descargar Forge
        """
        print("\nDESCARGAR FORGE:")
        print("   1. Ve a: https://www.slightlymagic.net/forum/viewforum.php?f=26")
        print("   2. Descarga: forge-gui-desktop-X.X.XX-jar-with-dependencies.jar")
        print("   3. Colócalo en la carpeta del proyecto")
        print("   4. Usa la opción 1 para detectarlo automáticamente")

        try:
            import webbrowser
            choice = input("\n¿Abrir página de descarga en el navegador? (S/n): ").strip().lower()
            if choice not in ['n', 'no']:
                webbrowser.open("https://www.slightlymagic.net/forum/viewforum.php?f=26")
                print("Página abierta en el navegador")
        except Exception:
            print("No se pudo abrir el navegador automáticamente")

    # ==============================================================================
    # SUBMENÚS: ESTADÍSTICAS
    # ==============================================================================

    def menu_estadisticas(self):
        """
        Muestra estadísticas completas del sistema y ejecuciones previas
        """
        print("\n" + "=" * 70)
        print("ESTADÍSTICAS DEL SISTEMA")
        print("=" * 70)

        # === 1. CARTAS ===
        if self.cards_available:
            catalog_file = os.path.join(self.data_dir, "card_catalog.json")
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            print(f"\nCARTAS:")
            print(f"   Total: {len(catalog):,}")
            lands = sum(1 for c in catalog.values() if c['is_land'])
            creatures = sum(1 for c in catalog.values() if c['is_creature'])
            spells = sum(1 for c in catalog.values() if c['is_instant'] or c['is_sorcery'])
            print(f"   Tierras: {lands:,}")
            print(f"   Criaturas: {creatures:,}")
            print(f"   Hechizos: {spells:,}")
            print(f"   Otros: {len(catalog) - lands - creatures - spells:,}")
        else:
            print("\nCARTAS: no descargadas (opción 1 del menú)")

        # === 2. POBLACIONES INICIALES ===
        if self.population_available:
            print(f"\nPOBLACIONES INICIALES:")
            for label, fname in [("Completa", "initial_population.json"),
                                  ("Prueba", "test_population.json")]:
                path = os.path.join(self.decks_dir, fname)
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        pop = json.load(f)
                    print(f"   {label}: {len(pop)} mazos ({fname})")
        else:
            print("\nPOBLACIONES: ninguna generada (opción 2 del menú)")

        # === 3. GAUNTLET TIER-1 ===
        if self.gauntlet_available:
            print(f"\nGAUNTLET TIER-1 (Fase 7):")
            print(f"   Ubicación: {self.gauntlet_dir}/")
            print(f"   Anchors: {self.gauntlet_n_anchors}")
            for i, a in enumerate(self.gauntlet_anchors):
                colors = '/'.join(a.get('colors', [])) or '—'
                print(f"     A{i}  {a['name']} [{a['archetype']}, {colors}]")
        else:
            print(f"\nGAUNTLET TIER-1: no configurado (γ_t = 0)")

        # === 4. ÚLTIMO RUN — CSV de evolución ===
        evolution_stats = os.path.join(self.evolved_dir, "parallel_evolution_stats.csv")
        if os.path.exists(evolution_stats):
            try:
                import pandas as pd
                df = pd.read_csv(evolution_stats)
                if not df.empty:
                    print(f"\nÚLTIMO RUN ({self.evolved_dir}/):")
                    print(f"   Generaciones registradas: {len(df)}")
                    print(f"   Mejor fitness alcanzado:  {df['best_fitness'].max():.4f}")
                    print(f"   Fitness avg gen 0:        {df['avg_fitness'].iloc[0]:.4f}")
                    print(f"   Fitness avg final:        {df['avg_fitness'].iloc[-1]:.4f}")
                    if 'archetype_entropy' in df.columns:
                        print(f"   Entropía arq. gen 0:      {df['archetype_entropy'].iloc[0]:.3f}")
                        print(f"   Entropía arq. final:      {df['archetype_entropy'].iloc[-1]:.3f}")
            except Exception as e:
                print(f"\nÚLTIMO RUN: error leyendo CSV ({e})")
        else:
            print(f"\nÚLTIMO RUN: sin datos en {self.evolved_dir}/")

        # === 5. HALL OF FAME del último run ===
        hof_dir = os.path.join(self.evolved_dir, "hall_of_fame")
        if os.path.isdir(hof_dir):
            json_files = sorted(f for f in os.listdir(hof_dir) if f.endswith('.json'))
            if json_files:
                print(f"\nHALL OF FAME del último run ({len(json_files)} mazos):")
                for fname in json_files:
                    try:
                        with open(os.path.join(hof_dir, fname)) as f:
                            entry = json.load(f)
                        fit = entry.get('fitness', 0)
                        arch = entry.get('archetype', '?')
                        deck = entry.get('deck', {})
                        colors = '/'.join(deck.get('colors') or []) if isinstance(deck, dict) else '—'
                        name = fname.removesuffix('.json')
                        print(f"   fit={fit:.4f}  {name:<28} [{arch:<10}] {colors}")
                    except Exception:
                        pass

        # === 6. HARDWARE ===
        if self.hardware_analyzer:
            config = self.hardware_analyzer.optimization_config
            profile = self.hardware_analyzer.performance_profile
            print(f"\nHARDWARE ANALIZADO:")
            print(f"   Perfil: {profile['system_tier'].replace('_', ' ').title()}")
            print(f"   Workers óptimos: {config['max_workers']}")
            print(f"   Timeout base: {config['base_timeout']} s")
        else:
            print(f"\nHARDWARE: no analizado todavía (opción 6 del menú)")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # MODOS DE EJECUCIÓN AUTOMÁTICA
    # ==============================================================================

    def ejecucion_completa_optimizada(self):
        """
        Ejecuta pipeline completo: cartas → mazos → algoritmo genético
        """
        print("\n" + "=" * 60)
        print("EJECUCIÓN AUTOMÁTICA COMPLETA — pipeline cartas → mazos → algoritmo")
        print("=" * 60)

        if not self.forge_configured:
            print("\nForge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return

        # Analizar hardware automáticamente
        if not self.analyze_hardware_if_needed():
            print("No se pudo analizar el hardware.")
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

        estimated_time = self.hardware_analyzer.estimate_time(
            population_size, generations, use_swiss=True,
            with_gauntlet=(self.GAUNTLET_ENABLED_BY_DEFAULT and self.gauntlet_available),
            gauntlet_size=self.gauntlet_n_anchors or 5,
        )

        # Calcular detalles Swiss
        import math
        k_rounds = min(12, max(5, math.ceil(math.log2(population_size)) + 2))
        enfrentamientos = (population_size * k_rounds) // 2
        combates_totales = enfrentamientos * 2

        print("Esta opción ejecutará todo el proceso con SWISS TOURNAMENT:")
        print("  1. Obtener cartas de Standard (si no están disponibles)")
        print(f"  2. Generar población de {population_size} mazos aleatorios")
        print(f"  3. Ejecutar algoritmo genético Swiss Tournament:")
        print(f"     - {generations} generaciones")
        print(f"     - {k_rounds} rondas Swiss por generación")
        print(f"     - {combates_totales} combates por generación")
        print(f"     - {config['max_workers']} workers paralelos")
        print(f"\n  Tiempo estimado total: {estimated_time}")
        print(f"  Sistema: {profile['system_tier'].replace('_', ' ').title()}")
        print(f"  Swiss Tournament: Activado (k={k_rounds}, n=1 invocación = 3 partidas internas)")
        self._print_gauntlet_config(indent="  ")

        confirm = input("\n¿Ejecutar proceso completo AUTO-OPTIMIZADO? (s/N): ").strip().lower()
        if confirm not in ['s', 'sí', 'si', 'y', 'yes']:
            return

        total_start = time.time()

        try:
            # Paso 1: Cartas
            if not self.cards_available:
                print("\nPaso 1/3: Obteniendo cartas...")
                scraper = MTGCardScraper(output_dir=self.data_dir, exclude_latest_set=True)
                scraper.run()
                self.check_system_status()

            # Paso 2: Mazos
            print(f"\nPaso 2/3: Generando {population_size} mazos...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(population_size)
            self.check_system_status()

            # Paso 3: Algoritmo genético
            print(f"\nPaso 3/3: Ejecutando algoritmo genético AUTO-OPTIMIZADO...")
            print(f"   ({generations} generaciones, {config['max_workers']} workers paralelos)")

            # Calcular parámetros dinámicamente
            import math
            elite_size = max(2, int(population_size * 0.225))  # Fase 4: 22.5%
            tournament_size = max(3, int(population_size * 0.125))
            use_swiss = True
            k_rounds = min(12, max(5, math.ceil(math.log2(population_size)) + 2))
            n_games_per_match = 1   # 1 invocación de Forge = `sim -n 3` = 3 partidas internas

            print(f"\nCONFIGURACIÓN:")
            print(f"   Población: {population_size} mazos")
            print(f"   Elite: {elite_size} ({int(elite_size/population_size*100)}%)")
            print(f"   Tournament: {tournament_size} mazos")
            print(f"   Swiss: (k={k_rounds}, n={n_games_per_match})")

            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "initial_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=generations,
                population_size=population_size,
                mutation_rate=0.6,
                crossover_rate=0.30,
                tournament_size=tournament_size,     # Calculado dinámicamente
                elite_size=elite_size,               # Calculado dinámicamente
                # Swiss Tournament
                use_swiss_tournament=use_swiss,
                k_rounds=k_rounds,
                n_games_per_match=n_games_per_match,
                # Parámetros de paralelización
                max_workers=config['max_workers'],
                parallel_batch_size=config['parallel_batch_size'],
                base_timeout=config['base_timeout'],
                log_level=config['log_level'],
                save_forge_outputs=config['save_forge_outputs'],
                headless_mode=self.headless_mode,
                # Parámetros de fitness multi-componente
                fitness_alpha=0.7,
                fitness_beta=0.3,
                enable_quality_metrics=True,
                # Gauntlet tier-1 (Fase 7) — vacío si no hay anchors
                **self._gauntlet_kwargs(),
            )

            best_deck = ga.evolve()

            total_elapsed = time.time() - total_start
            hours = total_elapsed // 3600
            minutes = (total_elapsed % 3600) // 60

            print(f"\nEJECUCIÓN COMPLETA FINALIZADA")
            print(f"   Tiempo total: {int(hours)}h {int(minutes)}m")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            print(f"   Modo: Swiss Tournament (k={k_rounds}, n={n_games_per_match})")
            print(f"   Workers utilizados: {config['max_workers']}")
            self._print_gauntlet_report(ga, indent="   ")

            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_complete_parallel.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            self.print_deck_summary(best_deck, ga=ga)

        except KeyboardInterrupt:
            print(f"\n\n  Ejecución interrumpida por el usuario")
        except Exception as e:
            print(f"\nError en ejecución completa: {e}")

        input("\nPresiona Enter para continuar...")

    def modo_prueba_optimizado(self):
        """
        Modo de prueba rápida con población pequeña
        """
        print("\n" + "=" * 60)
        print("MODO DE PRUEBA RÁPIDA")
        print("=" * 60)

        if not self.forge_configured:
            print("\nForge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return

        # Analizar hardware automáticamente
        if not self.analyze_hardware_if_needed():
            print("No se pudo analizar el hardware. Usando configuración por defecto.")
            test_size = 8
            test_gens = 3
            workers = 2
            # Fallback sin hardware analyzer: estimación conservadora basada en
            # prueba_gauntlet_test (pop=15 + gauntlet, ~85 min/gen con 4 workers).
            # Sin gauntlet y pop=8, ~30-50 min/gen con 2 workers. 3 gens ~ 1.5-3 h.
            estimated_time = "1.5 - 3 horas"
        else:
            config = self.hardware_analyzer.optimization_config
            test_size = config['recommended_populations']['test']
            test_gens = config['recommended_generations']['quick']
            workers = config['max_workers']
            estimated_time = self.hardware_analyzer.estimate_time(
                test_size, test_gens,
                with_gauntlet=(self.GAUNTLET_ENABLED_BY_DEFAULT and self.gauntlet_available),
                gauntlet_size=self.gauntlet_n_anchors or 5,
            )

        # Calcular configuración Swiss para la información
        import math
        use_swiss_info = test_size >= 20
        if use_swiss_info:
            k_rounds_info = min(12, max(5, math.ceil(math.log2(test_size)) + 2))
            n_games_info = 1   # 1 invocación de Forge = `sim -n 3` = 3 partidas internas
            enfrentamientos_info = (test_size * k_rounds_info) // 2
            combates_info = enfrentamientos_info * n_games_info
            mode_info = f"Swiss Tournament (k={k_rounds_info}, n={n_games_info})"
        else:
            enfrentamientos_info = test_size * (test_size - 1) // 2
            combates_info = enfrentamientos_info * 3
            mode_info = f"Round-Robin completo (población pequeña)"

        print("Esta opción ejecutará una prueba rápida:")
        print("  1. Usar cartas existentes de Standard o descargar si es necesario")
        print(f"  2. Generar población de {test_size} mazos")
        print(f"  3. Ejecutar algoritmo genético por {test_gens} generaciones")
        print(f"     - Modo: {mode_info}")
        print(f"     - Combates por generación: {combates_info}")
        print(f"  4. Usar {workers} workers paralelos")
        print(f"\n Tiempo estimado total: {estimated_time}")

        confirm = input("\n¿Ejecutar prueba rápida? (S/n): ").strip().lower()
        if confirm in ['n', 'no']:
            return

        test_start = time.time()

        try:
            # Paso 1: Cartas
            if not self.cards_available:
                print("\nObteniendo cartas...")
                scraper = MTGCardScraper(output_dir=self.data_dir, exclude_latest_set=True)
                scraper.run()
                self.check_system_status()

            # Paso 2: Mazos de prueba
            print(f"\nGenerando {test_size} mazos de prueba...")
            generator = MTGDeckGenerator(
                cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.decks_dir
            )
            population = generator.generate_population_exact_size(test_size)
            self.check_system_status()

            # Paso 3: Algoritmo genético de prueba
            print(f"\nEjecutando algoritmo genético de prueba...")
            print(f"   ({test_gens} generaciones, {workers} workers paralelos)")

            # Calcular parámetros dinámicamente
            import math
            elite_size = max(2, int(test_size * 0.225))  # Fase 4: 22.5%
            tournament_size = max(3, int(test_size * 0.125))
            use_swiss = test_size >= 20  # Solo Swiss si pop >= 20
            k_rounds = min(12, max(5, math.ceil(math.log2(test_size)) + 2)) if use_swiss else test_size - 1
            n_games_per_match = 1 if use_swiss else 3   # Swiss: 1 invocación = 3 partidas internas

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
                    'base_timeout': 600,
                    'log_level': 'INFO',
                    'save_forge_outputs': True
                }

            print(f"\nCONFIGURACIÓN:")
            print(f"   Población: {test_size} mazos")
            print(f"   Elite: {elite_size} ({int(elite_size/test_size*100)}%)")
            print(f"   Tournament: {tournament_size} mazos")
            print(f"   Swiss: {'activado' if use_swiss else 'desactivado'} (k={k_rounds}, n={n_games_per_match})")
            self._print_gauntlet_config(indent="   ")

            ga = MTGGeneticAlgorithm(
                population_file=os.path.join(self.decks_dir, "test_population.json"),
                catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                indices_path=os.path.join(self.data_dir, "card_indices.json"),
                output_dir=self.evolved_dir,
                forge_jar_path=self.forge_jar,
                max_generations=test_gens,
                population_size=test_size,
                mutation_rate=0.6,
                crossover_rate=0.30,
                tournament_size=tournament_size,     # Calculado dinámicamente
                elite_size=elite_size,               # Calculado dinámicamente
                # Swiss Tournament
                use_swiss_tournament=use_swiss,
                k_rounds=k_rounds,
                n_games_per_match=n_games_per_match,
                # Parámetros de fitness multi-componente
                fitness_alpha=0.7,
                fitness_beta=0.3,
                enable_quality_metrics=True,
                headless_mode=self.headless_mode,
                # Gauntlet tier-1 (Fase 7) — vacío si no hay anchors
                **self._gauntlet_kwargs(),
                **ga_config
            )

            best_deck = ga.evolve()

            test_elapsed = time.time() - test_start
            minutes = test_elapsed // 60
            seconds = test_elapsed % 60

            print(f"\nPRUEBA COMPLETADA")
            print(f"   Tiempo total: {int(minutes)}m {int(seconds)}s")
            print(f"   Mejor fitness: {ga.best_fitness_ever:.4f}")
            print(f"   Modo: {'Swiss Tournament' if use_swiss else 'Round-Robin'}")
            print(f"   Workers utilizados: {workers}")
            self._print_gauntlet_report(ga, indent="   ")

            # Guardar mejor mazo
            best_deck_file = os.path.join(self.evolved_dir, "best_deck_test_parallel.json")
            with open(best_deck_file, 'w', encoding='utf-8') as f:
                json.dump(best_deck, f, ensure_ascii=False, indent=2)

            self.print_deck_summary(best_deck, ga=ga)

            print(f"\nSi la prueba funcionó correctamente, puedes ejecutar")
            print(f"   la versión completa con la opción 8 del menú principal.")

        except KeyboardInterrupt:
            print(f"\n\n  Prueba interrumpida por el usuario")
        except Exception as e:
            print(f"\nError en prueba: {e}")

        input("\nPresiona Enter para continuar...")

    def experimento_mutation_crossover(self):
        """
        Experimento para encontrar el punto dulce de mutation_rate y crossover_rate
        Prioriza configuraciones con alta mutación
        """
        print("\n" + "=" * 70)
        print("EXPERIMENTO: PUNTO DULCE MUTATION/CROSSOVER")
        print("=" * 70)

        print("\nOBJETIVO:")
        print("  Encontrar la mejor combinación de mutation_rate y crossover_rate")
        print("  priorizando alta mutación (ya que el cruce destruye combinaciones)")
        print()
        print("MÉTODO:")
        print("  - Población pequeña: 20 mazos (rápido)")
        print("  - Generaciones: 5 (suficiente para ver tendencia)")
        print("  - Swiss Tournament: k=6, n=1 invocación/match (3 partidas internas)")
        print("  - Probar múltiples combinaciones de mutation/crossover")
        print("  - Sin gauntlet tier-1 (experimento aislado de operadores)")
        print()
        # 20 pop x k=6 x n=1 = 60 cmb/gen x ~195 s / 8 workers = ~25 min/gen
        # x 5 gen x N combinaciones probadas ~ 4-6 combinaciones tipicas
        print("TIEMPO ESTIMADO: ~8-12 horas (5 gen x 4-6 combinaciones)")

        if not self.forge_configured:
            print("\nForge no está configurado. Configúralo primero (Opción 4).")
            input("\nPresiona Enter para continuar...")
            return

        confirm = input("\n¿Ejecutar experimento? (S/n): ").strip().lower()
        if confirm in ['n', 'no']:
            return

        # Limpiar checkpoints antiguos para evitar interrupciones
        checkpoint_dir = os.path.join(self.evolved_dir, "checkpoints")
        if os.path.exists(checkpoint_dir):
            import shutil
            shutil.rmtree(checkpoint_dir)
            print(f"Checkpoints antiguos eliminados para evitar pausas")
            os.makedirs(checkpoint_dir, exist_ok=True)

        # Configuraciones a probar (priorizando alta mutación)
        configs = [
            ("Mut: 90%, Cross: 10%", 0.9, 0.1),
            ("Mut: 85%, Cross: 15%", 0.85, 0.15),
            ("Mut: 80%, Cross: 20%", 0.8, 0.2),
            ("Mut: 75%, Cross: 25%", 0.75, 0.25),
            ("Mut: 70%, Cross: 30%", 0.7, 0.3),
            ("Mut: 60%, Cross: 40%", 0.6, 0.4),
            ("Mut: 50%, Cross: 50%", 0.5, 0.5),
            # Referencia (configuración antigua invertida)
            ("Mut: 15%, Cross: 90% [OLD]", 0.15, 0.9),
        ]

        print(f"\nProbando {len(configs)} configuraciones...")
        print("=" * 70)

        # Verificar que hay cartas y generar mazos de prueba
        if not self.cards_available:
            print("\nObteniendo cartas...")
            from obtener_cartas_mtg import MTGCardScraper
            scraper = MTGCardScraper(output_dir=self.data_dir, exclude_latest_set=True)
            scraper.run()
            self.check_system_status()

        # Generar población de prueba de 20 mazos
        print(f"\nGenerando 20 mazos para el experimento...")
        from generador_mazos_mtg import MTGDeckGenerator
        generator = MTGDeckGenerator(
            cards_csv_path=os.path.join(self.data_dir, "processed_standard_cards.csv"),
            catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
            indices_path=os.path.join(self.data_dir, "card_indices.json"),
            output_dir=self.decks_dir
        )
        population = generator.generate_population_exact_size(20)

        # Guardar la población con el nombre correcto para el experimento
        pop_file = os.path.join(self.decks_dir, "experiment_population.json")
        import json
        with open(pop_file, 'w', encoding='utf-8') as f:
            json.dump(population, f, ensure_ascii=False, indent=2)
        print(f"Población de experimento guardada: {pop_file}")

        # Obtener configuración de hardware
        if not self.analyze_hardware_if_needed():
            workers = 4
        else:
            workers = self.hardware_analyzer.optimization_config['max_workers']

        results = []

        for i, (name, mut_rate, cross_rate) in enumerate(configs, 1):
            print(f"\n{'=' * 70}")
            print(f"CONFIGURACIÓN {i}/{len(configs)}: {name}")
            print(f"{'=' * 70}")

            try:
                import time
                start_time = time.time()

                ga = MTGGeneticAlgorithm(
                    population_file=pop_file,
                    catalog_path=os.path.join(self.data_dir, "card_catalog.json"),
                    indices_path=os.path.join(self.data_dir, "card_indices.json"),
                    output_dir=self.evolved_dir,
                    forge_jar_path=self.forge_jar,
                    max_generations=5,
                    population_size=20,
                    mutation_rate=mut_rate,
                    crossover_rate=cross_rate,
                    tournament_size=3,
                    elite_size=6,
                    use_swiss_tournament=True,
                    k_rounds=6,
                    n_games_per_match=2,
                    max_workers=workers,
                    parallel_batch_size=6,
                    base_timeout=300,
                    log_level='WARNING',  # Menos ruido en logs
                    save_forge_outputs=False,
                    headless_mode=self.headless_mode,
                    fitness_alpha=0.7,
                    fitness_beta=0.3,
                    enable_quality_metrics=True
                )

                best_deck = ga.evolve()
                elapsed = time.time() - start_time

                results.append({
                    'name': name,
                    'mutation_rate': mut_rate,
                    'crossover_rate': cross_rate,
                    'best_fitness': ga.best_fitness_ever,
                    'time_seconds': elapsed,
                    'stagnation_count': ga.stagnation_counter
                })

                print(f"\nCompletado en {int(elapsed // 60)}m {int(elapsed % 60)}s")
                print(f"   Best fitness: {ga.best_fitness_ever:.4f}")
                print(f"   Estancamiento: {ga.stagnation_counter}/3")

            except Exception as e:
                print(f"\nError en configuración {name}: {e}")
                results.append({
                    'name': name,
                    'mutation_rate': mut_rate,
                    'crossover_rate': cross_rate,
                    'best_fitness': 0.0,
                    'time_seconds': 0,
                    'stagnation_count': 0
                })

        # Mostrar resultados
        print("\n" + "=" * 70)
        print("RESULTADOS DEL EXPERIMENTO")
        print("=" * 70)

        # Ordenar por best_fitness descendente
        results.sort(key=lambda x: x['best_fitness'], reverse=True)

        print("\n┌─────────────────────────────┬──────────┬─────────┬────────────┐")
        print("│ Configuración               │ Fitness  │ Tiempo  │ Estanc.    │")
        print("├─────────────────────────────┼──────────┼─────────┼────────────┤")

        for r in results:
            mins = int(r['time_seconds'] // 60)
            badge = "" if r == results[0] else "  "
            print(f"│ {badge} {r['name']:25} │ {r['best_fitness']:6.4f}  │ {mins:3}m    │ {r['stagnation_count']}/3        │")

        print("└─────────────────────────────┴──────────┴─────────┴────────────┘")

        # Análisis y recomendación
        best = results[0]
        print(f"\nMEJOR CONFIGURACIÓN:")
        print(f"   {best['name']}")
        print(f"   Fitness: {best['best_fitness']:.4f}")
        print(f"   mutation_rate = {best['mutation_rate']}")
        print(f"   crossover_rate = {best['crossover_rate']}")

        print(f"\nRECOMENDACIONES:")

        # Encontrar top 3
        top_3 = results[:3]
        avg_mut = sum(r['mutation_rate'] for r in top_3) / 3
        avg_cross = sum(r['crossover_rate'] for r in top_3) / 3

        print(f"   - Basado en el top 3, el rango óptimo parece ser:")
        print(f"     mutation_rate: ~{avg_mut:.2f} ({avg_mut*100:.0f}%)")
        print(f"     crossover_rate: ~{avg_cross:.2f} ({avg_cross*100:.0f}%)")
        print(f"\n   - Si quieres aplicar la mejor configuración, edita mtg_main.py")
        print(f"     y cambia mutation_rate={best['mutation_rate']}, crossover_rate={best['crossover_rate']}")

        # Guardar resultados
        results_file = os.path.join(self.evolved_dir, "mutation_crossover_experiment.json")
        import json
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResultados guardados en: {results_file}")

        input("\nPresiona Enter para continuar...")

    # ==============================================================================
    # UTILIDADES
    # ==============================================================================

    def print_deck_summary(self, deck, ga=None):
        """
        Imprime resumen completo del mejor mazo: composición, perfil, listado
        de cartas por categoría, y win-rate vs gauntlet si está disponible.

        Args:
            deck (dict): Diccionario con información completa del mazo
            ga (MTGGeneticAlgorithm | None): GA del que extraer datos del gauntlet
        """
        print("\n" + "=" * 80)
        print("MEJOR MAZO ENCONTRADO")
        print("=" * 80)

        # === Identidad y perfil ===
        colors = deck.get('colors') or []
        print(f"  Nombre:        {deck.get('name', '(sin nombre)')}")
        print(f"  Colores:       {'/'.join(colors) if colors else 'Incoloro'}")
        arch = deck.get('archetype') or deck.get('detected_archetype')
        if arch:
            print(f"  Arquetipo:     {arch}")

        # === Estadísticas estructurales ===
        stats = deck.get('stats', {})
        print()
        print(f"  Total de cartas: {stats.get('total_cards', '?')}")
        print(f"  Tierras:         {stats.get('lands', '?')}")
        print(f"  Criaturas:       {stats.get('creatures', '?')}")
        print(f"  Hechizos:        {stats.get('spells', '?')}")
        if 'artifacts_enchantments' in stats:
            print(f"  Artef./Encant.:  {stats['artifacts_enchantments']}")
        if 'planeswalkers' in stats:
            print(f"  Planeswalkers:   {stats['planeswalkers']}")
        avg_cmc = stats.get('avg_cmc')
        if isinstance(avg_cmc, (int, float)):
            print(f"  CMC promedio:    {avg_cmc:.2f}")

        # === Listado de cartas agrupado por categoría ===
        cards = deck.get('cards', [])
        if cards:
            def kind(c):
                if c.get('is_land'):
                    return ('1_lands', 'Tierras')
                if c.get('is_creature'):
                    return ('2_creatures', 'Criaturas')
                if c.get('is_planeswalker'):
                    return ('3_planeswalkers', 'Planeswalkers')
                if c.get('is_instant') or c.get('is_sorcery'):
                    return ('4_spells', 'Hechizos')
                if c.get('is_artifact') or c.get('is_enchantment'):
                    return ('5_artif_ench', 'Artefactos / Encantamientos')
                return ('9_other', 'Otros')

            groups = {}
            for c in cards:
                k, label = kind(c)
                groups.setdefault((k, label), []).append(c)

            print("\n  COMPOSICIÓN COMPLETA:")
            for (k, label), items in sorted(groups.items()):
                items.sort(key=lambda x: (-x.get('count', 0), x.get('name', '')))
                subtotal = sum(c.get('count', 0) for c in items)
                print(f"\n    {label} ({subtotal}):")
                for c in items:
                    cnt = c.get('count', 0)
                    name = c.get('name', '?')
                    cmc = c.get('cmc')
                    cmc_str = f"  cmc {int(cmc)}" if isinstance(cmc, (int, float)) else ""
                    set_name = c.get('set', '').upper()
                    set_str = f"  [{set_name}]" if set_name else ""
                    print(f"      {cnt:>2}x {name}{cmc_str}{set_str}")

        # === Win-rate vs gauntlet (si el GA tiene datos) ===
        if ga is not None and getattr(ga, 'gauntlet_decks', None):
            wr = getattr(ga, 'last_gauntlet_winrates', None)
            mm = getattr(ga, 'last_gauntlet_matchup', None)
            # Si el deck tiene un índice de pop disponible, mostrar su matchup
            idx = deck.get('pop_index') if isinstance(deck.get('pop_index'), int) else None
            if wr and mm and idx is not None and idx < len(wr):
                anchors_meta = getattr(ga, 'gauntlet_metadata', [])
                print("\n  WIN-RATE DEL MEJOR MAZO vs GAUNTLET:")
                print(f"    Win-rate global: {wr[idx]:.2f} "
                      f"({int(round(wr[idx] * len(anchors_meta)))}/{len(anchors_meta)} anchors)")
                for a, anc in enumerate(anchors_meta):
                    if a < len(mm[idx]):
                        result = "GANA" if mm[idx][a] == 1 else "pierde"
                        print(f"      A{a} {anc.get('name', '?'):<32} [{anc.get('archetype', '?'):<10}]  {result}")

        print("=" * 80)


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
        print("\n\n¡Hasta luego!")
    except Exception as e:
        print(f"\nError crítico: {e}")
        print("Por favor, reporta este error si persiste.")


if __name__ == "__main__":
    main()
