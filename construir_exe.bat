@echo off
REM Construye el ejecutable. Lo corre el desarrollador en Windows, no el usuario final.
REM PyInstaller no hace cross-compilacion: esto tiene que ejecutarse sobre Windows.
setlocal

if not exist .venv-win\Scripts\python.exe (
    echo Creando entorno virtual de Windows...
    py -3.14 -m venv .venv-win || goto :error
)

call .venv-win\Scripts\activate.bat
python -m pip install --quiet --upgrade pip || goto :error
python -m pip install --quiet -r requirements-dev.txt || goto :error

echo.
echo === Pruebas ===
python -m pytest -q || goto :error

echo.
echo === Empaquetando ===
python -m PyInstaller hcauto.spec --noconfirm --clean || goto :error

REM alias.json va JUNTO al .exe, no dentro de _internal\ como haria 'datas' del
REM spec: es un archivo de datos que el usuario puede querer ampliar a mano.
REM Si no existe, la columna 'Nombre corto' sale vacia y no pasa nada mas.
if exist alias.json (
    copy /Y alias.json dist\ExtraccionSIC\alias.json >nul || goto :error
    echo   alias.json incluido
) else (
    echo   AVISO: no hay alias.json. Generarlo con: python sembrar_alias.py
)

REM El .exe NO arranca desde una ruta de red o UNC (\\wsl.localhost\...): el
REM bootloader de PyInstaller no puede usar ese directorio como directorio de
REM trabajo y Windows responde 'no encuentra el archivo "\"'. Si el proyecto
REM vive en WSL, se copia el resultado a una ruta local para poder probarlo.
set "DESTINO=%USERPROFILE%\ExtraccionSIC"
echo.
echo === Copiando a una ruta local para prueba ===
REM Si el .exe esta abierto, Windows no deja reemplazarlo y robocopy lo deja
REM estar: la construccion "termina bien" y deja el binario VIEJO en su sitio.
taskkill /F /IM ExtraccionSIC.exe >nul 2>&1
robocopy dist\ExtraccionSIC "%DESTINO%" /MIR /NJH /NJS /NP /NDL >nul
if errorlevel 8 goto :error

REM Un import que PyInstaller no recoja no da la cara al construir: el .exe se
REM abre y muere sin decir nada, porque va con console=False. --autoprueba
REM importa todo y comprueba que las carpetas de trabajo son escribibles.
echo.
echo === Autoprueba del ejecutable ===
"%DESTINO%\ExtraccionSIC.exe" --autoprueba
if errorlevel 1 (
    type "%DESTINO%\autoprueba.txt"
    goto :error
)
echo El ejecutable arranca y encuentra sus carpetas.

echo.
echo Listo.
echo   Compilado : dist\ExtraccionSIC\ExtraccionSIC.exe
echo   Ejecutable: %DESTINO%\ExtraccionSIC.exe   ^<- abrir este
exit /b 0

:error
echo.
echo FALLO la construccion. No se genero el ejecutable.
exit /b 1
