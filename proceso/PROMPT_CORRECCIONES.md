# Prompt — Correcciones post-entrega, Extracción SIC

Copiar todo lo que sigue como prompt a un modelo con acceso al repo
`HCAutomation`.

---

## Contexto que debes leer antes de tocar nada

Este proyecto está marcado como "Fase 10/10 — terminado" en `ESTADO.md`, pero
el usuario final ya lo probó en Windows y encontró 7 puntos a corregir. Antes
de escribir una sola línea:

1. Lee `ESTADO.md` completo — especialmente la sección "Contexto no obvio"
   (34 puntos numerados de comportamientos verificados contra SIPI real) y
   "Deuda y limitaciones". Varias de las correcciones de abajo tocan
   decisiones que ya están documentadas ahí con su porqué; no las repitas
   a ciegas.
2. Lee `DOCUMENTACION.md` — es el manual de usuario final. Cualquier cambio
   de columnas, carpetas o comportamiento visible tiene que reflejarse ahí
   (`tests/test_documentacion.py` falla si el manual se desincroniza del
   código: no es opcional).
3. Lee `plan.md` para el diseño completo si algo no queda claro en los dos
   anteriores.
4. Revisa las salidas reales en `tests/propios/` — son corridas del usuario
   contra SIPI real, con sus `.log` y los `.xlsx` generados. Son la evidencia
   de los bugs del punto 7 (y de otros). Ábrelos con `openpyxl` antes de
   suponer nada.

Este proyecto tiene una cultura de trabajo específica, notoria en `ESTADO.md`:
cada decisión se verifica contra datos reales (nunca "debería funcionar"),
cada bug encontrado se documenta con el caso concreto que lo destapó, y
`ESTADO.md` + `DOCUMENTACION.md` se actualizan en el mismo cambio que el
código, no después. Sigue ese patrón para las correcciones.

---

## Correcciones pedidas

### 1. Carpeta `salida\soportes\<expediente>\` para los PDFs

