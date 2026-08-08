"""Resolución de rutas, con y sin PyInstaller.

Único sitio del proyecto que sabe si estamos dentro de un `.exe`. Todo lo demás
pide las carpetas aquí; si esta lógica se duplica, el ejecutable termina
escribiendo en la carpeta equivocada (típicamente dentro de `_internal/`).
"""

from __future__ import annotations

import sys
from pathlib import Path


def esta_empaquetado() -> bool:
    """True si el código corre dentro de un ejecutable de PyInstaller."""
    return getattr(sys, "frozen", False)


def base_dir() -> Path:
    """Carpeta de trabajo del programa.

    Empaquetado: la carpeta que contiene el `.exe`, para que `salida/` y `temp/`
    queden junto al ejecutable y el usuario los encuentre sin buscar.
    Desde el fuente: la raíz del repositorio.
    """
    if esta_empaquetado():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def asegurar_dir(ruta: Path) -> Path:
    """Crea el directorio si falta y lo devuelve, para poder encadenar."""
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
