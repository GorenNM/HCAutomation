# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller.

--onedir (no --onefile): onefile descomprime todo a %TEMP% en cada arranque,
lo que da segundos de ventana en blanco y es el patron que mas disparan los
antivirus. Se entrega la carpeta dist/ExtraccionSIC comprimida en un zip.
"""

NOMBRE = "ExtraccionSIC"

# Modulos que PyInstaller arrastra por analisis estatico y no se usan en runtime.
EXCLUIDOS = [
    "pytest",
    "hypothesis",
    "cairosvg",
    "unittest",
    "pydoc",
    "doctest",
    "pdb",
    "tarfile",
    "lib2to3",
]

a = Analysis(
    ["app/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUIDOS,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NOMBRE,
    debug=False,
    strip=False,
    upx=False,  # UPX aumenta los falsos positivos de antivirus.
    console=False,  # sin ventana negra detras de la interfaz
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=NOMBRE,
)
