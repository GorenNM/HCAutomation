"""El manual tiene que seguir siendo cierto.

`DOCUMENTACION.md` cita textualmente los mensajes de la columna «Observaciones»
y las columnas del Excel de salida. En cuanto alguien cambie una frase en el
código, el manual pasa a mentir — y un manual que miente con autoridad es peor
que no tenerlo. Estas pruebas atan lo uno a lo otro.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import VERSION
from app.excel.writer import CABECERAS
from tests.conftest import RAIZ

MANUAL = RAIZ / "DOCUMENTACION.md"


@pytest.fixture(scope="module")
def manual() -> str:
    if not MANUAL.is_file():
        pytest.skip("Falta DOCUMENTACION.md")
    return MANUAL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def codigo() -> str:
    """Todo `app/` en una cadena, con los literales partidos ya reunidos.

    Un mensaje largo se escribe en varias líneas del fuente; al quitar comillas
    y colapsar espacios, el texto vuelve a quedar contiguo y se puede buscar.
    """
    crudo = "\n".join(
        ruta.read_text(encoding="utf-8") for ruta in sorted((RAIZ / "app").rglob("*.py"))
    )
    # Los prefijos f/r/rf van pegados a la comilla: si solo se quitan las
    # comillas queda una «f» suelta partiendo el mensaje justo por la mitad.
    sin_prefijos = re.sub(r"\b[fbru]{1,2}(?=[\"'])", "", crudo)
    return re.sub(r"\s+", " ", sin_prefijos.replace('"', "").replace("'", ""))


def literales_citados(manual: str) -> list[str]:
    """Los mensajes entre comillas invertidas de la tabla de la sección 5."""
    seccion = manual.split("## 5.")[1].split("## 6.")[0]
    return re.findall(r"\| `([^`]{20,})` \|", seccion)


def fragmentos_buscables(cita: str) -> list[str]:
    """Los trozos literales de un mensaje, sin lo que el programa interpola.

    Se corta por los valores variables y también por punto, porque un mensaje
    puede componerse de dos literales unidos con `+` y entonces la frase entera
    no existe en ningún sitio del fuente.

    Se devuelven **todos** los trozos, no solo el más largo: comprobar uno solo
    deja media frase sin vigilar, y ahí es justo donde se cuela la deriva.
    """
    partes = re.split(r"«[^»]*»|\b136[a-z]?\b|\d+|…|\.\s", cita)
    limpios = (re.sub(r"\s+", " ", parte).strip(" .:;,") for parte in partes)
    return [parte for parte in limpios if len(parte) >= 15]


# --- Sección 5: los mensajes de Observaciones --------------------------------


def test_la_seccion_5_documenta_bastantes_mensajes(manual):
    """Guarda contra un cambio de formato que dejara la tabla sin detectar."""
    assert len(literales_citados(manual)) >= 12


def test_todos_los_mensajes_documentados_existen_en_el_codigo(manual, codigo):
    huerfanos = [
        f"{cita}\n      → no está en el código: «{trozo}»"
        for cita in literales_citados(manual)
        for trozo in fragmentos_buscables(cita)
        if trozo not in codigo
    ]
    assert not huerfanos, (
        "El manual describe mensajes que el programa ya no emite:\n  "
        + "\n  ".join(huerfanos)
    )


def test_cada_mensaje_citado_deja_algo_que_comprobar(manual):
    """Si el troceado se quedara sin fragmentos, la prueba de arriba pasaría sola."""
    vacios = [c for c in literales_citados(manual) if not fragmentos_buscables(c)]
    assert not vacios, f"citas sin ningún trozo verificable: {vacios}"


@pytest.mark.parametrize(
    "frase",
    [
        # Los tres avisos que más le importan a quien revisa el Excel a mano.
        "no se cuenta como motivo",
        "no se pudo determinar la causal",
        "Conviene revisar esta fila a mano",
    ],
)
def test_los_avisos_criticos_estan_explicados_en_el_manual(manual, frase):
    assert frase in manual, f"«{frase}» sale en el Excel y no está en el manual"


# --- Sección 4: las columnas de la salida ------------------------------------


def test_el_manual_describe_todas_las_columnas_que_se_escriben(manual):
    seccion = manual.split("## 4.")[1].split("## 5.")[0]
    faltan = [
        cabecera for cabecera in CABECERAS["poc"] if cabecera not in seccion
    ]
    assert not faltan, f"columnas sin documentar: {faltan}"


def test_no_se_documentan_columnas_que_no_existen(manual):
    seccion = manual.split("## 4.")[1].split("## 5.")[0]
    inventadas = [
        nombre
        for nombre in ("MOTIVO 1 Negación", "MOTIVO 2 Negación")
        if f"| {nombre} |" in seccion
    ]
    assert not inventadas, f"el layout vigente no tiene: {inventadas}"


# --- Coherencia general ------------------------------------------------------


def test_el_manual_lleva_la_version_del_programa(manual):
    assert VERSION in manual.split("\n")[2], "la versión del encabezado no coincide"


def test_los_archivos_y_las_imagenes_que_enlaza_existen(manual):
    enlaces = re.findall(r"\]\((?!https?://)(?!#)([^)]+)\)", manual)
    rotos = [destino for destino in enlaces if not (RAIZ / destino).exists()]
    assert not rotos, f"enlaces rotos en el manual: {rotos}"


def test_las_nueve_secciones_del_plan_estan_todas(manual):
    for numero in range(1, 10):
        assert f"\n## {numero}. " in manual, f"falta la sección {numero}"


def test_los_comandos_de_la_seccion_9_son_los_que_existen(manual):
    seccion = manual.split("## 9.")[1]
    assert "construir_exe.bat" in seccion
    assert (RAIZ / "construir_exe.bat").is_file()
    assert "--autoprueba --red" in seccion
    assert "--red" in (RAIZ / "app" / "__main__.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "modulo",
    ["app/parser/patterns.py", "app/parser/extractor.py", "app/excel/writer.py",
     "app/excel/reader.py", "app/config.py"],
)
def test_los_modulos_que_el_manual_manda_tocar_existen(manual, modulo):
    assert modulo in manual
    assert (RAIZ / modulo).is_file()


# --- Diagramas ---------------------------------------------------------------


def test_los_diagramas_estan_generados_en_los_dos_formatos():
    """PNG para incrustar, SVG para poder editarlo sin regenerar."""
    for nombre in ("arquitectura", "flujo"):
        for extension in ("svg", "png"):
            ruta = RAIZ / "docs" / f"{nombre}.{extension}"
            assert ruta.is_file(), f"falta {ruta.name}"
            assert ruta.stat().st_size > 5_000, f"{ruta.name} parece vacío"


def test_los_svg_usan_la_unica_fuente_que_cairosvg_tiene(monkeypatch):
    """Con cualquier otra fuente el PNG sale con el texto desbordado."""
    for nombre in ("arquitectura", "flujo"):
        svg = (RAIZ / "docs" / f"{nombre}.svg").read_text(encoding="utf-8")
        assert "DejaVu Sans" in svg
        assert svg.count("font-family") == svg.count("DejaVu Sans")


def test_los_svg_son_xml_bien_formado():
    """Un `&` o un `<` sin escapar en un <text> rompe el rasterizado."""
    from xml.etree import ElementTree

    for nombre in ("arquitectura", "flujo"):
        ElementTree.parse(RAIZ / "docs" / f"{nombre}.svg")


def test_el_lienzo_de_cada_svg_cubre_todo_lo_que_dibuja():
    """El recorte por altura corta es el fallo clásico de este método."""
    for nombre in ("arquitectura", "flujo"):
        svg = (RAIZ / "docs" / f"{nombre}.svg").read_text(encoding="utf-8")
        alto = int(re.search(r'<svg[^>]*height="(\d+)"', svg).group(1))
        bordes = [
            int(y) + int(h)
            for y, h in re.findall(r'<rect[^>]*y="(\d+)"[^>]*height="(\d+)"', svg)
        ]
        assert max(bordes) <= alto, f"{nombre}.svg recorta por abajo"
        assert alto - max(bordes) <= 60, f"{nombre}.svg deja hueco vacío al final"


def test_el_generador_de_diagramas_es_reproducible(tmp_path, monkeypatch):
    """Correrlo dos veces tiene que dar el mismo archivo, byte a byte."""
    import docs.gen_diagramas as generador

    antes = (RAIZ / "docs" / "arquitectura.svg").read_text(encoding="utf-8")
    assert generador.arquitectura() == antes, "el SVG versionado está desactualizado"
    assert generador.flujo() == (RAIZ / "docs" / "flujo.svg").read_text(encoding="utf-8")
