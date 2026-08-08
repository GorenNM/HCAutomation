# -*- coding: utf-8 -*-
"""Genera los dos diagramas de DOCUMENTACION.md, en SVG y PNG.

    python docs/gen_diagramas.py

Se sigue `guia-diagramas-imagen.md`: el SVG se compone a mano y se rasteriza con
`cairosvg`. Las invariantes que no se tocan, porque cada una viene de un fallo
real (§12 de la guía):

* `font-family` DejaVu — es la única fuente que cairosvg tiene garantizada.
  Con cualquier otra el PNG sale con métricas mal calculadas y texto desbordado.
* Los acentos se escriben como `\\uXXXX` en el fuente y el XML se escapa: un `&`
  o un `<` suelto en un `<text>` rompe el parser.
* Las flechas se dibujan **antes** que las tarjetas, para que ninguna línea
  quede por encima de una caja.
* La altura del lienzo y la del último contenedor se cuadran al contenido: es el
  origen habitual de los recortes.

`cairosvg` está en `requirements-dev.txt`, no en las dependencias del programa:
los diagramas se generan una vez y se versionan como archivos.
"""

from __future__ import annotations

import sys
from pathlib import Path

SALIDA = Path(__file__).resolve().parent

FUENTE = "DejaVu Sans, Arial, sans-serif"

PAGINA = "#FFFFFF"
BANDA_FONDO = "#FAFCFE"
BANDA_BORDE = "#DCE3EB"
TARJETA_FONDO = "#FFFFFF"
TARJETA_BORDE = "#C7D0DA"
FLECHA = "#6B7A8A"
TXT_TITULO = "#16202C"
TXT_SUB = "#5A6B7B"
TXT_NOMBRE = "#1A2A3A"
TXT_TAG = "#7B8794"
TXT_BANDA = "#5E6E7E"

# Una categoría, un color. Se repiten en los dos diagramas para que se lean juntos.
ENTRADA = "#2E6FE8"  # lee del Excel
RED_ = "#8C4FFF"  # habla con SIPI
ANALISIS = "#E8770F"  # interpreta los PDFs
SALIDA_C = "#2E8B57"  # escribe el resultado
CONTROL = "#5A6B7B"  # orquesta
FALLO = "#C0392B"  # puntos donde se puede fallar


def marcador() -> str:
    return (
        f'<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M2 1 L8 5 L2 9" fill="none" stroke="{FLECHA}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/></marker></defs>'
    )


def flecha(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{FLECHA}" '
        f'stroke-width="1.6" marker-end="url(#arr)"/>'
    )


def titulo(texto: str, subtitulo: str) -> str:
    return (
        f'<text x="28" y="44" font-family="{FUENTE}" font-size="18" font-weight="bold" '
        f'fill="{TXT_TITULO}">{texto}</text>'
        f'<text x="28" y="66" font-family="{FUENTE}" font-size="11.5" '
        f'fill="{TXT_SUB}">{subtitulo}</text>'
    )


def banda(x: float, y: float, ancho: float, alto: float, etiqueta: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{ancho}" height="{alto}" rx="10" '
        f'fill="{BANDA_FONDO}" stroke="{BANDA_BORDE}" stroke-width="1" '
        f'stroke-dasharray="6,4"/>'
        f'<text x="{x + 16}" y="{y + 18}" font-family="{FUENTE}" font-size="10.5" '
        f'font-weight="bold" fill="{TXT_BANDA}" letter-spacing="0.3">{etiqueta}</text>'
    )


def tamano_nombre(nombre: str) -> float:
    """Los nombres largos desbordan a 11.5px. Ver §6.4 de la guía."""
    return max(9.3, min(11.5, 152 / (len(nombre) * 0.60)))


