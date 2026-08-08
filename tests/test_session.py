"""Pruebas de la sesión HTTP.

No tocan la red: se sustituye `session.get` para provocar cada fallo. Lo que se
comprueba es que el usuario recibe un mensaje entendible y que la política de
reintentos está realmente cableada, no solo escrita en el plan.
"""

from __future__ import annotations

import time

import pytest
import requests

from app.config import REINTENTOS
from app.downloader.session import ErrorRed, SesionSIPI, forzar_https


# --- Caso 2b: las URLs del reporte vienen por http, que no responde ----------


@pytest.mark.parametrize(
    "entrada,esperada",
    [
        (
            "http://sipi.sic.gov.co/sipi/View.ashx?3857028",
            "https://sipi.sic.gov.co/sipi/View.ashx?3857028",
        ),
        (
            "https://sipi.sic.gov.co/sipi/View.ashx?1",
            "https://sipi.sic.gov.co/sipi/View.ashx?1",
        ),
        ("http://www.sic.gov.co/algo", "https://www.sic.gov.co/algo"),
        # Otro dominio: no se toca.
        ("http://ejemplo.com/x", "http://ejemplo.com/x"),
        # 'sic.gov.co' en la ruta, no en el host: tampoco se toca.
        ("http://ejemplo.com/sic.gov.co/x", "http://ejemplo.com/sic.gov.co/x"),
        ("", ""),
    ],
)
def test_forzar_https(entrada, esperada):
    assert forzar_https(entrada) == esperada


def test_la_peticion_sale_por_https_aunque_llegue_por_http(monkeypatch):
    sesion = SesionSIPI(delay=0)
    pedidas = []

    def falso_get(url, **kwargs):
        pedidas.append(url)
        return _respuesta(200)

    monkeypatch.setattr(sesion.session, "get", falso_get)
    sesion.obtener("http://sipi.sic.gov.co/sipi/View.ashx?1")

    assert pedidas == ["https://sipi.sic.gov.co/sipi/View.ashx?1"]


def test_el_referer_tambien_se_reescribe(monkeypatch):
    sesion = SesionSIPI(delay=0)
    capturado = {}

    def falso_get(url, **kwargs):
        capturado.update(kwargs.get("headers") or {})
        return _respuesta(200)

    monkeypatch.setattr(sesion.session, "get", falso_get)
    sesion.obtener(
        "https://sipi.sic.gov.co/a", referer="http://sipi.sic.gov.co/sipi/Browse.aspx"
    )

    assert capturado["Referer"].startswith("https://")


# --- Caso 21: la red falla ---------------------------------------------------


def _respuesta(codigo: int) -> requests.Response:
    respuesta = requests.Response()
    respuesta.status_code = codigo
    respuesta.url = "https://sipi.sic.gov.co/x"
    respuesta._content = b""
    return respuesta


@pytest.mark.parametrize(
    "excepcion,fragmento",
    [
        (requests.exceptions.Timeout(), "no respondió"),
        (requests.exceptions.ConnectionError(), "No se pudo conectar"),
        (requests.exceptions.TooManyRedirects(), "Error de red"),
    ],
)
def test_los_fallos_de_red_llegan_como_errorred_legible(
    monkeypatch, excepcion, fragmento
):
    sesion = SesionSIPI(delay=0)

    def falso_get(url, **kwargs):
        raise excepcion

    monkeypatch.setattr(sesion.session, "get", falso_get)

    with pytest.raises(ErrorRed) as error:
        sesion.obtener("https://sipi.sic.gov.co/x")

    assert fragmento in str(error.value)
    # Nada de nombres de clase de requests en la cara del usuario.
    assert "requests.exceptions" not in str(error.value)


def test_el_timeout_menciona_los_segundos(monkeypatch):
    sesion = SesionSIPI(delay=0, timeout=7)
    monkeypatch.setattr(
        sesion.session,
        "get",
        lambda url, **kw: (_ for _ in ()).throw(requests.exceptions.Timeout()),
    )

    with pytest.raises(ErrorRed, match="7 s"):
        sesion.obtener("https://sipi.sic.gov.co/x")


# --- Caso 22: HTTP 429 -------------------------------------------------------


def test_429_pide_bajar_el_ritmo_en_vez_de_insistir(monkeypatch):
    sesion = SesionSIPI(delay=0)
    monkeypatch.setattr(sesion.session, "get", lambda url, **kw: _respuesta(429))

    with pytest.raises(ErrorRed) as error:
        sesion.obtener("https://sipi.sic.gov.co/x")

    mensaje = str(error.value)
    assert "429" in mensaje
    assert "hilos" in mensaje


@pytest.mark.parametrize("codigo", [400, 403, 404, 500, 503])
def test_los_codigos_de_error_se_reportan_con_su_numero(monkeypatch, codigo):
    sesion = SesionSIPI(delay=0)
    monkeypatch.setattr(sesion.session, "get", lambda url, **kw: _respuesta(codigo))

    with pytest.raises(ErrorRed, match=str(codigo)):
        sesion.obtener("https://sipi.sic.gov.co/x")


# --- La política de reintentos está realmente puesta -------------------------


def test_los_reintentos_estan_cableados_en_el_adaptador():
    sesion = SesionSIPI(delay=0)
    for esquema in ("http://", "https://"):
        politica = sesion.session.adapters[esquema].max_retries
        assert politica.total == REINTENTOS
        assert 429 in politica.status_forcelist
        assert 503 in politica.status_forcelist
        assert politica.respect_retry_after_header is True
        assert "GET" in politica.allowed_methods


def test_hay_user_agent_de_navegador():
    # SIPI es un WebForms viejo; sin User-Agent reconocible se comporta raro.
    assert "Mozilla" in SesionSIPI(delay=0).session.headers["User-Agent"]


# --- El ritmo entre peticiones -----------------------------------------------


def test_espera_el_delay_entre_peticiones(monkeypatch):
    sesion = SesionSIPI(delay=0.05)
    monkeypatch.setattr(sesion.session, "get", lambda url, **kw: _respuesta(200))

    inicio = time.monotonic()
    for _ in range(3):
        sesion.obtener("https://sipi.sic.gov.co/x")
    transcurrido = time.monotonic() - inicio

    # Tres peticiones = al menos dos esperas.
    assert transcurrido >= 0.10


def test_delay_cero_no_espera(monkeypatch):
    sesion = SesionSIPI(delay=0)
    monkeypatch.setattr(sesion.session, "get", lambda url, **kw: _respuesta(200))

    inicio = time.monotonic()
    for _ in range(20):
        sesion.obtener("https://sipi.sic.gov.co/x")

    assert time.monotonic() - inicio < 0.5


def test_la_sesion_sirve_de_gestor_de_contexto():
    with SesionSIPI(delay=0) as sesion:
        assert sesion.session is not None
