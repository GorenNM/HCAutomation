# Graph Report - HCAutomation  (2026-09-07)

## Corpus Check
- 76 files · ~120,732 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1222 nodes · 2799 edges · 66 communities (56 shown, 4 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 196 edges (avg confidence: 0.91)
- Token cost: 361,934 input · 0 output

## Community Hubs (Navigation)
- Escritura del Excel de salida
- Lectura del Excel de entrada
- Sesión HTTP contra SIPI
- Orquestación del pipeline
- Pruebas de documentación
- Motivos de negación y zona de conclusión
- Scraping y clasificación de documentos
- Extracción de opositores
- Pruebas de descarga
- Normalización de texto
- PDF a texto
- Logging hacia la ventana
- Scripts de comparación de salida
- Sembrado de alias
- Configuración y rutas
- Pruebas de la ventana
- Nombres de archivo en Windows
- Conversión Markdown a docx
- Página del expediente y modelos
- Pruebas end-to-end
- Pruebas basadas en propiedades
- Ventana Tkinter
- Diagrama de flujo del expediente
- Extractor de la resolución
- Diagrama de arquitectura
- Generador de informes docx
- Sesiones falsas de prueba
- Descarga y validación de PDFs
- Cerrojo de corrida y rutas Windows
- Generación de diagramas SVG
- Decisiones técnicas y empaquetado
- Sesiones grabadas y concurrencia
- Captura de la ventana
- Clases de Niza en oposiciones
- Detección y limpieza de opositor
- Puente GUI-logging
- Documentos del proyecto
- Validación por magic bytes
- Progreso y contadores
- Patrones regex de causales
- Carpeta de distribución del exe
- Guía de problemas frecuentes
- Estilos ttk de la ventana
- Cultura de verificación con datos reales
- Estrategia de descarga
- Riesgos y estrategia de pruebas
- Decisiones descartadas y concurrencia
- Marca y naturaleza
- Fixture de ventana sin display
- Mapa de cambios y alias
- Caché y corrida definitiva
- Abrir carpeta de salida
- Seguridad de celdas y HTTPS
- Invariante de fila por expediente
- Fixtures de respuesta PDF
- Generador de literales
- Paquete app
- Formato clásico de salida
- Corte del nombre del opositor
- Nombre corto en celda

## God Nodes (most connected - your core abstractions)
1. `normalizar()` - 74 edges
2. `TipoDoc` - 44 edges
3. `SesionSIPI` - 43 edges
4. `escribir()` - 43 edges
5. `origen()` - 37 edges
6. `extraido()` - 37 edges
7. `reporte_de()` - 36 edges
8. `descargar_documento()` - 34 edges
9. `leer_reporte()` - 34 edges
10. `correr()` - 34 edges

## Surprising Connections (you probably didn't know these)
- `test_la_tabla_de_documentos_sigue_teniendo_la_misma_forma()` --uses--> `TipoDoc`  [INFERRED]
  tests/test_live.py → app/models.py
- `test_solo_tm9_y_tm128_son_resoluciones()` --uses--> `TipoDoc`  [INFERRED]
  tests/test_scraper.py → app/models.py
- `Texto de la resolución TM9 de SD2022/0000017` --references--> `Corrida definitiva: 987 expedientes, 0 errores`  [AMBIGUOUS]
  tests/fixtures/texto/SD2022-0000017_TM9.txt → ESTADO.md
- `FormatoSinTraza — la traza no llega a la ventana` --semantically_similar_to--> `Nunca inferir un dato dudoso`  [INFERRED] [semantically similar]
  ESTADO.md → DOCUMENTACION_TECNICA.md
- `ExtraccionSIC.exe --autoprueba [--red]` --semantically_similar_to--> `Validación visual obligatoria mirando el PNG (§8)`  [INFERRED] [semantically similar]
  ESTADO.md → guia-diagramas-imagen.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Defensas contra respuestas HTTP 200 que no son el contenido esperado** — estado_png_828_bytes, estado_validacion_magic_pdf, estado_reintento_por_contenido, estado_error_scraping, estado_cache_de_pagina [EXTRACTED 1.00]
- **Mecanismos que garantizan un .xlsx de salida legible y honesto** — estado_sanear_para_excel, estado_data_type_s, estado_normalizar_alias, documentacion_tecnica_cabeceras, manual_usuario_excel_salida, correcciones_enlace_https_expediente [INFERRED 0.85]
- **Cadena de correcciones para extraer bien el nombre del opositor** — estado_quitar_cabeceras, estado_limpiar_nombre, estado_nota_al_pie_parte_frase, estado_sin_tildes_enye, estado_alias_json, plan_nombre_corto_opositor [EXTRACTED 1.00]
- **Flujo de descarga: del Excel de entrada a los PDFs validados en disco** — docs_arquitectura_excel_reader, docs_arquitectura_downloader_scraper, docs_arquitectura_downloader_session, docs_arquitectura_downloader_files [EXTRACTED 1.00]
- **Flujo de análisis: PDF a texto, regex y zona de conclusión hasta el Excel de salida** — docs_arquitectura_parser_pdf_text, docs_arquitectura_parser_patterns, docs_arquitectura_parser_extractor, docs_arquitectura_excel_writer [EXTRACTED 1.00]
- **Aplicación de escritorio monolítica: GUI tkinter, pipeline multihilo y un único .exe sin servidor** — docs_arquitectura_gui, docs_arquitectura_pipeline, docs_arquitectura_exe_unico_sin_servidor, docs_arquitectura_concurrencia_8_hilos, docs_arquitectura_carpetas_temp_salida [INFERRED 0.85]
- **Flujo de entrada y descarga: Excel a PDFs en disco** — docs_arquitectura_excel_reader, docs_arquitectura_downloader_scraper, docs_arquitectura_downloader_session, docs_arquitectura_downloader_files [EXTRACTED 1.00]
- **Flujo de análisis: PDF a datos estructurados** — docs_arquitectura_parser_pdf_text, docs_arquitectura_parser_patterns, docs_arquitectura_parser_extractor [EXTRACTED 1.00]
- **Control y salida: GUI, orquestador multihilo y escritura del Excel** — docs_arquitectura_gui, docs_arquitectura_pipeline, docs_arquitectura_excel_writer, docs_arquitectura_carpetas_temp_salida [INFERRED 0.85]
- **ExtraccionSIC runtime folder layout (exe + bundled runtime + I/O dirs)** — docs_carpeta_extraccionsic_exe, docs_carpeta_internal_folder, docs_carpeta_salida_folder, docs_carpeta_temp_folder [INFERRED 0.85]
- **Self-test run evidence: exe writes autoprueba plus salida/temp outputs** — docs_carpeta_extraccionsic_exe, docs_carpeta_autoprueba_log, docs_carpeta_salida_folder, docs_carpeta_temp_folder [INFERRED 0.75]
- **Pipeline de un expediente: de fila del Excel a N filas de salida** — docs_flujo_fila_excel, docs_flujo_pagina_expediente, docs_flujo_descarga_pdfs, docs_flujo_texto_resolucion, docs_flujo_zona_conclusion, docs_flujo_motivos_opositores, docs_flujo_n_filas_salida [EXTRACTED 1.00]
- **Modos de fallo degradados que preservan la fila en el Excel** — docs_flujo_regla_no_perder_fila, docs_flujo_fallo_sipi_caido, docs_flujo_fallo_no_es_pdf, docs_flujo_fallo_pdf_escaneado, docs_flujo_fallo_sin_marcador, docs_flujo_fallo_causal_no_reconocida, docs_flujo_fallo_cero_motivos [INFERRED 0.95]
- **Pipeline de 7 pasos: de una fila del Excel a N filas de salida** — docs_flujo_fila_excel, docs_flujo_pagina_expediente, docs_flujo_descarga_pdfs, docs_flujo_texto_resolucion, docs_flujo_zona_conclusion, docs_flujo_motivos_opositores, docs_flujo_n_filas_salida [EXTRACTED 1.00]
- **Degradación elegante: cada fallo produce fila con observación en vez de perderla** — docs_flujo_fallo_sipi_caido, docs_flujo_fallo_respuesta_no_pdf, docs_flujo_fallo_pdf_escaneado, docs_flujo_fallo_sin_marcador_resuelve, docs_flujo_fallo_causal_no_reconocida, docs_flujo_fallo_cero_motivos, docs_flujo_regla_invariante, docs_flujo_observaciones [EXTRACTED 1.00]
- **Run configuration inputs before Iniciar** — docs_ventana_input_excel_selector, docs_ventana_output_folder_selector, docs_ventana_parallel_downloads_setting, docs_ventana_reuse_pdfs_option, docs_ventana_start_stop_controls [EXTRACTED 1.00]
- **Live run feedback surface (progress, counters, log)** — docs_ventana_progress_panel, docs_ventana_counters_row, docs_ventana_registro_log, docs_ventana_open_output_button [INFERRED 0.85]

## Communities (66 total, 4 thin omitted)

### Community 0 - "Escritura del Excel de salida"
Cohesion: 0.05
Nodes (111): _apelacion(), cargar_alias(), ErrorEscritura, escribir(), _escribir_encabezado(), expandir(), _nombre_corto(), normalizar_alias() (+103 more)

### Community 1 - "Lectura del Excel de entrada"
Cohesion: 0.05
Nodes (78): _abrir(), _avisar_duplicados(), _clases_del_reporte(), _clave(), ErrorLectura, _filas_de_datos(), _leer_libro(), leer_reporte() (+70 more)

### Community 2 - "Sesión HTTP contra SIPI"
Cohesion: 0.05
Nodes (54): ErrorRed, Exception, Response, Sesión HTTP contra SIPI. Lo que obliga a que exista este módulo: sin cookies,…, Falló la comunicación con SIPI. El mensaje va al log y a la interfaz., Envoltorio fino sobre `requests.Session`: reintentos, timeout y ritmo., Deja al menos `delay` segundos entre peticiones de esta sesión., GET con reintentos. Lanza ErrorRed con un mensaje legible. (+46 more)

### Community 3 - "Orquestación del pipeline"
Cohesion: 0.10
Nodes (47): procesar_expediente(), Un expediente completo: página → PDFs → texto → registros. `carpeta` es la…, correr(), filas_del_excel(), Pruebas de la orquestación (casos 31–34 del §13.3). Todo corre **offline**…, 0097089 tiene dos motivos: 3 expedientes -> 4 registros. Es el requisito., Con 8 hilos el orden de terminación es aleatorio; el del Excel no., 0001545 trae dos anexos OTRO (uno escaneado): no se bajan. (+39 more)

### Community 4 - "Pruebas de documentación"
Cohesion: 0.06
Nodes (38): codigo(), fragmentos_buscables(), literales_citados(), manual(), plano(), fixture, parametrize, El manual tiene que seguir siendo cierto. `MANUAL_USUARIO.md` cita textualmente… (+30 more)

### Community 5 - "Motivos de negación y zona de conclusión"
Cohesion: 0.08
Nodes (39): extraer_motivos(), El tramo donde concluye la Dirección, no donde alega el opositor. Una…, Causales por las que se niega el registro. Aquí vive el riesgo principal del…, zona_de_conclusion(), normalizar(), Colapsa el texto a una sola línea con espacios simples. Reúne las palabras…, no se encuentra incurso en la causal relativa…' — hay 5 palabras de por medio…, Ante una construcción ambigua, no adivinar: no contarla y avisar. (+31 more)

### Community 6 - "Scraping y clasificación de documentos"
Cohesion: 0.10
Nodes (35): clasificar(), ErrorScraping, extraer_documentos(), Exception, La página del expediente no tiene la forma esperada., Traduce el texto de la columna «Documento» a un tipo conocido., Saca los documentos de la tabla del Histórico de Documentos. Devuelve lista…, html_grabado() (+27 more)

### Community 7 - "Extracción de opositores"
Cohesion: 0.11
Nodes (36): asignar_fundadas(), extraer(), Rellena `fundada` en cada opositor a partir de la parte resolutiva., Analiza la resolución completa. Nunca lanza excepción., Texto ya extraído de una resolución real (ver make_fixtures.grabar_texto)., texto_grabado(), _oposicion(), Pruebas del extractor: los 15 casos del §13.3 del plan. Los textos base son las… (+28 more)

### Community 8 - "Pruebas de descarga"
Cohesion: 0.13
Nodes (33): ErrorDescarga, Exception, No se pudo obtener o guardar un documento. Afecta a un expediente, no a la…, documento(), Exception, skipif, Pruebas de la descarga a disco. Cubre los casos 16–18 y 22–24 del §13.3 del…, Lo peor sería confiar en él: quedaría basura en el Excel final. (+25 more)

### Community 9 - "Normalización de texto"
Cohesion: 0.09
Nodes (29): _contradice_al_excel(), El Excel de entrada dice una cosa y la resolución otra. Gana la resolución., _apto_para_celda(), clave_comparacion(), nombre_archivo_seguro(), Normalización de texto. Los PDFs de la SIC parten frases a mitad de línea y a…, Convierte un expediente en un nombre de archivo válido en Windows.…, Quita diacríticos. Para comparar, nunca para mostrar. La ñ se preserva: en… (+21 more)

### Community 10 - "PDF a texto"
Cohesion: 0.15
Nodes (27): ErrorPdf, PdfEscaneadoError, Exception, Path, quitar_cabeceras(), PDF → texto listo para aplicar expresiones regulares. Dos limpiezas que no son…, El PDF no se pudo leer., El PDF no tiene capa de texto: es una imagen. No se intenta OCR. Se marca el… (+19 more)

### Community 11 - "Logging hacia la ventana"
Cohesion: 0.12
Nodes (24): ColaHandler, configurar(), FormatoSinTraza, Path, Queue, Configuración de logging: archivo en salida/ + cola para la ventana., Como el normal, pero sin la traza de la excepción. Un traceback de Python en la…, Empuja los registros a una cola que la GUI drena desde el hilo de tkinter. Los… (+16 more)

### Community 12 - "Scripts de comparación de salida"
Cohesion: 0.17
Nodes (27): autotest(), comparar(), leer_out(), leer_ref(), main(), norm(), norm_exp(), norm_motivo() (+19 more)

### Community 13 - "Sembrado de alias"
Cohesion: 0.16
Nodes (25): construir(), leer_pares(), main(), Path, Genera `alias.json` a partir del archivo de referencia. python sembrar_alias.py…, Devuelve (alias por clave de comparación, avisos de conflicto). Cuando el mismo…, construir_referencia(), corto_de() (+17 more)

### Community 14 - "Configuración y rutas"
Cohesion: 0.14
Nodes (23): dir_salida(), dir_temp(), Path, Constantes y parámetros. Un solo sitio donde tocar valores., autoprueba(), main(), Punto de entrada: `python -m app` y también el del ejecutable. Con…, Comprueba que el paquete está completo. Devuelve el código de salida. (+15 more)

### Community 15 - "Pruebas de la ventana"
Cohesion: 0.13
Nodes (21): _ejecutar_offline(), esperar(), estado_de(), Pruebas de la ventana. Crean un `Tk()` de verdad y accionan los botones por…, Bombea la ventana hasta que se cumpla la condición., El usuario solo debería tener que elegir el Excel., Copiar «como ruta de acceso» en Windows envuelve la ruta en comillas., El contrato del módulo. Si se rompe, tkinter cuelga sin avisar. (+13 more)

### Community 16 - "Nombres de archivo en Windows"
Cohesion: 0.13
Nodes (21): nombre_de_archivo(), `SD2022/0000017` + TM9 -> `SD2022-0000017_TM9.pdf`. El sufijo numérico solo…, Tipos de documento del Histórico de Documentos del expediente. La clasificación…, Documentos de los que se extrae información., TipoDoc, Enum, str, Regresión: el reporte real repite expedientes y el pipeline usa 8 hilos. Con un… (+13 more)

### Community 17 - "Conversión Markdown a docx"
Cohesion: 0.15
Nodes (21): _add_code_block(), _add_runs(), _add_table(), _cell_bg(), _cell_borders(), convert(), _fix_styles(), Mark a table row to repeat as header on every page. (+13 more)

### Community 18 - "Página del expediente y modelos"
Cohesion: 0.17
Nodes (19): _abrir_con_reintentos(), abrir_expediente(), _datos_de_la_fila(), documentos_de_expediente(), _es_enlace_de_archivo(), PaginaExpediente, De la URL del expediente a la lista de documentos descargables.…, Número de resolución y fecha, que están en las primeras celdas de la fila. Son… (+11 more)

### Community 19 - "Pruebas end-to-end"
Cohesion: 0.19
Nodes (21): corrida(), filas_como_diccionarios(), hoja_de(), De punta a punta con datos reales, sin red. Los tres Excel de `tests/data/` son…, El requisito que motivó todo el cambio de formato., «Repitiendo el resto de la información», textual del requisito., 0097089 trae dos oposiciones: NESTLE a las clases 30 y 32, KRAFT a las 5, 30,…, Ida y vuelta completa: si openpyxl lo relee, Excel también lo abre. (+13 more)

### Community 20 - "Pruebas basadas en propiedades"
Cohesion: 0.22
Nodes (20): given, _RAPIDO, Pruebas basadas en propiedades (§13.4 del plan). Acotadas a propósito a dos…, Da igual cuántos literales haya: si dice 'no', no son motivos., No puede borrar contenido: solo colapsa espacios., Es una letra, no un acento: fundir MUÑOZ con MUNOZ juntaría opositores., test_clave_comparacion_es_idempotente(), test_el_orden_invertido_de_la_referencia_da_lo_mismo() (+12 more)

### Community 21 - "Ventana Tkinter"
Cohesion: 0.18
Nodes (5): Transcurrido y estimado. El estimado sale del ritmo real, no de una constante:…, `754` → `12:34`; a partir de una hora, `1:05:20`., Estado y widgets. Una sola instancia por proceso., reloj(), Ventana

### Community 22 - "Diagrama de flujo del expediente"
Cohesion: 0.15
Nodes (20): Paso 3: Descarga de los PDFs (TM9, TM128, TM6, apelación), Flujo de un expediente (diagrama), Diagrama: Flujo de un expediente, Fallo: causal no reconocida → MOTIVO vacío con observación, Fallo: 0 motivos → igual sale 1 fila, Fallo: respuesta que no es PDF → validación por bytes, no por código HTTP, Fallo: PDF escaneado → se marca para revisión manual (sin OCR), Fallo: respuesta que no es PDF (validación por bytes, no por HTTP) (+12 more)

### Community 23 - "Extractor de la resolución"
Cohesion: 0.15
Nodes (18): _alcanza_la_clase(), _avisar_sin_motivos(), clases_de_la_oposicion(), _Oposicion, _oposiciones_del_texto(), _opositores_del_resuelve(), _parece_nombre(), Match (+10 more)

### Community 24 - "Diagrama de arquitectura"
Cohesion: 0.25
Nodes (19): Capa: Análisis (del PDF a los datos), Capa: Control y salida, Capa: Entrada y descarga (del Excel a los PDFs en disco), Carpetas junto al .exe: temp\ (PDFs borrables) y salida\ (Excel y registro), Concurrencia: hasta 8 hilos, una sesión HTTPS por hilo, Extracción SIC — Diagrama de Arquitectura, downloader/files.py (descarga y valida %PDF- / %%EOF), downloader/scraper.py (lista los PDFs, 3-5 documentos) (+11 more)

### Community 25 - "Generador de informes docx"
Cohesion: 0.20
Nodes (17): _add_code_block(), _add_cover(), _add_runs(), _add_table(), _cell_bg(), _cell_borders(), _clear_body(), convert() (+9 more)

### Community 26 - "Sesiones falsas de prueba"
Cohesion: 0.12
Nodes (9): Sirve las respuestas grabadas de un expediente. Falla si piden otra URL., RespuestaFalsa, SesionGrabada, Devuelve basura las primeras veces y el PDF bueno después. Es el comportamiento…, Otra forma del mismo problema: llega algo, pero incompleto., SesionQuePrimeroFalla, test_descargar_documentos_sigue_tras_un_fallo(), test_un_pdf_truncado_tambien_se_reintenta() (+1 more)

### Community 27 - "Descarga y validación de PDFs"
Cohesion: 0.22
Nodes (16): _asegurar_carpeta(), Descarga, descargar_documento(), descargar_documentos(), _diagnostico(), _guardar(), _pedir_con_reintentos(), Path (+8 more)

### Community 28 - "Cerrojo de corrida y rutas Windows"
Cohesion: 0.13
Nodes (16): ejecutar(), ErrorPipeline, Exception, Corre el proceso completo y escribe el Excel. Devuelve qué pasó., El mensaje va directo al usuario., Event, Si el cerrojo se quedara tomado, la app no volvería a correr nunca., test_caso_33_la_segunda_corrida_se_rechaza() (+8 more)

### Community 29 - "Generación de diagramas SVG"
Cohesion: 0.24
Nodes (15): arquitectura(), banda(), chip(), escribir(), flecha(), flujo(), main(), marcador() (+7 more)

### Community 30 - "Decisiones técnicas y empaquetado"
Cohesion: 0.16
Nodes (15): Arquitectura de diez módulos con pipeline central, Empaquetado y distribución con construir_exe.bat, Documentación técnica — panorama del sistema, Reglas de concurrencia del diseño, utils/rutas.py como único punto que conoce el empaquetado, ExtraccionSIC.exe --autoprueba [--red], lxml descartado — ninguna dependencia con binario, MarkItDown descartado para leer PDFs (+7 more)

### Community 31 - "Sesiones grabadas y concurrencia"
Cohesion: 0.14
Nodes (11): Como `SesionGrabada` pero sirve los tres expedientes a la vez. Es lo que…, SesionGrabadaMulti, parametrize, Falla siempre en un expediente concreto, y con algo que nadie captura., Medido sobre los 987: sin esto, repetir la corrida no converge. La segunda…, SesionQueRevienta, SesionSinRed, test_cada_hilo_abre_su_propia_sesion_y_todas_se_cierran() (+3 more)

### Community 32 - "Captura de la ventana"
Cohesion: 0.23
Nodes (14): Extracción SIC 0.1.0 (Tkinter Desktop App), Rationale: Excel written only at the end (atomic output), Counters: Expedientes, PDFs, Filas, Avisos, Errores, Excel de entrada (SIPI report file picker), Rationale: guided single-screen UX for non-technical lawyers, Abrir carpeta de salida (disabled until run finishes), Carpeta de salida (default C:\Users\femur\ExtraccionSIC\salida), Descargas en paralelo (spinbox, default 4) (+6 more)

### Community 33 - "Clases de Niza en oposiciones"
Cohesion: 0.15
Nodes (13): extraer_opositores(), Opositores en orden de aparición, con los artículos que invocaron. Se leen…, Dos oposiciones seguidas: la segunda no hereda la clase de la primera. La…, Se filtra por opositor, no por frase: basta con que una de sus oposiciones…, con fundamento en el literal a) del artículo 136 y artículo 147' — sin «las…, SD2022/0049055: 'los literales b) del artículo 135 y a) del artículo 136'. El…, El conector 'y en el' no está soportado, así que 136a no se captura. Lo que no…, test_cadena_de_articulos_sin_repetir_la_palabra_literal() (+5 more)

