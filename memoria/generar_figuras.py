#!/usr/bin/env python3
"""
Genera las figuras de la memoria a partir de los datos limpios del run final
(Campaña B, exp07_run_final) y de los resultados del experimento A/B.

Salida: memoria/images/*.pdf (vectorial, para LaTeX).
Ejecutar desde la raíz del proyecto:  python3 memoria/generar_figuras.py
"""
import os
import csv
import json
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- Rutas ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, 'experimentos', 'exp07_run_final')
CSV = os.path.join(RUN, 'parallel_evolution_stats.csv')
CHAMP = os.path.join(RUN, 'best_deck_final_parallel.json')
OUT = os.path.join(ROOT, 'memoria', 'images')
os.makedirs(OUT, exist_ok=True)

# --- Estilo común (académico, sobrio) ---
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'figure.autolayout': True,
})
AZUL, ROJO, VERDE, GRIS = '#1f4e79', '#c0392b', '#27ae60', '#7f8c8d'


def cargar_csv():
    gens, best, avg, div, mut, ent = [], [], [], [], [], []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            gens.append(int(r['generation']))
            best.append(float(r['best_fitness']))
            avg.append(float(r['avg_fitness']))
            div.append(float(r['diversity']))
            mut.append(float(r['mutation_rate']))
            ent.append(float(r['archetype_entropy']))
    return gens, best, avg, div, mut, ent


# ============================================================
# 1. Coste Swiss vs round-robin (crecimiento del nº de enfrentamientos)
# ============================================================
def fig_swiss_vs_rr():
    N = list(range(10, 101))
    rr = [n * (n - 1) // 2 for n in N]
    def k(n): return min(12, max(5, math.ceil(math.log2(n)) + 2))
    sw = [n * k(n) // 2 for n in N]

    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.plot(N, rr, color=ROJO, lw=2, label=r'Round-robin completo: $\binom{N}{2}$')
    ax.plot(N, sw, color=AZUL, lw=2, label=r'Swiss: $N\cdot k/2$')
    # Punto de trabajo N=40
    ax.scatter([40, 40], [780, 160], color=GRIS, zorder=5, s=30)
    ax.annotate('780', (40, 780), textcoords='offset points', xytext=(6, 4), color=ROJO)
    ax.annotate('160', (40, 160), textcoords='offset points', xytext=(6, -12), color=AZUL)
    ax.axvline(40, color=GRIS, ls=':', lw=1)
    ax.set_xlabel('Tamaño de la población ($N$)')
    ax.set_ylabel('Enfrentamientos por generación')
    ax.set_title('Coste de la evaluación: round-robin frente a Swiss')
    ax.legend()
    fig.savefig(os.path.join(OUT, 'fig_swiss_vs_roundrobin.pdf'))
    plt.close(fig)


# ============================================================
# 2. Evolución del fitness (best y avg por generación)
# ============================================================
def fig_evolucion_fitness():
    gens, best, avg, *_ = cargar_csv()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(gens, best, color=AZUL, lw=1.8, marker='o', ms=3, label='Mejor de la población')
    ax.plot(gens, avg, color=ROJO, lw=1.8, ls='--', label='Media de la población')
    gpico = best.index(max(best))
    ax.scatter([gens[gpico]], [best[gpico]], color=VERDE, zorder=5, s=45)
    ax.annotate(f'{best[gpico]:.4f} (gen {gens[gpico]})',
                (gens[gpico], best[gpico]), textcoords='offset points',
                xytext=(-95, -6), color=VERDE)
    ax.set_xlabel('Generación')
    ax.set_ylabel('Fitness')
    ax.set_title('Evolución del fitness en el run final')
    ax.set_ylim(0.45, 1.0)
    ax.legend(loc='lower right')
    fig.savefig(os.path.join(OUT, 'fig_evolucion_fitness.pdf'))
    plt.close(fig)


# ============================================================
# 3. Dinámica de la población: diversidad, entropía y mutación
# ============================================================
def fig_dinamica_poblacion():
    gens, best, avg, div, mut, ent = cargar_csv()
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 6.6), sharex=True)

    axes[0].plot(gens, div, color=AZUL, lw=1.8)
    axes[0].set_ylabel('Diversidad')
    axes[0].set_title('Dinámica de la población')

    axes[1].plot(gens, ent, color=VERDE, lw=1.8)
    axes[1].axhline(math.log(3), color=GRIS, ls=':', lw=1)
    axes[1].annotate(r'$\ln 3$ (máximo)', (0, math.log(3)),
                     textcoords='offset points', xytext=(4, 3), color=GRIS, fontsize=9)
    axes[1].set_ylabel('Entropía de\narquetipo (nats)')

    axes[2].plot(gens, mut, color=ROJO, lw=1.8, drawstyle='steps-post')
    axes[2].set_ylabel('Tasa de\nmutación')
    axes[2].set_xlabel('Generación')

    fig.savefig(os.path.join(OUT, 'fig_dinamica_poblacion.pdf'))
    plt.close(fig)


