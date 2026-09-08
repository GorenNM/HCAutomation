"""Pruebas de la descarga a disco.

Los PDFs buenos son los
grabados de SIPI; los malos se construyen cortándolos o sustituyéndolos por la
respuesta real que devolvió el sitio cuando no entregó el documento.
"""

from __future__ import annotations

import os
import sys

import pytest

from app.downloader.files import (
    Descarga,
    ErrorDescarga,
    descargar_documento,
    descargar_documentos,
    es_pdf_completo,
    nombre_de_archivo,
)
from app.downloader.scraper import extraer_documentos
from app.downloader.session import ErrorRed
from app.models import DocumentLink, TipoDoc
from tests.conftest import HTTP, RespuestaFalsa, SesionGrabada, html_grabado

EXPEDIENTE = "SD2022/0000017"


@pytest.fixture
def pdf_real() -> bytes:
    return (HTTP / "SD2022-0000017" / "doc02.bin").read_bytes()  # el TM9


@pytest.fixture
def respuesta_no_pdf() -> bytes:
    """La respuesta real de SIPI cuando no entregó el documento: un PNG de 828 b."""
    ruta = HTTP / "respuesta_no_pdf.bin"
    if not ruta.is_file():
        pytest.skip("Falta la fixture respuesta_no_pdf.bin")
    return ruta.read_bytes()


class SesionQueDevuelve:
    """Sesión mínima que responde siempre lo mismo. Cuenta las peticiones."""

    def __init__(self, contenido: bytes | Exception) -> None:
        self.contenido = contenido
        self.peticiones = 0

    def obtener(self, url: str, referer: str | None = None) -> RespuestaFalsa:
        self.peticiones += 1
        if isinstance(self.contenido, Exception):
            raise self.contenido
        return RespuestaFalsa(content=self.contenido, url=url)


def documento(tipo: TipoDoc = TipoDoc.TM9, url: str = "https://x/GetFile.aspx?&id=1"):
    return DocumentLink(tipo=tipo, etiqueta=f"{tipo.value} - prueba", url=url)


# --- Validación del contenido ------------------------------------------------


def test_un_pdf_real_pasa_la_validacion(pdf_real):
    assert es_pdf_completo(pdf_real)


def test_todos_los_pdfs_grabados_pasan_la_validacion():
    grabados = sorted(HTTP.rglob("doc*.bin"))
    assert len(grabados) == 11, "cambió el juego de fixtures"
    assert all(es_pdf_completo(g.read_bytes()) for g in grabados)


@pytest.mark.parametrize(
    "datos",
    [
        b"",  # caso 18: respuesta vacía
        b"%PDF-1.5 sin final",  # caso 17: truncado
        b"<html>error</html>",
        b"\x89PNG\r\n\x1a\n",
        b"   %PDF-1.5 ... %%EOF",  # el magic tiene que estar al principio
    ],
)
def test_contenidos_invalidos_se_rechazan(datos):
    assert not es_pdf_completo(datos)


def test_un_pdf_truncado_a_la_mitad_se_rechaza(pdf_real):
    """Caso 17: la cabecera está bien, así que solo el final lo delata."""
    mitad = pdf_real[: len(pdf_real) // 2]
    assert mitad.startswith(b"%PDF-")
    assert not es_pdf_completo(mitad)


def test_el_png_que_devolvio_sipi_se_rechaza(respuesta_no_pdf):
    """Caso 16: HTTP 200 y 828 bytes que no son un PDF."""
    assert not es_pdf_completo(respuesta_no_pdf)


# --- Nombres de archivo ------------------------------------------------------


def test_nombre_de_archivo_convierte_la_barra_del_expediente():
    assert nombre_de_archivo("SD2022/0000017", TipoDoc.TM9) == "SD2022-0000017_TM9.pdf"


def test_el_segundo_documento_del_mismo_tipo_lleva_sufijo():
    assert nombre_de_archivo("SD2022/0000017", TipoDoc.TM9, 1).endswith("_TM9.pdf")
    assert nombre_de_archivo("SD2022/0000017", TipoDoc.TM9, 2).endswith("_TM9_2.pdf")


# --- Descarga: camino feliz --------------------------------------------------


def test_descarga_y_guarda_el_pdf(tmp_path, pdf_real):
    sesion = SesionQueDevuelve(pdf_real)
    descarga = descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert descarga.ruta.name == "SD2022-0000017_TM9.pdf"
    assert descarga.ruta.read_bytes() == pdf_real
    assert not descarga.desde_cache


def test_no_deja_archivos_part_al_terminar(tmp_path, pdf_real):
    descargar_documento(SesionQueDevuelve(pdf_real), documento(), EXPEDIENTE, tmp_path)
    assert list(tmp_path.glob("*.part")) == []


def test_crea_la_carpeta_si_no_existe(tmp_path, pdf_real):
    destino = tmp_path / "a" / "b" / "temp"
    descargar_documento(SesionQueDevuelve(pdf_real), documento(), EXPEDIENTE, destino)
    assert destino.is_dir()


# --- Caché y reanudación -----------------------------------------------------


def test_no_vuelve_a_bajar_lo_que_ya_esta(tmp_path, pdf_real):
    sesion = SesionQueDevuelve(pdf_real)
    descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)
    segunda = descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert segunda.desde_cache
    assert sesion.peticiones == 1


