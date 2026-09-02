"""Pruebas de resolución de rutas con y sin PyInstaller.

Si esto se rompe, el `.exe` escribe los resultados donde el usuario no los
encuentra — un fallo que no se ve nunca corriendo desde el código fuente.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from app import config
from app.utils import rutas


def test_desde_fuente_la_base_es_la_raiz_del_repo():
    assert not rutas.esta_empaquetado()
    assert (rutas.base_dir() / "requirements.txt").is_file()


def test_empaquetado_la_base_es_la_carpeta_del_exe(monkeypatch, tmp_path):
    exe = tmp_path / "ExtraccionSIC" / "ExtraccionSIC.exe"
    exe.parent.mkdir()
    exe.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert rutas.esta_empaquetado()
    assert rutas.base_dir() == exe.parent
    # Y las carpetas de trabajo cuelgan de ahí, no de _internal/.
    assert config.dir_salida() == exe.parent / "salida"
    assert config.dir_temp() == exe.parent / "temp"


def test_asegurar_dir_crea_los_padres_que_falten(tmp_path):
    objetivo = tmp_path / "a" / "b" / "c"
    assert rutas.asegurar_dir(objetivo) == objetivo
    assert objetivo.is_dir()


def test_asegurar_dir_no_falla_si_ya_existe(tmp_path):
    rutas.asegurar_dir(tmp_path)
    assert rutas.asegurar_dir(tmp_path).is_dir()


def test_no_hay_open_sin_encoding_en_el_codigo():
    """En Linux `open()` usa UTF-8; en Windows usa cp1252 y rompe los acentos de
    las resoluciones. El fallo solo aparece en la máquina del usuario, así que
    se prohíbe la construcción, no el síntoma.
    """
    sospechosos = []
    for archivo in (Path(rutas.base_dir()) / "app").rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for numero, linea in enumerate(texto.splitlines(), 1):
            # `\b` no basta: `Popen(` y `.open(` acabarían aquí. Solo interesa la
            # función incorporada `open(`, sola o tras un espacio o paréntesis.
            if not re.search(r"(?:^|[^\w.])open\(", linea):
                continue
            if any(t in linea for t in ("encoding=", '"rb"', "'rb'", '"wb"', "'wb'")):
                continue
            if linea.lstrip().startswith(("#", "*", '"')):
                continue
            sospechosos.append(f"{archivo.name}:{numero}: {linea.strip()}")
    assert not sospechosos, "open() sin encoding explícito:\n" + "\n".join(sospechosos)
