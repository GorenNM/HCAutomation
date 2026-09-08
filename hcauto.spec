# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller.

--onefile: UN solo archivo. Se descarga el repo, se hace doble clic en
ExtraccionSIC.exe y se abre la ventana. Nada que extraer ni que instalar.

El coste conocido de onefile es que en cada arranque se descomprime a %TEMP%,
lo que anade unos segundos a la primera ventana. No afecta a donde escribe el
programa: `rutas.base_dir()` usa `sys.executable`, no `sys._MEIPASS`, asi que
salida\\ y temp\\ salen JUNTO al .exe y no en el temporal que Windows borra.
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
    # alias.json NO se empaqueta: `writer.cargar_alias` lo busca en
    # `base_dir() / "alias.json"`, es decir junto al .exe, y nunca dentro del
    # bundle. Empaquetarlo seria peso muerto que nadie lee. Va versionado en la
    # raiz del repo, asi que al descargar el ZIP queda al lado del ejecutable.
    # Si falta, la columna «Nombre corto» sale vacia y no pasa nada mas.
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
    a.binaries,
    a.datas,
    [],
    name=NOMBRE,
    debug=False,
    strip=False,
    upx=False,  # UPX aumenta los falsos positivos de antivirus.
    console=False,  # sin ventana negra detras de la interfaz
)