def test_reusar_desactivado_vuelve_a_bajar(tmp_path, pdf_real):
    sesion = SesionQueDevuelve(pdf_real)
    descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)
    segunda = descargar_documento(
        sesion, documento(), EXPEDIENTE, tmp_path, reusar=False
    )

    assert not segunda.desde_cache
    assert sesion.peticiones == 2


def test_caso_23_un_archivo_en_cache_corrupto_se_vuelve_a_bajar(tmp_path, pdf_real):
    """Lo peor sería confiar en él: quedaría basura en el Excel final."""
    corrupto = tmp_path / nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)
    corrupto.write_bytes(b"%PDF-1.5 esto se corto a la mitad")

    sesion = SesionQueDevuelve(pdf_real)
    descarga = descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert not descarga.desde_cache
    assert sesion.peticiones == 1
    assert descarga.ruta.read_bytes() == pdf_real


def test_un_archivo_de_cero_bytes_en_cache_no_se_reutiliza(tmp_path, pdf_real):
    (tmp_path / nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)).write_bytes(b"")
    sesion = SesionQueDevuelve(pdf_real)

    assert not descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path).desde_cache


# --- Casos 16, 17, 18: la respuesta no sirve ---------------------------------


def test_caso_16_respuesta_que_no_es_pdf_da_error_explicito(
    tmp_path, respuesta_no_pdf
):
    sesion = SesionQueDevuelve(respuesta_no_pdf)

    with pytest.raises(ErrorDescarga) as error:
        descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    mensaje = str(error.value)
    assert "no es un PDF" in mensaje
    assert EXPEDIENTE in mensaje
    assert list(tmp_path.iterdir()) == []  # no deja nada a medias


def test_caso_17_pdf_truncado_da_error_y_no_se_guarda(tmp_path, pdf_real):
    sesion = SesionQueDevuelve(pdf_real[:5000])

    with pytest.raises(ErrorDescarga, match="incompleto"):
        descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_caso_18_respuesta_vacia_da_error(tmp_path):
    with pytest.raises(ErrorDescarga, match="vacía"):
        descargar_documento(SesionQueDevuelve(b""), documento(), EXPEDIENTE, tmp_path)


def test_una_descarga_fallida_borra_el_archivo_viejo(tmp_path, pdf_real):
    """Si lo que llega no sirve, quedarse con lo anterior sería peor: pareceria bueno."""
    ruta = tmp_path / nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)
    ruta.write_bytes(b"basura previa")

    with pytest.raises(ErrorDescarga):
        descargar_documento(
            SesionQueDevuelve(b"<html>error</html>"), documento(), EXPEDIENTE, tmp_path
        )

    assert not ruta.exists()


# --- Casos 21 y 22: la red falla ---------------------------------------------


def test_un_error_de_red_llega_como_errordescarga_con_contexto(tmp_path):
    sesion = SesionQueDevuelve(ErrorRed("SIPI no respondió en 60 s"))

    with pytest.raises(ErrorDescarga) as error:
        descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    mensaje = str(error.value)
    assert EXPEDIENTE in mensaje  # se sabe qué expediente falló
    assert "no respondió" in mensaje


# --- Caso 24: no se puede escribir -------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="los permisos POSIX no aplican")
def test_caso_24_sin_permiso_de_escritura_el_mensaje_es_para_un_humano(
    tmp_path, pdf_real
):
    carpeta = tmp_path / "protegida"
    carpeta.mkdir()
    os.chmod(carpeta, 0o500)  # lectura y listado, sin escritura
    try:
        with pytest.raises(ErrorDescarga) as error:
            descargar_documento(
                SesionQueDevuelve(pdf_real), documento(), EXPEDIENTE, carpeta
            )
        mensaje = str(error.value)
        assert "permisos" in mensaje
        assert "Traceback" not in mensaje
    finally:
        os.chmod(carpeta, 0o700)


@pytest.mark.skipif(sys.platform == "win32", reason="los permisos POSIX no aplican")
def test_no_se_puede_crear_la_carpeta(tmp_path, pdf_real):
    padre = tmp_path / "sin_permiso"
    padre.mkdir()
    os.chmod(padre, 0o500)
    try:
        with pytest.raises(ErrorDescarga, match="No se puede crear la carpeta"):
            descargar_documento(
                SesionQueDevuelve(pdf_real), documento(), EXPEDIENTE, padre / "hija"
            )
    finally:
        os.chmod(padre, 0o700)


