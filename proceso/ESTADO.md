# ESTADO

## Qué es esto

Automatización de un proceso manual: leer un Excel de expedientes de la SIC, descargar los
PDFs de cada expediente desde SIPI, extraer datos de las resoluciones y generar un Excel
nuevo. El diseño completo está en [plan.md](plan.md); el manual de uso, en
[DOCUMENTACION.md](DOCUMENTACION.md).

## Estado actual

**Fase 10 de 10 — cerrada (2026-08-07). El proyecto está terminado.** La aplicación corrió
el reporte completo de 987 expedientes contra SIPI y llega a **0 errores**.

Resultado de la corrida definitiva, `salida_v5.xlsx`:

| | |
|---|---|
| Expedientes | 987 |
| Filas generadas | **1011** (48 de ellas por los 24 expedientes con dos motivos) |
| PDFs descargados | 2416 (620 MB) |
| Errores | **0** |
| Filas con «Observaciones» | 182 (**18 %**) — el trabajo manual que queda |
| Naturaleza extraída | 95 % · **Motivo de negación: 96 %** |

Funciona hoy:
- **`python -m app` (o el `.exe`) abre la ventana de verdad**: elegir Excel y carpeta,
  hilos, «Reusar PDFs», Iniciar / Detener, barra de progreso, los cinco contadores,
  el registro en vivo y «Abrir carpeta de salida».
- `ExtraccionSIC.exe --autoprueba` no abre ventana: importa todo, comprueba que las carpetas
  de trabajo son escribibles, escribe `autoprueba.txt` y sale con 0 o 1. `construir_exe.bat`
  la ejecuta al terminar y falla la construcción si algo no cuadra.
  Con `--red` añade una petición HTTPS real contra SIPI. **Verificado sobre el `.exe`:**
  `red OK (200) hacia https://sipi.sic.gov.co/sipi/` — los certificados de `certifi` sí
  viajan dentro del paquete.
- **Prueba en frío superada.** Se copió `dist\ExtraccionSIC` a
  `C:\Users\femur\Escritorio de José\Extracción SIC ñ\` —espacios, tildes y una ñ— y el
  `.exe` arrancó ahí sin nada del entorno de desarrollo: `base_dir` resolvió a esa carpeta,
  los 10 módulos importaron y `salida\` y `temp\` se crearon con los acentos intactos.
- `app/excel/reader.py` lee el reporte real: **987 filas, 0 avisos**, con URL y expediente
  sacados de la fórmula HYPERLINK.
- `app/downloader/session.py` + `scraper.py`: de la URL del Excel a la lista de documentos
  clasificados (TM9 / TM128 / TM6 / APELACION / OTRO).
- `app/downloader/files.py`: descarga validada a `salida\soportes\<expediente>\` (un
  subdirectorio por caso), con caché, escritura atómica y migración automática de los
  PDFs que las versiones anteriores dejaron en `temp\` plano.
- `app/parser/`: `pdf_text.py` (PDF → texto de una línea, sin cabeceras de página),
  `patterns.py` (todos los regex, cada uno con el texto real contra el que se verificó) y
  `extractor.py` (naturaleza, marca, oposición, opositores, fundadas, motivos, avisos).
  Verificado contra las tres resoluciones reales grabadas:

  | Expediente | Naturaleza | Opositores | Motivos |
  |---|---|---|---|
  | SD2022/0000017 | Nominativa | — (sin oposición) | `136a` |
  | SD2022/0001545 | Mixta | Grupo Diagnostico S.A. Dimed S.A. (`136a`,`136b`, fundada SI) | `136a` — **`136b` descartado por la negación** |
  | SD2022/0097089 | Mixta | NESTLE, KRAFT (ambas SI) | `136a`, `136h` |

- `app/excel/writer.py`: expansión de filas (`expandir`) y escritura del `.xlsx`, con los dos
  layouts (`poc` de 20 columnas, `clasico` de 18) y el diccionario de nombres cortos.
  Desde las correcciones post-entrega (2026-08-07): enlace `https://` azul y subrayado,
  cabeceras amarillas en las columnas que produce el programa, bordes en todas las celdas
  y «Descripción de Productos y Servicios» como última columna.
  Salida real de los tres expedientes grabados, contrastada a mano:

  ```
  SD2022/0000017  MALTAVITAN           Nominativa  Oposición No   136a          (1 de 1)
  SD2022/0001545  idime                Mixta       Oposición Sí   136a          (1 de 1)
                  Opositor: Grupo Diagnostico S.A. Dimed S.A. · 136a, 136b · fundada SI
                  Observaciones: «dice expresamente que NO está comprendido en 136b»
  SD2022/0097089  BASIC FOODING MILKO  Mixta       Oposición Sí   136a          (1 de 2)
  SD2022/0097089  BASIC FOODING MILKO  Mixta       Oposición Sí   136h          (2 de 2)
                  Opositores: SOCIETE DES PRODUITS NESTLE SA · KRAFT FOODS SCHWEIZ HOLDING GMBH
  ```

- `app/pipeline.py`: `ejecutar()` recorre el reporte con `ThreadPoolExecutor`, una sesión por
  hilo, contadores con cerrojo, cancelación por `threading.Event` y una sola corrida a la vez.
  Contrastado contra el archivo de referencia sobre 50 expedientes: **45 motivos coinciden,
  4 difieren**, y las 4 son errores del propio archivo de referencia — celda `MOTIVO` vacía
  en expedientes cuya parte resolutiva dice literalmente «Negar el registro», verificado uno
  a uno en el PDF.

  Las cinco pasadas sobre los 987, en orden, muestran para qué sirvió cada arreglo:

  | Pasada | Qué cambió | Duración | PDFs | Errores |
  |---|---|---|---|---|
  | 1 | sin reintentos | 37 min | 2259 | 19 |
  | 2 | reintento por contenido | 66 min | 2416 | 10 |
  | 3 | repetición, sin caché de página | 33 min | 23 | 12 |
  | 4 | con caché de página | 31 min | 0 | 5 |
  | 5 | repetición | **2,8 min** | 0 | **0** |

  La 3ª es la interesante: recuperó los 10 expedientes caídos pero perdió 12 nuevos, porque
  volvía a pedir las 987 páginas. Ver el punto 33 de «Contexto no obvio».

