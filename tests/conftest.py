"""Utilidades compartidas por las pruebas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field as dataclasses_field
from pathlib import Path

import openpyxl
import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(__file__).resolve().parent / "data"
HTTP = Path(__file__).resolve().parent / "fixtures" / "http"

# Cabeceras reales del reporte de SIPI, fila 11.
CABECERAS_REPORTE = [
    "Número de caso",
    "Caso Título",
    "Imagen",
    "Fecha de radicación",
    "Vigencia",
    "Estado del Caso",
    "Referencia del solicitante",
    "Titular",
    "Descripción de Productos y Servicios",
    "Calendario Clasificación de Niza",
    "Productos y Servicios Descripción",
    "Bajo Oposición",
    "Apoderado",
    "Fecha de Registro",
    "Fecha de la publicación",
    "Fecha de prioridad",
    "Otra Información",
]


def formula_enlace(expediente: str, id_interno: str = "3857028") -> str:
    """Reproduce exactamente la fórmula que exporta SIPI en la columna A."""
    return (
        f'=HYPERLINK("http://sipi.sic.gov.co/sipi/View.ashx?{id_interno}",'
        f'"{expediente}")'
    )


def fila_datos(enlace: str, marca: str = "MARCA", oposicion: str = "No") -> list:
    """Una fila del reporte con las columnas que el lector necesita pobladas."""
    fila = [None] * len(CABECERAS_REPORTE)
    fila[0] = enlace
    fila[1] = marca
    fila[7] = "TITULAR S.A., Calle 1, BOGOTÁ"
    fila[8] = "5"
    fila[10] = "5. Productos farmacéuticos.\n"
    fila[11] = oposicion
    return fila


@pytest.fixture
def construir_reporte(tmp_path):
    """Fabrica un reporte con la estructura real: cabeceras en la fila 11."""

    def _construir(filas: list[list], cabeceras: list | None = None, nombre="rep.xlsx"):
        libro = openpyxl.Workbook()
        hoja = libro.active
        hoja.append(["Superintendencia de Industria y Comercio de Colombia (SIC)"])
        for _ in range(9):  # hasta dejar las cabeceras en la fila 11
            hoja.append([])
        hoja.append(cabeceras if cabeceras is not None else CABECERAS_REPORTE)
        for fila in filas:
            hoja.append(fila)
        ruta = tmp_path / nombre
        libro.save(ruta)
        libro.close()
        return ruta

    return _construir


@pytest.fixture(scope="session")
def reporte_real() -> Path:
    ruta = RAIZ / "Reporte 5 Enero 2025.xlsx"
    if not ruta.is_file():
        pytest.skip("No está el reporte real en la raíz del proyecto")
    return ruta


@pytest.fixture(scope="session")
def mini(request) -> Path:
    """Ruta a un mini-Excel recortado del reporte real (ver make_fixtures.py)."""
    ruta = DATOS / request.param
    if not ruta.is_file():
        pytest.skip(f"Falta la fixture {ruta.name}: correr python -m tests.make_fixtures")
    return ruta


# --- Reproducción offline de SIPI --------------------------------------------
#
# Las respuestas reales están grabadas en tests/fixtures/http (ver
# tests/make_fixtures.py). `SesionGrabada` las sirve con la misma interfaz que
# `SesionSIPI`, así que scraper y downloader se prueban sin tocar la red.


@dataclass
class RespuestaFalsa:
    content: bytes
    url: str
    status_code: int = 200
    headers: dict = dataclasses_field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class SesionGrabada:
    """Sirve las respuestas grabadas de un expediente. Falla si piden otra URL."""

    def __init__(self, expediente: str) -> None:
        self.carpeta = HTTP / expediente.replace("/", "-")
        self.indice = json.loads(
            (self.carpeta / "indice.json").read_text(encoding="utf-8")
        )
        self.pedidas: list[str] = []
        self._por_url = {
            d["url"]: (self.carpeta / d["archivo"], d["content_type"])
            for d in self.indice["documentos"]
        }

    @property
    def case_url(self) -> str:
        return self.indice["case_url"]

    @property
    def url_final(self) -> str:
        return self.indice["url_final"]

    def obtener(self, url: str, referer: str | None = None) -> RespuestaFalsa:
        self.pedidas.append(url)
        if url == self.case_url or url == self.url_final:
            return RespuestaFalsa(
                content=(self.carpeta / "browse.html").read_bytes(),
                url=self.url_final,
                headers={"Content-Type": "text/html"},
            )
        if url in self._por_url:
            archivo, tipo = self._por_url[url]
            return RespuestaFalsa(
                content=archivo.read_bytes(), url=url, headers={"Content-Type": tipo}
            )
        raise AssertionError(f"URL no grabada: {url}")


@pytest.fixture(autouse=True)
def sin_esperas_de_reintento(monkeypatch):
    """Acorta las esperas por contenido no-PDF en toda la suite.

    Son 31 segundos reales por documento que falla, a propósito: SIPI tarda
    medio minuto en recuperarse. En las pruebas eso convierte una suite de dos
    minutos en una de veinte. La prueba que comprueba que las esperas de verdad
    son largas está en `test_downloader.py` y no usa esta fixture.
    """
    for modulo in ("app.downloader.files", "app.downloader.scraper"):
        monkeypatch.setattr(
            f"{modulo}.ESPERAS_CONTENIDO_SEG", (0.0, 0.0, 0.0), raising=False
        )


EXPEDIENTES_GRABADOS = ("SD2022/0000017", "SD2022/0001545", "SD2022/0097089")


class SesionGrabadaMulti:
    """Como `SesionGrabada` pero sirve los tres expedientes a la vez.

    Es lo que necesita el pipeline: una sola sesión que responda a cualquier
    URL de la corrida. Cuenta las peticiones para poder afirmar que la caché
    funciona y que dos hilos no se pisan.
    """

    def __init__(self, expedientes=EXPEDIENTES_GRABADOS) -> None:
        self.pedidas: list[str] = []
        self.cerrada = False
        self._paginas: dict[str, tuple[Path, str]] = {}
        self._por_url: dict[str, tuple[Path, str]] = {}
        for expediente in expedientes:
            carpeta = HTTP / expediente.replace("/", "-")
            indice = json.loads((carpeta / "indice.json").read_text(encoding="utf-8"))
            for clave in ("case_url", "url_final"):
                # La respuesta lleva la URL final: SIPI redirige View.ashx a
                # Browse.aspx y esa es la que sirve de referer para los PDFs.
                self._paginas[indice[clave]] = (
                    carpeta / "browse.html",
                    indice["url_final"],
                )
            for documento in indice["documentos"]:
                self._por_url[documento["url"]] = (
                    carpeta / documento["archivo"],
                    documento["content_type"],
                )

    def obtener(self, url: str, referer: str | None = None) -> RespuestaFalsa:
        self.pedidas.append(url)
        if url in self._paginas:
            archivo, final = self._paginas[url]
            return RespuestaFalsa(
                content=archivo.read_bytes(),
                url=final,
                headers={"Content-Type": "text/html"},
            )
        if url in self._por_url:
            archivo, tipo = self._por_url[url]
            return RespuestaFalsa(
                content=archivo.read_bytes(), url=url, headers={"Content-Type": tipo}
            )
        raise AssertionError(f"URL no grabada: {url}")

    def cerrar(self) -> None:
        self.cerrada = True


@pytest.fixture
def hay_fixtures_http():
    for expediente in EXPEDIENTES_GRABADOS:
        if not (HTTP / expediente.replace("/", "-") / "indice.json").is_file():
            pytest.skip("Faltan las fixtures HTTP: correr python -m tests.make_fixtures")


def html_grabado(expediente: str) -> str:
    ruta = HTTP / expediente.replace("/", "-") / "browse.html"
    if not ruta.is_file():
        pytest.skip("Faltan las fixtures HTTP: correr python -m tests.make_fixtures")
    return ruta.read_text(encoding="utf-8")


def indice_grabado(expediente: str) -> dict:
    ruta = HTTP / expediente.replace("/", "-") / "indice.json"
    if not ruta.is_file():
        pytest.skip("Faltan las fixtures HTTP: correr python -m tests.make_fixtures")
    return json.loads(ruta.read_text(encoding="utf-8"))


TEXTO = Path(__file__).resolve().parent / "fixtures" / "texto"


def texto_grabado(nombre: str) -> str:
    """Texto ya extraído de una resolución real (ver make_fixtures.grabar_texto)."""
    ruta = TEXTO / f"{nombre}.txt"
    if not ruta.is_file():
        pytest.skip(f"Falta {ruta.name}: correr python -m tests.make_fixtures")
    return ruta.read_text(encoding="utf-8")
