# Extracción SIC — automatización SIPI

Automatización de un proceso manual: leer un Excel de expedientes de la
Superintendencia de Industria y Comercio (SIC), descargar los PDFs de cada
expediente desde SIPI (`sipi.sic.gov.co`), extraer los datos de las
resoluciones (naturaleza de la marca, oposición, opositores, motivos de
negación) y generar un Excel nuevo, listo para revisión manual.

Se entrega como aplicación de escritorio para Windows (ejecutable sin
instalación) con una ventana en `tkinter`: elegir Excel y carpeta de salida,
correr con varios hilos, ver progreso en vivo y abrir la carpeta de
resultados al terminar.

## Estado

**Fase 10 de 10 — cerrada. El proyecto está terminado y entregado.**

La corrida definitiva procesó los **987 expedientes** del reporte real
contra SIPI con **0 errores**: 1011 filas generadas, 2416 PDFs descargados
(620 MB) y un 18 % de filas marcadas con `Observaciones` — el trabajo manual
restante que el programa señala en vez de inventarse.

## Documentación

| Documento | Para qué sirve | Público |
|---|---|---|
| [`MANUAL_USUARIO.md`](MANUAL_USUARIO.md) | Instalar, correr, leer el Excel de salida, qué revisar a mano y problemas frecuentes. Se entrega también en `.docx` | Usuario final |
| [`DOCUMENTACION_TECNICA.md`](DOCUMENTACION_TECNICA.md) | Arquitectura, flujo, módulos, configuración, pruebas, empaquetado y dónde tocar cada cosa | Quien mantenga el código |
| [`ESTADO.md`](ESTADO.md) | Bitácora del proyecto: decisiones tomadas y revertidas con su porqué, contexto no obvio verificado contra SIPI real, deuda conocida | Quien retome el desarrollo |
| [`plan.md`](plan.md) | Diseño completo previo a escribir código | Quien quiera el diseño de fondo |

El manual de usuario está atado al código por pruebas
(`tests/test_documentacion.py`): si se desincroniza de lo que realmente hace
`app/`, la suite falla.

## Estructura del proyecto

```
app/
  gui.py            # Ventana tkinter: la aplicación de escritorio
  pipeline.py       # ejecutar(): orquesta todo con ThreadPoolExecutor
  config.py         # Constantes, parámetros y layout de salida
  models.py         # Modelos de datos del expediente
  excel/            # Lectura del reporte de entrada, escritura del Excel de salida
  parser/           # Texto de PDF -> patrones regex -> datos extraídos
  downloader/       # Sesión HTTP, scraping de SIPI, descarga validada de PDFs
  utils/            # Rutas, texto, logging sin trazas en la ventana

tests/              # 423 pruebas (pytest + hypothesis), ~96 % cobertura
  data/             # Mini-Excel recortados del reporte real, para tests offline
  fixtures/http/    # Respuestas HTTP grabadas de SIPI real, para tests offline
  propios/          # Corridas reales en Windows que destaparon bugs post-entrega

docs/               # Diagramas (SVG + PNG) versionados y conversor a .docx
scripts/            # Utilidades sueltas
alias.json          # Alias de opositores (nombre completo -> nombre corto)
hcauto.spec / construir_exe.bat   # Empaquetado con PyInstaller para Windows
```

Las carpetas de datos de trabajo (`temp/`, `salida/`, `build/`, `dist/`,
entornos virtuales, cachés) están fuera del control de versiones — ver
[`.gitignore`](.gitignore).

> **Nota sobre los datos incluidos:** los `.xlsx` sueltos en la raíz,
> `discrepancias.csv` y `tests/propios/` contienen expedientes, marcas y
> opositores reales de SIC. Es información administrativa pública, pero el
> repo se dejó **privado** por tratarse de casos concretos, no sintéticos.

## Desarrollo

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m app          # correr desde el código fuente
.venv/bin/python -m pytest -q    # toda la batería (~130 s)
```

Reconstruir el ejecutable, desde Windows: `construir_exe.bat`. Detalle en
[`DOCUMENTACION_TECNICA.md`](DOCUMENTACION_TECNICA.md#9-empaquetado-y-distribución).

## Ramas

- `main` — historia estable, lo entregado.
- `develop` — punto de partida para lo pendiente: bajar el 18 % de filas con
  `Observaciones` y ampliar `alias.json`.