### Community 34 - "Detección y limpieza de opositor"
Cohesion: 0.17
Nodes (13): hay_oposicion(), limpiar_nombre(), La frase explícita manda sobre la ausencia de menciones., Recorta el nombre del opositor del texto que lo rodea. El nombre viene…, parametrize, Varios patrones tienen cuantificadores anidados: son candidatos a ReDoS. El…, Si dice que no hubo oposiciones, eso manda aunque la palabra aparezca., test_caso_11_limpieza_de_nombres() (+5 more)

### Community 35 - "Puente GUI-logging"
Cohesion: 0.21
Nodes (9): _Aviso, _ColaDeTexto, main(), Queue, Ventana de la aplicación (§11 del plan). Lo único que ve el usuario final:…, Mensaje del hilo worker hacia la ventana. Solo datos, nunca widgets., Traductor: `logging_setup` empuja texto suelto, la ventana espera `_Aviso`.…, test_el_progreso_sin_total_no_divide_por_cero() (+1 more)

### Community 36 - "Documentos del proyecto"
Cohesion: 0.26
Nodes (12): Corrección 4 — cabeceras amarillas en columnas generadas, Prompt de correcciones post-entrega (7 puntos), Diccionario CABECERAS como definición viva de las columnas, ESTADO.md — bitácora y contexto no obvio, Excel de salida: veinte columnas documentadas, Manual de usuario de Extracción SIC, plan.md — diseño completo previo al código, ESTADO.md como trazabilidad META para agentes (§14.2) (+4 more)

