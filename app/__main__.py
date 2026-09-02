"""Punto de entrada: `python -m app` y también el del ejecutable.

Con `--autoprueba` no abre la ventana: importa todo, resuelve las rutas, escribe
un informe y sale con 0 o 1. Es la única forma de comprobar automáticamente que
el `.exe` empaquetado funciona — como se compila con `console=False`, un import
que falte no imprime nada, solo se ve al hacer doble clic.

Añadiendo `--red` hace además una petición HTTPS real contra SIPI. Va aparte
porque la construcción tiene que poder correr sin internet, pero es la única
comprobación que detecta que el `.exe` se quedó sin los certificados de
`certifi`, un clásico de PyInstaller que no se ve importando nada.
"""

from __future__ import annotations

import sys


def _probar_red(lineas: list[str], problemas: list[str]) -> None:
    """Una petición HTTPS de verdad contra SIPI.

    No es paranoia: un `.exe` de PyInstaller es el sitio clásico donde se pierde
    el paquete de certificados de `certifi` y **todo** HTTPS falla con un error
    de verificación. Importar `requests` no lo detecta; solo lo detecta usarlo.
    """
    from app.downloader.session import ErrorRed, SesionSIPI

    try:
        with SesionSIPI() as sesion:
            respuesta = sesion.obtener("https://sipi.sic.gov.co/sipi/")
        lineas.append(f"red OK ({respuesta.status_code}) hacia {respuesta.url}")
    except ErrorRed as error:
        problemas.append(f"red: {error}")


def autoprueba(con_red: bool = False) -> int:
    """Comprueba que el paquete está completo. Devuelve el código de salida."""
    lineas: list[str] = []
    problemas: list[str] = []

    from app import config
    from app.utils.rutas import base_dir, esta_empaquetado

    lineas.append(f"version={config.VERSION}")
    lineas.append(f"empaquetado={esta_empaquetado()}")
    lineas.append(f"base={base_dir()}")

    # Un import que PyInstaller no haya recogido revienta aquí y no en pantalla.
    modulos = (
        "app.gui",
        "app.pipeline",
        "app.excel.reader",
        "app.excel.writer",
        "app.parser.extractor",
        "app.parser.pdf_text",
        "app.downloader.files",
        "app.downloader.scraper",
        "app.downloader.session",
        "app.utils.logging_setup",
    )
    for nombre in modulos:
        try:
            __import__(nombre)
            lineas.append(f"import {nombre} OK")
        except Exception as error:  # noqa: BLE001
            problemas.append(f"import {nombre}: {error!r}")

    for etiqueta, carpeta in (("salida", config.dir_salida()), ("temp", config.dir_temp())):
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            testigo = carpeta / ".autoprueba"
            testigo.write_text("ok", encoding="utf-8")
            testigo.unlink()
            lineas.append(f"{etiqueta} escribible en {carpeta}")
        except OSError as error:
            problemas.append(f"{etiqueta} no escribible: {error}")

    if con_red:
        _probar_red(lineas, problemas)

    informe = base_dir() / "autoprueba.txt"
    informe.write_text(
        "\n".join(lineas + [f"PROBLEMA {p}" for p in problemas]) + "\n",
        encoding="utf-8",
    )
    return 1 if problemas else 0


def main() -> None:
    if "--autoprueba" in sys.argv:
        # `--red` aparte: la construcción tiene que poder correr sin internet.
        sys.exit(autoprueba(con_red="--red" in sys.argv))
    from app.gui import main as abrir_ventana

    abrir_ventana()


if __name__ == "__main__":
    main()
