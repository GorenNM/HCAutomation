"""Pruebas del lector del Excel de entrada.

Las entradas deformadas están hechas
a propósito para romper el lector; las entradas buenas salen del reporte real.
"""

from __future__ import annotations

import time
import tracemalloc

import openpyxl
import pytest

from app.excel.reader import ErrorLectura, leer_reporte
from tests.conftest import CABECERAS_REPORTE, fila_datos, formula_enlace

# --- El caso feliz, contra datos reales --------------------------------------


def test_lee_el_reporte_real_completo(reporte_real):
    resultado = leer_reporte(reporte_real)

    assert len(resultado.filas) == 987
    assert not resultado.avisos

    primera = resultado.filas[0]
    assert primera.expediente == "SD2022/0000017"
    assert primera.case_url == "http://sipi.sic.gov.co/sipi/View.ashx?3857028"
    assert primera.marca == "MALTAVITAN"
    assert primera.niza == "5"
    assert primera.bajo_oposicion == "No"
    assert primera.fila == 12
    assert primera.titular.startswith("Pieter Carl Alexander Heshusius Florez")


def test_todas_las_filas_del_reporte_real_traen_enlace(reporte_real):
    resultado = leer_reporte(reporte_real)
    sin_enlace = [f.expediente for f in resultado.filas if not f.case_url]
    assert sin_enlace == []


@pytest.mark.parametrize(
    "mini,esperadas",
    [("mini_1_caso.xlsx", 1), ("mini_2_casos.xlsx", 2), ("mini_multimotivo.xlsx", 1)],
    indirect=["mini"],
)
def test_lee_los_recortes_reales(mini, esperadas):
    resultado = leer_reporte(mini)
    assert len(resultado.filas) == esperadas
    assert all(f.case_url.startswith("http") for f in resultado.filas)


@pytest.mark.parametrize("mini", ["mini_2_casos.xlsx"], indirect=True)
def test_el_caso_de_la_negacion_lexica_esta_en_el_recorte(mini):
    """El expediente SD2022/0001545 tiene que sobrevivir al recorte."""
    resultado = leer_reporte(mini)
    assert {f.expediente for f in resultado.filas} == {
        "SD2022/0000017",
        "SD2022/0001545",
    }


# --- Caso 25: Excel sin filas de datos ---------------------------------------


def test_excel_sin_filas_de_datos_no_revienta(construir_reporte):
    resultado = leer_reporte(construir_reporte([]))
    assert resultado.filas == []
    assert resultado.avisos == []
    assert resultado.expedientes_unicos == set()


def test_filas_completamente_vacias_se_ignoran_sin_aviso(construir_reporte):
    filas = [fila_datos(formula_enlace("SD2022/0000017")), [None] * 17, []]
    resultado = leer_reporte(construir_reporte(filas))
    assert len(resultado.filas) == 1
    assert resultado.avisos == []


# --- Caso 26: fórmula malformada ---------------------------------------------


@pytest.mark.parametrize(
    "celda",
    [
        '=HYPERLINK("http://sipi.sic.gov.co/sipi/View.ashx?3857028")',  # sin etiqueta
        "=HYPERLINK(",
        "=HYPERLINK()",
        "texto cualquiera sin expediente",
        "=SUMA(A1:A2)",
        "   ",
    ],
)
def test_fila_sin_expediente_reconocible_se_descarta_nombrando_la_fila(
    construir_reporte, celda
):
    ruta = construir_reporte([fila_datos(celda)])
    resultado = leer_reporte(ruta)

    assert resultado.filas == []
    assert len(resultado.avisos) == 1
    assert "Fila 12" in resultado.avisos[0]


def test_una_fila_rota_no_arrastra_a_las_buenas(construir_reporte):
    filas = [
        fila_datos(formula_enlace("SD2022/0000017")),
        fila_datos("=HYPERLINK("),
        fila_datos(formula_enlace("SD2022/0000038", "3857230")),
    ]
    resultado = leer_reporte(construir_reporte(filas))

    assert [f.expediente for f in resultado.filas] == [
        "SD2022/0000017",
        "SD2022/0000038",
    ]
    assert "Fila 13" in resultado.avisos[0]


# --- Caso 27: texto plano en vez de fórmula ----------------------------------


def test_expediente_en_texto_plano_se_acepta_sin_enlace(construir_reporte):
    ruta = construir_reporte([fila_datos("SD2022/0000017")])
    resultado = leer_reporte(ruta)

    assert len(resultado.filas) == 1
    fila = resultado.filas[0]
    assert fila.expediente == "SD2022/0000017"
    assert fila.case_url == ""
    # No se pierde el expediente, pero se avisa: no se podrá descargar.
    assert "no trae enlace" in resultado.avisos[0]