### Community 37 - "Validación por magic bytes"
Cohesion: 0.18
Nodes (11): es_pdf_completo(), True si los bytes son un PDF entero, no un placeholder ni un truncado., parametrize, Caso 17: la cabecera está bien, así que solo el final lo delata., Caso 16: HTTP 200 y 828 bytes que no son un PDF., test_baja_todos_los_documentos_reales_de_un_expediente(), test_contenidos_invalidos_se_rechazan(), test_el_png_que_devolvio_sipi_se_rechaza() (+3 more)

### Community 38 - "Progreso y contadores"
Cohesion: 0.22
Nodes (7): Corre en el hilo worker. **Aquí no se toca ningún widget.**, _Contadores, Progreso, Los cinco números de la ventana, con su cerrojo. Sin el cerrojo, `n += 1` desde…, Instantánea de la corrida. Se entrega **congelada** al callback., Resultado, test_cerrar_con_una_corrida_activa_pide_confirmacion_y_la_detiene()

### Community 39 - "Patrones regex de causales"
Cohesion: 0.24
Nodes (8): _causales_de(), (afirmadas, negadas) en orden de aparición, sin repetir., codigos_de_referencia(), Match, Todas las expresiones regulares del proyecto, en un solo archivo. Cuando la SIC…, Códigos que encadenan con una referencia ya capturada, y dónde acaban. Devuelve…, 136' + 'a) y h)' -> ['136a', '136h']; '147' sin literal -> ['147']., referencias_encadenadas()