Hoy los PDFs se descargan a `temp\` en un solo nivel, con nombres tipo
`SD2022-0000017_TM128.pdf` (ver `app/downloader/files.py`,
`app/config.py::dir_temp`). El usuario quiere que, dentro de `salida\`, exista
una carpeta `soportes\` y que cada expediente tenga su propio subdirectorio
con los PDFs de ese caso — no todo mezclado en un directorio plano.

Decide con criterio si esto **reemplaza** `temp\` o convive con él (recuerda
que `temp\` hoy cumple doble función: caché para reanudar corridas —punto 33
de `ESTADO.md`— y carpeta de descargas). Si migras la ruta de descarga,
revisa que la caché de páginas (`<EXP>_pagina.html`) y la reanudación
("Reusar PDFs") sigan funcionando igual de bien: es la única razón por la que
la 5ª pasada sobre los 987 expedientes tardó 171 s en vez de volver a fallar.
No rompas esa propiedad.

### 2. Mejoras de interfaz (NO prioritario)

La GUI (`app/gui.py`) funciona pero puede pulirse. 

### 3. El link de la columna "Número de Expediente" no lleva a la web

**Bug real ya identificado, verificado en `tests/propios/*.xlsx`:** el
hipervínculo se escribe correctamente como hipervínculo de Excel (no como
texto plano), pero apunta a una URL `http://sipi.sic.gov.co/...` — con
`http`, no `https`. Según el punto 2c de `ESTADO.md`, **el puerto 80 del
sitio no responde**: ese enlace se queda colgado hasta el timeout del
navegador. La causa es que `app/excel/reader.py::_parsear_enlace` guarda la
URL tal como viene en la fórmula `HYPERLINK` del Excel de entrada (siempre
`http://`), y `app/excel/writer.py` la usa tal cual al escribir
`celda.hyperlink`. La reescritura a `https://` (`session.forzar_https()`) hoy
solo se aplica a las peticiones de red, nunca a la URL que se guarda para el
Excel de salida.

Corrígelo para que el link de salida sea `https://` y apunte a un expediente
navegable. De paso, dale estilo de hipervínculo (azul,
subrayado) — hoy el texto sale con la fuente por defecto aunque el
hipervínculo esté técnicamente presente, así que a simple vista no parece
clicable.

### 4. Color amarillo en las columnas que el programa añade

El Excel de salida mezcla columnas que vienen del reporte original (Marca,
Titular, NIZA, Descripción...) con columnas que este programa calcula
(Naturaleza, Presenta Oposición, Opositor 1/2, MOTIVO Negación, Apelación,
Motivo #, Motivos totales, Observaciones — ver la tabla del §4 de
`DOCUMENTACION.md` para la lista exacta y cuáles son "de la resolución" vs
"del reporte de entrada"). El usuario quiere identificar de un vistazo qué es
dato nuevo vs. qué venía del Excel que él entregó: rellena de amarillo el
encabezado (o la columna entera) de las columnas generadas por el programa.
Hoy `app/excel/writer.py::_escribir_encabezado` pinta **todas** las
cabeceras del mismo gris (`DDDDDD`); tendrás que diferenciar por columna, no
aplicar un solo relleno global.

### 5. Mover "Descripción de Productos y Servicios" al final del Excel

**Aclaración importante, para no interpretar esto al revés:** las columnas
`Bajo Oposición`, `Apoderado`, `Fecha de Registro`, `Fecha de la
publicación`, `Fecha de prioridad` y `Otra Información` **deben quedar
fuera** del Excel de salida. Es el comportamiento actual y es el correcto —
no las agregues. Verificado en código:

- `Apoderado`, las 3 fechas y `Otra Información` ya no se leen en absoluto
  (`app/excel/reader.py::_COLUMNAS` no las mapea): correcto, déjalo así.
- `Bajo Oposición` sí se lee (`SourceRow.bajo_oposicion`) porque
  `app/pipeline.py` la usa para comparar contra lo que dice la resolución y
  generar el aviso `"el reporte dice «Bajo Oposición = ...» y la resolución
  dice lo contrario"` (documentado en §5 de `DOCUMENTACION.md`). Eso sigue
  igual. Lo único que nunca ha estado bien es que no se escriba como columna
  propia en el Excel de salida — y **eso también es intencional, no lo
  cambies**: sigue sin ser una columna de salida.

Lo único que hay que mover es la columna **"Descripción de Productos y
Servicios"**: hoy sale en medio del bloque `_COMUNES_DERECHA` de
`app/excel/writer.py` (junto a Titular y NIZA), antes de `Motivo #` /
`Motivos totales` / `Observaciones`. Tiene que pasar a ser la **última**
columna de todo el Excel, después de `Observaciones`. El resto de columnas
heredadas del original (Titular, NIZA) no cambian de posición — solo
Descripción se mueve al final. Actualiza `CABECERAS`, `_COMUNES_DERECHA` (o
como la reestructures) y `valores()` en consecuencia.

Cuando termines, actualiza la tabla de columnas del §4 de
`DOCUMENTACION.md` (los tests de documentación comprueban que coincide con lo
que escribe el writer) y el ejemplo de "una fila por motivo".

### 6. Bordes en negrilla para todo el Excel generado

Hoy no hay bordes en ninguna celda (`app/excel/writer.py` no aplica
`Border`). Aplica borde negro y grueso (`Side(style="thick", ...)` o el
equivalente que decidas — usa criterio de legibilidad, no tiene que ser
tan grueso que estorbe) a **todas** las celdas con datos, cabeceras
incluidas, desde la fila 1 hasta la última fila escrita. si puedes poner una linea mas gruesa a los titulos mucho mejor

### 7. Casos donde la extracción falla o saca datos incorrectos — investigar `tests/propios/`

El usuario dejó ahí corridas reales contra SIPI. Ya hay al menos un caso
confirmado, mirando `tests/propios/Negacion_marcas_20260807_190500.xlsx`,
expediente **`SD2022/0005052`** (marca "Marigold HEALT & CARE"): la columna
`Opositor 1` no contiene un nombre de opositor, sino un fragmento de la
descripción de productos ("minerales y antioxidantes en cuanto suplementos
nutricionales y dietéticos."), y `Art OP 1` sale `135b` — un artículo de la
familia 135 (causal absoluta), no 136 (causal relativa, que es la familia
que cubre `app/parser/patterns.py` según el punto 22 de `ESTADO.md`). Esto
huele a que `extraer_opositores()` (o el patrón que identifica al opositor)
está enganchando texto equivocado en ese PDF concreto — abre el PDF
correspondiente en las descargas de esa corrida (o vuelve a descargarlo) y
compara contra el texto real, siguiendo la misma disciplina que el resto del
proyecto: cada regex de `patterns.py` lleva el fragmento real del PDF contra
el que se verificó (mira los comentarios ya existentes ahí como ejemplo de
formato).

No te quedes solo con ese caso: recorre **las cinco corridas** en
`tests/propios/` (los `.xlsx` y sus `.log` correspondientes) fila por fila y
señala cualquier otra donde el dato extraído no cuadre con lo esperable —
opositor vacío cuando `Presenta Oposición = Sí`, `MOTIVO Negación` vacío sin
`Observaciones` que lo explique, naturaleza ausente, etc. Para cada uno que
confirmes: identifica el patrón de `patterns.py` o la función de
`extractor.py` responsable, arréglalo, y añade un caso de test en
`tests/test_extractor.py` con el texto real (o un extracto fiel) que lo
reproduce — es el patrón que ya sigue el proyecto para cada bug de
extracción (ver Fase 4 y Fase 6 en la bitácora de `ESTADO.md`).
excato, la idea es que (no prioritario ) hagas unos test con exceles reales, osea, del orginal partir unos par ahacerlocon esos
---

## Qué entregar

- Los 7 puntos corregidos (el 2 es opcional/no prioritario).
- `ESTADO.md` actualizado: nueva entrada en "Bitácora" con fecha de hoy,
  cualquier hallazgo nuevo sumado a "Contexto no obvio" si aplica (como el
  bug del `http://` o lo que salga del punto 7), y las columnas de
  "Deuda y limitaciones" corregidas por esto tachadas o quitadas.
- `DOCUMENTACION.md` actualizado: tabla de columnas (§4), y cualquier mención
  a `temp\` / `soportes\` en la sección "Qué queda en el disco" (§3).
- Tests nuevos o actualizados para cada corrección — especialmente los que
  fijan el bug de extracción del punto 7 y el de la URL `http://` del
  punto 3, que son los dos con mayor probabilidad de reaparecer si alguien
  toca ese código sin saber por qué está así.
- `pytest -q` en verde antes de dar por cerrado nada.

No asumas que un cambio "debería funcionar": este proyecto se rige por
verificar contra datos y archivos reales, no contra lo que parece razonable.
Todo lo que necesitas para eso ya está en el repo (`tests/propios/`,
`tests/data/`, `tests/fixtures/http/`).
