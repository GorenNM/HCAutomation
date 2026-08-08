"""Pruebas de normalización de texto.

Las entradas salen de los PDFs reales de la SIC, no de ejemplos cómodos.
"""

from __future__ import annotations

import pytest

from app.config import LIMITE_CELDA_EXCEL
from app.utils.text import (
    clave_comparacion,
    nombre_archivo_seguro,
    normalizar,
    sanear_para_excel,
    sin_tildes,
)


def test_normalizar_colapsa_saltos_de_linea_del_pdf():
    crudo = "está comprendido en la causal de\nirregistrabilidad   establecida\n en el"
    assert normalizar(crudo) == (
        "está comprendido en la causal de irregistrabilidad establecida en el"
    )


def test_normalizar_reune_palabra_partida_por_guion():
    assert normalizar("irregis-\ntrabilidad") == "irregistrabilidad"


def test_normalizar_respeta_guion_legitimo():
    # Un guion que no está al final de línea no debe desaparecer.
    assert normalizar("Bogotá D.C. - Colombia") == "Bogotá D.C. - Colombia"


@pytest.mark.parametrize("entrada", ["", "   ", "\n\n"])
def test_normalizar_vacios_no_revientan(entrada):
    assert normalizar(entrada) == ""


def test_normalizar_es_idempotente():
    crudo = "Marca  MALTAVITAN\n(Nominativa)  para\ndistinguir"
    una = normalizar(crudo)
    assert normalizar(una) == una


def test_sin_tildes_conserva_la_enie():
    # La ñ no es una tilde: quitarla cambiaría el nombre.
    assert sin_tildes("Diagnóstico") == "Diagnostico"
    assert "ñ" in sin_tildes("Muñoz")


def test_clave_comparacion_une_las_variantes_del_mismo_opositor():
    # Las dos formas aparecen en la misma resolución del expediente SD2022/0001545.
    a = clave_comparacion("Grupo Diagnóstico S.A. Dimed S.A.")
    b = clave_comparacion("GRUPO DIAGNOSTICO DIMED")
    assert a == b == "grupo diagnostico dimed"


def test_clave_comparacion_no_funde_empresas_distintas():
    assert clave_comparacion("LABORATORIOS INCOBRA") != clave_comparacion(
        "LABORATORIOS NATURAL FRESHLY"
    )


def test_sanear_para_excel_quita_caracteres_de_control():
    assert sanear_para_excel("hola\x00mundo\x07", LIMITE_CELDA_EXCEL) == "holamundo"


def test_sanear_para_excel_trunca_en_el_limite_de_la_celda():
    salida = sanear_para_excel("x" * 40_000, LIMITE_CELDA_EXCEL)
    assert len(salida) == LIMITE_CELDA_EXCEL
    assert salida.endswith("[truncado]")


def test_nombre_archivo_seguro_convierte_la_barra_del_expediente():
    assert nombre_archivo_seguro("SD2022/0000017") == "SD2022-0000017"


@pytest.mark.parametrize("prohibido", ['<', '>', ':', '"', "\\", "|", "?", "*"])
def test_nombre_archivo_seguro_elimina_todo_lo_que_ntfs_rechaza(prohibido):
    assert prohibido not in nombre_archivo_seguro(f"SD2022{prohibido}0001")