- `tests/test_e2e.py` recorre el proceso entero sin red, con los tres mini-Excel de
  `tests/data/` (recortes del reporte real) y las respuestas grabadas: 1 caso, 2 casos y el
  multimotivo, incluida la reanudación desde caché y qué sale cuando no hay red.
- `tests/test_windows.py` cubre los casos 39–43 y **solo corre en Windows**: el `.xlsx`
  retenido con `FileShare 'None'` igual que hace Excel, el archivo de solo lectura, la barra
  del expediente sobre NTFS, una corrida completa en
  `…\José Ramírez\Mis documentos\Extracción SIC\` y una ruta de más de 300 caracteres.
- `DOCUMENTACION.md`: un solo archivo con las nueve secciones del §14, escrito para el
  usuario final. La sección larga es la 5, «Cómo leer Observaciones»: los 17 mensajes que
  puede dejar el programa, qué significa cada uno y qué hacer con él.
- `docs/gen_diagramas.py` genera `arquitectura` y `flujo` en SVG y PNG siguiendo
  `guia-diagramas-imagen.md`. Los cuatro archivos están versionados.
- `pytest` corre: **423 pruebas** — en WSL 411 + 12 omitidas (las de Windows), en Windows
  419 + 4 omitidas (las de permisos POSIX). Tarda ~130 s: las pruebas de concurrencia bajan
  y parsean PDFs reales decenas de veces, a propósito. **Cobertura global 96 %**: `excel/writer.py`,
  `utils/text.py` y `utils/logging_setup.py` 100 %, `pipeline.py` 98 %,
  `parser/extractor.py` 95 %, `patterns.py` 97 %, `pdf_text.py` 100 %,
  `downloader/` 95–100 %, `gui.py` 90 %.
- Las 15 pruebas de la ventana **abren un `Tk()` de verdad** y accionan los botones por
  código: corrida entera, Detener a mitad, fallo del pipeline, cierre con corrida activa.
  Corren en los dos sistemas — resulta que WSLg sí trae `tkinter` y un display.
- `pytest -m live` (3 pruebas, opt-in) confirma contra SIPI real que la página y la tabla
  siguen teniendo la forma esperada.
- `construir_exe.bat` produce `dist\ExtraccionSIC\ExtraccionSIC.exe` (30 MB), lo copia a
  `%USERPROFILE%\ExtraccionSIC` y **le pasa la autoprueba**. Verificado empaquetado:
  los 10 módulos importan, `base_dir` resuelve a la carpeta del `.exe`, y `salida\` y
  `temp\` son escribibles. **Desde una ruta UNC no arranca** — ver punto 10.

- `alias.json`: 139 opositores sembrados desde el archivo de referencia con
  `sembrar_alias.py`. Va **junto al `.exe`**, no dentro de `_internal\`, para poder ampliarlo
  a mano; `construir_exe.bat` lo copia.

## Siguiente paso

**Nada obligatorio: el proyecto está entregable.** Lo que queda es opcional y está en
«Deuda y limitaciones». Por orden de valor:

1. **Bajar el 18 % de filas con «Observaciones»**, que es el trabajo manual que sigue
   habiendo. El grupo más grande son 81 avisos de «no se pudo determinar en qué artículos
   fundó su oposición»: son formas de redacción que `OPOSICION` todavía no cubre. Cada una
   se arregla mirando el PDF y ampliando un patrón de `patterns.py`.
2. **La coma de `artículo 136, literal h)`**, que hoy da `136` en vez de `136h`. Salen 3
   filas así en los 987.
3. Ampliar `alias.json` a medida que aparezcan opositores nuevos.

## Decisiones tomadas

| Decisión | Fecha | Por qué | Dónde vive |
|---|---|---|---|
| Entregable = `.exe` de Windows (PyInstaller `--onedir`) | 2026-08-06 | El usuario final no es técnico; copiar carpeta y doble clic, sin instalar nada | `hcauto.spec`, `construir_exe.bat` |
| GUI en tkinter | 2026-08-06 | Diálogos nativos de archivo; va en la stdlib y PyInstaller la empaqueta sin configurar nada | `app/gui.py` |
| `requests` + `BeautifulSoup`, sin navegador | 2026-08-06 | El HTML de `Browse.aspx` ya trae los enlaces a los PDFs; Selenium sería 10x más lento y una dependencia enorme | Fase 2 |
| Ninguna dependencia con binario | 2026-08-06 | Empaquetado sin compilador ni DLLs sueltas. Por eso `html.parser` en vez de `lxml` | `requirements.txt` |
| Rutas de trabajo junto al `.exe`, no en `%APPDATA%` | 2026-08-06 | Copiar la carpeta se lleva caché y resultados; borrarla no deja rastros | `app/utils/rutas.py` |
| Salida: una fila por motivo de negación (POC) | 2026-08-06 | Requisito nuevo del usuario. Reversible con `config.LAYOUT = "clasico"` | `app/config.py` |

## Decisiones revertidas

| Se probó | Se descartó porque | Fecha |
|---|---|---|
| **Docker** para desarrollo y distribución | Un contenedor ejecuta un proceso Linux y PyInstaller no cross-compila: no puede producir el entregable. Peor aún, testear en Linux habría escondido los bugs propios de Windows (cp1252, bloqueo de archivo de Excel, rutas) | 2026-08-06 |
| **Interfaz web** con `http.server` | Solo existía para sobrevivir al contenedor. Sin contenedor, una ventana de escritorio le resulta más familiar al usuario | 2026-08-06 |
| **MarkItDown** para leer los PDFs | Envuelve pdfminer y produce Markdown; estos PDFs no tienen estructura que un Markdown preserve mejor. `pypdf` ya extrae texto limpio con tildes | 2026-08-06 |
| **`lxml`** como parser de HTML | Única dependencia con binario compilado; complicaba el empaquetado a cambio de una velocidad irrelevante frente al tiempo de red | 2026-08-06 |

## Contexto no obvio

Cosas que sorprenden al leer el código o al trabajar con SIPI, todas verificadas contra el
sitio real:

1. **La columna A del Excel de entrada no tiene hyperlink.** Tiene una fórmula `HYPERLINK`.
   `cell.hyperlink` devuelve `None` y quien no lo sepa concluye que el archivo está mal.
2. **Sin cookies, `View.ashx` entra en un bucle de redirecciones infinito** (curl se rinde
   a los 50 saltos, exit 47). Con una sesión que guarde `ASP.NET_SessionId` resuelve en 2.
   Por eso toda la navegación de un expediente comparte sesión.
2b. **`GetFile.aspx` responde HTTP 200 con un PNG de 828 bytes al arrancar una corrida
   grande.** Estuvo dos fases marcado como «visto una vez, no reproducible». **La corrida de
   los 987 lo reprodujo y midió**: 135 respuestas PNG, 50 expedientes afectados, **todas
   dentro de los primeros 26 segundos** y ni una sola después. No es la cookie de sesión —esa
   hipótesis se descartó en la Fase 2— sino el sitio calentando o limitando el ritmo al
   principio de una ráfaga.
   Dos consecuencias, las dos en el código: **validar el magic `%PDF-`**, porque el status
   code miente; y **reintentar** con esperas de 3, 8 y 20 segundos (`ESPERAS_CONTENIDO_SEG`),
   porque los reintentos de `urllib3` no cubren esto: para ellos un HTTP 200 es un éxito.
   Las esperas suman 31 s a propósito, más que los 26 observados. La respuesta real está
   guardada en `tests/fixtures/http/respuesta_no_pdf.bin`.
2c. **El puerto 80 del sitio no responde** y el reporte exporta las URLs con `http://`:
   cada expediente se colgaría hasta el timeout. `session.forzar_https()` reescribe el
   esquema. Esto costó un timeout de 60 s en la primera grabación de fixtures.
