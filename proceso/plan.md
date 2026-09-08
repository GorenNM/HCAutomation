# Plan — Automatización extracción SIC (SIPI)

Estado: **revisión 3** — entregable `.exe` de Windows, GUI tkinter, pruebas y documentación.
Decisiones del usuario en §18. No se escribe código hasta aprobación.

---

## 0. Hallazgos de la exploración previa

Se inspeccionaron los dos Excel y se hicieron pruebas reales contra `sipi.sic.gov.co`.
Estos hechos condicionan toda la arquitectura:

| # | Hallazgo | Consecuencia |
|---|---|---|
| 1 | La columna A de `Reporte 5 Enero 2025.xlsx` **no tiene hyperlink**; tiene la fórmula `=HYPERLINK("http://sipi.sic.gov.co/sipi/View.ashx?3857028","SD2022/0000017")` | Hay que leer el workbook **sin** `data_only=True` y extraer URL + expediente con regex sobre la fórmula |
| 2 | `View.ashx?<id>` responde 302 → `Browse.aspx?sid=<sid>`. El HTML resultante **ya contiene** los enlaces `Common/Utils/GetFile.aspx?&id=…` de los PDFs | **No se necesita Selenium ni Playwright**. `requests` + `BeautifulSoup` bastan |
| 2b | **El puerto 80 de `sipi.sic.gov.co` no responde**, y el reporte exporta las URLs con `http://`. Por `https://` contesta en 1.5 s | Reescribir el esquema a https antes de cada petición, o cada expediente se cuelga hasta el timeout |
| 3 | **Sin cookies, `View.ashx` entra en bucle de redirecciones** (50 saltos y curl se rinde); con sesión resuelve en 2. Aparte, `GetFile.aspx` puede responder **HTTP 200 con un PNG de 828 bytes** en vez del PDF — observado una vez, no reproducible después: probablemente limitación de ritmo, no falta de sesión | Obligatorio `requests.Session` persistente para navegar. Obligatorio **validar el magic `%PDF-`** del contenido, porque el status code miente |
| 4 | Los PDFs de resolución son **texto digital** (pypdf extrae ~18k chars limpios, con tildes) | No hace falta OCR en el camino feliz. MarkItDown no aporta nada |
| 5 | El número de documentos por expediente **varía (3 a 5)**, no siempre 3 | Clasificar por la columna "Documento" de la tabla, nunca por posición |
| 6 | Anexos tipo `Poder` / `Tipo de Imagen` son escaneos (0–7 chars extraídos) | Se descartan por tipo; no se les aplica OCR |
| 7 | El archivo de referencia tiene **652 filas** y el reporte **987**; además tiene inconsistencias manuales (`SI`/`Si`, `NO `/`no`, un caso negado con `MOTIVO 1` vacío) | La referencia define el **formato**, no es un oráculo de exactitud. No se puede prometer paridad 100% |

### Datos del expediente de prueba `SD2022/0000017`

```
Resolución N° 52886
Ref. Expediente N° SD2022/0000017
...solicitó el registro de la Marca MALTAVITAN (Nominativa) para distinguir productos
   comprendidos en la clase 5...
...no se presentaron oposiciones por parte de terceros.
...está comprendida en la causal de irregistrabilidad establecida en el artículo 136
   literal a) de la Decisión 486...
RESUELVE
ARTÍCULO PRIMERO: Negar el registro de la Marca MALTAVITAN (Nominativa)...
```

### Datos del expediente de prueba `SD2022/0001545` (con oposición y 2 causales)

```
...la sociedad Grupo Diagnostico S.A. Dimed S.A., presentó oposición con fundamento en
   las causal de irregistrabilidad contenidas en los literales a) y b) del artículo 136...
...está comprendido en la causal de irregistrabilidad establecida en el artículo 136 literal a)...
...NO está comprendido en la causal de irregistrabilidad establecida en el artículo 136 literal b)...
RESUELVE
ARTÍCULO 1. Declarar fundada la oposición interpuesta por parte de la sociedad Grupo
   Diagnóstico S.A. Dimed S.A.
ARTÍCULO 2. Negar el registro de la Marca idime (Mixta)...
```

Nótese el `no está comprendido`: **la negación léxica es el caso borde más peligroso** de todo
el proyecto. Un regex ingenuo de `causal ... literal X` marca 136b como motivo cuando el texto
dice exactamente lo contrario.

---

## 1. Arquitectura

Pipeline lineal de 5 etapas, cada una un módulo puro y testeable por separado.
El único componente con estado global es la sesión HTTP.

```
Excel entrada          SIPI                    disco                texto              Excel salida
     │                   │                       │                    │                     │
 ┌───▼────┐        ┌─────▼─────┐          ┌──────▼──────┐      ┌──────▼──────┐       ┌──────▼──────┐
 │ reader │───────►│  scraper  │─────────►│ downloader  │─────►│   parser    │──────►│   writer    │
 │        │ Case   │           │ DocLink  │             │ PDF  │             │ Record│             │
 └────────┘        └───────────┘          └─────────────┘      └─────────────┘       └─────────────┘
                          │                       │                    │
                          └───────────────────────┴────────────────────┘
                                        pipeline (orquestador)
                                                 │
                                          estado + callbacks
                                                 │
                                      gui.py  (ventana tkinter)
                                                 │
                            todo empaquetado en un .exe de Windows (§12)
```

Reglas de dependencia:

- `models` no importa nada del proyecto.
- `downloader`, `parser`, `excel` importan solo `models` + `utils`.
- `pipeline` importa todo lo anterior. **No importa `gui`**.
- `gui` importa `pipeline` y le pasa callbacks. La lógica de negocio nunca toca tkinter,
  y por eso la suite de pruebas corre entera sin abrir una ventana.

Concurrencia: `ThreadPoolExecutor` a nivel de **expediente** (I/O bound, red).
El parseo de PDF es CPU-ligero, corre en el mismo worker. Default 4 hilos, configurable.
No se usa `asyncio`: no aporta sobre 4 hilos y complica el código sin necesidad.

---

## 2. Estructura del proyecto

```
HCAutomation/
├── requirements.txt             # runtime, versiones fijas (==)
├── requirements-dev.txt         # pytest, pyinstaller, cairosvg
├── construir_exe.bat            # compila el .exe (lo corre el desarrollador, no el usuario)
├── hcauto.spec                  # receta de PyInstaller
├── plan.md
├── DOCUMENTACION.md             # ← documento único de usuario y técnico
├── ESTADO.md                    # ← trazabilidad META para agentes
├── guia-diagramas-imagen.md
├── app/
│   ├── __main__.py              # entrypoint: python -m app  /  punto de entrada del .exe
│   ├── config.py                # constantes, defaults, rutas
│   ├── models.py                # dataclasses del dominio
│   ├── gui.py                   # ventana tkinter
│   ├── pipeline.py              # orquestador + concurrencia + callbacks
│   ├── downloader/
│   │   ├── session.py           # requests.Session configurada, reintentos
│   │   ├── scraper.py           # Browse.aspx -> lista de DocumentLink
│   │   └── files.py             # GetFile.aspx -> PDF en disco, validación
│   ├── parser/
│   │   ├── pdf_text.py          # PDF -> texto normalizado
│   │   ├── patterns.py          # TODOS los regex, en un solo sitio
│   │   └── extractor.py         # texto -> ExtractedData
│   ├── excel/
│   │   ├── reader.py            # Reporte -> list[SourceRow]
│   │   └── writer.py            # list[OutputRecord] -> xlsx formato referencia
│   └── utils/
│       ├── rutas.py             # resuelve rutas con y sin PyInstaller (sys.frozen)
│       ├── logging_setup.py
│       └── text.py              # normalización de tildes, espacios, mayúsculas
├── docs/
│   ├── gen_diagramas.py         # genera SVG+PNG según guia-diagramas-imagen.md
│   └── img/                     # arquitectura.png/svg, flujo.png/svg
├── tests/
│   ├── conftest.py
│   ├── make_fixtures.py         # genera los mini-Excel y graba las respuestas HTTP
│   ├── data/                    # Excel reales recortados a 1-3 casos
│   ├── fixtures/
│   │   ├── http/                # HTML y PDFs reales grabados (replay offline)
│   │   └── texto/               # texto ya extraído de resoluciones reales
│   ├── test_text.py
│   ├── test_reader.py
│   ├── test_scraper.py
│   ├── test_downloader.py
│   ├── test_extractor.py
│   ├── test_writer.py
│   ├── test_pipeline.py
│   ├── test_e2e.py
│   ├── test_windows.py          # rutas, encoding y bloqueo de archivo (solo Windows)
│   └── test_live.py             # opt-in, golpea SIPI de verdad
└── dist/                        # lo genera PyInstaller; es lo único que se entrega
    └── ExtraccionSIC/
        ├── ExtraccionSIC.exe
        ├── _internal/           # Python y librerías embebidas
        ├── salida/              # resultados y logs (se crea al primer uso)
        └── temp/                # PDFs descargados (cache / reanudación)
```