### Community 40 - "Carpeta de distribución del exe"
Cohesion: 0.33
Nodes (10): alias (source file), autoprueba (self-test text document), ExtraccionSIC Distribution Layout (C:/Usuarios/femur/ExtraccionSIC), ExtraccionSIC.exe (Application), _internal (PyInstaller bundled runtime folder), One-folder Frozen Executable Packaging, salida (output folder), ExtraccionSIC Deployment Folder Screenshot (+2 more)

### Community 41 - "Guía de problemas frecuentes"
Cohesion: 0.22
Nodes (9): Clase de Niza objetivo en config.py, Nunca inferir un dato dudoso, FormatoSinTraza — la traza no llega a la ventana, 18 % de filas con Observaciones (trabajo manual restante), PdfEscaneadoError — PDFs escaneados sin capa de texto, El .exe no arranca desde una ruta UNC, Solo cuentan las oposiciones dirigidas a la clase del reporte, Columna Observaciones — qué revisar a mano (+1 more)

### Community 42 - "Estilos ttk de la ventana"
Cohesion: 0.29
Nodes (3): `clam` es el único tema de ttk que respeta los colores que se le piden. Con…, Un `tk.Frame`, no `ttk`: el borde de un color concreto solo se pide así., Frame

### Community 43 - "Cultura de verificación con datos reales"
Cohesion: 0.25
Nodes (8): Cultura del proyecto: verificar contra datos reales y actualizar docs en el mismo cambio, Clasificación de documentos por el texto de la columna, no por posición, Filas sin opositor en morado (#917AC3), Filas moradas = expedientes sin opositor, Datos reales, no inventados (§13.2), Manual atado al código por tests/test_documentacion.py, Fixture HTTP Browse.aspx de SD2022/0000017 (MALTAVITAN), Texto de la resolución TM9 de SD2022/0000017

### Community 44 - "Estrategia de descarga"
Cohesion: 0.25
Nodes (8): Flujo de un expediente (ficha → clasificación → descarga → texto → extracción → escritura), quitar_cabeceras() antes de cualquier regex, sanear_para_excel — subrogados sueltos corrompen el .xlsx, Sesión compartida por expediente (ASP.NET_SessionId), Validación por magic bytes %PDF- y %%EOF, Estrategia de descarga (§7), Fixture HTTP Browse.aspx de SD2022/0001545 (idime), Texto de la resolución TM128 de SD2022/0001545

### Community 45 - "Riesgos y estrategia de pruebas"
Cohesion: 0.25
Nodes (8): Anclaje del regex OPOSICION (acantilado de rendimiento / ReDoS), Deuda: la coma de «artículo 136, literal h)» da 136 en vez de 136h, Negación léxica «no está comprendido en … literal b)», Zona de conclusión (acotado de motivos), Catálogo adversarial de casos de prueba (§13.3), Cuatro capas de pruebas (§13.1), Motivos de negación — el punto crítico (§8.5), Riesgos conocidos (§15)