3. **`View.ashx?<id>` redirige a `Browse.aspx?sid=<sid>`** y ese HTML ya trae los enlaces
   `GetFile.aspx` de todos los documentos. Por eso no hace falta navegador.
4. **`no está comprendido en la causal … literal b)`** — la negación léxica. Un regex
   ingenuo marca 136b como motivo de negación cuando el texto dice lo contrario. Confirmado
   en el expediente `SD2022/0001545`. Es el error más probable de todo el sistema.
5. **`sin_tildes()` preserva la ñ** a propósito. Sin eso, `MUÑOZ` y `MUNOZ` dan la misma
   clave y se funden dos opositores distintos. Lo encontró un test, no una revisión.
6. **El "Nombre corto" del opositor no es derivable por regla** (`RED BULL GMBH` → `RedBull`).
   Es criterio humano. Se sembrará un diccionario con los 133 alias que ya existen en
   `Negacion marcas con información extra.xlsx`, y lo que no esté ahí sale marcado como
   sugerencia.
7. **El archivo de referencia tiene errores manuales** (`SI`/`Si`, `NO `/`no`, un expediente
   negado con `MOTIVO 1` vacío). Define el formato de salida, **no** es un oráculo de
   exactitud: no se puede validar con un diff exacto contra él.
8. **El Python 3.11 de la Microsoft Store no sirve** para empaquetar: corre con rutas
   redirigidas. Se usa el 3.14.6 de python.org (`py -3.14`).
9. **Compilar desde WSL funciona** con `pushd \\wsl.localhost\Ubuntu\...`, que mapea `Z:`.
   El código no sale de WSL; solo la construcción corre del lado Windows.
10. **El `.exe` no arranca desde una ruta UNC.** Doble clic sobre
    `\\wsl.localhost\Ubuntu\...\dist\ExtraccionSIC\ExtraccionSIC.exe` da un diálogo de
    Windows: *«no encuentra el archivo "\"»*. El bootloader de PyInstaller no puede usar un
    directorio UNC como directorio de trabajo. Desde una unidad mapeada (`Z:`) o desde una
    ruta local (`C:\...`) funciona sin problema. Por eso `construir_exe.bat` copia el
    resultado a `%USERPROFILE%\ExtraccionSIC` al terminar. **No afecta al usuario final**,
    que recibe un zip y lo descomprime en su disco local.
11. **La cabecera de página cae dentro del nombre del opositor.** En `SD2022/0001545` el
    texto crudo dice literalmente `la sociedad Grupo Resolución N° 78472 Ref. Expediente N°
    SD2022/0001545 Página 21 de 21 Diagnóstico S.A. Dimed S.A.`. Por eso
    `pdf_text.quitar_cabeceras()` corre **antes** que cualquier regex: sin eso el opositor
    sale partido o con la cabecera pegada. Hay un test de regresión dedicado.
12. **El nombre del opositor no se puede cortar por coma ni por punto.** El 18 % de los
    nombres reales llevan coma (`JHO INTELLECTUAL PROPERTY HOLDINGS, LLC.`) y casi todos
    llevan puntos (`S.A.`). Cortar por cualquiera de los dos parte un opositor en dos.
    `limpiar_nombre()` corta por coma solo si lo que sigue **no** es un sufijo societario,
    y nunca quita el punto final.
13. **El regex `OPOSICION` tenía un acantilado de rendimiento.** Su prefijo
    `(?P<antes>[^;:]{0,160}?)` se reintentaba en cada posición del texto: 11,5 s sobre 5 MB.
    La solución no fue tocar el patrón sino **anclarlo**: `extraer_opositores()` busca
    primero el literal barato `presentó oposición` y solo aplica el patrón completo a una
    ventana de ±180/400 caracteres alrededor. La suite de extracción bajó de 16,9 s a 1,5 s.
    Si alguien "simplifica" ese anclaje, el sistema se cuelga con un PDF grande.
14. **Un subrogado suelto (`\ud800`) produce un `.xlsx` que no se puede volver a abrir.**
    `openpyxl` lo guarda sin protestar y al releer el parser XML muere con *«reference to
    invalid character number»*. `pypdf` los emite con PDFs de codificación rara, así que el
    caso llega solo. `sanear_para_excel` los filtra junto con los caracteres de control.