# ============================================================
# 4. Integridad estructural: baseline vs pack-aware (datos del experimento A/B)
# ============================================================
def fig_estructura_ab():
    # Valores documentados en el análisis comparativo exp02 vs exp03
    metricas = ['Singletons\nno-tierra', 'Packs de\n4 copias', 'Tierras no\nbásicas']
    baseline = [3.55, 5.55, 0.68]
    packaware = [0.17, 7.83, 4.00]

    x = range(len(metricas))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    b1 = ax.bar([i - w/2 for i in x], baseline, w, color=ROJO, label='Baseline (copia individual)')
    b2 = ax.bar([i + w/2 for i in x], packaware, w, color=AZUL, label='Pack-aware')
    ax.bar_label(b1, fmt='%.2f', padding=2, fontsize=9)
    ax.bar_label(b2, fmt='%.2f', padding=2, fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(metricas)
    ax.set_ylabel('Media por mazo')
    ax.set_title('Integridad estructural de los mazos (población final)')
    ax.legend()
    fig.savefig(os.path.join(OUT, 'fig_estructura_ab.pdf'))
    plt.close(fig)


# ============================================================
# 5. Distribución de arquetipos: baseline vs pack-aware
# ============================================================
def fig_arquetipos_ab():
    arqs = ['Aggro', 'Midrange', 'Control']
    baseline = [29, 8, 3]
    packaware = [3, 33, 4]

    x = range(len(arqs))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    b1 = ax.bar([i - w/2 for i in x], baseline, w, color=ROJO, label='Baseline')
    b2 = ax.bar([i + w/2 for i in x], packaware, w, color=AZUL, label='Pack-aware')
    ax.bar_label(b1, padding=2, fontsize=9)
    ax.bar_label(b2, padding=2, fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(arqs)
    ax.set_ylabel('Nº de mazos (de 40)')
    ax.set_title('Distribución de arquetipos en la población final')
    ax.legend()
    fig.savefig(os.path.join(OUT, 'fig_arquetipos_ab.pdf'))
    plt.close(fig)


# ============================================================
# 6. Curva de maná del mazo campeón
# ============================================================
def fig_curva_mana():
    champ = json.load(open(CHAMP))
    curva = {}
    for c in champ['cards']:
        if not c['is_land']:
            cmc = int(c['cmc'])
            curva[cmc] = curva.get(cmc, 0) + c['count']
    xs = sorted(curva)
    ys = [curva[x] for x in xs]

    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    barras = ax.bar(xs, ys, color=AZUL, width=0.7)
    ax.bar_label(barras, padding=2, fontsize=9)
    ax.set_xlabel('Coste de maná convertido (CMC)')
    ax.set_ylabel('Nº de cartas')
    ax.set_title('Curva de maná del mazo campeón (R/W, fitness 0,9755)')
    ax.set_xticks(xs)
    fig.savefig(os.path.join(OUT, 'fig_curva_mana_campeon.pdf'))
    plt.close(fig)


if __name__ == '__main__':
    fig_swiss_vs_rr()
    fig_evolucion_fitness()
    fig_dinamica_poblacion()
    fig_estructura_ab()
    fig_arquetipos_ab()
    fig_curva_mana()
    print('Figuras generadas en', OUT)
    for f in sorted(os.listdir(OUT)):
        print('  ', f)
