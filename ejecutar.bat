@echo off
REM Abre el programa desde el codigo fuente. Doble clic y listo.
REM
REM Existe para el caso "descargo el repo como ZIP en un Windows nuevo y quiero
REM usarlo": no empaqueta nada, asi que no depende de PyInstaller ni de que el
REM Python instalado sirva para empaquetar. El build de la Microsoft Store lleva
REM Tcl/Tk en un zip embebido y rompe el .exe, pero corriendo desde el fuente
REM funciona igual de bien. Para construir el .exe esta construir_exe.bat.
setlocal

REM Al extraer el ZIP en Descargas la ruta es normal, pero si el proyecto vive en
REM WSL su ruta es UNC (\\wsl.localhost\...) y cmd.exe la rechaza como directorio
REM actual: se queda en C:\Windows y no encuentra nada. pushd la mapea a una
REM letra de unidad temporal. %~dp0 = la carpeta de este .bat.
pushd "%~dp0" || (
    echo No se pudo entrar en "%~dp0".
    pause
    exit /b 1
)

where py >nul 2>&1 || goto :sin_python

if not exist .venv\Scripts\python.exe (
    echo Primera vez: preparando el entorno. Tarda un par de minutos.
    py -3 -m venv .venv || goto :error
    REM Solo requirements.txt: las de desarrollo (pytest, pyinstaller, cairosvg)
    REM no hacen falta para usar el programa y tardan mucho mas en bajar.
    .venv\Scripts\python.exe -m pip install --quiet --upgrade pip || goto :error
    .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt || goto :error
    echo Entorno listo.
)

REM Sin `start`: si el arranque falla, el mensaje se queda en esta ventana.
.venv\Scripts\python.exe -m app || goto :error
popd
exit /b 0

:sin_python
echo.
echo No hay Python instalado (no se encontro el lanzador 'py').
echo Instale Python 3 desde https://www.python.org/downloads/windows/
echo y marque "Add python.exe to PATH" durante la instalacion.
echo.
pause
popd
exit /b 1

:error
echo.
echo No se pudo arrancar. El mensaje de arriba dice por que.
echo Si el entorno quedo a medias, borre la carpeta .venv y vuelva a intentar.
echo.
pause
popd
exit /b 1
