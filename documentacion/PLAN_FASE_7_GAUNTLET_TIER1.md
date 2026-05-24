# Plan Fase 7: gauntlet tier-1 en el fitness

**Fecha de apertura:** 2026-05-14
**Marco:** TFG en dirección A (estudio del ecosistema emergente). El gauntlet tier-1 entra como **una dimensión más del fitness**, NO como objetivo. Sirve simultáneamente como bench externo (coordenada que caracteriza al ecosistema emergente) y como presión selectiva cross-arquetipo (rompe monoculturas como la B/W midrange observada en prueba2).
**Base:** rama `develop` tras merge de `feature/ga-pack-level-mutation` (commit `b7f4a8c2`).

---

## 0. Por qué Fase 7 y por qué ahora

Tras prueba2 (pack-aware, 30 gens × 40 pop):

- Los 4 pendientes de la auditoría previa están resueltos o atenuados por pack-aware (ver `project_pendientes_post_auditoria.md`).
- Aparece un problema nuevo: **monocultura B/W midrange** (37/40 mazos en B/W). Los arquetipos no-dominantes sobreviven solo por la cuota del HoF.
- Diagnóstico: la presión selectiva proviene exclusivamente del Swiss intrapoblacional. Sin anchor externo, lo que más rinde contra "lo que la población produce" se autorefuerza.

Bajo el marco A esto es **el último problema metodológico relevante**. El gauntlet tier-1 cierra la pieza que falta para que el TFG tenga su instrumento de medida principal: un atractor caracterizable contra una referencia externa estable.

---

## 1. Lo que el gauntlet NO es

Antes de las decisiones, fijar lo que ya está descartado por el marco A:

- **No es el objetivo del fitness.** El TFG no defiende "este mazo saca X% contra meta". Defiende "el ecosistema emergente tiene tal estructura, una de cuyas coordenadas es su distancia al meta".
- **No es validación a posteriori.** Si entra solo al final, no influye en la evolución y no resuelve la monocultura. Tiene que estar en el fitness durante todo el run.
- **No se le filtra el pool a Standard-legal.** El pool es parte del espacio de búsqueda. El meta es solo una referencia externa.

---

## 2. Preguntas de diseño

**Estado: todas cerradas (2026-05-14).** Ver §3 *Bitácora de decisiones* para la resolución completa de cada pregunta con razonamiento. Resumen para lectura rápida:

| Pregunta | Decisión |
|---|---|
| 1.A Formato del meta | Standard |
| 1.B Número de anchors | K=5 |
| 1.C Fuente de anchors | Listas tier-1 públicas (mtgtop8 / mtggoldfish) |
| 1.D Anclas fijas o rotativas | Fijas |
| 1.E Gauntlet común o por arquetipo | Común, con 5 anchors diversos (1 por arquetipo) |
| 2.A Fórmula de combinación | Aditivo: `fitness = α·swiss + β·calidad + γ·gauntlet` |
| 2.B γ constante o γ(t) | γ(t) lineal: 0.05 (gen 0) → 0.30 (gen final) |
| 2.C Partidas por par | 1 (BO1) para toda la pop |
| 2.D Mitigación gradiente plano | γ(t) primero; métricas parciales como plan B |
| 3.A Motor y config | Mismo Forge, misma config |
| 3.B Reglas de partida | Las de Forge por defecto (mulligan London, play/draw aleatorio, sin sideboard) |
| 3.C Almacenamiento anchors | `gauntlet/tier1/{*.dck, manifest.json}` |
| 5.A Métricas reportadas | Win-rate por gen + matchup matrix + win-rate por arquetipo |
| 5.B Publicar `.dck` | Sí: 9 HoF + top-5 pop final |

---

## 3. Bitácora de decisiones

