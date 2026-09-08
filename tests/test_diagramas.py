"""Los diagramas de `docs/` tienen que seguir siendo válidos y reproducibles.

Los SVG están versionados y el manual los incrusta como PNG. Cada aserción de
aquí viene de un fallo real del método: una fuente que cairosvg no tiene, un
`&` sin escapar, un lienzo más corto que lo que se dibuja encima.
"""

from __future__ import annotations

import re

from tests.conftest import RAIZ

NOMBRES = ("arquitectura", "flujo")


def test_los_diagramas_estan_generados_en_los_dos_formatos():
    """PNG para incrustar, SVG para poder editarlo sin regenerar."""
    for nombre in NOMBRES:
        for extension in ("svg", "png"):
            ruta = RAIZ / "docs" / f"{nombre}.{extension}"
            assert ruta.is_file(), f"falta {ruta.name}"
            assert ruta.stat().st_size > 5_000, f"{ruta.name} parece vacío"


def test_los_svg_usan_la_unica_fuente_que_cairosvg_tiene():
    """Con cualquier otra fuente el PNG sale con el texto desbordado."""
    for nombre in NOMBRES:
        svg = (RAIZ / "docs" / f"{nombre}.svg").read_text(encoding="utf-8")
        assert "DejaVu Sans" in svg
        assert svg.count("font-family") == svg.count("DejaVu Sans")


def test_los_svg_son_xml_bien_formado():
    """Un `&` o un `<` sin escapar en un <text> rompe el rasterizado."""
    from xml.etree import ElementTree

    for nombre in NOMBRES:
        ElementTree.parse(RAIZ / "docs" / f"{nombre}.svg")


def test_el_lienzo_de_cada_svg_cubre_todo_lo_que_dibuja():
    """El recorte por altura corta es el fallo clásico de este método."""
    for nombre in NOMBRES:
        svg = (RAIZ / "docs" / f"{nombre}.svg").read_text(encoding="utf-8")
        alto = int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))
        bordes = [
            int(y) + int(h)
            for y, h in re.findall(r'<rect[^>]*y="(\d+)"[^>]*height="(\d+)"', svg)
        ]
        assert max(bordes) <= alto, f"{nombre}.svg recorta por abajo"
        assert alto - max(bordes) <= 60, f"{nombre}.svg deja hueco vacío al final"


def test_el_generador_de_diagramas_es_reproducible():
    """Correrlo dos veces tiene que dar el mismo archivo, byte a byte."""
    import docs.gen_diagramas as generador

    antes = (RAIZ / "docs" / "arquitectura.svg").read_text(encoding="utf-8")
    assert generador.arquitectura() == antes, "el SVG versionado está desactualizado"
    assert generador.flujo() == (RAIZ / "docs" / "flujo.svg").read_text(encoding="utf-8")