`models`, `config`, `pipeline`, `gui` son módulos de un archivo, no paquetes: no hay nada
que dividir dentro de ellos todavía. Se convierten en paquete el día que crezcan.
El código vive bajo `app/` para que PyInstaller tenga un único punto de entrada claro y para
que `python -m app` funcione igual con y sin empaquetar.

---

## 3. Modelo de datos

```python
@dataclass(frozen=True)
class SourceRow:
    """Una fila del Reporte de entrada."""
    expediente: str            # SD2022/0000017
    case_url: str              # https://sipi.sic.gov.co/sipi/View.ashx?3857028
    marca: str
    titular: str
    niza: str
    descripcion: str
    bajo_oposicion: str        # 'Sí' | 'No'
    row_number: int            # para trazar errores al Excel original

@dataclass(frozen=True)
class DocumentLink:
    doc_type: DocType          # enum: TM9 | TM128 | TM6 | APELACION | OTRO
    label: str                 # texto crudo: 'TM128 - Niega con oposición'
    url: str
    resolucion_nr: str | None
    fecha: str | None

@dataclass
class Opositor:
    nombre: str
    articulos: list[str]       # ['136a', '136b']
    fundada: str | None        # 'SI' | 'NO' | None

@dataclass
class ExtractedData:
    naturaleza: str | None     # Nominativa | Mixta | Figurativa | 3D
    presenta_oposicion: bool
    opositores: list[Opositor]
    motivos: list[str]         # ['136a', '136h']  <- genera N filas
    apelacion: bool | None
    warnings: list[str]

@dataclass
class OutputRecord:
    """UNA fila del Excel de salida = expediente x motivo."""
    source: SourceRow
    extracted: ExtractedData
    motivo: str | None
    motivo_index: int          # 1, 2, ...
    motivos_total: int
```

---

## 4. Flujo completo

1. **Leer Excel** → `list[SourceRow]`. Header en la fila 11, datos desde la 12.
   URL y expediente salen de la fórmula HYPERLINK de la columna A.
2. **Por cada expediente** (en pool de hilos):
   1. GET `View.ashx?id` con la sesión → sigue redirect → HTML de `Browse.aspx`.
   2. Parsear la tabla `MainContent_ctrlDocumentList_gvDocuments` → `list[DocumentLink]`.
   3. Filtrar a los tipos relevantes (`TM9`, `TM128`, `TM6`, apelaciones). Descartar anexos.
   4. Descargar cada uno a `temp\<EXPEDIENTE>_<TIPO>.pdf`. Si el archivo ya existe y es
      un PDF válido → se salta (reanudación gratis).
   5. Extraer texto de la resolución principal (TM9 o TM128) → `ExtractedData`.
   6. Expandir a `list[OutputRecord]`, uno por motivo de negación.
3. **Escribir Excel** de salida con el formato de la referencia.
4. **Escribir log** y un `errores.xlsx` aparte con los expedientes que fallaron.

---

## 5. Librerías

| Librería | Uso | Por qué esta |
|---|---|---|
| `openpyxl` | leer y escribir xlsx | Estándar de facto, permite leer fórmulas y escribir con estilos/merges |
| `requests` | HTTP + sesión | El sitio funciona con GET simples una vez hay cookie |
| `beautifulsoup4` | parsear la tabla de documentos | Tolera el HTML sucio de WebForms. Se usa con **`html.parser` de la stdlib**, no con `lxml` |
| `pypdf` | PDF → texto | Puro Python, sin binarios; ya validado contra los PDFs reales |
| `tkinter` | interfaz gráfica | **stdlib**. PyInstaller la empaqueta sin configuración extra |

**Ninguna dependencia de runtime tiene código compilado.** Es deliberado: con solo ruedas
puras, el `.exe` se construye sin compilador, sin DLLs sueltas y sin sorpresas de arquitectura.
Por eso se descarta `lxml`, que era el único binario. `html.parser` es más lento, pero sobre
987 páginas la diferencia se pierde frente al tiempo de red.

Dev / build (no van dentro del .exe):

| Librería | Uso |
|---|---|
| `pytest`, `pytest-cov` | suite de pruebas |
| `hypothesis` | property-based **solo** sobre `utils/text.py` y el parseo de literales |
| `pyinstaller` | construir el ejecutable (**6.21.0**, verificado con wheel para cp314) |
| `cairosvg` | rasterizar los diagramas de la documentación (§14.3) |

**Descartadas, con motivo:**

- **MarkItDown** — envuelve pdfminer y produce Markdown. Los PDFs de la SIC no tienen tablas
  ni estructura que un Markdown preserve mejor; el texto plano de pypdf ya sale limpio y con
  tildes. Añadiría una dependencia pesada (y transitivamente `onnxruntime` si se activa OCR)
  a cambio de nada. **No se usa.**
- **Selenium / Playwright** — innecesario, ver hallazgo #2. Descartarlo elimina la dependencia
  de un navegador, el driver, y ~10x de tiempo de ejecución.
- **pandas** — solo se necesita leer filas y escribirlas. `openpyxl` solo hace ambas cosas.
- **lxml** — ver arriba: era la única dependencia binaria y complicaba el empaquetado.
- **Docker** — se evaluó y **se descartó** (§12.5). Un contenedor produce un proceso Linux;
  el entregable es un `.exe` de Windows. No solo no ayudaba: testear en Linux y entregar en
  Windows habría escondido justo los bugs que este proyecto va a tener (encoding cp1252,
  bloqueo de archivo de Excel, separadores de ruta).
- **Interfaz web + `http.server`** — fue la propuesta de la revisión 2, y solo existía para
  sobrevivir al contenedor. Sin contenedor, una ventana de escritorio con diálogo nativo de
  archivos le resulta más familiar al usuario final que una pestaña del navegador.
- **pytesseract / OCR** — solo lo necesitarían los anexos escaneados, que no se leen.
  Si aparece una resolución escaneada se marca como error para revisión manual.

---

## 6. Responsabilidades por módulo

- **`config.py`** — URLs base, `USER_AGENT`, timeouts, nº de hilos, delay entre requests,
  rutas por defecto, mapa de tipos de documento, versión del layout de salida.
