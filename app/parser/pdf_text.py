"""PDF → texto listo para aplicar expresiones regulares.

Dos limpiezas que no son opcionales:

* **Cabecera de página.** Cada página repite
  `Resolución N° 78472 Ref. Expediente N° SD2022/0001545 Página 21 de 21`,
  y al concatenar las páginas ese bloque cae **en mitad de una frase**. En
  `SD2022/0001545` parte el nombre del opositor: «…la sociedad Grupo
  ‹cabecera› Diagnóstico S.A. Dimed S.A.». Sin quitarla, el nombre sale roto.
* **Normalización.** Los PDFs cortan las frases en cada línea, así que todos
  los regex del proyecto trabajan sobre una sola línea con espacios simples.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import MIN_CARACTERES_PDF
from app.utils.text import normalizar

log = logging.getLogger(__name__)

# 'Resolución N° 78472 Ref. Expediente N° SD2022/0001545 Página 21 de 21'
_CABECERA_PAGINA = re.compile(
    r"Resoluci[óo]n\s+N°\s*\d+\s*"
    r"Ref\.\s*Expediente\s+N°\s*\S+\s*"
    r"P[áa]gina\s+\d+\s+de\s+\d+",
    re.IGNORECASE,
)


class ErrorPdf(Exception):
    """El PDF no se pudo leer."""


class PdfEscaneadoError(ErrorPdf):
    """El PDF no tiene capa de texto: es una imagen.

    No se intenta OCR. Se marca el expediente para revisión manual antes que
    inventar datos a partir de un reconocimiento dudoso.
    """


def quitar_cabeceras(texto: str) -> str:
    return _CABECERA_PAGINA.sub(" ", texto)


def texto_crudo(ruta: Path) -> str:
    """Concatena el texto de todas las páginas, tal cual lo da pypdf."""
    try:
        lector = PdfReader(ruta)
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise ErrorPdf(f"No se pudo leer «{ruta.name}»: {exc}") from exc


def texto_de_pdf(ruta: Path, minimo: int = MIN_CARACTERES_PDF) -> str:
    """Devuelve el texto normalizado y sin cabeceras de página."""
    limpio = normalizar(quitar_cabeceras(texto_crudo(ruta)))
    if len(limpio) < minimo:
        raise PdfEscaneadoError(
            f"«{ruta.name}» no tiene texto seleccionable ({len(limpio)} caracteres): "
            "parece un documento escaneado. Hay que revisarlo a mano."
        )
    log.debug("%s: %d caracteres de texto", ruta.name, len(limpio))
    return limpio
