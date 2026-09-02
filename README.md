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

**Terminado y entregado.**

La corrida definitiva procesó los **987 expedientes** del reporte real
contra SIPI con **0 errores**: 1011 filas generadas, 2416 PDFs descargados
(620 MB), y solo un 18 % de filas marcadas con `Observaciones` — el trabajo
manual restante que el programa señala en vez de inventarse.

Pendiente: bajar ese 18 %, la coma de `artículo 136, literal h)` y ampliar
`alias.json`.

## Documentación

[`DOCUMENTACION.md`](DOCUMENTACION.md) es el manual completo: instalar,
correr, leer el Excel de salida, problemas frecuentes y la sección para
desarrolladores (entorno, pruebas, empaquetado). El `.md` es la fuente;
[`DOCUMENTACION.docx`](DOCUMENTACION.docx) es la versión para repartir a
quien no lee Markdown.

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

tests/               # Batería con pytest + hypothesis
  data/              # Mini-Excel recortados del reporte real, para tests offline
  fixtures/http/     # Respuestas HTTP grabadas de SIPI real, para tests offline
  propios/           # Corridas reales en Windows que destaparon bugs post-entrega

docs/                # Diagramas de arquitectura y flujo (SVG + PNG) versionados,
                      #   generados por gen_diagramas.py

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

No hace falta empaquetar nada para usar el programa. Abre la misma ventana
que el `.exe`.

Linux o WSL (`tkinter` va aparte: `sudo apt install python3-tk`):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m app
```

Windows:

```powershell
py -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv-win\Scripts\python.exe -m app
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

## Construir el `.exe` (Windows)

```bat
construir_exe.bat
```

Crea el entorno, **corre las pruebas y aborta si falla alguna**, empaqueta
con PyInstaller (`--onedir`), copia el resultado a
`%USERPROFILE%\ExtraccionSIC` y ejecuta la autoprueba
(`ExtraccionSIC.exe --autoprueba --red`) antes de darse por terminado.

> Hay que construir con CPython de python.org. El build de la Microsoft
> Store y del *Python Install Manager* guarda Tcl/Tk dentro de un zip
> embebido que PyInstaller no puede empaquetar: el `.exe` sale sin errores y
> muere al arrancar. El script lo detecta y se detiene antes. Detalle en
> [`DOCUMENTACION.md` §6](DOCUMENTACION.md#6-para-desarrolladores).

## Ramas

- `main` — historia estable, lo entregado.
- `develop` — punto de partida para lo que quede pendiente.
