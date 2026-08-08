# Extracción SIC — automatización SIPI

Automatización de un proceso manual: leer un Excel de expedientes de la
Superintendencia de Industria y Comercio (SIC), descargar los PDFs de cada
expediente desde SIPI (`sipi.sic.gov.co`), extraer los datos de las
resoluciones (naturaleza de la marca, oposición, opositores, motivos de
negación) y generar un Excel nuevo, listo para revisión manual.

Se entrega como aplicación de escritorio para Windows (`.exe`, PyInstaller
`--onedir`, sin instalación) con una ventana en `tkinter`: elegir Excel y
carpeta de salida, correr con varios hilos, ver progreso en vivo y abrir la
carpeta de resultados al terminar.

## Estado

**Fase 10 de 10 — cerrada. El proyecto está terminado y entregado.**

La corrida definitiva procesó los **987 expedientes** del reporte real
contra SIPI con **0 errores**: 1011 filas generadas, 2416 PDFs descargados
(620 MB), y solo un 18 % de filas marcadas con `Observaciones` — el trabajo
manual restante que el programa señala en vez de inventarse. El detalle
completo, con cifras por corrida, decisiones y los 37 puntos de contexto no
obvio verificados contra el sitio real, está en [`ESTADO.md`](ESTADO.md).

## Mapa de la documentación

Este repo trae varios documentos, cada uno con un propósito distinto — no
son borradores redundantes:

| Documento | Para qué sirve | Público |
|---|---|---|
| [`ESTADO.md`](ESTADO.md) | Fuente de verdad del proyecto: qué funciona hoy, decisiones tomadas y revertidas (con el porqué), 37 puntos de contexto no obvio verificados contra SIPI real, deuda conocida y bitácora fase a fase | Quien retome el desarrollo |
| [`plan.md`](plan.md) | Diseño completo previo a escribir código: arquitectura, modelo de datos, estrategia de descarga/extracción, empaquetado y plan de pruebas | Quien quiera el diseño de fondo |
| [`DOCUMENTACION.md`](DOCUMENTACION.md) / [`DOCUMENTACION.docx`](DOCUMENTACION.docx) | Manual de usuario final: instalar, correr, leer el Excel de salida, problemas frecuentes. El `.md` es la fuente; el `.docx` es la versión para repartir | Usuario final no técnico |
| [`PROMPT_CORRECCIONES.md`](PROMPT_CORRECCIONES.md) | Prompt usado para las correcciones post-entrega, con los 7 puntos que dejó el usuario tras probar el `.exe` en Windows | Trazabilidad de esa ronda de cambios |
| [`guia-diagramas-imagen.md`](guia-diagramas-imagen.md) | Guía para generar/validar los diagramas de `docs/` (arquitectura y flujo, en SVG y PNG) | Quien toque `docs/gen_diagramas.py` |

`DOCUMENTACION.md` está atado al código por pruebas
(`tests/test_documentacion.py`): si el manual se desincroniza de lo que
realmente hace `app/`, la suite falla. Un manual desactualizado no sobrevive
aquí.

## Estructura del proyecto

```
app/
  gui.py           # Ventana tkinter: la aplicación de escritorio
  pipeline.py       # ejecutar(): orquesta todo con ThreadPoolExecutor
  config.py         # Layout de salida (poc / clasico) y constantes
  models.py         # Modelos de datos del expediente
  excel/            # Lectura del reporte de entrada, escritura del Excel de salida
  parser/           # Texto de PDF -> patrones regex -> datos extraídos
  downloader/       # Sesión HTTP, scraping de SIPI, descarga validada de PDFs
  utils/            # Rutas, texto, logging sin trazas en la ventana

tests/               # 423 pruebas (pytest + hypothesis), ~96 % cobertura
  data/              # Mini-Excel recortados del reporte real, para tests offline
  fixtures/http/     # Respuestas HTTP grabadas de SIPI real, para tests offline
  propios/           # Corridas reales del usuario en Windows que destaparon bugs
                      #   post-entrega (§ "Correcciones post-entrega" en ESTADO.md)

docs/                # Diagramas de arquitectura y flujo (SVG + PNG) versionados,
                      #   generados por gen_diagramas.py y validados por prueba

scripts/             # Utilidades sueltas (comparar_salida.py)
alias.json           # 139 alias de opositores (nombre completo -> nombre corto)
sembrar_alias.py      # Script que generó alias.json desde el archivo de referencia
discrepancias.csv     # Diffs medidos contra el archivo de referencia manual
hcauto.spec / construir_exe.bat   # Empaquetado con PyInstaller para Windows
```

Las carpetas de datos de trabajo (`temp/`, `salida/`, `build/`, `dist/`,
entornos virtuales, cachés) están fuera del control de versiones — ver
[`.gitignore`](.gitignore).

> **Nota sobre los datos incluidos:** los `.xlsx` sueltos en la raíz
> (`Reporte 5 Enero 2025.xlsx`, `Negacion marcas con información extra.xlsx`,
> `Negacion_marcas_20260807_213955.xlsx`), `discrepancias.csv` y
> `tests/propios/` contienen expedientes, marcas y opositores reales de SIC.
> Es información administrativa pública (resoluciones de SIPI), pero el repo
> se dejó **privado** por eso mismo: son datos de casos concretos, no
> sintéticos.

## Correr desde el código fuente

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m app
```

## Correr las pruebas

```bash
.venv/bin/python -m pytest -q               # toda la batería (~130 s)
.venv/bin/python -m pytest -q --cov=app     # con cobertura
.venv/bin/python -m pytest -m live          # opt-in: pega contra SIPI real
```

Casi todo corre **offline**, contra respuestas de SIPI grabadas en
`tests/fixtures/http/`. `tests/test_windows.py` solo corre en Windows y se
omite en Linux/WSL.

## Reconstruir el `.exe` (Windows)

```bat
construir_exe.bat
```

Crea el entorno, **corre las pruebas y aborta si falla alguna**, empaqueta
con PyInstaller (`--onedir`), copia el resultado a
`%USERPROFILE%\ExtraccionSIC` y ejecuta la autoprueba
(`ExtraccionSIC.exe --autoprueba --red`) antes de darse por terminado. Ver
detalle en [`DOCUMENTACION.md` §6](DOCUMENTACION.md#6-para-desarrolladores).

## Ramas

- `main` — historia estable, lo entregado.
- `develop` — punto de partida para lo que quede pendiente (ver "Siguiente
  paso" en [`ESTADO.md`](ESTADO.md): bajar el 18 % de filas con
  `Observaciones`, la coma de `artículo 136, literal h)`, ampliar
  `alias.json`).