15. **Las celdas se escriben con `data_type = "s"` a propósito.** Sin eso, un texto que
    empiece por `=`, `+`, `-` o `@` (una marca llamada `+PLUS`, por ejemplo) se guarda como
    **fórmula** y Excel la evalúa al abrir el archivo.
16. **El diccionario de alias se indexa por `clave_comparacion`, no por el nombre crudo.**
    Pasar el JSON tal cual a `escribir()` deja la columna «Nombre corto» vacía **en
    silencio**, que es exactamente el fallo que no se nota hasta el final. Para eso está
    `writer.normalizar_alias()`.
17. **El expediente se escribe como texto con hyperlink, no como `=HYPERLINK(...)`.** La
    referencia usa la fórmula porque así la exporta SIPI, pero una fórmula sin valor cacheado
    se lee como `None` desde cualquier script — y esta salida está pensada para releerse.
18. **El archivo `.part` lleva un sufijo único (`uuid4`).** El reporte real repite
    expedientes y el pipeline usa hasta 8 hilos: con un `.part` de nombre fijo, el
    `os.replace` de un hilo se lleva el archivo del otro y el segundo muere con
    *«No such file or directory»*. Lo cazó una prueba con 8 hilos y una `Barrier`.
19. **En Windows `os.replace` da «Acceso denegado» si dos hilos reemplazan el mismo
    destino a la vez.** En Linux no pasa: el mismo test pasaba en WSL y fallaba en Windows.
    `_guardar` lo trata como éxito si lo que quedó en disco ya es un PDF completo — ganó
    otro hilo y escribió exactamente el mismo documento. **Este es el tipo de bug que el
    contenedor habría escondido.**
20. **Hay un cerrojo por expediente en el pipeline.** Sin él, dos hilos con la misma fila
    duplicada bajan los mismos PDFs a la vez y ninguno aprovecha la caché. Es también lo que
    hace cierto el aviso del lector, «se descargará una sola vez».
21. **La SIC escribe los plurales entre paréntesis.** `está comprendido en la (s) causal
    (es) de irregistrabilidad` es texto literal de `SD2022/0008040`. Sin admitirlo se perdía
    el único motivo del expediente. El patrón `_CAUSAL` de `patterns.py` los tolera.
22. **Los motivos NO se buscan en todo el documento, sino en la «zona de conclusión».**
    Una resolución transcribe los alegatos del opositor antes de analizarlos, con frases
    idénticas a las de la conclusión —*«se encuentra incurso en la causal … del artículo
    136, literal h)»*— que a veces la Dirección **desmiente** después. Contarlas inventa
    motivos. `extractor.zona_de_conclusion()` acota a los 8 000 caracteres previos a
    «En mérito de lo expuesto» más todo lo que sigue.
    El número está **medido, no supuesto**: sobre 50 resoluciones reales, la frase más
    lejana que sí era de la Dirección estaba a 2 511 caracteres del marcador, y el alegato
    citado más cercano a 41 579; cualquier ventana entre 3 000 y 30 000 da el mismo
    resultado. «En mérito de lo expuesto» aparece exactamente una vez en las 50;
    «Conclusión», que sería el marcador obvio, solo en 16 — por eso no se usa.
    Hay red de seguridad: si acotar deja la fila **sin ningún** motivo, se reanaliza el
    documento entero y se marca la fila en `Observaciones`.
23. **La traza de la excepción no llega nunca a la ventana.** Un `Traceback` en pantalla no
    le dice nada al usuario final y le hace creer que se rompió todo. `FormatoSinTraza`
    la recorta para la cola y la deja intacta en el archivo de log.
    El detalle que no se ve venir: redefinir `formatException` **no basta**, porque el
    handler de archivo ya cacheó la traza en `record.exc_text` y `Formatter` la reutiliza
    sin volver a pasar por ahí. Hay que vaciar `exc_info`, `exc_text` y `stack_info`, y
    devolverlos después: el mismo record lo ven todos los handlers.
24. **`widget["state"]` de tkinter devuelve un objeto de Tcl, no una cadena.**
    `boton["state"] == "normal"` es siempre falso. Hay que envolverlo en `str()`.
