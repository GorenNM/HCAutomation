"""Orquestación: del Excel de entrada al Excel de salida.

Es el único módulo que conoce el proceso completo. Los demás no se llaman entre
sí; todos cuelgan de aquí.

Tres reglas que gobiernan el diseño:

1. **Un expediente que falla no tumba la corrida.** Cualquier excepción que se
   escape de un worker se anota y se sigue con los 986 restantes.
2. **Detener no pierde trabajo.** El `Event` se mira al entrar en cada
   expediente; los que ya estaban en vuelo terminan y el Excel se escribe con lo
   que haya. Nunca queda un archivo a medias.
3. **Una corrida a la vez.** La segunda se rechaza con un mensaje en vez de
   pelearse por la carpeta `temp\\` y los contadores.

El callback de progreso se invoca **desde los hilos worker**. Quien lo pase debe
limitarse a encolar (la GUI lo hace con `queue.Queue`): tocar un widget de
tkinter desde aquí cuelga la ventana de forma intermitente.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Protocol

from app.config import HILOS_DEFECTO, HILOS_MAX, LAYOUT, dir_salida, dir_temp
from app.downloader.files import descargar_documentos
from app.downloader.scraper import (
    ErrorScraping,
    PaginaExpediente,
    documentos_de_expediente,
    extraer_documentos,
)
from app.downloader.session import SesionSIPI
from app.excel.reader import leer_reporte
from app.excel.writer import cargar_alias, escribir, expandir, ruta_por_defecto
from app.models import DocumentLink, ExtractedData, OutputRecord, SourceRow, TipoDoc
from app.parser.extractor import extraer
from app.parser.pdf_text import texto_de_pdf
from app.utils.text import nombre_archivo_seguro, sin_tildes

log = logging.getLogger(__name__)

# Tipos que se descargan. El resto (anexos, poderes, escaneos) se ignora: pesan
# y no aportan nada a la extracción.
TIPOS_UTILES = (TipoDoc.TM9, TipoDoc.TM128, TipoDoc.TM6, TipoDoc.APELACION)

# Una corrida a la vez en todo el proceso.
_EN_CURSO = threading.Lock()


class ErrorPipeline(Exception):
    """El mensaje va directo al usuario."""


class FabricaSesion(Protocol):
    """Lo único que el pipeline necesita saber de una sesión: cómo crearla.

    Existe para que las pruebas inyecten la sesión grabada sin tocar la red.
    """

    def __call__(self) -> SesionSIPI: ...  # pragma: no cover - solo tipado


@dataclass(frozen=True)
class Progreso:
    """Instantánea de la corrida. Se entrega **congelada** al callback."""

    total: int = 0
    expedientes: int = 0
    pdfs: int = 0
    registros: int = 0
    avisos: int = 0
    errores: int = 0
    actual: str = ""


@dataclass
class Resultado:
    progreso: Progreso = field(default_factory=Progreso)
    registros: list[OutputRecord] = field(default_factory=list)
    ruta_excel: Path | None = None
    errores: list[str] = field(default_factory=list)
    cancelado: bool = False


class _Contadores:
    """Los cinco números de la ventana, con su cerrojo.

    Sin el cerrojo, `n += 1` desde 8 hilos pierde incrementos: son tres
    operaciones (leer, sumar, escribir) y el intérprete puede cambiar de hilo en
    medio.
    """

    def __init__(self, total: int) -> None:
        self._cerrojo = threading.Lock()
        self._estado = Progreso(total=total)

    def anotar(self, **cambios: int | str) -> Progreso:
        with self._cerrojo:
            sumables = {
                clave: getattr(self._estado, clave) + valor
                for clave, valor in cambios.items()
                if clave != "actual"
            }
            if "actual" in cambios:
                sumables["actual"] = cambios["actual"]
            self._estado = replace(self._estado, **sumables)
            return self._estado

    @property
    def estado(self) -> Progreso:
        with self._cerrojo:
            return self._estado


# --- Un expediente -----------------------------------------------------------


def _resolucion_principal(descargas) -> Path | None:
    """TM128 manda sobre TM9: si hubo oposición, la resolución buena es la 128."""
    for tipo in (TipoDoc.TM128, TipoDoc.TM9):
        for descarga in descargas:
            if descarga.documento.tipo is tipo:
                return descarga.ruta
    return None


def _contradice_al_excel(fuente: SourceRow, datos: ExtractedData) -> str | None:
    """El Excel de entrada dice una cosa y la resolución otra. Gana la resolución."""
    declarado = sin_tildes(fuente.bajo_oposicion or "").strip().casefold()
    if declarado not in ("si", "no"):
        return None
    if (declarado == "si") == datos.presenta_oposicion:
        return None
    return (
        f"el reporte dice «Bajo Oposición = {fuente.bajo_oposicion}» y la resolución "
        f"dice lo contrario; se usa la resolución"
    )


def _ruta_de_pagina(carpeta: Path, expediente: str) -> Path:
    return carpeta / f"{nombre_archivo_seguro(expediente)}_pagina.html"


def _pagina_del_expediente(
    sesion: SesionSIPI, fuente: SourceRow, carpeta: Path, reusar: bool
) -> tuple[PaginaExpediente, list[DocumentLink]]:
    """La página del expediente, de disco si ya se tenía.

    Sin esto, volver a lanzar la corrida para recuperar los expedientes que
    fallaron **no converge**: se midió sobre los 987 reales. La segunda pasada
    recuperó los 10 que habían fallado, pero al volver a pedir las 987 páginas
    expuso 12 expedientes nuevos al mismo tropiezo de SIPI. Neto: peor.

    Guardando también el HTML, una repetición con «Reusar» no toca la red para
    lo que ya salió bien, y solo puede mejorar.
    """
    ruta = _ruta_de_pagina(carpeta, fuente.expediente)
    if reusar and ruta.is_file():
        try:
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            pagina = PaginaExpediente(url=guardado["url"], html=guardado["html"])
            return pagina, extraer_documentos(pagina.html)
        except (OSError, ValueError, KeyError, ErrorScraping) as error:
            # Caché inservible: se vuelve a pedir, como con un PDF corrupto.
            log.debug("%s: la página en caché no sirve (%s)", fuente.expediente, error)

    pagina, documentos = documentos_de_expediente(sesion, fuente.case_url)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps({"url": pagina.url, "html": pagina.html}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as error:  # que no se pueda guardar no invalida la corrida
        log.debug("%s: no se pudo guardar la página (%s)", fuente.expediente, error)
    return pagina, documentos


def procesar_expediente(
    sesion: SesionSIPI,
    fuente: SourceRow,
    carpeta: Path,
    reusar: bool = True,
    layout: str = LAYOUT,
    soportes: Path | None = None,
) -> tuple[list[OutputRecord], int, list[str]]:
    """Un expediente completo: página → PDFs → texto → registros.

    `carpeta` es la caché de trabajo (la página HTML del expediente).
    `soportes` es la carpeta de ESTE expediente dentro de `salida\\soportes\\`,
    donde quedan sus PDFs; si no se da, van a `carpeta`, como antes de que
    existiera `soportes\\`.

    Devuelve `(registros, pdfs_descargados, problemas)`. Siempre devuelve al
    menos un registro: un expediente que no se pudo leer sale con las celdas
    vacías y el motivo en `Observaciones`, nunca desaparece de la salida.
    """
    problemas: list[str] = []

    pagina, documentos = _pagina_del_expediente(sesion, fuente, carpeta, reusar)
    utiles = [doc for doc in documentos if doc.tipo in TIPOS_UTILES]
    if not utiles:
        problemas.append("el expediente no tiene resoluciones descargables")

    descargas, fallos = descargar_documentos(
        sesion,
        utiles,
        fuente.expediente,
        soportes or carpeta,
        referer=pagina.url,
        reusar=reusar,
        # Las corridas anteriores a `soportes\` dejaron sus PDFs en `temp\`:
        # se migran de ahí en vez de volver a bajar 620 MB.
        carpeta_legado=carpeta if soportes else None,
    )
    problemas.extend(fallos)

    apelacion = any(doc.tipo is TipoDoc.APELACION for doc in documentos) or None
    ruta = _resolucion_principal(descargas)

    if ruta is None:
        problemas.append("no se descargó ninguna resolución (TM9 / TM128)")
        datos = ExtractedData(apelacion=apelacion)
    else:
        datos = extraer(texto_de_pdf(ruta), apelacion=apelacion)
        conflicto = _contradice_al_excel(fuente, datos)
        if conflicto:
            problemas.append(conflicto)

    # Los problemas viajan en la misma columna que los avisos del extractor:
    # el usuario solo quiere saber qué mirar a mano, no de dónde salió cada uno.
    datos.avisos = list(dict.fromkeys([*datos.avisos, *problemas]))

    nuevos = sum(1 for descarga in descargas if not descarga.desde_cache)
    return expandir(fuente, datos, layout), nuevos, problemas


# --- La corrida --------------------------------------------------------------


def _sesiones_por_hilo(fabrica: FabricaSesion) -> tuple[Callable[[], SesionSIPI], list]:
    """Una sesión por hilo, y la lista de todas para poder cerrarlas al final.

    Compartir una `requests.Session` entre hilos funciona *casi* siempre; el
    'casi' aquí valdría cookies cruzadas entre expedientes.
    """
    local = threading.local()
    abiertas: list[SesionSIPI] = []
    cerrojo = threading.Lock()

    def obtener() -> SesionSIPI:
        sesion = getattr(local, "sesion", None)
        if sesion is None:
            sesion = fabrica()
            local.sesion = sesion
            with cerrojo:
                abiertas.append(sesion)
        return sesion

    return obtener, abiertas


def ejecutar(
    entrada: Path,
    salida: Path | None = None,
    hilos: int = HILOS_DEFECTO,
    reusar: bool = True,
    detener: threading.Event | None = None,
    al_progresar: Callable[[Progreso], None] | None = None,
    temp: Path | None = None,
    fabrica_sesion: FabricaSesion = SesionSIPI,
    layout: str = LAYOUT,
) -> Resultado:
    """Corre el proceso completo y escribe el Excel. Devuelve qué pasó."""
    if not _EN_CURSO.acquire(blocking=False):
        raise ErrorPipeline(
            "Ya hay una extracción en curso. Espere a que termine o púlselo en "
            "«Detener» antes de empezar otra."
        )
    try:
        return _correr(
            entrada,
            salida,
            hilos,
            reusar,
            detener or threading.Event(),
            al_progresar,
            temp or dir_temp(),
            fabrica_sesion,
            layout,
        )
    finally:
        _EN_CURSO.release()


def _correr(
    entrada: Path,
    salida: Path | None,
    hilos: int,
    reusar: bool,
    detener: threading.Event,
    al_progresar: Callable[[Progreso], None] | None,
    temp: Path,
    fabrica_sesion: FabricaSesion,
    layout: str,
) -> Resultado:
    filas = leer_reporte(Path(entrada))
    hilos = max(1, min(hilos, HILOS_MAX))
    contadores = _Contadores(total=len(filas.filas))
    resultado = Resultado(errores=list(filas.avisos))
    alias = cargar_alias()

    # `salida` admite carpeta o archivo: el usuario elige carpeta en la ventana,
    # pero las pruebas y una futura CLI quieren nombrar el archivo. Se resuelve
    # aquí, antes de arrancar, porque de la ruta cuelga `soportes\`: la carpeta
    # con los PDFs de cada expediente, uno por subdirectorio.
    if salida is None:
        ruta = ruta_por_defecto(dir_salida())
    elif Path(salida).suffix.lower() == ".xlsx":
        ruta = Path(salida)
    else:
        ruta = ruta_por_defecto(Path(salida))
    dir_soportes = ruta.parent / "soportes"

    def avisar(estado: Progreso) -> None:
        if al_progresar is None:
            return
        try:
            al_progresar(estado)
        except Exception:  # pragma: no cover - la GUI no puede tumbar la corrida
            log.exception("El callback de progreso falló; la corrida sigue")

    obtener_sesion, abiertas = _sesiones_por_hilo(fabrica_sesion)
    por_fila: dict[int, list[OutputRecord]] = {}
    errores: list[str] = []
    cerrojo_salida = threading.Lock()

    # Un cerrojo por expediente. El reporte repite expedientes (el real trae 11
    # duplicados) y sin esto dos hilos bajan los mismos archivos a la vez: el
    # segundo no reutiliza nada y se dobla el tráfico. Es también lo que hace
    # cierto el aviso del lector, «se descargará una sola vez».
    cerrojos: dict[str, threading.Lock] = {}
    cerrojo_de_cerrojos = threading.Lock()

    def cerrojo_del_expediente(expediente: str) -> threading.Lock:
        with cerrojo_de_cerrojos:
            return cerrojos.setdefault(expediente, threading.Lock())

    def trabajar(indice: int, fuente: SourceRow) -> None:
        if detener.is_set():
            return
        try:
            with cerrojo_del_expediente(fuente.expediente):
                registros, pdfs, problemas = procesar_expediente(
                    obtener_sesion(),
                    fuente,
                    temp,
                    reusar=reusar,
                    layout=layout,
                    soportes=dir_soportes
                    / nombre_archivo_seguro(fuente.expediente),
                )
        except Exception as error:  # noqa: BLE001 - a propósito: nada tumba la corrida
            # Incluye lo previsto (red, PDF ilegible) y lo no previsto, que es
            # justo lo que no puede costar los otros 986 expedientes.
            mensaje = f"{fuente.expediente} (fila {fuente.fila}): {error}"
            log.exception("Falló %s", fuente.expediente)
            with cerrojo_salida:
                errores.append(mensaje)
                por_fila[indice] = expandir(
                    fuente, ExtractedData(avisos=[str(error)]), layout
                )
            avisar(contadores.anotar(expedientes=1, errores=1, registros=1))
            return

        with cerrojo_salida:
            por_fila[indice] = registros
            errores.extend(problemas)
        avisar(
            contadores.anotar(
                expedientes=1,
                pdfs=pdfs,
                registros=len(registros),
                avisos=len(problemas),
                actual=fuente.expediente,
            )
        )

    try:
        with ThreadPoolExecutor(max_workers=hilos, thread_name_prefix="sipi") as pool:
            for indice, fuente in enumerate(filas.filas):
                pool.submit(trabajar, indice, fuente)
    finally:
        for sesion in abiertas:
            sesion.cerrar()

    # Orden del Excel de entrada, y las filas de un expediente contiguas.
    resultado.registros = [
        registro for indice in sorted(por_fila) for registro in por_fila[indice]
    ]
    resultado.errores.extend(errores)
    resultado.cancelado = detener.is_set()
    resultado.progreso = contadores.estado

    resultado.ruta_excel = escribir(resultado.registros, ruta, layout, alias)

    log.info(
        "Corrida %s: %d expedientes, %d PDFs, %d registros, %d errores → %s",
        "cancelada" if resultado.cancelado else "terminada",
        resultado.progreso.expedientes,
        resultado.progreso.pdfs,
        len(resultado.registros),
        len(resultado.errores),
        resultado.ruta_excel,
    )
    return resultado
