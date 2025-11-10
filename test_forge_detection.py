#!/usr/bin/env python3
"""
Script de diagnóstico para verificar detección de Forge JAR

Ejecutar en PowerShell:
    python test_forge_detection.py

Esto mostrará:
- Si se encuentra el JAR de Forge
- Qué ruta exacta se está usando
- Si el archivo realmente existe
- Versión de Python
- Sistema operativo
"""

import os
import sys
import glob
import platform

print("=" * 80)
print("DIAGNÓSTICO DE DETECCIÓN DE FORGE JAR")
print("=" * 80)
print()

# Información del sistema
print("📊 INFORMACIÓN DEL SISTEMA:")
print(f"   Python: {sys.version}")
print(f"   Sistema operativo: {platform.system()} {platform.release()}")
print(f"   Directorio actual: {os.getcwd()}")
print()

# Patrones de búsqueda (mismos que mtg_main.py)
forge_patterns = [
    "./forge-gui-desktop*.jar",
    "./forge*.jar",
    "../forge-gui-desktop*.jar",
    "~/Downloads/forge-gui-desktop*.jar",
    "~/Desktop/forge-gui-desktop*.jar",
    "./forge-gui-desktop-*-jar-with-dependencies.jar"
]

print("🔍 BUSCANDO FORGE JAR CON LOS SIGUIENTES PATRONES:")
print()

forge_jar = None
for i, pattern in enumerate(forge_patterns, 1):
    expanded_pattern = os.path.expanduser(pattern)
    print(f"{i}. Patrón: {pattern}")
    print(f"   Expandido: {expanded_pattern}")

    matches = glob.glob(expanded_pattern)
    if matches:
        matches.sort(reverse=True)
        # Convertir a ruta absoluta
        absolute_path = os.path.abspath(matches[0])
        print(f"   ✅ ENCONTRADO: {matches[0]}")
        print(f"   📁 Ruta absoluta: {absolute_path}")
        print(f"   📏 Tamaño: {os.path.getsize(absolute_path) / (1024*1024):.1f} MB")

        if forge_jar is None:
            forge_jar = absolute_path
            print(f"   ⭐ Esta será la ruta usada")
    else:
        print(f"   ❌ No encontrado")

    print()

print("=" * 80)

if forge_jar:
    print("✅ RESULTADO FINAL:")
    print(f"   Forge JAR detectado: {forge_jar}")
    print()

    # Verificar que el archivo realmente existe
    if os.path.exists(forge_jar):
        print("   ✅ El archivo existe")
        print(f"   📏 Tamaño: {os.path.getsize(forge_jar) / (1024*1024):.1f} MB")
    else:
        print("   ❌ ERROR: El archivo NO existe (esto es un bug)")

    print()

    # Probar comando java
    print("🧪 PROBANDO COMANDO JAVA:")
    print()

    # Verificar Java
    import subprocess
    try:
        result = subprocess.run(['java', '-version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        print("   ✅ Java está instalado")
        print(f"   Versión: {result.stderr.split('\\n')[0] if result.stderr else 'No detectada'}")
    except FileNotFoundError:
        print("   ❌ ERROR: Java NO está instalado o no está en PATH")
        print("   Instala Java desde: https://www.java.com/download/")
    except Exception as e:
        print(f"   ⚠️  Error verificando Java: {e}")

    print()

    # Comando que se ejecutaría
    print("📋 COMANDO QUE SE EJECUTARÁ:")
    print()
    print(f'   java -jar "{forge_jar}" sim ...')
    print()

else:
    print("❌ RESULTADO FINAL:")
    print("   No se encontró ningún JAR de Forge")
    print()
    print("📥 SOLUCIONES:")
    print("   1. Descarga Forge desde:")
    print("      https://github.com/Card-Forge/forge/releases")
    print()
    print("   2. Coloca el archivo JAR en:")
    print(f"      {os.getcwd()}")
    print()
    print("   3. O usa la opción 5 del menú para configurar la ruta manualmente")
    print()

print("=" * 80)
