"""Pruebas del scraper.

El HTML de los tres expedientes es el que devuelve SIPI de verdad (grabado por
`tests/make_fixtures.py`). Las deformaciones — tabla ausente, tabla vacía, fila
sin celdas — están hechas a propósito.
"""

from __future__ import annotations

import pytest

from app.downloader.scraper import (
    ErrorScraping,
    clasificar,
    documentos_de_expediente,
    extraer_documentos,
)
from app.models import TipoDoc
from tests.conftest import (
    RespuestaFalsa,
    SesionGrabada,
    html_grabado,
    indice_grabado,
)

EXPEDIENTES = ["SD2022/0000017", "SD2022/0001545", "SD2022/0097089"]


# --- Clasificación por etiqueta ----------------------------------------------


@pytest.mark.parametrize(
    "etiqueta,esperado",
    [
        # Etiquetas reales, tal cual vienen en la tabla.
        ("TM9     - Niega sin oposición", TipoDoc.TM9),
        ("TM128 - Niega con oposición", TipoDoc.TM128),
        ("TM6     - Resumen de la Solicitud de Marca", TipoDoc.TM6),
        ("184 - TM Apelación confirma", TipoDoc.APELACION),
        ("SD 438 Apelación confirma registro o negación marca lema", TipoDoc.APELACION),
        ("Poder", TipoDoc.OTRO),
        ("Tipo de Imagen", TipoDoc.OTRO),
        # Variantes plausibles: sin tildes, con espacios raros, en minúsculas.
        ("tm9 - niega sin oposicion", TipoDoc.TM9),
        ("TM  128 - Niega con oposición", TipoDoc.TM128),
        ("apelacion", TipoDoc.APELACION),
    ],
)
def test_clasificar_etiquetas(etiqueta, esperado):
    assert clasificar(etiqueta) == esperado


def test_tm128_no_se_confunde_con_tm9_ni_al_reves():
    """Comparten prefijo: si el orden de los patrones se rompe, esto lo caza."""
    assert clasificar("TM128 - Niega con oposición") == TipoDoc.TM128
    assert clasificar("TM9 - Niega sin oposición") == TipoDoc.TM9
    # Un número que empieza por 9 pero no es TM9.
    assert clasificar("TM90 - documento inventado") == TipoDoc.OTRO


def test_etiqueta_vacia_no_revienta():
    assert clasificar("") == TipoDoc.OTRO


def test_solo_tm9_y_tm128_son_resoluciones():
    assert TipoDoc.TM9.es_resolucion and TipoDoc.TM128.es_resolucion
    assert not TipoDoc.TM6.es_resolucion
    assert not TipoDoc.APELACION.es_resolucion
    assert not TipoDoc.OTRO.es_resolucion


# --- Extracción sobre el HTML real -------------------------------------------


@pytest.mark.parametrize("expediente", EXPEDIENTES)
def test_extrae_los_documentos_que_se_grabaron(expediente):
    documentos = extraer_documentos(html_grabado(expediente))
    esperados = indice_grabado(expediente)["documentos"]

    assert len(documentos) == len(esperados)
    assert [d.tipo.value for d in documentos] == [e["tipo"] for e in esperados]
    assert [d.url for d in documentos] == [e["url"] for e in esperados]


@pytest.mark.parametrize("expediente", EXPEDIENTES)
def test_todos_los_enlaces_son_absolutos_y_de_getfile(expediente):
    for documento in extraer_documentos(html_grabado(expediente)):
        assert documento.url.startswith("http")
        assert "GetFile.aspx" in documento.url


def test_el_numero_de_documentos_varia_entre_expedientes():
    """Confirma por qué no se puede clasificar por posición: 3 aquí, 5 allá."""
    cuantos = {e: len(extraer_documentos(html_grabado(e))) for e in EXPEDIENTES}
    assert cuantos["SD2022/0000017"] == 3
    assert cuantos["SD2022/0001545"] == 5


def test_cada_expediente_negado_trae_su_resolucion():
    for expediente in EXPEDIENTES:
        documentos = extraer_documentos(html_grabado(expediente))
        resoluciones = [d for d in documentos if d.tipo.es_resolucion]
        assert len(resoluciones) == 1, f"{expediente}: {len(resoluciones)} resoluciones"


def test_se_rescatan_resolucion_y_fecha_cuando_existen():
    documentos = extraer_documentos(html_grabado("SD2022/0000017"))
    tm9 = next(d for d in documentos if d.tipo is TipoDoc.TM9)
    assert tm9.resolucion_nr == "52886"
    assert tm9.fecha == "8 de agosto de 2022"


def test_los_anexos_sin_resolucion_no_inventan_datos():
    documentos = extraer_documentos(html_grabado("SD2022/0000017"))
    tm6 = next(d for d in documentos if d.tipo is TipoDoc.TM6)
    assert tm6.resolucion_nr is None
    assert tm6.fecha is None