### Community 46 - "Decisiones descartadas y concurrencia"
Cohesion: 0.25
Nodes (8): Cerrojo por expediente en el pipeline, Docker evaluado y descartado, Interfaz web con http.server descartada, ErrorScraping — página sin la tabla de documentos, os.replace concurrente falla en Windows y no en Linux, Archivo .part con sufijo uuid4, Reintento por contenido (ESPERAS_CONTENIDO_SEG 3/8/20), Entregable: .exe de Windows sin instalación

### Community 47 - "Marca y naturaleza"
Cohesion: 0.29
Nodes (7): extraer_marca(), extraer_naturaleza(), Nominativa' | 'Mixta' | 'Figurativa' | '3D'., El documento cita marcas de terceros con su naturaleza entre paréntesis., test_la_naturaleza_se_toma_de_la_marca_solicitada_no_de_las_citadas(), test_marca_con_parentesis_en_el_nombre(), test_todas_las_naturalezas_conocidas()

### Community 48 - "Fixture de ventana sin display"
Cohesion: 0.29
Nodes (7): BaseException, _es_fallo_de_entorno(), fixture, Si esto se relaja, un fallo real de `gui.py` pasa como prueba omitida., Una ventana real, sin mostrarla, y sin diálogos modales., test_solo_se_omite_por_entorno_no_por_un_bug_de_la_ventana(), ventana()