25. **`ExtraccionSIC.exe --autoprueba` es la única forma de comprobar el empaquetado.**
    Se compila con `console=False`: un import que PyInstaller no recoja no imprime nada,
    el `.exe` simplemente muere al hacer doble clic. La autoprueba importa los 10 módulos,
    verifica que `salida\` y `temp\` son escribibles, escribe `autoprueba.txt` y sale con
    0 o 1. `construir_exe.bat` la corre y falla la construcción si algo no cuadra.
26. **WSLg trae `tkinter` y un display**, al contrario de lo que decía este archivo hasta
    la Fase 7. Las pruebas de la ventana corren en los dos sistemas.
27. **SIPI tropieza de dos formas distintas bajo carga sostenida, y las dos se curan
    esperando.** Medido en la corrida de los 987 (37 minutos, 2259 PDFs):
    · **140 respuestas PNG** en vez del PDF, concentradas en los primeros 26 segundos
      (50 expedientes) y luego esporádicas hasta el final.
    · **19 expedientes con la página sin la tabla de documentos** (`ErrorScraping`),
      repartidos por toda la corrida. Se reintentaron dos a mano un minuto después y
      **los dos funcionaron**.
    Por eso el reintento por contenido está en los **dos** sitios: `files.py` para el PDF
    y `scraper.py` para la página. Ninguno de los dos casos lo cubre `urllib3`, porque
    los dos llegan con HTTP 200.
28. **Si el `.exe` está abierto, `robocopy` no lo reemplaza y no se queja.** La construcción
    «termina bien» y deja el binario **viejo** en `%USERPROFILE%\ExtraccionSIC`: se prueba
    una cosa creyendo que es otra. Por eso `construir_exe.bat` hace `taskkill /F /IM
    ExtraccionSIC.exe` antes de copiar. Pasó de verdad durante la Fase 8.
29. **El bloqueo de Excel se reproduce sin instalar nada**, con PowerShell:
    `[System.IO.File]::Open($ruta,'Open','ReadWrite','None')`. Ese `FileShare 'None'` es
    exactamente lo que hace Excel al abrir un libro, y provoca el mismo `PermissionError`.
    Está en `tests/test_windows.py`; evita depender de `pywin32`.
30. **`--autoprueba --red` es lo único que detecta que el `.exe` perdió los certificados.**
    Un paquete de PyInstaller sin el bundle de `certifi` importa `requests` perfectamente y
    falla en **todas** las peticiones HTTPS. Verificar imports no lo ve; hay que hacer una
    petición real. Va detrás de `--red` para que la construcción funcione sin internet.
31. **El manual está atado al código por pruebas.** `tests/test_documentacion.py` comprueba
    que cada mensaje citado en la sección 5 sigue existiendo en `app/`, que las 20 columnas
    documentadas son las que escribe el writer, y que ningún enlace del manual está roto.
    Un manual desactualizado miente con autoridad, igual que un `ESTADO.md` viejo.
    Detalle de implementación que costó dos intentos: para buscar los mensajes en el fuente
    hay que quitar los prefijos `f`/`r` de las cadenas —si no, queda una «f» suelta partiendo
    la frase— y comprobar **todos** los trozos de cada mensaje, no solo el más largo. Con la
    primera versión, cambiar «no se cuenta como motivo» en el código no rompía nada.
32. **Los SVG de `docs/` están versionados y hay una prueba que exige que coincidan** con lo
    que genera `gen_diagramas.py`. Además se valida que sean XML bien formado, que usen
    DejaVu y que el lienzo cubra todo lo dibujado — los tres fallos que enumera la guía.

33. **La página del expediente también se guarda en caché** (`<EXP>_pagina.html` en `temp\`),
    no solo los PDFs. Sin eso, **repetir la corrida para recuperar los fallos no converge**,
    y está medido: la 3ª pasada recuperó los 10 expedientes caídos pero volvió a pedir las
    987 páginas y expuso 12 nuevos al mismo tropiezo. Neto: peor.
    Con la caché de página, la 5ª pasada tardó **171 segundos y dio 0 errores** sin tocar
    la red. Esa es la diferencia entre «vuelva a lanzarla» siendo un consejo útil o una
    lotería.
34. **En Windows, comprobar si el destino ya es bueno tras un `os.replace` fallido también
    es una carrera.** Este fue un bug en el arreglo de la Fase 6, no en el código original:
    leer el archivo mientras otro hilo lo reemplaza da una violación de uso compartido, la
    comprobación devolvía «aquí no hay nada» y se informaba de un error inexistente.
    **Fallaba 1 de cada 3 ejecuciones**, así que la suite completa lo pasó limpio varias
    veces antes de delatarse: solo apareció corriendo el test aislado en bucle. Ahora
    `_guardar` reintenta el reemplazo hasta 5 veces en vez de decidir a la primera.
    **Al tocar `files.py`, correr `test_ocho_hilos_bajando_el_mismo_documento_no_se_pisan`
    varias veces seguidas en Windows; una sola pasada no prueba nada.**
35. **La nota al pie con la lista de productos cae DENTRO de la frase del opositor.**
    En SD2022/0005052 el texto extraído dice literalmente `…No. 951, MARYCOLOR S.A.S.
    c; preparaciones que contienen vitamina d; …` y el «presentó oposición» queda a
    **9 400 caracteres** del nombre: pypdf intercala la nota al pie (la lista de
    productos de la marca del opositor) en medio de la frase. Ninguna ventana razonable
    llega hasta el nombre. Por eso `extraer_opositores` exige que el candidato a nombre
    tenga alguna mayúscula (una cola de lista de productos va toda en minúsculas) y,
    si no queda nombre legible, lo rescata del «Declarar (in)fundada la oposición
    interpuesta por X» del RESUELVE, que siempre viene limpio.
36. **El enlace del Excel de salida iba con `http://`** — el mismo puerto 80 muerto del
    punto 2c, pero en la salida: `_parsear_enlace` guarda la URL tal como viene en la
    fórmula y el writer la escribía tal cual, así que el enlace se colgaba hasta el
    timeout del navegador. `forzar_https` vive ahora en `utils/text.py` (la sesión ya
    la aplicaba a las peticiones; el writer la aplica al hyperlink de salida).