# --- Varios documentos: un fallo no tumba al resto ---------------------------


def test_descargar_documentos_sigue_tras_un_fallo(tmp_path, pdf_real):
    class SesionMixta:
        """Rompe SIEMPRE el documento 2, no la segunda petición.

        Contar peticiones ya no vale: con los reintentos por contenido, el
        segundo intento del mismo documento devolvería un PDF bueno y el
        documento «roto» acabaría descargándose.
        """

        def __init__(self):
            self.peticiones = 0

        def obtener(self, url, referer=None):
            self.peticiones += 1
            datos = b"<html>ups</html>" if url.endswith("id=2") else pdf_real
            return RespuestaFalsa(content=datos, url=url)

    documentos = [
        documento(TipoDoc.TM9, "https://x/GetFile.aspx?&id=1"),
        documento(TipoDoc.TM6, "https://x/GetFile.aspx?&id=2"),
        documento(TipoDoc.APELACION, "https://x/GetFile.aspx?&id=3"),
    ]
    descargas, errores = descargar_documentos(
        SesionMixta(), documentos, EXPEDIENTE, tmp_path
    )

    assert [d.documento.tipo for d in descargas] == [TipoDoc.TM9, TipoDoc.APELACION]
    assert len(errores) == 1
    assert "TM6" in errores[0]


def test_dos_documentos_del_mismo_tipo_no_se_pisan(tmp_path, pdf_real):
    documentos = [
        documento(TipoDoc.TM9, "https://x/GetFile.aspx?&id=1"),
        documento(TipoDoc.TM9, "https://x/GetFile.aspx?&id=2"),
    ]
    descargas, errores = descargar_documentos(
        SesionQueDevuelve(pdf_real), documentos, EXPEDIENTE, tmp_path
    )

    assert errores == []
    nombres = sorted(d.ruta.name for d in descargas)
    assert nombres == ["SD2022-0000017_TM9.pdf", "SD2022-0000017_TM9_2.pdf"]


# --- Integración con las respuestas grabadas ---------------------------------


@pytest.mark.parametrize(
    "expediente", ["SD2022/0000017", "SD2022/0001545", "SD2022/0097089"]
)
def test_baja_todos_los_documentos_reales_de_un_expediente(tmp_path, expediente):
    sesion = SesionGrabada(expediente)
    documentos = extraer_documentos(html_grabado(expediente))

    descargas, errores = descargar_documentos(
        sesion, documentos, expediente, tmp_path, referer=sesion.url_final
    )

    assert errores == []
    assert len(descargas) == len(documentos)
    assert all(d.ruta.read_bytes().startswith(b"%PDF-") for d in descargas)
    assert all(isinstance(d, Descarga) for d in descargas)


def test_la_segunda_corrida_sobre_lo_ya_descargado_no_pide_nada(tmp_path):
    expediente = "SD2022/0000017"
    documentos = extraer_documentos(html_grabado(expediente))

    sesion = SesionGrabada(expediente)
    descargar_documentos(sesion, documentos, expediente, tmp_path)
    peticiones_primera = len(sesion.pedidas)

    sesion_dos = SesionGrabada(expediente)
    descargas, _ = descargar_documentos(sesion_dos, documentos, expediente, tmp_path)

    assert peticiones_primera == len(documentos)
    assert sesion_dos.pedidas == []
    assert all(d.desde_cache for d in descargas)


def test_ocho_hilos_bajando_el_mismo_documento_no_se_pisan(tmp_path, pdf_real):
    """Regresión: el reporte real repite expedientes y el pipeline usa 8 hilos.

    Con un nombre de `.part` compartido, el `os.replace` del primer hilo se
    llevaba el archivo del segundo y este moría con «No such file or directory».
    """
    import threading

    sesion = SesionQueDevuelve(pdf_real)
    fallos: list[Exception] = []
    listos = threading.Barrier(8)

    def bajar() -> None:
        listos.wait(10)  # que arranquen todos a la vez, no en fila
        try:
            descargar_documento(
                sesion, documento(), EXPEDIENTE, tmp_path, reusar=False
            )
        except Exception as error:  # noqa: BLE001 - se reporta al final
            fallos.append(error)

    hilos = [threading.Thread(target=bajar) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(30)

    assert not fallos, [str(f) for f in fallos]
    assert list(tmp_path.glob("*.part")) == [], "quedaron archivos temporales"
    destino = tmp_path / nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)
    assert es_pdf_completo(destino.read_bytes())


# --- Reintentos por contenido (el PNG de 828 bytes) --------------------------