def test_url_que_no_es_de_sipi_no_se_toma_como_enlace(construir_reporte):
    celda = '=HYPERLINK("http://ejemplo.com/otra","SD2022/0000017")'
    resultado = leer_reporte(construir_reporte([fila_datos(celda)]))

    assert resultado.filas[0].expediente == "SD2022/0000017"
    assert resultado.filas[0].case_url == ""
    assert "no trae enlace" in resultado.avisos[0]


# --- Caso 28: expediente duplicado -------------------------------------------


def test_expediente_duplicado_conserva_las_dos_filas_y_avisa(construir_reporte):
    filas = [
        fila_datos(formula_enlace("SD2022/0000017"), marca="UNA"),
        fila_datos(formula_enlace("SD2022/0000017"), marca="OTRA"),
    ]
    resultado = leer_reporte(construir_reporte(filas))

    assert len(resultado.filas) == 2
    assert len(resultado.expedientes_unicos) == 1
    assert any("ya aparecía en la fila 12" in a for a in resultado.avisos)


# --- Caso 29: el archivo no es un xlsx ---------------------------------------


def test_archivo_que_no_es_excel_da_mensaje_claro(tmp_path):
    falso = tmp_path / "reporte.xlsx"
    falso.write_text("esto es un csv, no un xlsx", encoding="utf-8")

    with pytest.raises(ErrorLectura) as error:
        leer_reporte(falso)

    mensaje = str(error.value)
    assert "no es un archivo de Excel" in mensaje
    assert "reporte.xlsx" in mensaje
    # Nada de trazas de openpyxl en la cara del usuario.
    assert "openpyxl" not in mensaje.lower()


def test_archivo_inexistente_da_mensaje_claro(tmp_path):
    with pytest.raises(ErrorLectura, match="No se encontró"):
        leer_reporte(tmp_path / "no_existe.xlsx")


def test_excel_con_otras_cabeceras_dice_cuales_faltan(construir_reporte):
    ruta = construir_reporte([], cabeceras=["Cosa", "Otra cosa"])

    with pytest.raises(ErrorLectura) as error:
        leer_reporte(ruta)

    mensaje = str(error.value)
    assert "faltan las columnas" in mensaje
    assert "marca" in mensaje and "titular" in mensaje


# --- Robustez de la ubicación de columnas ------------------------------------


def test_las_columnas_se_ubican_por_nombre_no_por_posicion(construir_reporte):
    """Si SIPI inserta una columna al principio, el lector debe seguir sirviendo."""
    cabeceras = ["Columna nueva"] + CABECERAS_REPORTE
    fila = [None] + fila_datos(formula_enlace("SD2022/0000017"), marca="DESPLAZADA")
    resultado = leer_reporte(construir_reporte([fila], cabeceras=cabeceras))

    assert resultado.filas[0].marca == "DESPLAZADA"
    assert resultado.filas[0].expediente == "SD2022/0000017"


def test_cabeceras_sin_tildes_o_con_espacios_de_mas(construir_reporte):
    cabeceras = [c.upper().replace("Ú", "U") + "  " for c in CABECERAS_REPORTE]
    fila = fila_datos(formula_enlace("SD2022/0000017"))
    resultado = leer_reporte(construir_reporte([fila], cabeceras=cabeceras))

    assert len(resultado.filas) == 1


# --- Caso 30: reporte enorme -------------------------------------------------


def test_diez_mil_filas_no_revientan_la_memoria(tmp_path):
    """El lector debe ser un flujo, no cargar el libro entero en memoria."""
    ruta = tmp_path / "grande.xlsx"
    libro = openpyxl.Workbook(write_only=True)
    hoja = libro.create_sheet()
    for _ in range(10):
        hoja.append([None])
    hoja.append(CABECERAS_REPORTE)
    for i in range(10_000):
        hoja.append(fila_datos(formula_enlace(f"SD2022/{i:07d}", str(3800000 + i))))
    libro.save(ruta)
    libro.close()

    tracemalloc.start()
    inicio = time.monotonic()
    resultado = leer_reporte(ruta)
    duracion = time.monotonic() - inicio
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert len(resultado.filas) == 10_000
    assert resultado.filas[-1].expediente == "SD2022/0009999"
    # 10 000 SourceRow caben de sobra en 60 MB; si esto crece, es que se está
    # materializando el libro entero.
    assert pico < 60 * 1024 * 1024, f"pico de memoria {pico / 1e6:.1f} MB"
    # Techo generoso a propósito: aquí manda la aserción de memoria. Esto solo
    # caza una regresión de orden (un O(n²) al reindexar), y el reloj depende
    # de la máquina — `tracemalloc` ya infla la medida por sí solo. Una VM
    # lenta no puede tumbar la construcción del .exe por 3 segundos.
    assert duracion < 120, f"tardó {duracion:.1f} s"
