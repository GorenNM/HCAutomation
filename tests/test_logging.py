"""Pruebas del registro: archivo en salida/ + cola hacia la ventana."""

from __future__ import annotations

import logging
import queue

import pytest

from app.utils.logging_setup import ColaHandler, FormatoSinTraza, configurar


@pytest.fixture
def registro_limpio():
    """Deja el logger raíz como estaba: `configurar` le quita los handlers."""
    raiz = logging.getLogger()
    previos, nivel = list(raiz.handlers), raiz.level
    yield raiz
    for handler in list(raiz.handlers):
        raiz.removeHandler(handler)
        handler.close()
    for handler in previos:
        raiz.addHandler(handler)
    raiz.setLevel(nivel)


def test_configurar_crea_el_archivo_y_lo_devuelve(tmp_path, registro_limpio):
    archivo = configurar(tmp_path / "salida")

    logging.getLogger("prueba").info("hola con tildes: ñáé")
    logging.shutdown()

    assert archivo.is_file()
    assert archivo.parent.name == "salida"
    # encoding explícito: sin esto Windows usa cp1252 y rompe los acentos.
    assert "ñáé" in archivo.read_text(encoding="utf-8")


def test_la_cola_recibe_lo_mismo_que_el_archivo(tmp_path, registro_limpio):
    cola: queue.Queue[str] = queue.Queue()
    archivo = configurar(tmp_path / "salida", cola)

    logging.getLogger("prueba").warning("algo que revisar")
    logging.shutdown()

    linea = cola.get_nowait()
    assert "algo que revisar" in linea
    assert "WARN" in linea
    assert "algo que revisar" in archivo.read_text(encoding="utf-8")


def test_la_traza_va_al_archivo_pero_nunca_a_la_ventana(tmp_path, registro_limpio):
    """Un traceback en la ventana solo asusta a quien no programa."""
    cola: queue.Queue[str] = queue.Queue()
    archivo = configurar(tmp_path / "salida", cola)

    try:
        raise RuntimeError("SIPI no responde")
    except RuntimeError:
        logging.getLogger("prueba").exception("la corrida falló")
    logging.shutdown()

    en_ventana = "\n".join(_vaciar(cola))
    assert "la corrida falló" in en_ventana
    assert "Traceback" not in en_ventana
    assert "RuntimeError" not in en_ventana

    en_archivo = archivo.read_text(encoding="utf-8")
    assert "Traceback" in en_archivo, "la traza sí tiene que quedar registrada"
    assert "SIPI no responde" in en_archivo


def test_el_orden_de_los_handlers_no_cambia_el_resultado(tmp_path, registro_limpio):
    """El archivo cachea la traza en el record; la cola no puede heredarla."""
    cola: queue.Queue[str] = queue.Queue()
    configurar(tmp_path / "salida", cola)
    raiz = logging.getLogger()
    raiz.handlers.reverse()  # ahora la cola formatea primero

    try:
        raise ValueError("boom")
    except ValueError:
        raiz.error("falló", exc_info=True)
    logging.shutdown()

    assert "Traceback" not in "\n".join(_vaciar(cola))


def test_configurar_dos_veces_no_duplica_las_lineas(tmp_path, registro_limpio):
    cola: queue.Queue[str] = queue.Queue()
    configurar(tmp_path / "salida", cola)
    configurar(tmp_path / "salida", cola)

    logging.getLogger("prueba").info("una sola vez")
    logging.shutdown()

    assert len(_vaciar(cola)) == 1


def test_una_cola_llena_no_tumba_la_corrida(tmp_path, registro_limpio):
    llena: queue.Queue[str] = queue.Queue(maxsize=1)
    llena.put("ocupada")
    handler = ColaHandler(llena)
    handler.setFormatter(FormatoSinTraza("%(message)s"))

    handler.emit(
        logging.LogRecord("x", logging.INFO, __file__, 1, "se pierde", None, None)
    )  # no debe lanzar


def _vaciar(cola: queue.Queue[str]) -> list[str]:
    lineas = []
    while not cola.empty():
        lineas.append(cola.get_nowait())
    return lineas