### Community 49 - "Mapa de cambios y alias"
Cohesion: 0.29
Nodes (7): Dónde tocar cada cosa (mapa de cambios), Todos los regex en patterns.py, con su texto real verificado, alias.json — 139 alias de opositores junto al .exe, writer.normalizar_alias — alias indexados por clave_comparacion, sin_tildes() preserva la ñ, Estrategia de extracción por expresiones regulares, Nombre corto del opositor (§8.7) — criterio humano

### Community 50 - "Caché y corrida definitiva"
Cohesion: 0.47
Nodes (6): Corrección 1 — carpeta salida\soportes\<expediente>\, Caché de la página del expediente (<EXP>_pagina.html), Corrida definitiva: 987 expedientes, 0 errores, PNG de 828 bytes con HTTP 200 desde GetFile.aspx, PDFs en salida\soportes\<expediente>\ con migración desde temp, Reusar PDFs ya descargados (reanudación)

### Community 51 - "Abrir carpeta de salida"
Cohesion: 0.50
Nodes (4): abrir_carpeta(), Path, Abre el explorador de archivos del sistema en esa carpeta., test_abrir_carpeta_crea_la_carpeta_y_llama_al_explorador()

### Community 52 - "Seguridad de celdas y HTTPS"
Cohesion: 0.50
Nodes (4): Corrección 3 — enlace del expediente en https, azul y subrayado, Celdas con data_type="s" (anti inyección de fórmulas), forzar_https — el puerto 80 de SIPI no responde, La columna A del Excel de entrada es fórmula HYPERLINK, no hyperlink

