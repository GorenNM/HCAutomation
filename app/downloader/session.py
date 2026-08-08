"""Sesión HTTP contra SIPI.

Lo que obliga a que exista este módulo: sin cookies, `View.ashx` entra en un
bucle de redirecciones infinito (curl se rinde a las 50). Con una sesión que
guarde `ASP.NET_SessionId` resuelve en dos saltos. Por eso toda la navegación
de un expediente comparte una misma sesión.

Aparte, `GetFile.aspx` puede responder **HTTP 200 con algo que no es un PDF**
(se observó un PNG de 32x32 y 828 bytes). No es un error HTTP, así que el
contenido se valida por sus bytes iniciales en `files.py`, no por el estado.

Cada hilo del pipeline debe usar su propia instancia: `requests.Session` no
garantiza seguridad entre hilos, y de paso cada uno mantiene su propia cookie.
"""

from __future__ import annotations

import logging
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import (
    BACKOFF_FACTOR,
    DELAY_ENTRE_PETICIONES_SEG,
    REINTENTOS,
    TIMEOUT_SEG,
    USER_AGENT,
)

log = logging.getLogger(__name__)

# 429 incluido a propósito: si SIPI limita el ritmo, se espera lo que pida en
# Retry-After en vez de insistir.
_ESTADOS_REINTENTABLES = (429, 500, 502, 503, 504)

# El reporte de SIPI exporta las URLs con http://, pero el puerto 80 del sitio
# no responde: se queda colgado hasta agotar el timeout. Por https contesta en
# menos de dos segundos. Se reescribe el esquema antes de cada petición.
# La función vive en utils.text porque el writer también la necesita; este
# reexport conserva el import histórico `from app.downloader.session import
# forzar_https`.
from app.utils.text import forzar_https  # noqa: F401  (reexport)


class ErrorRed(Exception):
    """Falló la comunicación con SIPI. El mensaje va al log y a la interfaz."""


class SesionSIPI:
    """Envoltorio fino sobre `requests.Session`: reintentos, timeout y ritmo."""

    def __init__(
        self,
        delay: float = DELAY_ENTRE_PETICIONES_SEG,
        timeout: int = TIMEOUT_SEG,
    ) -> None:
        self.timeout = timeout
        self.delay = delay
        self._ultima_peticion = 0.0
        self._candado = threading.Lock()
        self.session = self._construir()

    @staticmethod
    def _construir() -> requests.Session:
        sesion = requests.Session()
        sesion.headers.update({"User-Agent": USER_AGENT})
        reintentos = Retry(
            total=REINTENTOS,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=_ESTADOS_REINTENTABLES,
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adaptador = HTTPAdapter(max_retries=reintentos)
        sesion.mount("http://", adaptador)
        sesion.mount("https://", adaptador)
        return sesion

    def _esperar_turno(self) -> None:
        """Deja al menos `delay` segundos entre peticiones de esta sesión."""
        with self._candado:
            faltan = self.delay - (time.monotonic() - self._ultima_peticion)
            if faltan > 0:
                time.sleep(faltan)
            self._ultima_peticion = time.monotonic()

    def obtener(self, url: str, referer: str | None = None) -> requests.Response:
        """GET con reintentos. Lanza ErrorRed con un mensaje legible."""
        url = forzar_https(url)
        cabeceras = {"Referer": forzar_https(referer)} if referer else None
        self._esperar_turno()
        try:
            respuesta = self.session.get(
                url, headers=cabeceras, timeout=self.timeout, allow_redirects=True
            )
        except requests.exceptions.Timeout as exc:
            raise ErrorRed(
                f"SIPI no respondió en {self.timeout} s ({url})."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ErrorRed(
                f"No se pudo conectar con SIPI ({url}). Revise la conexión o el proxy."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ErrorRed(f"Error de red al pedir {url}: {exc}") from exc

        if respuesta.status_code == 429:
            raise ErrorRed(
                "SIPI está limitando las peticiones (HTTP 429). Conviene bajar el "
                "número de hilos y reintentar más tarde."
            )
        if respuesta.status_code >= 400:
            raise ErrorRed(f"SIPI respondió {respuesta.status_code} para {url}.")
        return respuesta

    def cerrar(self) -> None:
        self.session.close()

    def __enter__(self) -> "SesionSIPI":
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.cerrar()
