# Memoria del TFG — Algoritmo Genético para Magic: The Gathering

Carpeta de trabajo para la memoria académica del TFG. Plantilla oficial
de la facultad adaptada para flujo local en LaTeX.

## Estructura

```
memoria/
├── main.tex            Documento principal (capítulos, secciones)
├── images/             Imágenes oficiales de la plantilla + figuras propias
│   ├── image1.jpeg     Logo facultad
│   └── image2.png      Cabecera
├── referencia/
│   └── plantilla-original.pdf   Plantilla compilada de la facultad (referencia visual)
├── README.md           Este archivo
└── .gitignore          Ignora artefactos de compilación LaTeX
```

## Compilación local

### Dependencias del sistema (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install texlive-latex-extra texlive-fonts-recommended \
                 texlive-lang-spanish texlive-bibtex-extra latexmk
```

Esto pesa ~1.5 GB. Si quieres la distribución completa (no necesario):

```bash
sudo apt install texlive-full   # ~5-6 GB
```

### Compilar

Desde la carpeta `memoria/`:

```bash
latexmk -pdf main.tex            # compila a main.pdf (recomendado)
# o manualmente:
pdflatex main.tex && pdflatex main.tex   # 2 pasadas para referencias cruzadas
```

Resultado: `main.pdf` en la misma carpeta.

### Limpiar artefactos

```bash
latexmk -C   # borra .aux, .log, .toc, .out, etc.
```

## Trabajo con VS Code

### Extensiones recomendadas

1. **LaTeX Workshop** (`James-Yu.latex-workshop`)
   Autocompletado, compilación con un clic, preview en vivo del PDF, snippets.
2. **Code Spell Checker** (`streetsidesoftware.code-spell-checker`)
   Corrector ortográfico inline.
3. **Spanish - Code Spell Checker** (`streetsidesoftware.code-spell-checker-spanish`)
   Diccionario español para el corrector.

Instalar desde la terminal:

```bash
code --install-extension James-Yu.latex-workshop
code --install-extension streetsidesoftware.code-spell-checker
code --install-extension streetsidesoftware.code-spell-checker-spanish
```

O desde el panel de extensiones (Ctrl+Shift+X) buscando los nombres.

### Configuración recomendada de LaTeX Workshop

En `.vscode/settings.json` del proyecto (o user-level):

```json
{
  "latex-workshop.latex.autoBuild.run": "onSave",
  "latex-workshop.latex.recipe.default": "latexmk",
  "latex-workshop.view.pdf.viewer": "tab"
}
```

Con esto, al guardar `main.tex` se compila automáticamente y se ve el PDF en otra pestaña.

## Flujo de trabajo

1. Editar `main.tex` (o capítulos separados que se incluyan vía `\input{}`).
2. Guardar — LaTeX Workshop compila automáticamente.
3. Ver el PDF actualizado en la pestaña lateral.
4. Commit a git cuando un bloque coherente esté listo.

## Convenciones

- Los logs (`.aux`, `.log`, `.toc`, etc.) y el PDF compilado **NO se commitean**
  (ver `.gitignore`). Sí se commitea `main.tex`, las imágenes y este README.
- Si se parte `main.tex` en capítulos separados, ponerlos en `capitulos/`
  e incluirlos en `main.tex` con `\input{capitulos/01-introduccion}`.
- Las figuras propias del TFG (diagramas, gráficos de evolución, capturas)
  van en `images/` con nombres descriptivos: `images/curva-fitness-prueba2.png`.