### Community 53 - "Invariante de fila por expediente"
Cohesion: 0.50
Nodes (4): Un expediente que falla sigue apareciendo en el Excel, Una fila por motivo de negación, Fixture HTTP Browse.aspx de SD2022/0097089 (BASIC FOODING MILKO), Texto de la resolución TM128 de SD2022/0097089

### Community 54 - "Fixtures de respuesta PDF"
Cohesion: 0.50
Nodes (4): pdf_real(), fixture, La respuesta real de SIPI cuando no entregó el documento: un PNG de 828 b., respuesta_no_pdf()

### Community 55 - "Generador de literales"
Cohesion: 0.67
Nodes (3): composite, _lista_de_literales(), Genera 'a)', 'a) y b)', 'a), c) y h)' — como escribe la SIC.

## Ambiguous Edges - Review These
- `Corrida definitiva: 987 expedientes, 0 errores` → `Texto de la resolución TM9 de SD2022/0000017`  [AMBIGUOUS]
  tests/fixtures/texto/SD2022-0000017_TM9.txt · relation: references
- `ExtraccionSIC.exe (Application)` → `alias (source file)`  [AMBIGUOUS]
  docs/carpeta.png · relation: references
- `Paso 1: Fila del Excel (fórmula HYPERLINK)` → `Paso 3: Descarga de los PDFs (TM9, TM128, TM6, apelación)`  [AMBIGUOUS]
  docs/flujo.svg · relation: conceptually_related_to