- **`models.py`** — dataclasses de arriba. Sin lógica salvo propiedades derivadas triviales.
- **`utils/text.py`** — normalización: colapsar espacios y saltos de línea (los PDFs parten
  frases a mitad), quitar tildes para comparar, `casefold`. **Se conserva siempre el texto
  original**; la versión normalizada es solo para hacer match.
- **`utils/logging_setup.py`** — logger a `salida\run_<timestamp>.log` + handler en memoria
  que alimenta el panel de errores de la GUI.
- **`downloader/session.py`** — `requests.Session` con `User-Agent` de navegador, `Retry`
  (3 intentos, backoff exponencial, solo en 5xx/timeouts) y timeout global.
- **`downloader/scraper.py`** — HTML → `list[DocumentLink]`. Clasifica por el texto de la
  columna "Documento" con una tabla de patrones, no por índice de fila.
- **`downloader/files.py`** — descarga con `Referer`, **verifica que los primeros 5 bytes sean
  `%PDF-`**, escribe atómicamente (`.part` → `rename`), y salta si ya existe.
- **`parser/pdf_text.py`** — PDF → texto; si salen < 500 chars levanta `ScannedPdfError`.
- **`parser/patterns.py`** — todos los regex, con nombre y comentario del texto real que
  hacen match. Único archivo a tocar cuando la SIC cambie la redacción.
- **`parser/extractor.py`** — funciones pequeñas e independientes:
  `extract_naturaleza`, `extract_opositores`, `extract_motivos`, `extract_fundada`.
  Cada una devuelve su valor y acumula warnings; **ninguna lanza excepción** por no encontrar.
- **`excel/reader.py`**, **`excel/writer.py`** — I/O de Excel.
- **`pipeline.py`** — orquesta, paraleliza, cuenta, reporta progreso vía callbacks.
- **`gui.py`** — solo widgets y cableado. Cero lógica de negocio.
- **`utils/rutas.py`** — un único sitio que resuelve dónde están las cosas con y sin
  PyInstaller. Sin esto, el `.exe` escribe en la carpeta equivocada:

  ```python
  def base_dir() -> Path:
      """Carpeta junto al ejecutable (o a la raíz del repo si no está empaquetado)."""
      if getattr(sys, "frozen", False):
          return Path(sys.executable).parent
      return Path(__file__).resolve().parents[2]
  ```

---

## 7. Estrategia de descarga

1. Una sola `Session` para todo el proceso; la cookie `ASP.NET_SessionId` se obtiene en el
   primer GET y se reutiliza.
2. `GET View.ashx?<id>` con `allow_redirects=True`; la URL final es el `Referer` de las
   descargas siguientes.
3. Los `href` de `GetFile.aspx` vienen con `&amp;` — BeautifulSoup ya los desescapa.
4. Validación del contenido: `content-type` **y** magic bytes. Un PNG de 828 bytes con
   HTTP 200 es el modo de fallo real observado.
5. Nombres: `<EXPEDIENTE_SANITIZADO>_<TIPO>.pdf`, ej. `SD2022-0000017_TM9.pdf`.
   Si hay dos del mismo tipo se sufija `_2`. La `/` del expediente se sustituye por `-`.
6. Reanudación: si el archivo existe y empieza por `%PDF-`, no se vuelve a descargar.
   Reejecutar tras un corte de red es barato.
7. Cortesía: 4 hilos, delay configurable de 0.3 s por request. Ante un 429 o tres 5xx
   consecutivos, el pipeline **pausa y avisa** en la GUI en vez de martillear.
8. Los expedientes que fallen no abortan la corrida: se registran y se sigue.

---

## 8. Estrategia de extracción

Principio: **anclar a frases jurídicas fijas, nunca a posiciones ni a números de página.**
Todo regex corre sobre el texto normalizado (espacios colapsados), con `re.IGNORECASE`.

**Excepción medida, añadida tras la corrida real de 50 expedientes (2026-08-06).** Los
motivos no se buscan en todo el documento sino en la *zona de conclusión*: los 8 000
caracteres previos a «En mérito de lo expuesto» y todo lo que sigue. La razón es que la
resolución **transcribe los alegatos del opositor** antes de analizarlos, con frases
idénticas a las de la conclusión («se encuentra incurso en la causal … del artículo 136,
literal h)») que a veces la Dirección desmiente después. El número sale de medir, no de
suponer: sobre 50 resoluciones reales, la frase más lejana que sí era de la Dirección
estaba a 2 511 caracteres del marcador, y el alegato citado más cercano a 41 579. Cualquier
ventana entre 3 000 y 30 000 da el mismo resultado en el corpus. `En mérito de lo expuesto`
aparece exactamente una vez en las 50; `Conclusión`, que sería el marcador natural, solo en
16. Si faltan los marcadores, o si acotar deja la fila sin ningún motivo, se reanaliza el
documento entero y se marca la fila en `Observaciones`: perder un motivo es peor que colar
uno de más, porque el de más se ve al revisar.

### 8.1 Naturaleza

```
Marca\s+(?P<marca>.+?)\s*\((?P<nat>Nominativa|Mixta|Figurativa|Tridimensional|3D)\)
```
Se toma la primera coincidencia (aparece en el CONSIDERANDO y se repite en el RESUELVE).

### 8.2 Presenta oposición

Tres señales, en orden de confianza:
1. `no se presentaron oposiciones` → **No**.
2. `present[óo] oposici[óo]n` → **Sí**.
3. Tipo de documento: `TM9` = sin oposición, `TM128` = con oposición.

Si (1|2) contradicen al tipo de documento se registra un warning y gana el texto.
La columna `Bajo Oposición` del Excel de entrada se usa como **cuarta** verificación.

### 8.3 Opositores y sus artículos

```
(?:la sociedad|el señor|la señora)?\s*(?P<nombre>[^,]{3,120}?),?\s+present[óo] oposici[óo]n
\s+con fundamento en\s+(?:las?\s+causales?\s+de irregistrabilidad\s+contenidas?\s+en\s+)?
los?\s+literal(?:es)?\s+(?P<lits>[a-z]\)(?:\s*(?:,|y)\s*[a-z]\))*)\s+del art[íi]culo\s+(?P<art>\d+)
```

- `finditer`, no `search`: puede haber 2+ opositores. Orden de aparición = Opositor 1, 2, …
- `lits` se explota: `a) y b)` + `art=136` → `['136a', '136b']`.
- Variantes a soportar: `el artículo 136 literal a)`, `los literales a) y b) del artículo 136`,
  `el artículo 135 literal b)`, y artículos sin literal (`147`, `154`, `172`) → `'147'`.
- Fallback si el nombre sale sucio: se recorta en el `ARTÍCULO N. Declarar fundada la
  oposición interpuesta por (parte de) (la sociedad) X`, que da el nombre más limpio.

### 8.4 Fundada / Infundada

```
Declarar\s+(?P<fundada>fundada|infundada|parcialmente fundada)\s+la[s]?\s+oposici[óo]n(?:es)?
\s+(?:interpuesta[s]?\s+)?por\s+(?:parte de\s+)?(?P<nombre>.+?)(?=\.|ART[ÍI]CULO)
```
Se emparejan al opositor por nombre normalizado (sin tildes, sin `S.A.`/`S.A.S.`/`LTDA`,
casefold). Sin match de nombre pero con un solo opositor → se asigna igual.
`parcialmente fundada` → `SI` + warning.

### 8.5 Motivos de negación — el punto crítico

```
(?P<neg>no\s+)?(?:se\s+encuentra|est[áa])\s+(?:comprendid[oa]|incurs[oa])\s+en\s+
(?:la|las)\s+causal(?:es)?\s+de irregistrabilidad\s+(?:establecid[oa]s?|contenidas?|
contemplada)\s+en\s+el\s+art[íi]culo\s+(?P<art>\d+)\s+literal\s+(?P<lit>[a-z]\))
```

