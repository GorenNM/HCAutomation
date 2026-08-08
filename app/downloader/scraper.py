"""De la URL del expediente a la lista de documentos descargables.

`View.ashx?<id>` responde 302 hacia `Browse.aspx?sid=<sid>`, y ese HTML **ya
contiene** los enlaces `GetFile.aspx` de todos los documentos. No hace falta
navegador ni ejecutar JavaScript.

Los documentos se clasifican por el texto de la columna «Documento», nunca por
su posición: un expediente puede traer 3 documentos y otro 5.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.config import ESPERAS_CONTENIDO_SEG
from app.downloader.session import SesionSIPI
from app.models import DocumentLink, TipoDoc
from app.utils.text import normalizar, sin_tildes

log = logging.getLogger(__name__)

_ID_TABLA_DOCUMENTOS = "gvDocuments"

# El texto de la etiqueta manda. Se comprueba en este orden porque 'TM128' y
# 'TM9' comparten prefijo y las apelaciones llegan con nombres muy variados
# ('184 - TM Apelación confirma', 'SD 438 Apelación confirma registro...').
_PATRONES_TIPO: tuple[tuple[re.Pattern[str], TipoDoc], ...] = (
    (re.compile(r"\bTM\s*128\b", re.IGNORECASE), TipoDoc.TM128),
    (re.compile(r"\bTM\s*9\b", re.IGNORECASE), TipoDoc.TM9),
    (re.compile(r"\bTM\s*6\b", re.IGNORECASE), TipoDoc.TM6),
    (re.compile(r"apelacion", re.IGNORECASE), TipoDoc.APELACION),
)


class ErrorScraping(Exception):
    """La página del expediente no tiene la forma esperada."""


@dataclass(frozen=True)
class PaginaExpediente:
    url: str  # la URL final, tras el redirect: sirve de Referer para las descargas
    html: str


def clasificar(etiqueta: str) -> TipoDoc:
    """Traduce el texto de la columna «Documento» a un tipo conocido."""
    limpio = sin_tildes(normalizar(etiqueta))
    for patron, tipo in _PATRONES_TIPO:
        if patron.search(limpio):
            return tipo
    return TipoDoc.OTRO


def abrir_expediente(sesion: SesionSIPI, case_url: str) -> PaginaExpediente:
    """Sigue el redirect y devuelve el HTML del expediente.

    La cookie de sesión que deja esta petición es la que después habilita
    `GetFile.aspx`; sin abrir el expediente primero, las descargas fallan.
    """
    respuesta = sesion.obtener(case_url)
    return PaginaExpediente(url=respuesta.url, html=respuesta.text)


def extraer_documentos(html: str) -> list[DocumentLink]:
    """Saca los documentos de la tabla del Histórico de Documentos.

    Devuelve lista vacía si la tabla existe pero no tiene documentos; eso es un
    expediente sin documentos publicados, no un error.
    """
    sopa = BeautifulSoup(html, "html.parser")
    tabla = sopa.find(
        id=lambda valor: bool(valor) and _ID_TABLA_DOCUMENTOS in valor
    )
    if tabla is None:
        raise ErrorScraping(
            "La página del expediente no tiene la tabla de documentos "
            f"(«{_ID_TABLA_DOCUMENTOS}»). Puede que SIPI haya cambiado, que el "
            "expediente no exista o que la sesión haya caducado."
        )

    documentos: list[DocumentLink] = []
    for enlace in tabla.find_all("a", href=_es_enlace_de_archivo):
        etiqueta = normalizar(enlace.get_text(" ", strip=True))
        resolucion, fecha = _datos_de_la_fila(enlace)
        documentos.append(
            DocumentLink(
                tipo=clasificar(etiqueta),
                etiqueta=etiqueta,
                url=enlace["href"],
                resolucion_nr=resolucion or None,
                fecha=fecha or None,
            )
        )
    return documentos


def _abrir_con_reintentos(
    sesion: SesionSIPI, case_url: str
) -> tuple[PaginaExpediente, list[DocumentLink]]:
    for intento, espera in enumerate(ESPERAS_CONTENIDO_SEG, start=1):
        pagina = abrir_expediente(sesion, case_url)
        try:
            return pagina, extraer_documentos(pagina.html)
        except ErrorScraping as error:
            if intento == len(ESPERAS_CONTENIDO_SEG):
                raise
            log.warning(
                "%s: %s Reintento %d de %d en %.0f s",
                case_url,
                error,
                intento,
                len(ESPERAS_CONTENIDO_SEG),
                espera,
            )
            time.sleep(espera)
    raise AssertionError("inalcanzable")  # pragma: no cover


def _es_enlace_de_archivo(href: str | None) -> bool:
    return bool(href) and "GetFile.aspx" in href


def _datos_de_la_fila(enlace) -> tuple[str, str]:
    """Número de resolución y fecha, que están en las primeras celdas de la fila.

    Son informativos: si faltan (los anexos no los traen) no pasa nada.
    """
    fila = enlace.find_parent("tr")
    if fila is None:
        return "", ""
    celdas = [normalizar(c.get_text(" ", strip=True)) for c in fila.find_all("td")]
    resolucion = celdas[0] if len(celdas) > 0 else ""
    fecha = celdas[1] if len(celdas) > 1 else ""
    return resolucion, fecha


def documentos_de_expediente(
    sesion: SesionSIPI, case_url: str
) -> tuple[PaginaExpediente, list[DocumentLink]]:
    """Abre el expediente y devuelve la página y sus documentos.

    Reintenta si la página llega sin la tabla. En la corrida de los 987, dos
    expedientes fallaron así y **los dos funcionaron al volver a pedirlos un
    minuto después**: es el mismo tipo de tropiezo que el PNG de `files.py`,
    SIPI devolviendo algo distinto de lo suyo bajo carga sostenida.

    Si el expediente de verdad no existe, esto cuesta la espera completa antes
    de rendirse. Pasa dos veces de cada mil; esperar de más es preferible a
    marcar como perdido un expediente que sí estaba.
    """
    pagina, documentos = _abrir_con_reintentos(sesion, case_url)
    log.info(
        "%d documento(s) en %s: %s",
        len(documentos),
        pagina.url,
        ", ".join(d.tipo.value for d in documentos) or "ninguno",
    )
    return pagina, documentos