def tarjeta(
    izq: float,
    arriba: float,
    ancho: float,
    alto: float,
    nombre: str,
    detalle: str,
    tag: str,
    color: str,
) -> str:
    partes = [
        f'<rect x="{izq}" y="{arriba}" width="{ancho}" height="{alto}" rx="8" '
        f'fill="{TARJETA_FONDO}" stroke="{TARJETA_BORDE}" stroke-width="1"/>',
        f'<rect x="{izq}" y="{arriba + 10}" width="5" height="{alto - 20}" rx="2.5" '
        f'fill="{color}"/>',
    ]
    fs = tamano_nombre(nombre)
    partes.append(
        f'<text x="{izq + 20}" y="{arriba + 26}" font-family="{FUENTE}" '
        f'font-size="{fs:.1f}" font-weight="bold" fill="{TXT_NOMBRE}">{nombre}</text>'
    )
    partes.append(
        f'<text x="{izq + 20}" y="{arriba + 46}" font-family="{FUENTE}" font-size="11" '
        f'font-weight="bold" fill="{color}">{detalle}</text>'
    )
    partes.append(
        f'<text x="{izq + 20}" y="{arriba + 63}" font-family="{FUENTE}" font-size="9" '
        f'fill="{TXT_TAG}">{tag}</text>'
    )
    return "".join(partes)


def chip(x: float, y: float, color: str, texto: str) -> tuple[str, float]:
    """Devuelve el chip y la x donde empieza el siguiente."""
    svg = (
        f'<rect x="{x}" y="{y - 10}" width="13" height="13" rx="3" fill="{color}"/>'
        f'<text x="{x + 20}" y="{y}" font-family="{FUENTE}" font-size="10.5" '
        f'fill="{TXT_BANDA}">{texto}</text>'
    )
    return svg, x + 26 + len(texto) * 6.3


# --- Diagrama 1: arquitectura -------------------------------------------------