# --- Caso 19: la tabla no está -----------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        "<html><body>Sesión caducada</body></html>",
        "<html><body><table id='otraCosa'><tr><td>x</td></tr></table></body></html>",
        "",
        "no es html en absoluto",
    ],
)
def test_sin_tabla_de_documentos_falla_con_mensaje_util(html):
    with pytest.raises(ErrorScraping) as error:
        extraer_documentos(html)

    mensaje = str(error.value)
    assert "tabla de documentos" in mensaje
    assert "gvDocuments" in mensaje


# --- Caso 20: la tabla está pero está vacía ----------------------------------


def test_tabla_vacia_devuelve_lista_vacia_sin_error():
    html = """
    <table id="MainContent_ctrlDocumentList_gvDocuments">
      <tr><th>Documento</th></tr>
    </table>
    """
    assert extraer_documentos(html) == []


def test_tabla_con_enlaces_que_no_son_documentos_los_ignora():
    """La tabla real trae enlaces de ordenamiento (__doPostBack); no son PDFs."""
    html = """
    <table id="MainContent_ctrlDocumentList_gvDocuments">
      <tr><th><a href="javascript:__doPostBack('x','Sort$NAME')">Documento</a></th></tr>
      <tr><td>1</td><td>hoy</td><td></td>
          <td><a href="https://sipi.sic.gov.co/sipi/Common/Utils/GetFile.aspx?&amp;id=1">
              TM9 - Niega sin oposición</a></td></tr>
    </table>
    """
    documentos = extraer_documentos(html)
    assert len(documentos) == 1
    assert documentos[0].tipo is TipoDoc.TM9


def test_enlace_fuera_de_una_fila_no_revienta():
    html = """
    <table id="MainContent_ctrlDocumentList_gvDocuments">
      <a href="https://x/GetFile.aspx?&amp;id=1">TM6 - Resumen</a>
    </table>
    """
    documentos = extraer_documentos(html)
    assert documentos[0].resolucion_nr is None
    assert documentos[0].tipo is TipoDoc.TM6


# --- Flujo completo contra la sesión grabada ---------------------------------


@pytest.mark.parametrize("expediente", EXPEDIENTES)
def test_documentos_de_expediente_usa_la_url_final_como_referer(expediente):
    sesion = SesionGrabada(expediente)
    pagina, documentos = documentos_de_expediente(sesion, sesion.case_url)

    # La URL final es la de Browse.aspx tras el redirect, no la del Excel.
    assert pagina.url == sesion.url_final
    assert "Browse.aspx" in pagina.url
    assert len(documentos) == len(indice_grabado(expediente)["documentos"])
    assert sesion.pedidas == [sesion.case_url]


# --- Reintento cuando la página llega sin tabla ------------------------------


class SesionQueTardaEnDarLaTabla:
    """Devuelve una página inservible las primeras veces y la buena después.

    Es lo que hizo SIPI en la corrida de los 987: dos expedientes llegaron sin
    la tabla de documentos y los dos funcionaron al volver a pedirlos.
    """

    def __init__(self, malas: int, html_bueno: str) -> None:
        self.malas = malas
        self.html_bueno = html_bueno
        self.peticiones = 0

    def obtener(self, url: str, referer: str | None = None):
        self.peticiones += 1
        html = (
            "<html><body>Sesión expirada</body></html>"
            if self.peticiones <= self.malas
            else self.html_bueno
        )
        return RespuestaFalsa(content=html.encode("utf-8"), url=url)


def test_una_pagina_sin_tabla_se_reintenta_y_acaba_bien():
    sesion = SesionQueTardaEnDarLaTabla(2, html_grabado("SD2022/0000017"))

    _pagina, documentos = documentos_de_expediente(sesion, "https://x/View.ashx?1")

    assert sesion.peticiones == 3
    assert [d.tipo for d in documentos] == [
        TipoDoc.APELACION,
        TipoDoc.TM9,
        TipoDoc.TM6,
    ]


def test_si_nunca_aparece_la_tabla_se_rinde_con_el_mensaje_de_siempre():
    sesion = SesionQueTardaEnDarLaTabla(99, "")

    with pytest.raises(ErrorScraping) as error:
        documentos_de_expediente(sesion, "https://x/View.ashx?1")

    assert sesion.peticiones == 3
    assert "gvDocuments" in str(error.value)


def test_una_pagina_buena_no_se_pide_dos_veces():
    sesion = SesionQueTardaEnDarLaTabla(0, html_grabado("SD2022/0000017"))

    documentos_de_expediente(sesion, "https://x/View.ashx?1")

    assert sesion.peticiones == 1
