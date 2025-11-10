#!/usr/bin/env python3
"""
Diagnóstico profundo: Probar ejecución de Forge paso a paso

Este script intenta ejecutar Forge exactamente como lo haría el algoritmo genético
y te muestra dónde falla exactamente.
"""

import os
import sys
import subprocess
import glob
import platform

print("=" * 80)
print("DIAGNÓSTICO PROFUNDO: EJECUCIÓN DE FORGE")
print("=" * 80)
print()

# Paso 1: Información del sistema
print("📊 PASO 1: INFORMACIÓN DEL SISTEMA")
print("-" * 80)
print(f"Sistema operativo: {platform.system()} {platform.release()}")
print(f"Python: {sys.version}")
print(f"Directorio actual: {os.getcwd()}")
print()

# Paso 2: Verificar Java
print("☕ PASO 2: VERIFICAR JAVA")
print("-" * 80)

try:
    result = subprocess.run(
        ['java', '-version'],
        capture_output=True,
        text=True,
        timeout=5
    )
    java_version = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
    print(f"✅ Java está instalado: {java_version}")
except FileNotFoundError:
    print("❌ ERROR: Java no está en PATH")
    print("   Solución: Agrega Java al PATH de Windows")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERROR verificando Java: {e}")
    sys.exit(1)

print()

# Paso 3: Buscar JAR de Forge
print("🔍 PASO 3: BUSCAR JAR DE FORGE")
print("-" * 80)

forge_patterns = [
    "./forge-gui-desktop*.jar",
    "./forge*.jar",
    "forge-gui-desktop*.jar",
    "forge*.jar"
]

forge_jar = None
for pattern in forge_patterns:
    matches = glob.glob(pattern)
    if matches:
        matches.sort(reverse=True)
        forge_jar = os.path.abspath(matches[0])
        print(f"✅ Encontrado: {matches[0]}")
        print(f"   Ruta absoluta: {forge_jar}")
        print(f"   Tamaño: {os.path.getsize(forge_jar) / (1024*1024):.1f} MB")
        break

if not forge_jar:
    print("❌ ERROR: No se encontró JAR de Forge")
    print("   Archivos .jar en el directorio actual:")
    all_jars = glob.glob("*.jar")
    if all_jars:
        for jar in all_jars:
            print(f"   - {jar}")
    else:
        print("   (ninguno)")
    sys.exit(1)

print()

# Paso 4: Verificar que el JAR existe
print("📁 PASO 4: VERIFICAR ARCHIVO JAR")
print("-" * 80)

if os.path.exists(forge_jar):
    print(f"✅ El archivo existe: {forge_jar}")
else:
    print(f"❌ ERROR: El archivo NO existe: {forge_jar}")
    sys.exit(1)

print()

# Paso 5: Probar comando básico de Java con el JAR
print("🧪 PASO 5: PROBAR COMANDO JAVA -JAR")
print("-" * 80)
print("Comando a ejecutar:")
print(f'  java -jar "{forge_jar}"')
print()

try:
    # Intentar ejecutar Forge sin argumentos (debe mostrar ayuda o error)
    result = subprocess.run(
        ['java', '-jar', forge_jar],
        capture_output=True,
        text=True,
        timeout=10
    )

    print(f"Return code: {result.returncode}")

    if result.stdout:
        print("\n--- STDOUT (primeras 20 líneas) ---")
        print('\n'.join(result.stdout.split('\n')[:20]))

    if result.stderr:
        print("\n--- STDERR (primeras 20 líneas) ---")
        print('\n'.join(result.stderr.split('\n')[:20]))

    if result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower():
        print("\n✅ Forge JAR responde correctamente")
    else:
        print("\n⚠️  Forge respondió pero con código de error")

except FileNotFoundError as e:
    print(f"❌ ERROR: No se pudo ejecutar el comando")
    print(f"   Detalles: {e}")
    print()
    print("   Posibles causas:")
    print("   1. Java no está en PATH (pero ya verificamos que sí)")
    print("   2. La ruta del JAR tiene caracteres especiales")
    print("   3. Permisos insuficientes")
    sys.exit(1)

except subprocess.TimeoutExpired:
    print("⚠️  Timeout: Forge tardó más de 10 segundos")
    print("   Esto puede ser normal si Forge está cargando recursos")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Paso 6: Probar comando completo (simulación)
print("🎮 PASO 6: PROBAR COMANDO DE SIMULACIÓN")
print("-" * 80)

# Crear mazos de prueba dummy si no existen
test_decks_dir = "mtg_decks"
if not os.path.exists(test_decks_dir):
    print(f"⚠️  Directorio {test_decks_dir} no existe")
    print("   No se puede probar simulación completa")
else:
    print(f"Directorio de mazos: {test_decks_dir}")

    # Listar mazos disponibles
    import json
    population_files = [
        os.path.join(test_decks_dir, "initial_population.json"),
        os.path.join(test_decks_dir, "test_population.json"),
        os.path.join(test_decks_dir, "mtg_population.json")
    ]

    found_population = None
    for pop_file in population_files:
        if os.path.exists(pop_file):
            found_population = pop_file
            break

    if found_population:
        print(f"✅ Población encontrada: {found_population}")

        # Leer primer mazo
        with open(found_population, 'r', encoding='utf-8') as f:
            population = json.load(f)

        if len(population) >= 2:
            deck1_name = population[0]['name']
            deck2_name = population[1]['name']

            print(f"   Mazos de prueba: {deck1_name} vs {deck2_name}")
            print()
            print("Comando de simulación completo:")
            sim_cmd = ['java', '-jar', forge_jar, 'sim', '-d', deck1_name, deck2_name, '-n', '1']
            print(f"  {' '.join(sim_cmd)}")
            print()
            print("⚠️  NO SE EJECUTARÁ automáticamente (puede tardar minutos)")
            print("   Si quieres probarlo manualmente, copia el comando de arriba")
        else:
            print(f"⚠️  Población tiene menos de 2 mazos ({len(population)})")
    else:
        print("⚠️  No se encontró archivo de población")

print()
print("=" * 80)
print("RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)
print()
print("✅ Java: OK")
print(f"✅ Forge JAR: {os.path.basename(forge_jar)}")
print(f"✅ Ruta absoluta: {forge_jar}")
print()
print("Si el error WinError 2 persiste, el problema está en:")
print("  1. Cómo se construye el comando con los argumentos 'sim -d ...'")
print("  2. El directorio de trabajo (cwd) al ejecutar subprocess")
print("  3. Los nombres de los mazos (espacios o caracteres especiales)")
print()
print("Para depurar más, ejecuta el algoritmo y envíame el error COMPLETO,")
print("incluyendo el traceback y el comando que intentó ejecutar.")
print()