- `Extracción SIC 0.1.0 (Tkinter Desktop App)` → `Pipeline: SIPI Excel to PDFs to output Excel`  [AMBIGUOUS]
  docs/ventana.png · relation: implements

## Knowledge Gaps
- **15 isolated node(s):** `La nota al pie de productos cae dentro de la frase del opositor`, `El .exe no arranca desde una ruta UNC`, `Deuda: la coma de «artículo 136, literal h)» da 136 en vez de 136h`, `ErrorScraping — página sin la tabla de documentos`, `Segundo formato de salida «clasico»` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 415 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Corrida definitiva: 987 expedientes, 0 errores` and `Texto de la resolución TM9 de SD2022/0000017`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `ExtraccionSIC.exe (Application)` and `alias (source file)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Paso 1: Fila del Excel (fórmula HYPERLINK)` and `Paso 3: Descarga de los PDFs (TM9, TM128, TM6, apelación)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Extracción SIC 0.1.0 (Tkinter Desktop App)` and `Pipeline: SIPI Excel to PDFs to output Excel`?**
  _Edge tagged AMBIGUOUS (relation: implements) - confidence is low._
- **Why does `normalizar()` connect `Motivos de negación y zona de conclusión` to `Lectura del Excel de entrada`, `Detección y limpieza de opositor`, `Clases de Niza en oposiciones`, `Scraping y clasificación de documentos`, `Extracción de opositores`, `Normalización de texto`, `PDF a texto`, `Sembrado de alias`, `Marca y naturaleza`, `Página del expediente y modelos`, `Pruebas basadas en propiedades`, `Extractor de la resolución`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `SesionSIPI` connect `Sesión HTTP contra SIPI` to `Orquestación del pipeline`, `Configuración y rutas`, `Página del expediente y modelos`, `Descarga y validación de PDFs`, `Cerrojo de corrida y rutas Windows`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `texto_de_pdf()` connect `PDF a texto` to `Sesión HTTP contra SIPI`, `Orquestación del pipeline`, `Motivos de negación y zona de conclusión`, `Scripts de comparación de salida`, `Página del expediente y modelos`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._