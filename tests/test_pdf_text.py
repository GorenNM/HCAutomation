"""Pruebas de la lectura de PDFs."""

from __future__ import annotations

import json

import pytest

from app.parser.pdf_text import (
    ErrorPdf,
    PdfEscaneadoError,
    quitar_cabeceras,
    texto_crudo,
    texto_de_pdf,
)
from tests.conftest import HTTP


def _documentos(expediente: str):
    carpeta = HTTP / expediente.replace("/", "-")
    indice = carpeta / "indice.json"
    if not indice.is_file():
        pytest.skip("Faltan las fixtures HTTP")
    return carpeta, json.loads(indice.read_text(encoding="utf-8"))["documentos"]


@pytest.mark.parametrize(
    "expediente,tipo,minimo",
    [
        ("SD2022/0000017", "TM9", 15_000),
        ("SD2022/0001545", "TM128", 60_000),
        ("SD2022/0097089", "TM128", 90_000),
    ],
)
def test_las_resoluciones_reales_dan_texto_de_sobra(expediente, tipo, minimo):
    carpeta, documentos = _documentos(expediente)
    documento = next(d for d in documentos if d["tipo"] == tipo)

    texto = texto_de_pdf(carpeta / documento["archivo"])

    assert len(texto) > minimo
    assert "\n" not in texto  # queda en una sola línea


def test_las_cabeceras_de_pagina_desaparecen():
    """Si sobreviven, parten frases por la mitad y rompen los nombres."""
    carpeta, documentos = _documentos("SD2022/0001545")
    documento = next(d for d in documentos if d["tipo"] == "TM128")

    crudo = texto_crudo(carpeta / documento["archivo"])
    limpio = texto_de_pdf(carpeta / documento["archivo"])

    assert "Página 1 de 21" in crudo
    assert "Página" not in limpio
    assert "Ref. Expediente" not in limpio


def test_la_cabecera_partia_el_nombre_de_un_opositor():
    """Regresión concreta: en el PDF real la cabecera cae dentro del nombre."""
    carpeta, documentos = _documentos("SD2022/0001545")
    documento = next(d for d in documentos if d["tipo"] == "TM128")

    assert "Grupo Diagnóstico S.A. Dimed S.A." in texto_de_pdf(
        carpeta / documento["archivo"]
    )


@pytest.mark.parametrize(
    "texto,esperado",
    [
        (
            "la sociedad Grupo Resolución N° 78472 Ref. Expediente N° SD2022/0001545 "
            "Página 21 de 21 Diagnóstico S.A.",
            "la sociedad Grupo   Diagnóstico S.A.",
        ),
        ("Resolución N° 1 Ref. Expediente N° X Página 1 de 2", "  "),
        ("un texto cualquiera", "un texto cualquiera"),
    ],
)
def test_quitar_cabeceras(texto, esperado):
    assert quitar_cabeceras(texto).replace("  ", " ") == esperado.replace("  ", " ")


def test_un_pdf_escaneado_se_detecta_y_no_se_intenta_ocr():
    """El 'Poder' del expediente 0001545 es una imagen: 1 carácter de texto."""
    carpeta, documentos = _documentos("SD2022/0001545")
    anexos = [d for d in documentos if d["tipo"] == "OTRO"]

    fallos = []
    for anexo in anexos:
        try:
            texto_de_pdf(carpeta / anexo["archivo"])
        except PdfEscaneadoError as error:
            fallos.append(str(error))

    assert fallos, "alguno de los anexos tiene que dar PdfEscaneadoError"
    assert "escaneado" in fallos[0]
    assert "revisarlo a mano" in fallos[0]


def test_el_umbral_de_escaneado_es_configurable(tmp_path):
    carpeta, documentos = _documentos("SD2022/0000017")
    documento = next(d for d in documentos if d["tipo"] == "TM9")

    # Con un mínimo absurdo, hasta una resolución completa se marca.
    with pytest.raises(PdfEscaneadoError):
        texto_de_pdf(carpeta / documento["archivo"], minimo=10**9)


def test_un_archivo_que_no_es_pdf_da_errorpdf(tmp_path):
    falso = tmp_path / "roto.pdf"
    falso.write_bytes(b"esto no es un pdf")

    with pytest.raises(ErrorPdf) as error:
        texto_de_pdf(falso)

    assert "roto.pdf" in str(error.value)


def test_un_pdf_truncado_da_errorpdf(tmp_path):
    carpeta, documentos = _documentos("SD2022/0000017")
    documento = next(d for d in documentos if d["tipo"] == "TM9")
    entero = (carpeta / documento["archivo"]).read_bytes()

    cortado = tmp_path / "cortado.pdf"
    cortado.write_bytes(entero[: len(entero) // 3])

    with pytest.raises(ErrorPdf):
        texto_de_pdf(cortado)


def test_un_archivo_inexistente_da_errorpdf(tmp_path):
    with pytest.raises(ErrorPdf):
        texto_de_pdf(tmp_path / "no_existe.pdf")