37. **Mover los PDFs a `salida\soportes\` no rompió la reanudación.** La caché tiene dos
    patas: la página (`<EXP>_pagina.html`, sigue en `temp\`, punto 33) y los PDFs, ahora
    en `soportes\<expediente>\`, una ruta determinista que la corrida siguiente vuelve a
    mirar. Los PDFs de corridas anteriores, en `temp\` plano, se **mueven** a su carpeta
    nueva la primera vez que se piden, sin tocar la red.

## Deuda y limitaciones

- El `.exe` es **solo Windows x64**.
- **Antivirus y SmartScreen**: los binarios de PyInstaller disparan falsos positivos.
  Sin resolver; las salidas son excepción en TI o firmar el ejecutable.
- La construcción sobre `\\wsl.localhost` es lenta (2 min para crear el venv e instalar).
  Aceptable porque se hace una vez.
- Los tres mini-Excel de `tests/data/` pesan 1.2 MB cada uno: al borrar filas, openpyxl
  conserva la tabla de cadenas compartidas del reporte completo. Es feo pero inofensivo.
  Las fixtures HTTP suman 2.4 MB.
- Cobertura global 96 %. Lo que queda sin cubrir son los diálogos nativos de archivo
  (`askopenfilename` / `askdirectory`), que exigen a alguien haciendo clic.
- La coma de `artículo 136, literal h)` **sigue sin estar contemplada** en `_referencia`:
  esa forma cae en la tercera alternativa del patrón y daría `136` en vez de `136h`. Hoy no
  hace daño porque solo aparecía en alegatos citados, que la zona de conclusión ya descarta
  (ver punto 22). Si algún día sale en una conclusión, esto se convierte en un motivo mal
  leído; el arreglo es una coma opcional en `_referencia`.
- **`alias.json` todavía no existe.** La columna «Nombre corto» sale vacía hasta la Fase 10,
  que lo siembra con los 133 alias del archivo de referencia. El writer ya lo lee si aparece
  junto al `.exe`; que falte no es un error.
- El layout `"clasico"` **pierde el tercer motivo** de un expediente con más de dos. Es la
  limitación del formato viejo, no un fallo: por eso existe la POC. Hay un test que lo fija.
- **El archivo de referencia contradice a los documentos en `SD2022/0001545`**: dice
  `Fundada NO`, `MOTIVO 1` vacío y apelación `no`, mientras la resolución dice
  «Declarar fundada», `136a`, y el expediente tiene un documento de apelación. Coherente con
  el punto 7: el archivo define el formato, no la verdad. No se "corrigió" nada.
- **Los PDFs escaneados no se procesan.** Un anexo de `SD2022/0001545` es una imagen (1
  carácter de texto). Se detecta con `PdfEscaneadoError` y se avisa al usuario para que lo
  revise a mano. No hay OCR y no se piensa añadir.
- **No se sabe por qué SIPI devolvió una vez un PNG en lugar de un PDF.** Se conserva la
  respuesta real como fixture y se valida por magic bytes, pero la causa sigue sin
  confirmar (ver punto 2b).

## Bitácora

- **2026-08-06** · Exploración del sitio y de los dos Excel; hallazgos volcados al §0 del
  plan. Tres revisiones del plan: contenedor → descartado → `.exe`. Fase 0 cerrada: armazón,
  26 tests en verde en ambos SO, `.exe` de 30 MB construido y verificado.
- **2026-08-06** · Fase 1 cerrada: `reader.py` + 24 pruebas nuevas (50 en total, verdes en
  WSL y Windows). Dos bugs los encontró la suite, no una revisión: `sin_tildes` fundía
  `MUÑOZ` con `MUNOZ`, y `BadZipFile` no estaba capturada, así que un archivo renombrado
  llegaba al usuario como traza de `zipfile`.
- **2026-08-06** · Fase 2 cerrada: `session.py` + `scraper.py` + 56 pruebas nuevas (106 en
  total) y 3 de humo contra SIPI real. Grabadas las fixtures HTTP de 3 expedientes.
  **Se corrigió un hallazgo falso del plan**: se creía que `GetFile.aspx` exigía cookie de
  sesión y por eso devolvía un PNG; resultó que hoy baja sin sesión, y lo que sí exige
  cookies es `View.ashx`, que sin ellas entra en bucle de redirecciones. Además apareció
  algo no previsto: el puerto 80 del sitio no responde y el reporte trae URLs `http://`.
  Abierto: Fase 3.
- **2026-08-06** · Fase 3 cerrada: `files.py` + 31 pruebas nuevas (137 en total).
  La validación de contenido acabó siendo doble: `%PDF-` al principio **y** `%%EOF` en los
  últimos 2 KB. Solo con el magic inicial, un PDF cortado a la mitad pasaba como bueno —
  se verificó que los 11 PDFs reales grabados terminan en `%%EOF` a menos de 7 bytes del
  final. Abierto: Fase 4.
- **2026-08-06** · Fase 4 cerrada: `parser/` completo + 85 pruebas nuevas (222 en total,
  220 + 2 omitidas en Windows). Tres bugs los encontró la suite, ninguno una revisión:
  1. **La doble negación se escapaba** (caso 3). El patrón no contemplaba la forma verbal
     `esté`, así que el `no` dejaba de ser adyacente y `136b` se contaba como motivo — el
     error número uno del proyecto, apareciendo en la prueba que existía justo para eso.
     Se ampliaron las alternativas verbales a `est[áaée]n?` y compañía.
  2. **11,5 s sobre 5 MB de texto** (caso 13, presupuesto anti-ReDoS). El perfilado señaló a
     `OPOSICION`; se arregló anclando la búsqueda, no relajando el patrón (punto 13).
  3. **`hypothesis` encontró un bug en mi propio arreglo de la ñ**: `sin_tildes('\x01')`
     devolvía `'ñ'`, porque yo usaba `\x01` como marcador temporal y los PDFs traen
     caracteres de control de verdad. Se reemplazó por conservar la virgulilla solo cuando
     va sobre una `n`, con recomposición NFC.

  Aparte, los IDs de `pytest` reventaban en Windows: la parametrización anti-ReDoS usaba
  cadenas de 500 KB como identificador y generaba 4,3 MB de salida. Se añadieron `ids=`
  cortos; las entradas son las mismas. Abierto: Fase 5.
- **2026-08-06** · Fase 5 cerrada: `writer.py` + `expandir()` + 52 pruebas nuevas (274 en
  total, 271 + 3 omitidas en Windows). Cobertura 100 % en `writer.py` y en `utils/text.py`.
  Los 43 primeros tests pasaron a la primera, así que **se siguió empujando** hasta que algo
  se rompiera. Se rompió dos veces:
  1. **Inyección de fórmulas**: una marca `=1+1` se guardaba con `data_type='f'` y Excel la
     evaluaba al abrir el archivo. Arreglado forzando `data_type = "s"` en cada celda
     (punto 15).
  2. **`.xlsx` corrupto por un subrogado suelto**: `openpyxl` guardaba `\ud800` sin
     protestar y el archivo ya no se podía volver a abrir. Arreglado en
     `sanear_para_excel` (punto 14).

  Y una trampa que se encontró generando la salida de muestra: pasar el diccionario de alias
  crudo a `escribir()` dejaba «Nombre corto» vacío en silencio. Ahora existe
  `normalizar_alias()` y un test que fija las dos ramas (punto 16). Abierto: Fase 6.
