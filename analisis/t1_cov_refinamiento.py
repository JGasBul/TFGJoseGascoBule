import json, numpy as np, sys, os, contextlib
sys.path.insert(0, os.getcwd())

# Instanciar la clase de forma ligera (solo catálogo; sin Forge)
from algoritmo_genetico_mtg import MTGGeneticAlgorithm
with open(os.devnull, 'w') as dn, contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
    ga = MTGGeneticAlgorithm(
        catalog_path="mtg_data/card_catalog.json",
        indices_path="mtg_data/card_indices.json",
        forge_jar_path="./forge-gui-desktop-2.0.04-jar-with-dependencies.jar",
        log_level='ERROR',
        enable_quality_metrics=True,
        gauntlet_path=None,
    )

# Cargar los 40 mazos finales de exp03 (misma población que la tabla 6.4)
d = json.load(open('experimentos/exp03_pack_aware/final_population_20260424_152946.json'))
pop = d['final_population']
arrays = [np.array(m['array']) for m in pop]
print(f"Mazos cargados: {len(arrays)}")

W_OLD = {'structural':0.10,'card_power':0.15,'mana_curve':0.20,
         'synergy':0.20,'card_balance':0.20,'coherence':0.15}

rows = []
for a in arrays:
    info = ga.detect_archetype(a); arch = info['archetype']
    syn = ga.evaluate_synergy(a)
    bal = ga.evaluate_card_balance(a, archetype=arch)
    coh = ga.evaluate_archetype_coherence(a, archetype=arch, info=info)
    stru = ga.evaluate_structural(a)
    pwr = ga.evaluate_card_power(a)
    mana = ga.evaluate_mana_curve(a, archetype=arch)
    q_ref = 0.35*syn + 0.35*bal + 0.30*coh
    q_old = (W_OLD['structural']*stru + W_OLD['card_power']*pwr + W_OLD['mana_curve']*mana +
             W_OLD['synergy']*syn + W_OLD['card_balance']*bal + W_OLD['coherence']*coh)
    rows.append(dict(arch=arch, syn=syn, bal=bal, coh=coh, stru=stru, pwr=pwr, mana=mana,
                     q_ref=q_ref, q_old=q_old))

def stats(vals):
    v=np.array(vals); m=v.mean(); s=v.std(ddof=0)
    return m, s, (s/m*100 if m else 0), v.min(), v.max()

print("\n=== MÉTRICA ORIGINAL (6 componentes) — reproduce el 'antes' de la tabla 6.4 ===")
m,s,cov,lo,hi = stats([r['q_old'] for r in rows])
print(f"  media={m:.3f}  std={s:.3f}  CoV={cov:.1f}%  rango=[{lo:.3f},{hi:.3f}]  (tesis dice 0,751 / 11,6%)")

print("\n=== MÉTRICA REFINADA (3 componentes 35/35/30) — el 'después' MEDIDO ===")
m,s,cov,lo,hi = stats([r['q_ref'] for r in rows])
print(f"  media={m:.3f}  std={s:.3f}  CoV={cov:.1f}%  rango=[{lo:.3f},{hi:.3f}]  (tesis PROYECTABA 0,60-0,65 / 22-25%)")

print("\n=== CoV por componente (contraste con tabla 6.4) ===")
for name,key,peso in [('Sinergia','syn','27,7'),('Equilibrio','bal','30,7'),('Coherencia','coh','17,3'),
                      ('Estructura','stru','0,5'),('Poder','pwr','7,1'),('Curva','mana','7,7')]:
    m,s,cov,lo,hi = stats([r[key] for r in rows])
    print(f"  {name:11s} media={m:.3f} std={s:.3f} CoV={cov:4.1f}%  (tabla 6.4: {peso}%)")