class SesionQuePrimeroFalla:
    """Devuelve basura las primeras veces y el PDF bueno después.

    Es el comportamiento real de SIPI: durante los primeros segundos de una
    corrida responde HTTP 200 con un PNG de 828 bytes, y luego se recupera.
    """

    def __init__(self, malas: int, bueno: bytes, basura: bytes) -> None:
        self.malas = malas
        self.bueno = bueno
        self.basura = basura
        self.peticiones = 0

    def obtener(self, url: str, referer: str | None = None) -> RespuestaFalsa:
        self.peticiones += 1
        contenido = self.basura if self.peticiones <= self.malas else self.bueno
        return RespuestaFalsa(content=contenido, url=url)


def test_una_respuesta_que_no_es_pdf_se_reintenta_y_acaba_bien(
    tmp_path, pdf_real, respuesta_no_pdf
):
    sesion = SesionQuePrimeroFalla(2, pdf_real, respuesta_no_pdf)

    descarga = descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert sesion.peticiones == 3
    assert es_pdf_completo(descarga.ruta.read_bytes())
    assert not descarga.desde_cache


def test_si_no_se_recupera_nunca_se_rinde_diciendo_cuantas_veces_probo(
    tmp_path, respuesta_no_pdf
):
    sesion = SesionQuePrimeroFalla(99, b"", respuesta_no_pdf)

    with pytest.raises(ErrorDescarga) as error:
        descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert sesion.peticiones == 3
    assert "no es un PDF" in str(error.value)
    assert "3 intentos" in str(error.value)
    assert not list(tmp_path.glob("*.pdf")), "no puede quedar un archivo malo"


def test_un_pdf_truncado_tambien_se_reintenta(tmp_path, pdf_real):
    """Otra forma del mismo problema: llega algo, pero incompleto."""
    sesion = SesionQuePrimeroFalla(1, pdf_real, pdf_real[: len(pdf_real) // 2])

    descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert sesion.peticiones == 2


def test_un_error_de_red_no_se_reintenta_aqui(tmp_path):
    """De los timeouts ya se encarga urllib3; repetirlo aquí multiplicaría la espera."""
    sesion = SesionQueDevuelve(ErrorRed("se agotó el tiempo"))

    with pytest.raises(ErrorDescarga):
        descargar_documento(sesion, documento(), EXPEDIENTE, tmp_path)

    assert sesion.peticiones == 1


def test_las_esperas_de_verdad_superan_el_corte_observado():
    """En la corrida real el sitio devolvió el PNG durante 26 segundos.

    Esta prueba mira la constante de `config`, no la acortada por la fixture:
    si alguien la baja a 2 o 3 segundos, los reintentos dejan de servir para
    el único caso por el que existen.
    """
    from app.config import ESPERAS_CONTENIDO_SEG

    assert sum(ESPERAS_CONTENIDO_SEG) > 26
    assert len(ESPERAS_CONTENIDO_SEG) >= 3
    assert list(ESPERAS_CONTENIDO_SEG) == sorted(ESPERAS_CONTENIDO_SEG), "van de menos a más"


# --- Migración desde la carpeta antigua (temp\ plano, pre-soportes) ----------


def test_un_pdf_de_la_carpeta_antigua_se_migra_sin_tocar_la_red(tmp_path, pdf_real):
    """Las corridas viejas dejaron los PDFs en temp\\ en plano. Se mueven a la
    carpeta nueva en vez de volver a bajar 620 MB."""
    legado = tmp_path / "temp"
    legado.mkdir()
    nombre = nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)
    (legado / nombre).write_bytes(pdf_real)
    sesion = SesionQueDevuelve(pdf_real)

    descarga = descargar_documento(
        sesion,
        documento(),
        EXPEDIENTE,
        tmp_path / "soportes" / "SD2022-0000017",
        carpeta_legado=legado,
    )

    assert sesion.peticiones == 0
    assert descarga.desde_cache
    assert descarga.ruta.read_bytes() == pdf_real
    assert not (legado / nombre).exists(), "se copia moviendo, no duplicando"


def test_un_pdf_corrupto_en_la_carpeta_antigua_no_se_migra(tmp_path, pdf_real):
    legado = tmp_path / "temp"
    legado.mkdir()
    (legado / nombre_de_archivo(EXPEDIENTE, TipoDoc.TM9)).write_bytes(
        b"%PDF- cortado"
    )
    sesion = SesionQueDevuelve(pdf_real)

    descarga = descargar_documento(
        sesion,
        documento(),
        EXPEDIENTE,
        tmp_path / "soportes" / "SD2022-0000017",
        carpeta_legado=legado,
    )

    assert sesion.peticiones == 1, "el corrupto se ignora y se baja de la red"
    assert descarga.ruta.read_bytes() == pdf_real