- **El grupo `neg` es obligatorio evaluarlo.** `no está comprendido en la causal … literal b)`
  significa que 136b **no** es motivo. Es el error más probable de todo el sistema y está
  confirmado en `SD2022/0001545`.
- Segunda fuente: encabezados de sección `Análisis de la causal de irregistrabilidad
  contenida en el literal X) del artículo NNN` — indican causal **analizada**, no
  necesariamente aplicada. Se usan solo para detectar candidatos y avisar si el regex
  principal no encontró nada.
- Tercera fuente: la parte resolutiva. Si `RESUELVE … Negar el registro` existe pero no se
  halló ningún motivo → `motivos = []` + warning "negada sin motivo detectado" (existe en la
  referencia: `SD2022/0001545` tiene MOTIVO 1 vacío).
- Deduplicar preservando orden de aparición.

### 8.6 Apelación

`True` si existe un documento cuyo label contenga `Apelaci[óo]n` (ej. `184 - TM Apelación
confirma`, `SD 438 Apelación confirma registro o negación`). Se decide con **la tabla de
documentos**, no con el PDF. Se emite `SI`/`NO` en mayúsculas (la referencia mezcla
`SI`/`NO`/`no`; se normaliza).

### 8.7 Nombre corto del opositor

La referencia usa nombres cortos hechos a mano (`RED BULL GMBH` → `RedBull`,
`LABORATORIOS INCOBRA` → `Incobra`). **No es derivable por regla.** Estrategia:

1. Diccionario `alias.json` sembrado con los 133 nombres cortos ya existentes en el archivo
   de referencia (se extrae una vez, automáticamente).
2. Si el opositor está en el diccionario → se usa el alias.
3. Si no → heurística: quitar sufijos societarios y prefijos genéricos (`LABORATORIOS`,
   `INDUSTRIAS`, `GRUPO`), tomar la primera palabra significativa en Capitalizado, y
   **marcar la celda como sugerencia** (warning) para revisión manual.

Esto es lo único del proyecto que no se puede automatizar del todo, y conviene decirlo claro.

---

## 9. Múltiples motivos → múltiples filas

Regla de expansión, en `pipeline.py`:

```python
def expand(source: SourceRow, data: ExtractedData) -> list[OutputRecord]:
    motivos = data.motivos or [None]        # sin motivo -> igual se emite 1 fila
    return [
        OutputRecord(source, data, m, i + 1, len(motivos))
        for i, m in enumerate(motivos)
    ]
```

- 0 motivos → **1 fila** con motivo vacío + warning. Nunca se pierde un expediente.
- 1 motivo → 1 fila.
- N motivos → N filas idénticas salvo la columna `MOTIVO Negación`.
- El resto de columnas (opositores, titular, niza…) se **repite** en cada fila, tal como pide
  el requisito.
- Las filas de un mismo expediente salen **contiguas y en el orden de aparición** del motivo
  en la resolución.
- La GUI reporta `expedientes procesados` y `registros generados` por separado, porque ahora
  difieren.

### Formato de salida — decisión a confirmar

La referencia tiene dos columnas `MOTIVO 1 Negación` y `MOTIVO 2 Negación`. El nuevo
requisito (una fila por motivo) las hace redundantes. Propuesta:

| Columna | Cambio |
|---|---|
| `MOTIVO 1 Negación` | se renombra a **`MOTIVO Negación`** |
| `MOTIVO 2 Negación` | **se elimina** |
| — | se añaden al final **`Motivo #`** y **`Motivos totales`** (para filtrar y auditar) |
| — | se añade al final **`Observaciones`** con los warnings de extracción |

Las 16 columnas restantes conservan nombre, orden y la fila-banner combinada
(`OPOSITOR 1 a clase 5` / `OPOSITOR 2 a clase 5`).
**Confirmar antes de implementar la fase 5.**

---

## 10. Cruce con el Excel de entrada

Clave de cruce: el número de expediente (`SD2022/0000017`), normalizado (trim, mayúsculas).

De la **entrada** (`Reporte …xlsx`) salen directamente:

| Salida | Origen |
|---|---|
| `Número de Expediente` | col A (texto de la fórmula HYPERLINK) |
| `Marca` | `Caso Título` |
| `Titular` | `Titular` |
| `NIZA` | `Descripción de Productos y Servicios` (lista de clases) |
| `Descripción de Productos y Servicios` | `Productos y Servicios Descripción` |
| `Presenta Oposición` | `Bajo Oposición`, **verificado** contra el PDF |

Del **PDF** salen: `Naturaleza`, opositores 1 y 2 con sus artículos y `Fundada`, y los motivos.
De la **tabla de documentos**: `Apelación a la negación`.

Ante conflicto Excel vs PDF gana el PDF, y se anota en `Observaciones`.

---

## 11. Interfaz gráfica

Ventana única de escritorio, tkinter, ~560x640. Es lo que se ve al abrir el `.exe`:
sin consola, sin navegador, sin nada que instalar.

```
┌──────────────────────────────────────────────────────┐
│  Extracción SIC                                       │
│                                                       │
│  Excel de entrada   [ C:\...\Reporte 5 Enero.xlsx ] […]│
│  Carpeta de salida  [ C:\...\ExtraccionSIC\salida ] […]│
│  Hilos [4]   ☑ Reusar PDFs ya descargados             │
│                                                       │
│              [ Iniciar ]   [ Detener ]                │
│                                                       │
│  [████████████░░░░░░░░]  412 / 987                    │
│  Procesando SD2022/0034221 …                          │
│                                                       │
│  Expedientes 412 · PDFs 1103 · Registros 449          │
│  Advertencias 23 · Errores 7                          │
│  ┌── Registro ────────────────────────────────────┐   │
│  │ 14:02:11 WARN  SD2022/0031: motivo no det.     │   │
│  │ 14:02:14 ERROR SD2022/0033: timeout            │   │
│  └────────────────────────────────────────────────┘   │
│  [ Abrir carpeta de salida ]                          │
└──────────────────────────────────────────────────────┘
```

Cubre los 6 requisitos pedidos: seleccionar entrada, seleccionar salida, iniciar, progreso,
errores, y los tres contadores (expedientes, PDFs, registros).

Detalles técnicos:

- Diálogos nativos de Windows (`filedialog.askopenfilename` / `askdirectory`), que es
  exactamente lo que un funcional espera al pulsar "…".
