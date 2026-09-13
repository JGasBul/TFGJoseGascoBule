# Generación automática de mazos de Magic: The Gathering mediante algoritmos genéticos

Trabajo de Fin de Grado (TFG) — José Gascó Bule, Escola Politècnica Superior de
Gandia (Universitat Politècnica de València).

Este repositorio contiene el sistema descrito en la memoria: un algoritmo genético
que genera mazos competitivos para el formato Standard de Magic: The Gathering,
evaluando cada mazo mediante la simulación real de partidas con el motor Forge.

## Requisitos

- **Python 3.10 o superior**, con las dependencias del fichero `requirements.txt`
  (`numpy`, `pandas`, `matplotlib`, `psutil`, `tqdm`, `requests`).
- **Java 21 o superior** (necesario para ejecutar Forge).
- **Forge** (motor de simulación). El sistema espera el JAR
  `forge-gui-desktop-2.0.04-jar-with-dependencies.jar` en la raíz del repositorio.
- **Conexión a internet** para descargar el catálogo de cartas de la API pública de
  Scryfall (solo la primera vez).

Instalación de las dependencias de Python:

```
pip install -r requirements.txt
```

## Estructura del código

El sistema se organiza en cuatro módulos, uno por etapa del flujo:

- `obtener_cartas_mtg.py` — descarga las cartas del formato Standard desde Scryfall y
  genera el catálogo (`mtg_data/card_catalog.json`) y los índices (`mtg_data/card_indices.json`).
- `generador_mazos_mtg.py` — produce la población inicial de mazos.
- `algoritmo_genetico_mtg.py` — núcleo del sistema; la clase `MTGGeneticAlgorithm`
  encapsula el ciclo evolutivo completo (inicialización, evaluación, selección, cruce,
  mutación, elitismo y persistencia).
- `mtg_main.py` — orquestador; conecta las tres etapas y analiza el hardware disponible
  antes de cada ejecución.

## Uso rápido

1. **Obtener el catálogo de cartas** (solo la primera vez):

   ```
   python3 obtener_cartas_mtg.py
   ```

2. **Lanzar el sistema** y seguir el menú interactivo:

   ```
   python3 mtg_main.py
   ```

   El orquestador detecta el hardware, ajusta el número de procesos paralelos y permite
   generar la población inicial y lanzar la evolución.

## Reproducibilidad de los experimentos

Los experimentos de la memoria están en la carpeta `experimentos/` (`exp01`…`exp08`),
cada uno con su configuración, sus poblaciones, sus estadísticas y sus registros. Al
término de cada generación el sistema guarda un punto de control (`checkpoints/`), lo que
permite reanudar una ejecución interrumpida sin repetir el cómputo ya realizado.

> Nota: el sistema no fija una semilla aleatoria, por lo que dos ejecuciones con la
> misma configuración parten de poblaciones iniciales distintas. Fijar la semilla para
> lograr reproducibilidad exacta se plantea como línea de trabajo futuro.

## Memoria

La memoria completa del TFG se encuentra en la carpeta `memoria/` (fuente LaTeX y PDF
compilado).