| Fecha | Pregunta | Decisión | Razonamiento |
|---|---|---|---|
| 2026-05-14 | **1.A** Formato del meta | **Standard** | `card_catalog` ya está alineado (sets DMU→FIN, expansiones Standard 2022-2025). Existe `processed_standard_cards.csv` como evidencia adicional. Cambiar a Modern/Pioneer obligaría a reconstruir el pool. |
| 2026-05-14 | **1.C** Fuente de anchors | **(a) Listas tier-1 públicas** (mtgtop8 / mtggoldfish) | Coherente con A: referencia externa, neutra, reproducible. (b) sería co-evolución (rompe el marco). (c) queda como plan B si algún anchor real usa cartas fuera del `card_catalog`. |
| 2026-05-14 | **1.B** Número de anchors | **K=5** | Sweet spot computacional (+200 combates/gen, ~3 h extra/gen). Permite cubrir los grandes arquetipos del meta (aggro / midrange / control / combo / ramp) con uno por bloque. K=3 quedaría corto en representatividad; K≥8 dispara el coste (>140 h totales). |
| 2026-05-14 | **1.D** Anclas fijas o rotativas | **Fijas durante todo el run** | El TFG necesita un eje "win-rate vs gauntlet por gen" estable y comparable. Las rotaciones introducirían ruido externo indistinguible de la evolución. El no-determinismo de los combates en Forge ya genera miles de partidas distintas con anchors fijos. |
| 2026-05-14 | **1.E** Gauntlet común o por arquetipo | **Común, con 5 anchors diversos (1 por arquetipo del meta)** | Bajo A el gauntlet caracteriza al ecosistema entero. Diversidad interna del gauntlet garantiza presión heterogénea para todos los arquetipos. Una matchup matrix 9 (HoF) × 5 (gauntlet) basta para análisis rock-paper-scissors. Gauntlet por arquetipo triplicaría el coste sin ganancia interpretativa proporcional. |
| 2026-05-14 | **2.A** Fórmula de combinación con Swiss + calidad | **Aditivo ponderado: `fitness = α·swiss + β·calidad + γ·gauntlet`** | Multiplicativo es más elegante (premia sinergia) pero **descalifica bajo A**: un control malo en Swiss pero competente vs meta seguiría hundido (swiss bajo × modulador ≈ sigue bajo), y eso es justo el perfil que el gauntlet debe rescatar para romper la monocultura. Aditivo permite compensación cross-componente, es interpretable directamente (γ = peso absoluto), y descomponible posthoc. Sustitutivo descartado (sesgo top-K, no rompe monocultura). |
| 2026-05-14 | **2.C** Partidas por par (candidato, anchor) | **1 partida (BO1) para toda la pop** | Coste viable (+200 combates/gen → run ~157 h ~6.5 días). Varianza alta por par (0 o 1), pero promediada sobre 5 anchors y agregada sobre toda la pop, da gradiente suficiente. Posible refinado futuro: 3 partidas extra para candidatos que entren a elite/HoF (varianza baja donde más importa, sin disparar coste global). |
| 2026-05-14 | **2.B** Peso γ constante o γ(t) | **γ(t) lineal creciente: γ_min=0.05 (gen 0) → γ_max=0.30 (gen final)** | Currículum clásico EA: Swiss + calidad rigen cuando la pop es ruido aleatorio (gen 0-10); gauntlet domina cuando hay candidatos competentes vs meta (gen 20+). Lineal es interpretable y predecible. γ_max=0.30 deja al bloque interno (α+β=0.70) con peso suficiente para no descartar información de Swiss. |
| 2026-05-14 | **2.D** Mitigación del gradiente plano temprano | **Plan en dos tiempos: (i) solo γ(t) en primer test; (ii) métricas parciales (turnos, vida final) solo si validación corta muestra gradiente plano real** | El gauntlet *diverso* (5 arquetipos) ya facilita matchups favorables en gen 0 para algunos candidatos. No pre-construir métricas parciales hasta confirmar que hacen falta. Plan B claro: parser de logs Forge para extraer datos parciales. |
| 2026-05-14 | **3.A** Motor y config base | **Mismo Forge, misma config (timeout adaptativo, pool de workers, BO1)** | Las partidas del gauntlet entran a la cola normal igual que las del Swiss. No abrir motor secundario ni separar pool de workers — complica orquestación sin ganancia. |
| 2026-05-14 | **3.B** Reglas de partida | **Reglas que Forge ya aplica al Swiss: play/draw aleatorio, London mulligan automático, SIN sideboarding** | Forge no soporta sideboarding limpio entre juegos. Como vamos a BO1 (2.C), no aplica de todos modos. Resto de reglas heredadas del Swiss = consistencia y cero código nuevo. |
| 2026-05-14 | **3.C** Almacenamiento de anchor decks | **Carpeta `gauntlet/tier1/` con un `.dck` por anchor + `manifest.json` con metadata** | Estructura versionada en git (texto liviano). `manifest.json` contiene por anchor: nombre, arquetipo declarado, fuente (URL mtgtop8/mtggoldfish), fecha de extracción, formato (Standard). Garantiza reproducibilidad y trazabilidad para el TFG. |
| 2026-05-14 | **5.A** Métricas reportadas del gauntlet | **(i) Win-rate medio pop vs gauntlet por gen; (ii) win-rate medio HoF vs gauntlet; (iii) matchup matrix HoF×anchors (9×5); (iv) win-rate por arquetipo de la pop vs gauntlet por gen** | Bajo A, estas son las coordenadas que caracterizan al ecosistema contra el meta externo. (i) es el eje temporal principal; (iii) sostiene el análisis rock-paper-scissors; (iv) muestra si γ desplaza qué arquetipo domina. |
| 2026-05-14 | **5.B** Publicar `.dck` evolucionados | **Sí — 9 HoF + top-5 pop final** | Continuidad con la práctica de prueba2 (`hall_of_fame/*.dck`). Es el output material del TFG además de los gráficos. |