- Valores por defecto que ya funcionan sin tocar nada: salida en `salida\` junto al `.exe`,
  4 hilos, reutilización de PDFs activada. El usuario solo elige el Excel y pulsa *Iniciar*.
- El pipeline corre en un hilo aparte y se comunica por `queue.Queue`; la ventana la drena
  con `root.after(150, …)`. **Nunca se toca un widget desde un hilo worker** — hacerlo
  cuelga tkinter de forma intermitente e imposible de reproducir.
- `Detener` activa un `threading.Event`; los workers terminan el expediente en curso y salen
  limpiamente. Se escribe el Excel con lo procesado hasta ese punto.
- El log se ve en la ventana y se guarda completo en `salida\run_<timestamp>.log`.
- Cerrar la ventana con una corrida activa pide confirmación; no deja hilos huérfanos.

---

## 12. Empaquetado y distribución (.exe)

Objetivo: que en otro PC sea *copiar la carpeta → doble clic → funciona*. Sin instalar
Python, sin `pip`, sin Docker, sin permisos de administrador.

### 12.1 Por qué un .exe y no un contenedor

Un contenedor Docker ejecuta un proceso **Linux** y no puede producir un ejecutable de
Windows; PyInstaller, además, **no cross-compila** — el `.exe` se construye obligatoriamente
sobre Windows. Un `.exe` de PyInstaller ya lleva dentro el intérprete y todas las librerías,
que es exactamente la repetibilidad entre máquinas que se buscaba, pero en la forma que el
usuario final sí puede usar. El detalle completo del descarte, en §12.5.

### 12.2 Entorno de construcción — verificado

Comprobado en la máquina de desarrollo antes de escribir código:

| Elemento | Valor |
|---|---|
| SO | Windows 11 (10.0.26200) |
| Python | 3.14.6 (`py -3.14`), MSC v.1944 64-bit |
| tkinter | 8.6, disponible |
| PyInstaller | 6.21.0, con wheel `py3-none-win_amd64` para cp314 |
| Acceso al código | `pushd \\wsl.localhost\Ubuntu\home\fabio\perso\HCAutomation` monta `Z:` |

El código sigue viviendo en WSL; solo la compilación se ejecuta del lado Windows. No hay que
duplicar el repositorio ni mover archivos.

> **El `.exe` no se ejecuta desde una ruta UNC.** Doble clic sobre
> `\\wsl.localhost\Ubuntu\...\ExtraccionSIC.exe` da *«Windows no encuentra el archivo "\"»*:
> el bootloader de PyInstaller no admite un directorio UNC como directorio de trabajo.
> Desde `Z:` o desde `C:\...` funciona. Por eso `construir_exe.bat` termina copiando el
> resultado a `%USERPROFILE%\ExtraccionSIC`, que es donde se prueba.
> Al usuario final no le afecta: recibe un zip y lo descomprime en su disco.

> El Python 3.11 de la Microsoft Store que también está instalado **no sirve** para esto:
> corre en un contenedor de aplicación con rutas redirigidas y da fallos raros al empaquetar.
> Se usa el 3.14 de python.org.

### 12.3 Receta de construcción

`construir_exe.bat`, que corre el desarrollador:

```bat
@echo off
py -3.14 -m venv .venv-win
call .venv-win\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q || exit /b 1
pyinstaller hcauto.spec --noconfirm
echo Listo: dist\ExtraccionSIC\
```

**Los tests corren antes de empaquetar y frenan la construcción si fallan.** Un `.exe`
generado a partir de código en rojo es peor que no tener `.exe`.

Decisiones del `.spec`:

- **`--onedir`, no `--onefile`.** Onefile descomprime todo a `%TEMP%` en cada arranque:
  varios segundos de ventana en blanco, y es el patrón que más disparan los antivirus.
  Onedir arranca al instante. Se entrega la carpeta comprimida en un `.zip`.
- **`console=False`** para que no aparezca una ventana negra detrás de la interfaz.
  El precio de esto: un import que PyInstaller no recoja **no imprime nada**, el `.exe`
  muere al hacer doble clic y no queda rastro. Por eso el ejecutable acepta
  **`--autoprueba`**: importa los diez módulos, comprueba que `salida\` y `temp\` son
  escribibles, escribe `autoprueba.txt` junto al `.exe` y sale con 0 o 1.
  `construir_exe.bat` la ejecuta al terminar y **falla la construcción** si algo no cuadra.
  Es lo que hace verificable el caso 44 del §13.3 sin que nadie tenga que hacer clic.
- **`excludes`** de lo que PyInstaller arrastra sin que se use: `pytest`, `hypothesis`,
  `unittest`, `pydoc`, `email` si no hace falta. Recorta bastante el tamaño.
- Tamaño estimado de `dist\ExtraccionSIC\`: **35–50 MB** (la mayor parte es tcl/tk).

### 12.4 Entrega al usuario final

1. Descomprimir `ExtraccionSIC.zip` donde quiera (Escritorio sirve).
2. Doble clic en `ExtraccionSIC.exe`.
3. Elegir el Excel, pulsar *Iniciar*.
4. El resultado queda en la subcarpeta `salida\`.

No hay paso 0. No hay que instalar nada.

**Fricciones reales que quedan, dichas de frente:**

- **Antivirus.** Los ejecutables de PyInstaller disparan falsos positivos con cierta
  frecuencia; no es una rareza. Si el antivirus corporativo lo bloquea, las salidas son
  pedir excepción a TI o firmar el ejecutable con un certificado. Va documentado desde el
  primer día, no como sorpresa el día de la entrega.
- **SmartScreen** avisará "editor desconocido" la primera vez: *Más información → Ejecutar
  de todas formas*. Con captura de pantalla en `DOCUMENTACION.md`.
- El `.exe` es **solo Windows x64**. No corre en macOS ni en Linux; para eso habría que
  compilar en cada uno.

### 12.5 Docker: evaluado y descartado

Se consideró en la revisión 2 y se descartó por tres razones, en orden de peso:

1. **No produce el entregable.** Contenedor = proceso Linux. PyInstaller no cross-compila.
   Serían dos construcciones sin relación entre sí, y el contenedor no aportaría nada a la
   que importa.
2. **Daría confianza falsa.** La suite pasando en Linux esconde justo los fallos que este
   programa va a tener en Windows: `open()` sin `encoding=` explícito (UTF-8 en Linux,
   cp1252 en Windows → acentos rotos), `PermissionError` al escribir un `.xlsx` que el
   usuario tiene abierto en Excel, separadores de ruta, antivirus interceptando escrituras.
3. **No hay nada que orquestar.** Sin servidor, sin base de datos, sin servicios. Es un
   programa con ventana y cinco librerías puras de Python. El contenedor resolvía un
   problema que este proyecto no tiene.

Alternativas técnicas también descartadas: **Wine dentro del contenedor** (imágenes tipo
`cdrx/pyinstaller-windows`, abandonadas y con Python viejo) y **contenedores Windows
nativos** (imágenes de varios GB y cambiar el modo de Docker Desktop).

### 12.6 Reproducibilidad

- `requirements.txt` con **versiones exactas** (`==`), incluidas las transitivas.
- Se fija la versión de PyInstaller (`==6.21.0`): un cambio de versión cambia el binario.
- El `.exe` lleva dentro el número de versión y la fecha de construcción, visibles en la
  barra de título. Así, ante un reporte de error, se sabe qué build está usando el usuario.
- Todo lo que el programa escribe va **junto al ejecutable**, no a `%APPDATA%`: copiar la
  carpeta se lleva la caché de PDFs y los resultados, y borrarla no deja rastros.

---

## 13. Estrategia de pruebas

Principio, en las palabras del requisito: **las pruebas no se acomodan para que pasen.
Se escriben para reventar el sistema y ver cómo reacciona.**

Regla operativa, sin excepciones: si una prueba falla, se arregla **el código** o se
documenta la limitación en `ESTADO.md`. Nunca se relaja la aserción, ni se marca `xfail`,
ni se recorta el caso de entrada para que encaje. Un test que se ablanda deja de ser un test.

### 13.1 Cuatro capas

| Capa | Qué cubre | Datos | Red |
|---|---|---|---|
| **Unitaria** | `text`, `patterns`, `extractor`, `reader`, `writer` | texto real + casos deformados a mano | no |
| **Integración** | `scraper` + `downloader` | respuestas HTTP **reales grabadas** | no (replay) |
| **E2E** | Excel entrada → Excel salida | mini-Excel de 1 y 2 casos reales | no (replay) |
| **Live** | humo contra SIPI real | 2 expedientes | **sí**, opt-in |

Solo la capa *live* toca la red. Se marca `@pytest.mark.live` y está **desactivada por
defecto** (`addopts = -m "not live"`); se corre a mano con `pytest -m live`. Así la suite es
determinista y no depende de que la SIC esté arriba, pero existe una prueba que detecta el
día que la SIC cambie el HTML.

### 13.2 Datos reales, no inventados

`tests/make_fixtures.py` se ejecuta **una vez** y produce, a partir de los archivos reales
que ya están en el directorio:

- `tests/data/mini_1_caso.xlsx` — copia del reporte real recortada a la fila de
  `SD2022/0000017` (sin oposición, 1 motivo `136a`), **conservando las 11 filas de cabecera
  y la fórmula HYPERLINK intactas**. Si el recorte alterara el formato, el E2E dejaría de
  probar el lector real.
- `tests/data/mini_2_casos.xlsx` — añade `SD2022/0001545` (con oposición, causal `a`
  aplicada y causal `b` **rechazada** — el caso de la negación léxica).
- `tests/data/mini_multimotivo.xlsx` — un expediente con 2 motivos, tomado de los 18 que
  existen en el archivo de referencia (p. ej. `SD2022/0097089`, `136a` + `136h`).
- `tests/fixtures/http/<expediente>/browse.html` y `<expediente>/<doc>.pdf` — respuestas
  reales grabadas tal cual las devuelve SIPI, incluido **el PNG de 828 bytes** que el
  servidor manda cuando falta la sesión. Ese PNG es una fixture de primera clase.
- `tests/fixtures/texto/*.txt` — texto ya extraído de 8 resoluciones reales, para que los
  tests del extractor no dependan de pypdf.

El *replay* es una clase `FakeSession` de ~20 líneas con la misma interfaz que
`requests.Session`: mapea URL → archivo grabado. Sin `responses`, sin `vcrpy`.

### 13.3 Catálogo adversarial

Cada línea es un test que **debe** existir. El criterio de aprobado es *el sistema no
miente*: o extrae bien, o marca el problema. Reventar es aceptable solo si es ruidoso.

**Extracción — el corazón del riesgo**

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 1 | `no está comprendido en la causal … literal b)` | 136b **NO** aparece en motivos |
| 2 | Mismo párrafo con `no` a 40 caracteres de distancia (frase larga) | sigue detectando la negación |
| 3 | Doble negación: `no es cierto que no esté comprendido` | no adivina: warning y no lo cuenta |
| 4 | Texto sin ninguna tilde (PDF mal codificado) | extrae igual (normalización) |
| 5 | Palabra partida por salto de línea: `irregis-\ntrabilidad` | extrae igual |
| 6 | 3 opositores en una resolución | llena 2, avisa del tercero en `Observaciones` |
| 7 | 5 motivos distintos | genera 5 filas, ninguna duplicada |
| 8 | Motivo repetido dos veces en el texto | 1 sola fila |
| 9 | `parcialmente fundada` | `SI` + warning |
| 10 | Resolución que **concede** en vez de negar | 0 motivos + warning, no inventa |
| 11 | Nombre de opositor con coma, `&`, `S.A.S.` y tildes | nombre completo, sin cortar en la coma |
| 12 | Texto vacío (`""`) | `ExtractedData` vacío + warning, **sin excepción** |
| 13 | Texto de 5 MB de basura aleatoria | termina en < 2 s, sin catastrophic backtracking |
| 14 | Literal inexistente (`literal z)`) | lo registra tal cual, no lo descarta en silencio |
| 15 | Artículo sin literal (`147`, `172`) | motivo `'147'` |

El #13 no es decorativo: varios de los regex del §8 tienen cuantificadores anidados y
son candidatos a ReDoS. El test corre con un **timeout duro** y falla si se excede.

**Descarga y red**

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 16 | `GetFile` devuelve el PNG de 828 bytes con HTTP 200 | detectado por magic bytes → reintento → error explícito |
| 17 | PDF truncado a la mitad | error del expediente, no corrupción silenciosa de la salida |
| 18 | Respuesta de 0 bytes | idem |
| 19 | HTML sin la tabla `gvDocuments` | error del expediente, el resto sigue |
| 20 | HTML con la tabla vacía | 0 documentos + warning |
| 21 | Timeout / connection reset | reintenta 3 veces, luego error del expediente |
| 22 | HTTP 429 | pausa y avisa; **no** martillea |
| 23 | Archivo ya en `temp\` pero corrupto | lo re-descarga en vez de confiar en él |
| 24 | Sin permiso de escritura en `temp\` | error claro al usuario, no traza cruda |

**Excel de entrada**

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 25 | Excel de 0 filas de datos | corrida vacía limpia, no división por cero en el progreso |
| 26 | Fórmula HYPERLINK malformada | fila descartada con warning que **nombra la fila** |
| 27 | Celda con texto plano en vez de fórmula | se acepta si contiene un expediente válido |
| 28 | Expediente duplicado en el reporte | se descarga una vez, se emiten las dos filas |
| 29 | Archivo que no es xlsx (renombrado) | error claro, no traza de openpyxl |
| 30 | Excel con 10 000 filas sintéticas | el lector no revienta la memoria (test de perf, `read_only`) |

**Pipeline y concurrencia**

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 31 | `Detener` a mitad de la corrida | Excel parcial escrito, hilos terminan, sin datos a medias |
| 32 | Un expediente lanza excepción no prevista | los otros 999 terminan; el fallo queda en el log |
| 33 | Dos corridas simultáneas | la segunda se rechaza con mensaje, no corrompe el estado |
| 34 | Contadores bajo 8 hilos | expedientes/PDFs/registros cuadran exactamente (sin *race*) |

**Salida**

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 35 | Salida de 0 registros | archivo con solo cabeceras, válido al abrirlo |
| 36 | Texto con caracteres ilegales para xlsx (`\x00`, control chars) | se sanea, openpyxl no revienta |
| 37 | Descripción de >32 767 caracteres (límite de celda) | se trunca con marca, no error |
| 38 | El xlsx generado se relee | `reader` lo abre y los valores coinciden (ida y vuelta) |

**Windows — `tests/test_windows.py`, la capa donde vive el usuario**

Se salta con `@pytest.mark.skipif(os.name != "nt")`, pero es **obligatoria antes de entregar**
(Fase 8). Cada uno de estos es un fallo real que solo aparece en la máquina del usuario.

| # | Ataque | Comportamiento exigido |
|---|---|---|
| 39 | Escribir el `.xlsx` de salida mientras está **abierto en Excel** | mensaje claro "cierre el archivo e intente de nuevo", no `PermissionError` crudo |
| 40 | Leer un archivo de texto sin `encoding=` explícito | **no debe existir ese código**: test que falla si algún `open()` omite el encoding |
| 41 | Expediente `SD2022/0000017` → nombre de archivo | la `/` se convierte en `-`; el archivo se crea de verdad en NTFS |
| 42 | Ruta de salida con acentos y espacios (`C:\Users\José\Mis documentos\`) | funciona |
| 43 | Ruta total > 260 caracteres | error explícito, no truncamiento silencioso |
| 44 | El `.exe` empaquetado arranca y encuentra sus carpetas | `utils/rutas.py` resuelve bien con `sys.frozen` (test manual sobre el build) |

### 13.4 Property-based (hypothesis), acotado

Solo dos objetivos, donde el espacio de entrada es grande y las reglas son claras:

- `utils/text.normalizar` — idempotente (`f(f(x)) == f(x)`), nunca lanza, nunca devuelve
  `None` para `str`, y no altera el conteo de expedientes detectables.
- Parseo de listas de literales (`a)`, `a) y b)`, `a), b) y h)`) — el resultado siempre es una
  lista de literales válidos, ordenada como en el texto y sin duplicados.

No se usa hypothesis contra el extractor completo: generar prosa jurídica aleatoria no prueba
nada útil. Ahí manda el catálogo del §13.3, que sí modela fallos reales.

### 13.5 Cobertura y ejecución

- Objetivo: **≥ 90 % en `parser/`** (donde está el riesgo) y ≥ 80 % global.
  La cobertura es un piso, no la meta: los 44 casos de arriba importan más que el número.
- Un caso de la lista sin test = fase incompleta. No se avanza de fase.
- **La suite se corre en los dos lados.** En WSL durante el desarrollo, porque es más rápido;
  en Windows antes de cada `.exe`, porque es donde vive el usuario. Los casos 39–44 solo
  cuentan del lado Windows.

```bash
# desarrollo, desde WSL
pytest -q                      # suite completa, sin red
pytest -m live                 # humo contra SIPI (opt-in)
pytest --cov=app --cov-report=term-missing

# antes de empaquetar, desde Windows (o desde WSL vía interop)
cmd.exe /c "pushd \\wsl.localhost\Ubuntu\home\fabio\perso\HCAutomation && .venv-win\Scripts\pytest -q"
```

---

## 14. Documentación

Dos archivos, con públicos distintos y sin solaparse.

### 14.1 `DOCUMENTACION.md` — archivo único

Todo lo que un humano necesita, en un solo documento, tal como se pidió. Secciones:

1. **Qué hace** — en tres frases, sin jerga.
2. **Instalación** — descomprimir el zip y doble clic. Con capturas de SmartScreen y de qué
   hacer si el antivirus lo bloquea.
3. **Uso diario** — dónde poner el Excel, qué botón pulsar, dónde aparece el resultado.
4. **Qué significa cada columna de la salida** — incluida la regla de una fila por motivo.
5. **Cómo leer `Observaciones`** — qué warnings hay y qué hacer con cada uno. Es la sección
   que evita que la persona confíe ciegamente en el resultado.
6. **Arquitectura** — con los diagramas de §14.3.
7. **Decisiones técnicas y por qué** — resumen del plan, no el plan entero.
8. **Problemas frecuentes** — antivirus bloquea el .exe, SmartScreen, SIPI caído, el Excel de
   salida está abierto, corrida interrumpida, proxy corporativo.
9. **Para desarrolladores** — correr desde el fuente, correr los tests, reconstruir el `.exe`,
   dónde tocar los regex.

Un solo archivo, con índice al principio. Nada de `docs/` con doce markdown.

### 14.2 `ESTADO.md` — trazabilidad META para agentes

Archivo pensado para que **un agente que abre el proyecto en frío lea solo esto** y sepa qué
pasa y dónde seguir. No documenta el código (para eso está el código); documenta el
*contexto que no está en el código*.

Estructura fija:

```markdown
# ESTADO

## Qué es esto            (2 frases + enlace a plan.md y DOCUMENTACION.md)
## Estado actual          Fase N de 10. Qué funciona hoy, qué no.
## Siguiente paso         Lo primero que haría alguien que entra ahora.
## Decisiones tomadas     Tabla: decisión | fecha | por qué | dónde vive en el código
## Decisiones revertidas  Qué se probó y se descartó, y por qué. Evita repetir el error.
## Contexto no obvio      Lo que sorprende al leer el código: la fórmula HYPERLINK, el PNG
                          de 828 bytes, la negación léxica, el alias de opositores manual.
## Deuda y limitaciones   Lo que se sabe que falta o falla, sin maquillar.
## Bitácora               Una línea por sesión: fecha · qué se hizo · qué quedó abierto.
```

Reglas:

- Se actualiza **al cerrar cada fase**, en el mismo commit que el código de la fase.
  Un `ESTADO.md` desactualizado es peor que no tenerlo, porque miente con autoridad.
- Nunca contiene fragmentos de código ni instrucciones de uso. Eso vive en los otros dos.
- Fechas absolutas, nunca "la semana pasada".

### 14.3 Diagramas

Se generan como **imagen** (SVG + PNG), siguiendo `guia-diagramas-imagen.md`, mediante
`docs/gen_diagramas.py`. Dos diagramas:

1. **Arquitectura** — los 5 módulos del pipeline y sus dependencias, con el `.exe` y sus
   carpetas (`salida\`, `temp\`) como banda envolvente.
2. **Flujo de un expediente** — desde la fila del Excel hasta las N filas de salida, marcando
   dónde puede fallar.

Se respetan las invariantes de la guía, que son las que hacen que el PNG no salga roto:

- `font-family="DejaVu Sans, Arial, sans-serif"` — es la única fiable para cairosvg.
- Escapado XML obligatorio (`&lt;`, `&amp;`) y acentos como `\uXXXX` en el fuente Python.
- Layout por niveles topológicos, aristas largas ruteadas ortogonalmente por canal libre.
- Rasterizado con `cairosvg` a `scale=2.0`.
- **Validación visual obligatoria**: abrir el PNG y revisar el checklist del §8 de la guía
  (sin recortes, sin texto desbordado, sin flechas sobre tarjetas).

`cairosvg` va en `requirements-dev.txt`, no en la imagen de producción: los diagramas se
generan una vez y se versionan como archivos.

---

## 15. Riesgos conocidos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| La SIC cambia la redacción de las resoluciones | Alto | Todos los regex aislados en `parser/patterns.py`; suite de tests con PDFs reales |
| `GetFile.aspx` devuelve PNG por sesión expirada | Alto | Validación de magic bytes + renovación de sesión y reintento |
| Rate limiting / bloqueo por IP | Alto | 4 hilos, delay, backoff, pausa ante 429; reanudación desde `temp\` |
| Resolución escaneada sin capa de texto | Medio | Se detecta (< 500 chars) y se marca para revisión manual; no se inventa dato |
| Nombre corto de opositor no derivable | Medio | Diccionario sembrado desde la referencia + sugerencia marcada |
| Corrida de ~1 hora interrumpida | Medio | Cache en `temp\`; reejecutar retoma donde iba |
| La referencia tiene errores manuales | Medio | Se documenta; la validación se hace por muestreo, no por diff exacto |
| **El antivirus bloquea el `.exe`** | Alto | Documentado desde el día 1; `--onedir` reduce la probabilidad; salidas: excepción en TI o firma con certificado |
| ReDoS en los regex de §8 con un PDF anómalo | Medio | Test #13 con timeout duro; cuantificadores acotados (`{3,120}`) en vez de `.*` |
| Proxy corporativo entre el PC y `sipi.sic.gov.co` | Medio | `requests` respeta `HTTP_PROXY`/`HTTPS_PROXY`; error explícito en la ventana, no cuelgue mudo |
| Encoding cp1252 de Windows rompe acentos | Alto | `encoding="utf-8"` explícito en **todo** `open()`; test #40 falla si alguno lo omite |
| El usuario tiene el Excel de salida abierto en Excel | Medio | Se detecta y se pide cerrarlo (test #39); nunca se pierde la corrida |
| PyInstaller cambia de versión y el binario deja de funcionar | Bajo | Versión fijada (`==6.21.0`) en `requirements-dev.txt` |
| SIPI caído | Bajo | Reintentos con backoff; errores por expediente, no aborto global |
| Windows del usuario sin x64 (ARM) | Bajo | Se detecta al entregar; habría que compilar aparte |

---

## 16. Casos borde

1. **`no está comprendido en la causal … literal b)`** — negación léxica. Test obligatorio.
2. Expediente con **0 documentos** de resolución (solo TM6 o anexos) → fila con warning.
3. **3+ opositores** — el layout solo tiene 2. Se llenan los dos primeros y el tercero en
   adelante se menciona en `Observaciones`. **No se generan filas ni columnas extra**
   (decisión confirmada, §18).
4. **Artículo sin literal** (`147`, `154`, `172`) → motivo `'147'`, sin sufijo.
5. `parcialmente fundada` → `SI` + warning.
6. **Dos documentos del mismo tipo** (dos TM9) → se usa el de fecha más reciente.
7. Marca con paréntesis en el nombre → el regex de naturaleza usa lista cerrada de valores,
   no `.*`.
8. Expediente que aparece **dos veces** en el reporte → se procesa una vez, se emite dos.
9. Filas de pie de página o vacías al final del reporte → se filtra por patrón de expediente.
10. Palabras partidas por salto de línea en el PDF → se normaliza antes de aplicar regex.
11. `Fundada` para el opositor 2 cuando la resolución solo nombra a uno → queda vacío.
12. Nombres con `&`, tildes o comas internas → el corte del regex usa lookahead a `.`/`ARTÍCULO`.
13. Descarga parcial por corte de red → escritura atómica `.part` + rename.

---

## 17. Plan de implementación por fases

Cada fase deja algo ejecutable y verificable. **Ninguna fase se cierra sin sus tests y sin
actualizar `ESTADO.md` en el mismo commit.** No se avanza sin validar la anterior.

**Fase 0 — Andamiaje y cadena de construcción**
`requirements*.txt`, `app/config.py`, `app/models.py`, `app/utils/`, `hcauto.spec`,
`construir_exe.bat`, `ESTADO.md` inicial.
Verificación: `python -m app` abre una ventana vacía en WSL, `pytest` corre (aunque haya 0
tests), y `construir_exe.bat` **produce un `.exe` que abre esa misma ventana vacía**.
*El empaquetado se prueba en la fase 0, no al final*: descubrir en la fase 10 que PyInstaller
no encuentra un módulo o que el antivirus bloquea el binario es la forma clásica de perder
una semana. Mejor que falle cuando no hay nada que perder.

**Fase 1 — Lectura del Excel**
`app/excel/reader.py`. Parseo de la fórmula HYPERLINK.
Tests: casos 25–30 del §13.3 + lectura del reporte real completo.
Verificación: 987 `SourceRow` con URL y expediente correctos.

**Fase 2 — Scraping**
`app/downloader/session.py` + `scraper.py`. Sin descargar aún.
Antes de escribir el parser se ejecuta `tests/make_fixtures.py` para **grabar** las respuestas
HTTP reales; a partir de aquí la suite es offline.
Tests: casos 19, 20, 21 del §13.3.
Verificación: para 5 expedientes reales, lista los documentos con su tipo.

**Fase 3 — Descarga**
`app/downloader/files.py`. Validación de PDF, nombres, cache.
Tests: casos 16, 17, 18, 22, 23, 24 — incluido el PNG de 828 bytes.
Verificación: descarga los PDFs de 5 expedientes; los 5 abren; reejecutar no baja nada.

**Fase 4 — Extracción** ← *la fase larga y la de mayor riesgo*
`app/parser/`. Se construye contra los PDFs de la fase 3.
Tests: **los 15 casos de extracción del §13.3, completos**, más las dos propiedades de §13.4.
Verificación: cobertura ≥ 90 % en `parser/`; el caso de negación léxica en verde.

**Fase 5 — Escritura del Excel**
`app/excel/writer.py` + expansión de filas.
Tests: casos 35–38, incluida la ida y vuelta (escribir → releer).
Verificación: salida de 20 expedientes contrastada a mano contra la referencia.

**Fase 6 — Orquestación**
`app/pipeline.py`: hilos, contadores, cancelación.
Tests: casos 31–34, con 8 hilos para forzar condiciones de carrera.
Verificación: corrida por CLI sobre 50 expedientes reales.

**Fase 7 — Interfaz gráfica**
`app/gui.py`.
Verificación: corrida completa desde la ventana, incluido `Detener` a mitad y cerrar la
ventana con la corrida activa.

**Fase 8 — E2E y prueba en frío en Windows**
`tests/test_e2e.py` con los mini-Excel de 1 y 2 casos, offline.
`tests/test_windows.py` (casos 39–44) corriendo del lado Windows.
Verificación adicional: construir el `.exe`, **copiar `dist\ExtraccionSIC` a otra ruta con
espacios y acentos, y ejecutarlo ahí desde cero**. Si eso falla, el entregable no sirve.

**Fase 9 — Documentación**
`DOCUMENTACION.md` completo, diagramas generados con `docs/gen_diagramas.py` y validados
visualmente, `ESTADO.md` al día.
Verificación: alguien que no ha visto el proyecto sigue el documento y logra una corrida.

**Fase 10 — Corrida real y ajuste**
987 expedientes. Revisar `Observaciones`, afinar regex, sembrar `alias.json`.
Reconstruir el `.exe` final y entregarlo comprimido.

Estimación de la corrida completa: ~987 expedientes × ~3 PDFs, 4 hilos → **40–70 minutos**.

---

## 18. Decisiones confirmadas

Respuestas del 2026-08-06, ya incorporadas al plan:

| # | Pregunta | Decisión | Dónde queda |
|---|---|---|---|
| 1 | ¿Fusionar `MOTIVO 1/2` en `MOTIVO Negación` + `Motivo #`, `Motivos totales`, `Observaciones`? | **Sí, como POC.** Si no convence, se revierte al layout de 18 columnas | §9. El writer deja el layout viejo detrás de una constante `LAYOUT` en `config.py`, para que revertir sea cambiar un valor, no reescribir el módulo |
| 2 | Expedientes sin motivo detectado | **Fila con la celda en blanco** (no se excluyen) | §9 |
| 3 | Más de 2 opositores | **No se agrega nada**: la salida se queda con 2. El resto solo se menciona en `Observaciones` | §16, caso 3 |
| 4 | ¿El reporte de entrada siempre trae el mismo formato? | **Sí**, cabeceras en la fila 11 | §4. Aun así el lector valida y falla con mensaje claro si cambia (caso 29) |
| 5 | ¿`errores.xlsx` aparte? | **No.** Basta la columna `Observaciones` | §9 |
| 6 | Trazabilidad para agentes | **`ESTADO.md`**, actualizado al cerrar cada fase | §14.2 |

Adicionales, revisión 2:

| Tema | Decisión |
|---|---|
| Documentación | **Un solo** `DOCUMENTACION.md` para humanos + `ESTADO.md` para agentes. Nada más (§14) |
| Diagramas | Imagen SVG+PNG generada con `docs/gen_diagramas.py` siguiendo `guia-diagramas-imagen.md` (§14.3) |
| Pruebas | Datos reales, replay offline, catálogo adversarial de 44 casos. **Las aserciones no se ablandan para que pasen** (§13) |

Adicionales, revisión 3 (2026-08-06):

| Tema | Decisión |
|---|---|
| Empaquetado | **`.exe` de Windows con PyInstaller `--onedir`**. Copiar carpeta y doble clic; sin instalar nada (§12) |
| Docker | **Descartado.** No puede producir el entregable y habría escondido los bugs propios de Windows (§12.5) |
| Interfaz | **Vuelve tkinter**: ventana de escritorio con diálogos nativos de archivo (§11) |
| `lxml` | **Fuera.** Se usa `html.parser` de la stdlib para que ninguna dependencia tenga binario (§5) |
| Entorno de build | Python 3.14.6 de Windows + PyInstaller 6.21.0, **verificados** en la máquina de desarrollo (§12.2) |
| Dónde vive el código | Sigue en WSL; solo la compilación corre del lado Windows vía `pushd` a `\\wsl.localhost\...` (§12.2) |
| Pruebas en Windows | Nueva capa obligatoria, casos 39–44: encoding, bloqueo de archivo, rutas (§13.3) |
