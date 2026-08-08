"""Configuración de logging: archivo en salida/ + cola para la ventana."""

from __future__ import annotations

import logging
import queue
from datetime import datetime
from pathlib import Path


class FormatoSinTraza(logging.Formatter):
    """Como el normal, pero sin la traza de la excepción.

    Un traceback de Python en la ventana no le dice nada al usuario final y le
    hace pensar que el programa se rompió del todo. La traza completa sí va al
    archivo de log, que es donde sirve para arreglar algo.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Redefinir `formatException` no basta: si el handler de archivo formateó
        # antes, la traza ya está cacheada en `record.exc_text` y `Formatter`
        # la reutiliza sin volver a pasar por ahí. Hay que vaciar los tres
        # campos y devolverlos, porque el mismo record lo ven los demás handlers.
        guardados = (record.exc_info, record.exc_text, record.stack_info)
        record.exc_info = record.exc_text = record.stack_info = None
        try:
            return super().format(record).rstrip("\n")
        finally:
            record.exc_info, record.exc_text, record.stack_info = guardados


class ColaHandler(logging.Handler):
    """Empuja los registros a una cola que la GUI drena desde el hilo de tkinter.

    Los widgets de tkinter no son seguros entre hilos: tocarlos desde un worker
    cuelga la ventana de forma intermitente. La cola es la frontera.
    """

    def __init__(self, cola: queue.Queue[str]) -> None:
        super().__init__()
        self.cola = cola

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.cola.put_nowait(self.format(record))
        except queue.Full:  # pragma: no cover - la cola es ilimitada
            pass


def configurar(dir_salida: Path, cola: queue.Queue[str] | None = None) -> Path:
    """Deja el logging listo y devuelve la ruta del archivo de log."""
    dir_salida.mkdir(parents=True, exist_ok=True)
    archivo = dir_salida / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for viejo in list(raiz.handlers):
        raiz.removeHandler(viejo)

    formato = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", "%H:%M:%S")

    # encoding explícito: sin esto Windows usa cp1252 y rompe los acentos.
    a_archivo = logging.FileHandler(archivo, encoding="utf-8")
    a_archivo.setFormatter(formato)
    raiz.addHandler(a_archivo)

    if cola is not None:
        a_cola = ColaHandler(cola)
        a_cola.setFormatter(
            FormatoSinTraza("%(asctime)s %(levelname)-5s %(message)s", "%H:%M:%S")
        )
        raiz.addHandler(a_cola)

    return archivo