- **2026-08-06** · Fase 6 cerrada: `pipeline.py` + 37 pruebas nuevas (311 en total, 308 + 3
  omitidas en Windows). Cuatro bugs, tres de ellos de concurrencia y ninguno visible en el
  camino feliz:
  1. **`.part` compartido entre hilos.** Dos hilos con el mismo expediente duplicado
     escribían el mismo archivo temporal; el `os.replace` de uno se llevaba el del otro
     (punto 18). Sufijo `uuid4` y una prueba con 8 hilos y `Barrier` que se verificó que
     falla sin el arreglo.
  2. **`os.replace` concurrente falla en Windows y no en Linux** (punto 19). El mismo test
     pasaba en WSL. Es exactamente el bug que el contenedor habría escondido.
  3. **Sin cerrojo por expediente**, el aviso «se descargará una sola vez» del lector era
     mentira (punto 20).
  4. **`la (s) causal (es)`**: la corrida real de 50 expedientes destapó que `SD2022/0008040`
     perdía su único motivo por los plurales entre paréntesis (punto 21). Corregido en
     `patterns.py`; ahora coincide con la referencia.

  La corrida de 50 dejó también un falso positivo (`SD2022/0007247`, un `136` de más
  sacado del alegato del opositor). Se cerró **antes de la Fase 7, a petición del usuario**:
  `zona_de_conclusion()` acota los motivos a la parte donde decide la Dirección (punto 22),
  con la ventana medida sobre las 50 resoluciones en vez de elegida a ojo. Resultado de la
  corrida tras el cambio: **51 filas, 45 de 45 motivos correctos**; las 4 diferencias que
  quedan contra la referencia son celdas vacías del archivo de referencia en expedientes
  cuyo `RESUELVE` dice «Negar el registro», verificado uno a uno. Abierto: Fase 7.
- **2026-08-06** · Fase 7 cerrada: `gui.py` completo + 21 pruebas nuevas (338 en total,
  334 + 4 omitidas en Windows), cobertura global del 92 % al **96 %**.
  Las pruebas de la ventana **no usan simulacros**: abren un `Tk()` real y accionan los
  botones por código, porque lo que falla de una GUI es el pegamento entre hilos y eso no
  se ve con widgets falsos. Dos hallazgos:
  1. **La traza de Python se colaba en la ventana** (punto 23). Cazado por la prueba que
     exige que no aparezca la palabra `Traceback` en el registro. El arreglo obvio
     —redefinir `formatException`— no funcionaba por el caché de `record.exc_text`.
  2. **`widget["state"]` no es una cadena** (punto 24). Siete pruebas «pasaban» comparando
     un objeto de Tcl con `"normal"`; ninguna comprobaba nada.

  Además: `--autoprueba` en el ejecutable (punto 25), enganchada a `construir_exe.bat`.
  El `.exe` reconstruido la pasa: 10 módulos importados, rutas resueltas a
  `C:\Users\...\ExtraccionSIC`, carpetas de trabajo escribibles. Abierto: Fase 8.
- **2026-08-06** · Fase 8 cerrada: `test_e2e.py` + `test_windows.py`, 23 pruebas nuevas
  (361 en total). El E2E va del Excel de entrada al de salida sin que nadie toque nada, con
  los recortes reales del reporte y las respuestas grabadas.
  Las de Windows reproducen el bloqueo de Excel con PowerShell en vez de exigir `pywin32`
  (punto 28), y las 12 se omiten limpiamente en Linux.
  Dos cosas salieron de correr esto de verdad:
  1. **`robocopy` dejaba el binario viejo** si el `.exe` estaba abierto, y la construcción
     decía «Listo» igualmente (punto 27). Arreglado con `taskkill` previo.
  2. **Faltaba comprobar TLS desde el paquete**: `--autoprueba` solo importaba módulos, y
     un `.exe` sin los certificados de `certifi` importa `requests` sin inmutarse y falla
     en todo HTTPS (punto 29). Ahora existe `--autoprueba --red`, verificada sobre el
     ejecutable: `red OK (200)`.

  Prueba en frío superada: `dist\ExtraccionSIC` copiado a
  `…\Escritorio de José\Extracción SIC ñ\` arranca sin nada del entorno de desarrollo.
  Abierto: Fase 9.
- **2026-08-06** · Fase 9 cerrada: `DOCUMENTACION.md` (nueve secciones) +
  `docs/gen_diagramas.py` con los dos diagramas en SVG y PNG + 22 pruebas nuevas
  (383 en total).
  Los dos diagramas salieron mal a la primera y se corrigieron mirando el PNG, que es lo que
  manda el §8 de la guía: en el de arquitectura las flechas de la misma fila se dibujaban en
  diagonal hacia la tarjeta de al lado, y el canal de retorno cruzaba el rótulo de una banda;
  en el de flujo el lienzo recortaba la última tarjeta y la leyenda, y un detalle desbordaba
  su caja. El alto ahora se calcula del contenido en vez de escribirse a ojo.
  La deriva del manual está atada con pruebas (punto 30), y esa comprobación **también hubo
  que arreglarla**: la primera versión pasaba aunque se cambiara un mensaje en el código
  (punto 30). Abierto: Fase 10.
- **2026-08-07** · Fase 10 cerrada. **El proyecto está terminado.**
  `sembrar_alias.py` + `alias.json` (139 opositores, 3 erratas del archivo de referencia
  detectadas y resueltas por frecuencia) + 28 pruebas nuevas (411 en total).
  Hicieron falta **cinco pasadas** sobre los 987 expedientes para llegar a 0 errores, y cada
  una destapó algo que las 383 pruebas anteriores no podían ver porque no tenían la escala:
  1. **El PNG de 828 bytes se reprodujo por fin**, tras dos fases marcado como
     «no reproducible»: 140 respuestas en los primeros 26 segundos, 50 expedientes.
     Reintento por contenido en `files.py` (punto 2b).
  2. **19 expedientes con la página sin tabla.** Reintenté dos a mano y los dos funcionaron:
     mismo transitorio. Reintento también en `scraper.py` (punto 27).
  3. **Repetir la corrida no convergía** (punto 33). Se midió: la 3ª pasada recuperó 10 y
     perdió 12. Se arregló guardando también la página en caché; la 5ª pasada tardó
     171 segundos y dio 0 errores sin tocar la red.
  4. **Un bug en mi propio arreglo de la Fase 6** (punto 34): la comprobación de recuperación
     tras un `os.replace` fallido es a su vez una carrera en Windows. Fallaba 1 de cada 3
     ejecuciones y la suite completa lo había pasado limpio varias veces.

  Queda un 18 % de filas con «Observaciones»: no es un fallo, es el trabajo manual que el
  programa señala en vez de inventarse. Ver «Siguiente paso» para cómo bajarlo.
- **2026-08-07** · **Correcciones post-entrega.** El usuario probó el `.exe` en Windows y
  dejó 7 puntos, con sus corridas reales en `tests/propios/`. Los bugs de extracción se
  verificaron re-descargando los PDFs de SIPI (de paso se reprodujo otra vez el PNG de
  828 bytes del punto 2b; el reintento lo absorbió).
  1. **PDFs por expediente**: `salida\soportes\<expediente>\` en vez de `temp\` plano.
     `temp\` queda solo como caché de páginas; los PDFs viejos se migran moviéndolos, sin
     volver a bajar 620 MB, y la reanudación se conserva (punto 37).
  2. GUI: sin cambios (el usuario lo marcó como no prioritario).
  3. **El enlace del expediente iba con `http://`** — puerto muerto — y sin pinta de
     enlace. Ahora sale `https://`, azul y subrayado (punto 36).
  4. Cabeceras **amarillas** en las columnas que produce el programa; el gris queda solo
     para las heredadas del reporte de entrada.
  5. **«Descripción de Productos y Servicios» pasa a ser la última columna**, después de
     `Observaciones`. En el layout clásico ya era la última. Las columnas excluidas
     (`Bajo Oposición`, `Apoderado`, fechas, `Otra Información`) siguen excluidas a
     propósito.
  6. **Bordes** en todas las celdas con datos; más gruesos en cabeceras y banners.
  7. Tres redacciones reales que la extracción no cubría, cazadas en `tests/propios/` y
     reproducidas contra los PDFs re-descargados:
     · **SD2022/0005052**: `Opositor 1` salía como un trozo de la lista de productos y
       `Art OP 1 = 135b` a secas — la nota al pie parte la frase (punto 35). Ahora:
       `MARYCOLOR S.A.S.`, `135b, 136a`, fundada `NO`.
     · **SD2022/0004420**: «con fundamento en el literal a) del artículo 136 y artículo
       147», sin la fórmula «las causales de irregistrabilidad» — la fórmula es ahora
       opcional en `OPOSICION` y las referencias de artículos distintos se encadenan
       (`referencias_encadenadas`). El `MOTIVO 147` de ese expediente **no era un bug**:
       la resolución dice literalmente «está comprendido en la causal … artículo 147».
     · **SD2022/0004110**: «con fundamento en **lo dispuesto en**…» y «con **base** en
       lo dispuesto en…» — cubiertas.
     `DECLARACION_OPOSICION` además corta el nombre en «, en contra de»: antes el
     «nombre» declarado se tragaba media parte resolutiva y no casaba con nada.
     De rebote, la generalización de `OPOSICION` debería rebajar el grupo de 81 avisos
     de «no se pudo determinar en qué artículos fundó su oposición» («Siguiente paso» 1);
     falta re-correr los 987 para medirlo.

  12 pruebas nuevas (423 en total), todas con los extractos reales de los PDFs.
  `DOCUMENTACION.md` §3/§4/§5 actualizados en el mismo cambio.