---

## 4. Plan de implementación

Diseño ya cerrado en §3. Trabajo a ejecutar, ordenado por dependencia:

### 4.1 Anchors (fuera del código, depende del usuario)
- Identificar los 5 mazos tier-1 del Standard actual desde mtgtop8 / mtggoldfish, repartidos por arquetipo (aggro / midrange / control / combo / ramp — o el reparto que dicte el meta del momento).
- Verificar que cada anchor sea reconstruible con el `card_catalog` actual. Si alguna carta crítica del anchor no está en el pool, decidir: (i) sustituir por una funcionalmente equivalente del pool, (ii) ampliar el pool, o (iii) elegir otro anchor.
- Crear `gauntlet/tier1/*.dck` (formato Forge `[metadata]` + `[Main]`) y `gauntlet/tier1/manifest.json` con metadata por anchor (nombre, arquetipo, fuente URL, fecha, formato).

### 4.2 Carga y orquestación
- Función `load_gauntlet(path) → list[Deck]` que parsea los `.dck` y los convierte a arrays compatibles con el resto del pipeline.
- Función `evaluate_vs_gauntlet(deck_array, gauntlet, n_games=1) → float` que ejecuta los combates BO1 contra cada anchor y devuelve `win_rate ∈ [0, 1]`.
- Integración en el worker pool existente: los combates del gauntlet entran a la misma cola paralela que el Swiss.

### 4.3 Integración en el fitness
- Añadir cálculo de `gauntlet_winrate[i]` por candidato en cada gen.
- Calcular `γ_t = γ_min + (γ_max − γ_min) · t / (T − 1)` por generación.
- Modificar `fitness_multicomponent` para incluir el término aditivo `γ_t · gauntlet_winrate[i]`. Decidir cómo se redistribuye el peso (α, β) para que `α + β + γ_t = 1` — opciones: decrecer α proporcionalmente, o decrecer α y β a partes iguales.

### 4.4 Persistencia y métricas
- Por generación: persistir `gauntlet_winrates[i]` de cada candidato en `evolution_history.json` y en CSV.
- Al finalizar: generar matchup matrix `9 (HoF) × 5 (gauntlet)` como JSON + figura.
- Plot de "win-rate medio pop vs gauntlet por generación" y "win-rate medio por arquetipo vs gauntlet por gen".

### 4.5 Validación corta antes del run grande
- Test de 2-3 gens con la pop de prueba2 ya cargada (resume desde un checkpoint final) para validar que la matriz de win-rates no es identidicamente 0 ni 1.
- Si gradiente plano persiste → activar plan B (métricas parciales: parser de logs Forge para extraer turnos y vida final).

### 4.6 Run completo
- 40 pop × 30 gens con gauntlet activo. Coste estimado: ~157 h (~6.5 días).
- Dedicated `output_dir` (ej. `prueba3/` o `prueba_gauntlet/`) para no mezclar con runs previos.

---

## 5. Riesgos identificados

- **Coste prohibitivo:** si K·M es grande, el run no termina en plazo razonable. Mitigación: empezar con K=5, M=1.
- **Gradiente plano:** ver §2.D. Mitigación: γ(t) creciente y/o métrica parcial.
- **Sesgo de anchors:** si elegimos 5 aggros, todos los midranges/controles se ven mal contra el gauntlet aunque sean buenos. Mitigación: diversidad de arquetipos en el gauntlet (ver 1.E).
- **Anchor rot:** los tier-1 del meta cambian. Si los anclamos en una fecha y publicamos resultados meses después, la referencia ya no es válida. Mitigación documental: registrar fecha del meta y URL/fuente de cada anchor.