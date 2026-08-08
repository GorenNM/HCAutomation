"""Normalización de texto.

Los PDFs de la SIC parten frases a mitad de línea y a veces cortan palabras con
guion. Los regex de extracción se aplican SIEMPRE sobre `normalizar()`; el texto
original se conserva aparte porque es lo que se muestra al usuario.
"""

from __future__ import annotations

import re
import unicodedata

_GUION_PARTIDO = re.compile(r"(\w)[-‐‑]\s*\n\s*(\w)")
_ESPACIOS = re.compile(r"\s+")
_SUFIJOS_SOCIETARIOS = re.compile(
    r"\b(s\.?a\.?s\.?|s\.?a\.?|ltda\.?|s\.?l\.?|inc\.?|llc\.?|gmbh|corp\.?|"
    r"co\.?|limited|company|de c\.?v\.?)\b",
    re.IGNORECASE,
)


def normalizar(texto: str) -> str:
    """Colapsa el texto a una sola línea con espacios simples.

    Reúne las palabras partidas por guion al final de línea antes de colapsar,
    porque hacerlo después ya no se puede distinguir de un guion legítimo.
    """
    if not texto:
        return ""
    unido = _GUION_PARTIDO.sub(r"\1\2", texto)
    return _ESPACIOS.sub(" ", unido).strip()


def sin_tildes(texto: str) -> str:
    """Quita diacríticos. Para comparar, nunca para mostrar.

    La ñ se preserva: en español es una letra distinta, no una n acentuada.
    Sin esto, 'MUÑOZ' y 'MUNOZ' darían la misma clave y se fundirían dos
    opositores diferentes en uno solo.

    Se conserva la virgulilla solo cuando va sobre una n, en vez de sustituir
    la ñ por un marcador temporal: un marcador puede aparecer en el texto real
    (los PDFs traen caracteres de control) y saldría convertido en ñ.
    """
    conservados: list[str] = []
    for caracter in unicodedata.normalize("NFD", texto):
        if unicodedata.category(caracter) != "Mn":
            conservados.append(caracter)
        elif caracter == "̃" and conservados and conservados[-1] in "nN":
            conservados.append(caracter)
    return unicodedata.normalize("NFC", "".join(conservados))


def clave_comparacion(nombre: str) -> str:
    """Forma canónica de un nombre de empresa, para emparejar menciones.

    'Grupo Diagnóstico S.A. Dimed S.A.' y 'GRUPO DIAGNOSTICO DIMED'
    deben dar la misma clave: en una resolución el mismo opositor aparece
    escrito de varias formas.
    """
    limpio = sin_tildes(nombre).casefold()
    limpio = _SUFIJOS_SOCIETARIOS.sub(" ", limpio)
    limpio = re.sub(r"[^\w\s]", " ", limpio)
    return _ESPACIOS.sub(" ", limpio).strip()


def _apto_para_celda(caracter: str) -> bool:
    """Filtro por carácter para `sanear_para_excel`.

    Fuera van los de control (openpyxl lanza `IllegalCharacterError`) y los
    subrogados sueltos. Estos últimos son peores: openpyxl los guarda sin
    protestar y el `.xlsx` resultante ya **no se puede volver a abrir** —
    el parser XML muere con «reference to invalid character number».
    `pypdf` los produce con PDFs de codificación rara.
    """
    if caracter in "\n\t":
        return True
    punto = ord(caracter)
    return punto >= 32 and not 0xD800 <= punto <= 0xDFFF


def sanear_para_excel(valor: str, limite: int) -> str:
    """Deja el texto apto para una celda: sin caracteres prohibidos, acotado.

    Excel rechaza celdas de más de 32 767 caracteres. Truncar con marca visible
    es preferible a perder la fila entera.
    """
    if not valor:
        return ""
    limpio = "".join(c for c in valor if _apto_para_celda(c))
    if len(limpio) > limite:
        marca = "… [truncado]"
        return limpio[: limite - len(marca)] + marca
    return limpio


# El reporte de SIPI exporta las URLs con http://, pero el puerto 80 del sitio
# no responde: un enlace http:// se queda colgado hasta agotar el timeout del
# navegador. Por https contesta en menos de dos segundos. Vive aquí (y no en
# `downloader.session`) porque también el writer necesita reescribir el enlace
# que va al Excel de salida, y los módulos no se importan entre sí.
_HTTP_SIPI = re.compile(r"^http://(?=[^/]*sic\.gov\.co)", re.IGNORECASE)


def forzar_https(url: str) -> str:
    return _HTTP_SIPI.sub("https://", url)


def nombre_archivo_seguro(texto: str) -> str:
    """Convierte un expediente en un nombre de archivo válido en Windows.

    'SD2022/0000017' -> 'SD2022-0000017'
    """
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", texto).strip(" .")
