"""Humo contra SIPI de verdad. Desactivado por defecto.

    pytest -m live

Existe para detectar el día que la SIC cambie el HTML o las URLs. No se corre
en el ciclo normal: la suite tiene que ser determinista y no depender de que el
sitio esté en pie.
"""

from __future__ import annotations

import pytest

from app.downloader.scraper import documentos_de_expediente
from app.downloader.session import SesionSIPI
from app.models import TipoDoc

pytestmark = pytest.mark.live

CASO = "http://sipi.sic.gov.co/sipi/View.ashx?3857028"  # SD2022/0000017


@pytest.fixture(scope="module")
def resultado():
    with SesionSIPI() as sesion:
        return documentos_de_expediente(sesion, CASO)


def test_el_expediente_sigue_abriendo_y_redirigiendo(resultado):
    pagina, _ = resultado
    assert pagina.url.startswith("https://")
    assert "Browse.aspx?sid=" in pagina.url
    assert "SD2022/0000017" in pagina.html


def test_la_tabla_de_documentos_sigue_teniendo_la_misma_forma(resultado):
    _, documentos = resultado
    assert len(documentos) >= 3
    tipos = {d.tipo for d in documentos}
    assert TipoDoc.TM9 in tipos
    assert TipoDoc.TM6 in tipos
    assert all("GetFile.aspx" in d.url for d in documentos)


def test_la_resolucion_sigue_bajando_como_pdf(resultado):
    pagina, documentos = resultado
    tm9 = next(d for d in documentos if d.tipo is TipoDoc.TM9)
    with SesionSIPI() as sesion:
        sesion.obtener(CASO)  # primero el expediente: deja la cookie
        contenido = sesion.obtener(tm9.url, referer=pagina.url).content
    assert contenido.startswith(b"%PDF-")
