"""Descarga de los documentos a disco.

Dos reglas que no se negocian:

1. **El status code miente.** `GetFile.aspx` puede responder HTTP 200 con algo
   que no es un PDF (se observó un PNG de 828 bytes). El contenido se valida por
   sus bytes: `%PDF-` al principio y `%%EOF` al final. Lo segundo detecta las
   descargas cortadas a la mitad, que sí pasarían la primera comprobación.
2. **Escritura atómica.** Se escribe en `.part` y se renombra al terminar. Un
   corte de red no deja un PDF a medias que la siguiente corrida daría por bueno.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.config import ESPERAS_CONTENIDO_SEG
from app.downloader.session import ErrorRed, SesionSIPI
from app.models import DocumentLink, TipoDoc
from app.utils.text import nombre_archivo_seguro

log = logging.getLogger(__name__)

_CABECERA_PDF = b"%PDF-"
_FIN_PDF = b"%%EOF"
# El marcador final aparece en los últimos bytes; 2 KB es margen de sobra para
# los rellenos que dejan algunos generadores.
_COLA_A_REVISAR = 2048

# Intentos de `os.replace` sobre el mismo destino. Las esperas suman medio
# segundo: sobra para una carrera entre hilos del mismo proceso.
_INTENTOS_REEMPLAZO = 5


class ErrorDescarga(Exception):
    """No se pudo obtener o guardar un documento. Afecta a un expediente, no a la corrida."""


@dataclass(frozen=True)
class Descarga:
    documento: DocumentLink
    ruta: Path
    desde_cache: bool


def es_pdf_completo(datos: bytes) -> bool:
    """True si los bytes son un PDF entero, no un placeholder ni un truncado."""
    if not datos.startswith(_CABECERA_PDF):
        return False
    return _FIN_PDF in datos[-_COLA_A_REVISAR:]


def _diagnostico(datos: bytes) -> str:
    """Explica en una frase por qué el contenido no sirve."""
    if not datos:
        return "la respuesta vino vacía (0 bytes)"
    if not datos.startswith(_CABECERA_PDF):
        return (
            f"la respuesta no es un PDF (empieza por {datos[:8]!r}, "
            f"{len(datos)} bytes)"
        )
    return f"el PDF está incompleto: faltan los bytes finales ({len(datos)} bytes)"


def nombre_de_archivo(expediente: str, tipo: TipoDoc, orden: int = 1) -> str:
    """`SD2022/0000017` + TM9 -> `SD2022-0000017_TM9.pdf`.

    El sufijo numérico solo aparece a partir del segundo documento del mismo
    tipo, para que el caso normal quede con el nombre limpio.
    """
    base = nombre_archivo_seguro(expediente)
    sufijo = "" if orden <= 1 else f"_{orden}"
    return f"{base}_{tipo.value}{sufijo}.pdf"


def _asegurar_carpeta(carpeta: Path) -> None:
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErrorDescarga(
            f"No se puede crear la carpeta «{carpeta}»: {exc.strerror or exc}. "
            "Revise los permisos o elija otra ubicación."
        ) from exc


def _guardar(datos: bytes, destino: Path) -> None:
    """Escribe primero un .part y luego renombra: nunca queda un PDF a medias.

    El .part lleva un sufijo único **a propósito**. Si el mismo expediente sale
    repetido en el reporte, dos hilos bajan los mismos archivos a la vez; con un
    nombre de .part compartido, el `os.replace` de uno se lleva el archivo del
    otro y el segundo muere con «No such file or directory». `os.replace` sí es
    atómico, así que el destino nunca queda a medias.
    """
    parcial = destino.with_suffix(f"{destino.suffix}.{uuid4().hex}.part")
    try:
        parcial.write_bytes(datos)
    except OSError as exc:
        parcial.unlink(missing_ok=True)
        raise ErrorDescarga(
            f"No se pudo guardar «{destino.name}»: {exc.strerror or exc}. "
            "Revise los permisos de la carpeta."
        ) from exc

    # Windows tiene aquí **dos** carreras, no una, y las dos solo aparecen con
    # el mismo expediente repetido en el reporte y varios hilos:
    #   1. `os.replace` da «Acceso denegado» si otro hilo está reemplazando ese
    #      mismo destino en ese instante. En Linux no pasa.
    #   2. Comprobar si el destino ya es bueno **también** falla, porque leerlo
    #      mientras el otro hilo lo reemplaza da una violación de uso compartido.
    #      Ese fue el fallo real: la comprobación decía «no hay nada bueno» y se
    #      informaba de un error que no existía. Salía 1 de cada 3 veces.
    # Por eso se reintenta en vez de decidir a la primera.
    ultimo: OSError | None = None
    for intento in range(_INTENTOS_REEMPLAZO):
        try:
            os.replace(parcial, destino)
            return
        except OSError as exc:
            ultimo = exc
            if _sirve_lo_que_hay(destino):
                log.debug("%s ya lo dejó otro hilo", destino.name)
                parcial.unlink(missing_ok=True)
                return
            time.sleep(0.05 * (intento + 1))

    parcial.unlink(missing_ok=True)
    raise ErrorDescarga(
        f"No se pudo guardar «{destino.name}»: "
        f"{ultimo.strerror if ultimo else ultimo}. "
        "Revise los permisos de la carpeta."
    ) from ultimo


def _sirve_lo_que_hay(ruta: Path) -> bool:
    """Un archivo en caché solo vale si sigue siendo un PDF completo."""
    try:
        if not ruta.is_file() or ruta.stat().st_size == 0:
            return False
        return es_pdf_completo(ruta.read_bytes())
    except OSError:
        return False


def _pedir_con_reintentos(
    sesion: SesionSIPI,
    documento: DocumentLink,
    expediente: str,
    destino: Path,
    referer: str | None,
) -> bytes:
    """Pide el documento hasta obtener un PDF completo, o se rinde con motivo.

    Los reintentos de `urllib3` no sirven aquí: SIPI responde **HTTP 200** con
    un PNG de 828 bytes, así que para la capa de transporte la petición salió
    bien. El único que puede darse cuenta es quien mira el contenido.

    Se observó en la corrida de los 987 expedientes: durante los primeros 26
    segundos el sitio devolvió el PNG a todo el mundo —135 respuestas, 50
    expedientes— y a partir de ahí ni una sola vez. Sin reintentar, esos 50
    salían vacíos por un problema que se cura solo esperando.
    """
    ultimo = b""
    for intento, espera in enumerate(ESPERAS_CONTENIDO_SEG, start=1):
        try:
            respuesta = sesion.obtener(documento.url, referer=referer)
        except ErrorRed as exc:
            raise ErrorDescarga(f"{expediente} · {documento.etiqueta}: {exc}") from exc

        ultimo = respuesta.content
        if es_pdf_completo(ultimo):
            return ultimo

        log.warning(
            "%s · %s: %s. Reintento %d de %d en %.0f s",
            expediente,
            documento.etiqueta,
            _diagnostico(ultimo),
            intento,
            len(ESPERAS_CONTENIDO_SEG),
            espera,
        )
        time.sleep(espera)

    # Si había un archivo viejo, se borra: es preferible no tener nada a dejar
    # algo que la próxima corrida dé por válido.
    destino.unlink(missing_ok=True)
    raise ErrorDescarga(
        f"{expediente} · {documento.etiqueta}: {_diagnostico(ultimo)} "
        f"tras {len(ESPERAS_CONTENIDO_SEG)} intentos."
    )


def descargar_documento(
    sesion: SesionSIPI,
    documento: DocumentLink,
    expediente: str,
    carpeta: Path,
    referer: str | None = None,
    orden: int = 1,
    reusar: bool = True,
    carpeta_legado: Path | None = None,
) -> Descarga:
    """Baja un documento y lo deja validado en disco.

    `carpeta_legado` es donde las versiones anteriores guardaban los PDFs
    (`temp\\`, en plano). Si el archivo está ahí completo, se **mueve** a
    `carpeta` en vez de volver a pedirlo: sin esto, la primera corrida tras
    estrenar `salida\\soportes\\` volvería a bajar los 620 MB que ya se tenían.
    """
    _asegurar_carpeta(carpeta)
    destino = carpeta / nombre_de_archivo(expediente, documento.tipo, orden)

    if reusar and _sirve_lo_que_hay(destino):
        log.debug("%s: se reutiliza %s", expediente, destino.name)
        return Descarga(documento=documento, ruta=destino, desde_cache=True)

    if reusar and carpeta_legado is not None:
        viejo = carpeta_legado / destino.name
        if viejo != destino and _sirve_lo_que_hay(viejo):
            try:
                os.replace(viejo, destino)
                log.info("%s: %s migrado desde la carpeta antigua", expediente, destino.name)
                return Descarga(documento=documento, ruta=destino, desde_cache=True)
            except OSError:
                pass  # se baja de la red, como si el archivo viejo no existiera

    datos = _pedir_con_reintentos(sesion, documento, expediente, destino, referer)
    _guardar(datos, destino)
    log.info("%s: descargado %s (%d KB)", expediente, destino.name, len(datos) // 1024)
    return Descarga(documento=documento, ruta=destino, desde_cache=False)


def descargar_documentos(
    sesion: SesionSIPI,
    documentos: list[DocumentLink],
    expediente: str,
    carpeta: Path,
    referer: str | None = None,
    reusar: bool = True,
    carpeta_legado: Path | None = None,
) -> tuple[list[Descarga], list[str]]:
    """Baja todos los documentos de un expediente.

    Un documento que falla no tumba a los demás: se devuelve su error como
    aviso y se sigue. Devuelve (descargas, errores).
    """
    descargas: list[Descarga] = []
    errores: list[str] = []
    vistos: dict[TipoDoc, int] = {}

    for documento in documentos:
        vistos[documento.tipo] = vistos.get(documento.tipo, 0) + 1
        try:
            descargas.append(
                descargar_documento(
                    sesion,
                    documento,
                    expediente,
                    carpeta,
                    referer=referer,
                    orden=vistos[documento.tipo],
                    reusar=reusar,
                    carpeta_legado=carpeta_legado,
                )
            )
        except ErrorDescarga as exc:
            errores.append(str(exc))
            log.warning("%s", exc)

    return descargas, errores