- **2026-08-07** · Reconstrucción del `.exe` tras las correcciones post-entrega. La primera
  pasada la abortó `construir_exe.bat` con un fallo: `test_windows.py` seguía buscando los
  PDFs en `temp\` cuando la corrección 1 los había movido a `salida\soportes\<expediente>\`.
  Se actualizaron `test_pipeline.py` y `test_e2e.py` en su momento, pero **las pruebas de
  Windows solo corren al construir**, así que una prueba desactualizada ahí sobrevive a
  cualquier cantidad de pasadas en WSL. Arreglado el assert; **419 pasadas, 4 omitidas** en
  Windows y `.exe` de 7,2 MB verificado con `--autoprueba --red`: `red OK (200)`.
- **2026-08-07** · **Filas sin opositor en morado** (`#917AC3`), a petición del usuario tras
  probar el `.exe`: los cuatro primeros expedientes salían con las nueve columnas de
  opositor vacías y no se distinguía «no hubo oposición» de «no se pudo extraer». Los tres
  eran correctos —la resolución dice «no se presentaron oposiciones por parte de terceros» y
  el archivo de referencia los marca igual—, pero eso había que comprobarlo a mano abriendo
  el PDF. El color lo dice de un vistazo. `DOCUMENTACION.md` §4 y 1 prueba nueva (424).
- **2026-08-07** · **Seguimiento de la corrida rehecho** en `gui.py`. Antes había una barra
  sin escala y una línea corrida («Expedientes 412 · PDFs 1103 · …») que había que leer
  entera para encontrar un número. Ahora: porcentaje grande, expediente en curso,
  **tiempo transcurrido y estimado** —calculado del ritmo real, porque SIPI va a
  velocidades muy distintas según la hora— y las cinco cifras como fichas, con avisos en
  ámbar y errores en rojo **solo cuando los hay**. La paleta usa el mismo `#917AC3` del
  Excel. Hizo falta `theme_use("clam")`: con el tema `vista` de Windows los colores que se
  le piden a ttk **se ignoran en silencio**.
  Verificado con captura real en Windows (`PrintWindow` sobre la ventana) y muestreo de
  píxeles, porque las pruebas no ven un color: los tonos raros a simple vista eran el
  fringing de ClearType, no un fallo de la paleta.
- **2026-08-07** · `tests/test_gui.py` **ya no omite por cualquier `TclError`**. El fixture
  `ventana` convertía en `skip` tanto «no hay display» como un bug real de `gui.py`, y esas
  15 pruebas son la única red del arranque de la ventana: un `TclError` al construirla
  habría salido en verde, la construcción habría dicho «Listo» y el `.exe` (con
  `console=False`) moriría al doble clic sin mensaje. La autoprueba tampoco lo vería,
  porque `__main__` importa `app.gui` pero nunca construye `Ventana`. Ahora solo se omite
  si el mensaje es de entorno (`init.tcl`, `display`); lo demás falla. Comprobado
  rompiendo `gui.py` a propósito: 14 errores en vez de 14 omitidas.
