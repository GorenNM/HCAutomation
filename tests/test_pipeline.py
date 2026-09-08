"""Pruebas de la orquestación.

Todo corre **offline** contra las respuestas grabadas de SIPI, y con 8 hilos
allí donde puede haber carrera. Lo que se busca aquí no es que el camino feliz
funcione, sino qué hace el sistema cuando algo revienta a mitad de la corrida.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import FrozenInstanceError

import openpyxl
import pytest

from app.excel.reader import ErrorLectura
from app.excel.writer import PRIMERA_FILA_DATOS
from app.models import TipoDoc
from app.pipeline import (
    TIPOS_UTILES,
    ErrorPipeline,
    Progreso,
    ejecutar,
    procesar_expediente,
)
from tests.conftest import (
    EXPEDIENTES_GRABADOS,
    SesionGrabadaMulti,
    fila_datos,
    formula_enlace,
)

pytestmark = pytest.mark.usefixtures("hay_fixtures_http")

# id interno de cada expediente dentro de la URL View.ashx?<id>
IDS = {
    "SD2022/0000017": "3857028",
    "SD2022/0001545": "3857575",
    "SD2022/0097089": "4371435",
}

# Lo que dice de verdad la columna 'Bajo Oposición' del reporte para cada uno.
# Ponerlo mal hace saltar el aviso de conflicto y ensucia todas las cuentas.
OPOSICION = {
    "SD2022/0000017": "No",
    "SD2022/0001545": "Sí",
    "SD2022/0097089": "Sí",
}

# Documentos de los tipos útiles (TM9/TM128/TM6/apelación) de cada expediente.
# 0001545 trae además dos anexos OTRO y 0097089 uno: esos no se descargan.
PDFS_UTILES = {"SD2022/0000017": 3, "SD2022/0001545": 3, "SD2022/0097089": 2}

# Motivos de negación -> filas que genera cada expediente.
FILAS = {"SD2022/0000017": 1, "SD2022/0001545": 1, "SD2022/0097089": 2}


def reporte_de(construir_reporte, expedientes, oposicion=None):
    filas = [
        fila_datos(
            formula_enlace(exp, IDS[exp]),
            marca=f"MARCA {n}",
            oposicion=oposicion or OPOSICION[exp],
        )
        for n, exp in enumerate(expedientes)
    ]
    return construir_reporte(filas)


def correr(entrada, tmp_path, **kwargs):
    kwargs.setdefault("fabrica_sesion", SesionGrabadaMulti)
    kwargs.setdefault("temp", tmp_path / "temp")
    kwargs.setdefault("salida", tmp_path / "salida.xlsx")
    return ejecutar(entrada, **kwargs)


def filas_del_excel(ruta):
    hoja = openpyxl.load_workbook(ruta)["Hoja1"]
    return [
        [celda.value for celda in fila]
        for fila in hoja.iter_rows(min_row=PRIMERA_FILA_DATOS)
    ]


# --- Camino completo, offline ------------------------------------------------


def test_un_expediente_recorre_todo_el_proceso(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])

    resultado = correr(entrada, tmp_path)

    assert resultado.progreso.expedientes == 1
    assert resultado.progreso.pdfs == 3  # apelación + TM9 + TM6
    assert len(resultado.registros) == 1
    assert resultado.registros[0].motivo == "136a"
    assert resultado.registros[0].extracted.naturaleza == "Nominativa"
    assert resultado.registros[0].extracted.apelacion is True
    assert not resultado.cancelado
    assert resultado.ruta_excel.is_file()


def test_los_tres_expedientes_reales_dan_cuatro_filas(tmp_path, construir_reporte):
    """0097089 tiene dos motivos: 3 expedientes -> 4 registros. Es el requisito."""
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    resultado = correr(entrada, tmp_path, hilos=3)

    assert resultado.progreso.expedientes == 3
    assert len(resultado.registros) == 4
    assert [r.motivo for r in resultado.registros] == ["136a", "136a", "136a", "136h"]
    assert filas_del_excel(resultado.ruta_excel).__len__() == 4


def test_las_filas_salen_en_el_orden_del_excel_de_entrada(tmp_path, construir_reporte):
    """Con 8 hilos el orden de terminación es aleatorio; el del Excel no."""
    orden = ["SD2022/0097089", "SD2022/0000017", "SD2022/0001545"]
    entrada = reporte_de(construir_reporte, orden)

    resultado = correr(entrada, tmp_path, hilos=8)

    expedientes = [r.source.expediente for r in resultado.registros]
    assert expedientes == ["SD2022/0097089", "SD2022/0097089", *orden[1:]]


def test_las_filas_de_un_expediente_quedan_contiguas(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 4)

    resultado = correr(entrada, tmp_path, hilos=8)

    expedientes = [r.source.expediente for r in resultado.registros]
    for expediente in set(expedientes):
        posiciones = [i for i, e in enumerate(expedientes) if e == expediente]
        bloques = [
            b
            for a, b in zip(posiciones, posiciones[1:])
            if b - a != 1  # un salto = otro expediente en medio
        ]
        # Cada aparición del expediente ocupa 1 o 2 filas seguidas; los saltos
        # solo pueden ser entre apariciones distintas, nunca dentro de una.
        assert len(bloques) == 3, expediente


def test_solo_se_descargan_los_tipos_utiles(tmp_path, construir_reporte):
    """0001545 trae dos anexos OTRO (uno escaneado): no se bajan."""
    entrada = reporte_de(construir_reporte, ["SD2022/0001545"])

    resultado = correr(entrada, tmp_path)

    assert TipoDoc.OTRO not in TIPOS_UTILES
    assert resultado.progreso.pdfs == 3  # de los 5 documentos del expediente
    # Los PDFs quedan en soportes\<expediente>\, junto al Excel de salida.
    assert len(list((tmp_path / "soportes" / "SD2022-0001545").glob("*.pdf"))) == 3


def test_la_segunda_corrida_reutiliza_los_pdfs(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, ["SD2022/0097089"])

    primera = correr(entrada, tmp_path)
    segunda = correr(entrada, tmp_path, salida=tmp_path / "otra.xlsx")

    assert primera.progreso.pdfs == PDFS_UTILES["SD2022/0097089"]
    assert segunda.progreso.pdfs == 0  # todos desde caché
    assert len(segunda.registros) == len(primera.registros)


def test_el_conflicto_entre_el_excel_y_el_pdf_lo_gana_el_pdf(
    tmp_path, construir_reporte
):
    """El reporte dice 'Sí' y la resolución dice que no hubo oposición."""
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"], oposicion="Sí")

    resultado = correr(entrada, tmp_path)
    datos = resultado.registros[0].extracted

    assert datos.presenta_oposicion is False
    assert any("Bajo Oposición" in aviso for aviso in datos.avisos)


# --- Caso 31: detener a mitad ------------------------------------------------


def test_caso_31_detener_escribe_el_excel_con_lo_procesado(
    tmp_path, construir_reporte
):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 20)
    detener = threading.Event()

    def al_progresar(estado):
        if estado.expedientes >= 5:
            detener.set()

    resultado = correr(
        entrada, tmp_path, hilos=4, detener=detener, al_progresar=al_progresar
    )

    assert resultado.cancelado
    assert 5 <= resultado.progreso.expedientes < 60, "no se detuvo, o no procesó nada"
    assert resultado.ruta_excel.is_file()
    assert len(filas_del_excel(resultado.ruta_excel)) == len(resultado.registros)


def test_caso_31_detenido_antes_de_empezar_escribe_un_excel_vacio(
    tmp_path, construir_reporte
):
    """Sin filas no se pierde el archivo: se escribe solo con cabeceras."""
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))
    detener = threading.Event()
    detener.set()

    resultado = correr(entrada, tmp_path, detener=detener)

    assert resultado.cancelado
    assert resultado.progreso.expedientes == 0
    assert resultado.registros == []
    assert filas_del_excel(resultado.ruta_excel) == []


def test_caso_31_ningun_registro_queda_a_medias(tmp_path, construir_reporte):
    """Un expediente cortado no puede aparecer con la mitad de sus motivos."""
    entrada = reporte_de(construir_reporte, ["SD2022/0097089"] * 12)
    detener = threading.Event()

    def al_progresar(estado):
        detener.set()  # cortar en cuanto termine el primero

    resultado = correr(
        entrada, tmp_path, hilos=2, detener=detener, al_progresar=al_progresar
    )

    por_fila: dict[int, int] = {}
    for registro in resultado.registros:
        por_fila[registro.source.fila] = por_fila.get(registro.source.fila, 0) + 1
    assert set(por_fila.values()) == {2}, "algún expediente salió con 1 de sus 2 motivos"


# --- Caso 32: excepción no prevista ------------------------------------------


class SesionQueRevienta(SesionGrabadaMulti):
    """Falla siempre en un expediente concreto, y con algo que nadie captura."""

    veneno = "3857575"  # SD2022/0001545

    def obtener(self, url, referer=None):
        if self.veneno in url:
            raise RuntimeError("boom inesperado")
        return super().obtener(url, referer)


def test_caso_32_una_excepcion_no_prevista_no_tumba_a_los_demas(
    tmp_path, construir_reporte
):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    resultado = correr(entrada, tmp_path, fabrica_sesion=SesionQueRevienta, hilos=3)

    assert resultado.progreso.expedientes == 3
    assert resultado.progreso.errores == 1
    assert any("boom inesperado" in error for error in resultado.errores)
    # Los otros dos se extrajeron de verdad.
    buenos = [r for r in resultado.registros if r.extracted.naturaleza]
    assert len(buenos) == 3  # 1 de 0000017 + 2 de 0097089


def test_caso_32_el_expediente_que_falla_sigue_apareciendo_en_la_salida(
    tmp_path, construir_reporte
):
    """No se puede perder una fila en silencio: quien revisa a mano no lo vería."""
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    resultado = correr(entrada, tmp_path, fabrica_sesion=SesionQueRevienta, hilos=3)

    fallido = [
        r for r in resultado.registros if r.source.expediente == "SD2022/0001545"
    ]
    assert len(fallido) == 1
    assert fallido[0].motivo is None
    assert "boom inesperado" in " ".join(fallido[0].extracted.avisos)
    assert len(filas_del_excel(resultado.ruta_excel)) == 4


class SesionSinRed(SesionGrabadaMulti):
    def obtener(self, url, referer=None):
        raise OSError("la red no responde")


def test_caso_32_sin_red_ningun_expediente_desaparece(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    resultado = correr(entrada, tmp_path, fabrica_sesion=SesionSinRed, hilos=3)

    assert resultado.progreso.errores == 3
    assert len(resultado.registros) == 3
    assert len(filas_del_excel(resultado.ruta_excel)) == 3


# --- Caso 33: dos corridas simultáneas ---------------------------------------


def test_caso_33_la_segunda_corrida_se_rechaza(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 8)
    arrancada = threading.Event()
    soltar = threading.Event()

    def al_progresar(_estado):
        arrancada.set()
        soltar.wait(5)

    fallo: list[BaseException] = []

    def primera():
        try:
            correr(entrada, tmp_path, hilos=2, al_progresar=al_progresar)
        except BaseException as error:  # pragma: no cover - solo si algo va mal
            fallo.append(error)

    hilo = threading.Thread(target=primera)
    hilo.start()
    try:
        assert arrancada.wait(10), "la primera corrida no arrancó"
        with pytest.raises(ErrorPipeline) as error:
            correr(entrada, tmp_path, salida=tmp_path / "segunda.xlsx")
    finally:
        soltar.set()
        hilo.join(30)

    assert "en curso" in str(error.value)
    assert not fallo


def test_caso_33_tras_terminar_se_puede_volver_a_correr(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])

    correr(entrada, tmp_path)
    segunda = correr(entrada, tmp_path, salida=tmp_path / "b.xlsx")

    assert segunda.ruta_excel.is_file()


def test_caso_33_un_fallo_libera_el_cerrojo(tmp_path):
    """Si el cerrojo se quedara tomado, la app no volvería a correr nunca."""
    with pytest.raises(ErrorLectura):
        ejecutar(tmp_path / "no_existe.xlsx", salida=tmp_path / "s.xlsx")
    with pytest.raises(ErrorLectura):
        ejecutar(tmp_path / "no_existe.xlsx", salida=tmp_path / "s.xlsx")


# --- Caso 34: contadores bajo 8 hilos ----------------------------------------


def test_caso_34_los_contadores_cuadran_exactos_con_ocho_hilos(
    tmp_path, construir_reporte
):
    """40 expedientes, 8 hilos. Un `n += 1` sin cerrojo pierde incrementos aquí."""
    expedientes = list(EXPEDIENTES_GRABADOS) * 14  # 42
    entrada = reporte_de(construir_reporte, expedientes)

    resultado = correr(entrada, tmp_path, hilos=8)

    assert resultado.progreso.expedientes == len(expedientes)
    assert resultado.progreso.registros == len(resultado.registros)
    assert len(filas_del_excel(resultado.ruta_excel)) == len(resultado.registros)
    # 42 expedientes, 14 de ellos con dos motivos.
    assert len(resultado.registros) == 42 + 14


def test_caso_34_los_pdfs_se_cuentan_una_sola_vez(tmp_path, construir_reporte):
    """El mismo expediente 14 veces comparte archivos: la caché no puede contar."""
    entrada = reporte_de(construir_reporte, ["SD2022/0097089"] * 14)

    resultado = correr(entrada, tmp_path, hilos=8)

    assert resultado.progreso.pdfs == PDFS_UTILES["SD2022/0097089"]
    assert len(list((tmp_path / "soportes" / "SD2022-0097089").glob("*.pdf"))) == 2


def test_el_progreso_que_recibe_la_gui_es_inmutable(tmp_path, construir_reporte):
    """Si fuera mutable, la ventana leería contadores cambiando bajo sus pies."""
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    vistos: list[Progreso] = []

    correr(entrada, tmp_path, al_progresar=vistos.append)

    assert vistos and isinstance(vistos[0], Progreso)
    with pytest.raises(FrozenInstanceError):
        vistos[0].expedientes = 99


def test_un_callback_que_revienta_no_tumba_la_corrida(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    def al_progresar(_estado):
        raise ZeroDivisionError("la ventana se cerró en mal momento")

    resultado = correr(entrada, tmp_path, hilos=3, al_progresar=al_progresar)

    assert resultado.progreso.expedientes == 3
    assert len(resultado.registros) == 4


def test_el_progreso_nunca_retrocede(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 5)
    vistos: list[Progreso] = []

    correr(entrada, tmp_path, hilos=8, al_progresar=vistos.append)

    cuenta = [estado.expedientes for estado in vistos]
    assert cuenta == sorted(cuenta)
    assert cuenta[-1] == 15


# --- Sesiones y recursos -----------------------------------------------------


def test_cada_hilo_abre_su_propia_sesion_y_todas_se_cierran(
    tmp_path, construir_reporte
):
    creadas: list[SesionGrabadaMulti] = []

    def fabrica():
        sesion = SesionGrabadaMulti()
        creadas.append(sesion)
        return sesion

    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 4)
    correr(entrada, tmp_path, hilos=4, fabrica_sesion=fabrica)

    assert 1 <= len(creadas) <= 4, "una sesión por hilo, no una por expediente"
    assert all(sesion.cerrada for sesion in creadas)


@pytest.mark.parametrize("pedidos,esperado", [(0, 1), (-3, 1), (99, 8), (4, 4)])
def test_los_hilos_se_acotan_al_rango_permitido(
    tmp_path, construir_reporte, pedidos, esperado
):
    creadas = []

    def fabrica():
        sesion = SesionGrabadaMulti()
        creadas.append(sesion)
        return sesion

    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 6)
    correr(entrada, tmp_path, hilos=pedidos, fabrica_sesion=fabrica)

    assert len(creadas) <= esperado


# --- Entradas rotas ----------------------------------------------------------


def test_un_excel_de_entrada_inexistente_da_errorlectura(tmp_path):
    with pytest.raises(ErrorLectura):
        ejecutar(tmp_path / "fantasma.xlsx", salida=tmp_path / "s.xlsx")


def test_un_reporte_sin_filas_produce_un_excel_solo_con_cabeceras(
    tmp_path, construir_reporte
):
    resultado = correr(construir_reporte([]), tmp_path)

    assert resultado.progreso.total == 0
    assert filas_del_excel(resultado.ruta_excel) == []


def test_si_se_da_una_carpeta_el_nombre_lo_pone_el_pipeline(
    tmp_path, construir_reporte
):
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    carpeta = tmp_path / "resultados"

    resultado = correr(entrada, tmp_path, salida=carpeta)

    assert resultado.ruta_excel.parent == carpeta
    assert resultado.ruta_excel.name.startswith("Negacion_marcas_")


# --- Un expediente aislado ---------------------------------------------------


def test_procesar_expediente_devuelve_los_tres_datos(tmp_path, construir_reporte):
    from app.excel.reader import leer_reporte

    entrada = reporte_de(construir_reporte, ["SD2022/0001545"])
    (fuente,) = leer_reporte(entrada).filas

    registros, pdfs, problemas = procesar_expediente(
        SesionGrabadaMulti(), fuente, tmp_path / "temp"
    )

    assert len(registros) == 1
    assert pdfs == 3
    assert registros[0].extracted.opositores[0].fundada == "SI"
    # 136b se descartó por la negación léxica: eso llega como aviso, no como error.
    assert any("136b" in aviso for aviso in registros[0].extracted.avisos)
    assert problemas == []


def test_un_expediente_sin_resolucion_sale_con_la_observacion(
    tmp_path, construir_reporte
):
    from app.excel.reader import leer_reporte

    class SoloAnexos(SesionGrabadaMulti):
        """Devuelve la página pero ningún PDF baja bien."""

        def obtener(self, url, referer=None):
            if "GetFile" in url:
                from app.downloader.session import ErrorRed

                raise ErrorRed("no se pudo descargar")
            return super().obtener(url, referer)

    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    (fuente,) = leer_reporte(entrada).filas

    registros, pdfs, problemas = procesar_expediente(
        SoloAnexos(), fuente, tmp_path / "temp"
    )

    assert pdfs == 0
    assert len(registros) == 1
    assert registros[0].motivo is None
    assert any("resolución" in problema for problema in problemas)


# --- Duración ----------------------------------------------------------------


def test_ocho_hilos_no_serializan_la_corrida(tmp_path, construir_reporte):
    """Si el cerrojo de contadores abrazara el trabajo, esto tardaría 8 veces más."""
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS) * 8)

    comienzo = time.monotonic()
    correr(entrada, tmp_path, hilos=8)
    duracion = time.monotonic() - comienzo

    assert duracion < 60, f"24 expedientes offline tardaron {duracion:.1f} s"


# --- Caché de la página del expediente ---------------------------------------


def test_la_pagina_se_guarda_en_cache_y_no_se_vuelve_a_pedir(
    tmp_path, construir_reporte
):
    """Medido sobre los 987: sin esto, repetir la corrida no converge.

    La segunda pasada recuperaba los expedientes caídos pero exponía otros
    nuevos al mismo tropiezo, porque volvía a pedir las 987 páginas.
    """
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))
    sesiones = []

    def fabrica():
        sesion = SesionGrabadaMulti()
        sesiones.append(sesion)
        return sesion

    correr(entrada, tmp_path, fabrica_sesion=fabrica, hilos=1)
    correr(entrada, tmp_path, fabrica_sesion=fabrica, hilos=1, salida=tmp_path / "b.xlsx")

    primera, segunda = sesiones
    assert any("View.ashx" in u for u in primera.pedidas)
    assert segunda.pedidas == [], "la segunda corrida no debería tocar la red"


def test_la_segunda_corrida_da_exactamente_lo_mismo(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, list(EXPEDIENTES_GRABADOS))

    primera = correr(entrada, tmp_path)
    segunda = correr(entrada, tmp_path, salida=tmp_path / "b.xlsx")

    assert filas_del_excel(segunda.ruta_excel) == filas_del_excel(primera.ruta_excel)


def test_sin_reusar_la_pagina_se_vuelve_a_pedir(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    sesiones = []

    def fabrica():
        sesion = SesionGrabadaMulti()
        sesiones.append(sesion)
        return sesion

    correr(entrada, tmp_path, fabrica_sesion=fabrica)
    correr(
        entrada, tmp_path, fabrica_sesion=fabrica, reusar=False, salida=tmp_path / "b.xlsx"
    )

    assert any("View.ashx" in u for u in sesiones[1].pedidas)


def test_una_pagina_en_cache_corrupta_se_vuelve_a_pedir(tmp_path, construir_reporte):
    """La caché no puede envenenar la corrida siguiente."""
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    correr(entrada, tmp_path)

    (cache,) = (tmp_path / "temp").glob("*_pagina.html")
    cache.write_text("{no es json", encoding="utf-8")

    resultado = correr(entrada, tmp_path, salida=tmp_path / "b.xlsx")

    assert resultado.progreso.errores == 0
    assert resultado.registros[0].motivo == "136a"


def test_una_pagina_en_cache_sin_tabla_se_vuelve_a_pedir(tmp_path, construir_reporte):
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    correr(entrada, tmp_path)

    (cache,) = (tmp_path / "temp").glob("*_pagina.html")
    cache.write_text(
        '{"url": "https://x", "html": "<html>sin tabla</html>"}', encoding="utf-8"
    )

    resultado = correr(entrada, tmp_path, salida=tmp_path / "b.xlsx")

    assert resultado.progreso.errores == 0
    assert resultado.registros[0].extracted.naturaleza == "Nominativa"


def test_la_pagina_guardada_conserva_la_url_final(tmp_path, construir_reporte):
    """Es la que sirve de Referer para bajar los PDFs."""
    entrada = reporte_de(construir_reporte, ["SD2022/0000017"])
    correr(entrada, tmp_path)

    (cache,) = (tmp_path / "temp").glob("*_pagina.html")
    guardado = json.loads(cache.read_text(encoding="utf-8"))

    assert "Browse.aspx" in guardado["url"]
    assert "gvDocuments" in guardado["html"]
