"""Constantes y parámetros. Un solo sitio donde tocar valores."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from app.utils.rutas import base_dir

VERSION: Final = "0.1.0"
NOMBRE_APP: Final = "Extracción SIC"

# --- Red ---------------------------------------------------------------------
# View.ashx?<id> redirige a Browse.aspx?sid=<sid>; el HTML resultante ya trae los
# enlaces GetFile.aspx de los PDFs. Sin cookie de sesión, View.ashx entra en un
# bucle de redirecciones infinito: por eso una única Session para todo.
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT_SEG: Final = 60
REINTENTOS: Final = 3
BACKOFF_FACTOR: Final = 1.5
DELAY_ENTRE_PETICIONES_SEG: Final = 0.3

# Esperas entre reintentos cuando GetFile responde HTTP 200 con algo que no es
# un PDF (un PNG de 828 bytes). Los reintentos de urllib3 NO cubren este caso:
# para ellos la petición fue un éxito. Medido en la corrida de los 987: el sitio
# devolvió el PNG durante los primeros 26 segundos y después ni una sola vez, así
# que las esperas tienen que sumar más de eso o no sirven de nada.
ESPERAS_CONTENIDO_SEG: Final = (3.0, 8.0, 20.0)

# --- Concurrencia ------------------------------------------------------------
HILOS_DEFECTO: Final = 4
HILOS_MAX: Final = 8

# --- Excel de entrada --------------------------------------------------------
FILA_CABECERAS: Final = 11  # los datos empiezan en la 12
COLUMNA_ENLACE: Final = 1

# --- Extracción --------------------------------------------------------------
# Menos caracteres que esto en una resolución = PDF escaneado sin capa de texto.
MIN_CARACTERES_PDF: Final = 500

# --- Salida ------------------------------------------------------------------
# LAYOUT define el formato del Excel generado. "poc" = una fila por motivo de
# negación. "clasico" = las 18 columnas del archivo de referencia,
# con MOTIVO 1 / MOTIVO 2. Revertir la POC es cambiar este valor.
LAYOUT: Final = "poc"
LIMITE_CELDA_EXCEL: Final = 32_767


def dir_salida() -> Path:
    return base_dir() / "salida"


def dir_temp() -> Path:
    return base_dir() / "temp"