def arquitectura() -> str:
    ancho, alto = 1340, 690
    cw, ch = 232, 84
    columnas = [176, 452, 728, 1004]
    fila1, fila2, fila3 = 168, 312, 456

    modulos = {
        "reader": (columnas[0], fila1, "excel/reader.py", "987 filas", "lee el reporte", ENTRADA),
        "scraper": (columnas[1], fila1, "downloader/scraper.py", "3–5 documentos", "lista los PDFs", RED_),
        "session": (columnas[2], fila1, "downloader/session.py", "HTTPS · reintentos", "una por hilo", RED_),
        "files": (columnas[3], fila1, "downloader/files.py", "%PDF- · %%EOF", "descarga y valida", RED_),
        "pdf": (columnas[1], fila2, "parser/pdf_text.py", "PDF → texto", "quita cabeceras", ANALISIS),
        "patterns": (columnas[2], fila2, "parser/patterns.py", "12 patrones", "todos los regex", ANALISIS),
        "extractor": (columnas[3], fila2, "parser/extractor.py", "zona de conclusión", "saca los datos", ANALISIS),
        "writer": (columnas[3], fila3, "excel/writer.py", "1 fila por motivo", "escribe la salida", SALIDA_C),
        "gui": (columnas[0], fila3, "gui.py", "tkinter · queue", "lo que ve el usuario", CONTROL),
        "pipeline": (columnas[1], fila3, "pipeline.py", "hasta 8 hilos", "orquesta todo", CONTROL),
    }

    partes: list[str] = []
    add = partes.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
        f'viewBox="0 0 {ancho} {alto}">')
    add(marcador())
    add(f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="{PAGINA}"/>')
    add(titulo(
        "Extracción SIC — arquitectura",
        "10 módulos dentro de un único .exe · ninguna dependencia con binario "
        "compilado · sin servidor, sin navegador",
    ))

    add(banda(40, 138, 1260, 128, "Entrada y descarga · del Excel a los PDFs en disco"))
    add(banda(40, 282, 1260, 128, "Análisis · del PDF a los datos"))
    add(banda(40, 426, 1260, 128, "Control y salida"))

    aristas = [
        ("reader", "scraper"),
        ("scraper", "session"),
        ("session", "files"),
        ("scraper", "pdf"),
        ("files", "extractor"),
        ("pdf", "patterns"),
        ("patterns", "extractor"),
        ("extractor", "writer"),
        ("gui", "pipeline"),
        ("pipeline", "writer"),
    ]
    for origen, destino in aristas:
        cx1, arriba1, *_ = modulos[origen]
        cx2, arriba2, *_ = modulos[destino]
        if arriba1 == arriba2:
            # Misma fila: de costado a costado, nunca de abajo hacia arriba.
            add(flecha(cx1 + cw // 2, arriba1 + ch // 2, cx2 - cw // 2, arriba2 + ch // 2))
        else:
            add(flecha(cx1, arriba1 + ch, cx2, arriba2))

    # pipeline -> reader: sale de costado y sube por la columna 0, que está vacía
    # en la fila del medio. Es el único canal libre; por el margen no cabe.
    # El canal va en x=270 y no en el centro de la columna para pasar por detrás
    # del rótulo de la banda del medio, que llega hasta unos 245 px.
    px, parriba, *_ = modulos["pipeline"]
    _rx, rarriba, *_ = modulos["reader"]
    canal = 270
    add(f'<path d="M{px - cw // 2},{parriba + ch // 2} H{canal} V{rarriba + ch}" '
        f'fill="none" stroke="{FLECHA}" stroke-width="1.6" marker-end="url(#arr)"/>')

    for cx, arriba, nombre, detalle, tag, color in modulos.values():
        add(tarjeta(cx - cw // 2, arriba, cw, ch, nombre, detalle, tag, color))

    ly = 574
    add(f'<rect x="40" y="{ly}" width="1260" height="86" rx="10" fill="{TARJETA_FONDO}" '
        f'stroke="{TARJETA_BORDE}" stroke-width="1"/>')
    add(f'<text x="58" y="{ly + 24}" font-family="{FUENTE}" font-size="11.5" '
        f'font-weight="bold" fill="{TXT_BANDA}">Leyenda</text>')
    x = 58
    for color, texto in (
        (ENTRADA, "lee el Excel de entrada"),
        (RED_, "habla con SIPI"),
        (ANALISIS, "interpreta los PDFs"),
        (SALIDA_C, "escribe el Excel de salida"),
        (CONTROL, "orquesta"),
    ):
        svg, x = chip(x, ly + 52, color, texto)
        add(svg)
    add(f'<text x="58" y="{ly + 76}" font-family="{FUENTE}" font-size="10.5" '
        f'fill="{TXT_BANDA}">Carpetas junto al .exe: temp\\ guarda los PDFs (se puede '
        f'borrar) · salida\\ guarda el Excel y el registro de la corrida</text>')
    add("</svg>")
    return "\n".join(partes)


# --- Diagrama 2: flujo de un expediente ---------------------------------------


def flujo() -> str:
    cw, ch = 248, 78
    izquierda = 300
    # El detalle de cada tarjeta no pasa de ~30 caracteres: a 11px en negrita,
    # más largo se sale de los 248 px de la tarjeta.
    pasos = [
        ("Fila del Excel", "fórmula HYPERLINK", "de ahí salen expediente y URL", ENTRADA),
        ("Página del expediente", "View.ashx → Browse.aspx", "la tabla ya trae los enlaces", RED_),
        ("Descarga de los PDFs", "TM9 · TM128 · TM6 · apelación", "se descartan los anexos", RED_),
        ("Texto de la resolución", "pypdf + quitar cabeceras", "todo en una sola línea", ANALISIS),
        ("Zona de conclusión", "8 000 car. antes de RESUELVE", "no cuentan los alegatos citados", ANALISIS),
        ("Motivos y opositores", "136a · 136h · …", "lo negado se descarta y se avisa", ANALISIS),
        ("N filas de salida", "una por motivo de negación", "el resto se repite en cada fila", SALIDA_C),
    ]
    fallos = [
        "",
        "SIPI caído o sin red → la fila sale con la explicación",
        "respuesta que no es PDF → se valida por sus bytes, no por el código HTTP",
        "PDF escaneado → se marca para revisar a mano, no hay OCR",
        "sin el marcador → se analiza el documento entero y se avisa",
        "causal no reconocida → fila con MOTIVO vacío y observación",
        "0 motivos → igual sale 1 fila: nunca desaparece un expediente",
    ]

    primero = 148
    salto = ch + 30  # hueco suficiente para que se vea la flecha entre tarjetas
    # El alto se calcula: bajarlo a ojo y olvidar el último elemento es el
    # recorte clásico que avisa el §8 de la guía.
    ly = primero + len(pasos) * salto + 12
    ancho, alto = 1340, ly + 70 + 30

    partes: list[str] = []
    add = partes.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
        f'viewBox="0 0 {ancho} {alto}">')
    add(marcador())
    add(f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="{PAGINA}"/>')
    add(titulo(
        "Flujo de un expediente",
        "de una fila del reporte a N filas de salida · a la derecha, qué pasa "
        "cuando cada paso falla",
    ))

    for indice in range(len(pasos) - 1):
        y1 = primero + indice * salto + ch
        y2 = primero + (indice + 1) * salto
        add(flecha(izquierda + cw // 2, y1, izquierda + cw // 2, y2))

    for indice, (nombre, detalle, tag, color) in enumerate(pasos):
        arriba = primero + indice * salto
        add(tarjeta(izquierda, arriba, cw, ch, nombre, detalle, tag, color))
        add(f'<circle cx="{izquierda - 34}" cy="{arriba + ch // 2}" r="15" '
            f'fill="{TARJETA_FONDO}" stroke="{color}" stroke-width="1.6"/>')
        add(f'<text x="{izquierda - 34}" y="{arriba + ch // 2 + 4}" '
            f'font-family="{FUENTE}" font-size="12" font-weight="bold" fill="{color}" '
            f'text-anchor="middle">{indice + 1}</text>')

        aviso = fallos[indice]
        if not aviso:
            continue
        y = arriba + ch // 2
        add(f'<line x1="{izquierda + cw}" y1="{y}" x2="{izquierda + cw + 26}" y2="{y}" '
            f'stroke="{FALLO}" stroke-width="1.2" stroke-dasharray="4,3"/>')
        add(f'<text x="{izquierda + cw + 34}" y="{y + 4}" font-family="{FUENTE}" '
            f'font-size="10.5" fill="{FALLO}">{aviso}</text>')

    add(f'<rect x="40" y="{ly}" width="1260" height="70" rx="10" fill="{TARJETA_FONDO}" '
        f'stroke="{TARJETA_BORDE}" stroke-width="1"/>')
    add(f'<text x="58" y="{ly + 24}" font-family="{FUENTE}" font-size="11.5" '
        f'font-weight="bold" fill="{TXT_BANDA}">Regla que no se rompe nunca</text>')
    add(f'<text x="58" y="{ly + 48}" font-family="{FUENTE}" font-size="10.5" '
        f'fill="{TXT_BANDA}">Un expediente que falla en cualquier paso sigue apareciendo '
        f'en el Excel, con las celdas vacías y el motivo del fallo en '
        f'«Observaciones». Perder una fila en silencio sería el peor error '
        f'posible: nadie la echaría de menos al revisar.</text>')
    add("</svg>")
    return "\n".join(partes)


# --- Generación ---------------------------------------------------------------


def escribir(nombre: str, svg: str) -> tuple[Path, Path]:
    ruta_svg = SALIDA / f"{nombre}.svg"
    ruta_png = SALIDA / f"{nombre}.png"
    ruta_svg.write_text(svg, encoding="utf-8")

    import cairosvg

    cairosvg.svg2png(
        url=str(ruta_svg), write_to=str(ruta_png), scale=2.0, background_color="#ffffff"
    )
    return ruta_svg, ruta_png


def main() -> int:
    for nombre, generador in (("arquitectura", arquitectura), ("flujo", flujo)):
        svg, png = escribir(nombre, generador())
        print(f"{svg.name}  {svg.stat().st_size // 1024} KB")
        print(f"{png.name}  {png.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
