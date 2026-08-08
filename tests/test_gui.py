"""Pruebas de la ventana.

Crean un `Tk()` de verdad y accionan los botones por código. No hay simulacros
de widgets: lo que puede fallar de una GUI es justamente el pegamento entre el
hilo worker y el hilo de la ventana, y eso solo se ve con la ventana montada.

Se omiten enteras si no hay tkinter o no hay display — el Python de WSL no trae
`tkinter`, así que en Linux esto no corre. **Del lado Windows sí corre**, que es
donde el programa se usa.
"""

from __future__ import annotations

import queue
import threading

import pytest

tk = pytest.importorskip("tkinter", reason="El Python de WSL no trae tkinter")

from app.pipeline import Progreso, Resultado  # noqa: E402
from tests.conftest import (  # noqa: E402
    EXPEDIENTES_GRABADOS,
    SesionGrabadaMulti,
    fila_datos,
    formula_enlace,
)
from tests.test_pipeline import IDS, OPOSICION  # noqa: E402


def estado_de(widget) -> str:
    """`widget["state"]` devuelve un objeto de Tcl, no una cadena."""
    return str(widget["state"])


# `TclError` es el error genérico de tkinter: lo lanza tanto «no hay display»
# como una opción de widget mal escrita en `gui.py`. Omitir ante cualquiera de
# los dos deja sin red la ÚNICA prueba que abre la ventana: la construcción
# seguiría en verde y saldría un .exe que muere al doble clic sin decir nada,
# porque va con console=False. Aquí solo se omite por entorno.
# Cualquier `.tcl`, no solo `init.tcl`: el Python de Windows falla de forma
# intermitente al leer su propia biblioteca de Tcl —«couldn't read file
# panedwindow.tcl: no such file or directory» sobre un archivo que existe—, y el
# nombre del archivo cambia entre corridas. Un bug de `gui.py` no menciona un
# `.tcl`: dice `unknown option "-bg"` o `invalid color name`.
_FALLOS_DE_ENTORNO = (
    ".tcl",
    "display",  # 'no display name', "couldn't connect to display"
)


def _es_fallo_de_entorno(error: BaseException) -> bool:
    return any(senal in str(error).lower() for senal in _FALLOS_DE_ENTORNO)


def test_solo_se_omite_por_entorno_no_por_un_bug_de_la_ventana():
    """Si esto se relaja, un fallo real de `gui.py` pasa como prueba omitida."""
    assert _es_fallo_de_entorno(tk.TclError("Can't find a usable init.tcl in ..."))
    assert _es_fallo_de_entorno(tk.TclError("Can't find a usable tk.tcl in ..."))
    assert _es_fallo_de_entorno(
        tk.TclError('couldn\'t read file "…/tk8.6/panedwindow.tcl": no such file')
    )
    assert _es_fallo_de_entorno(tk.TclError("no display name and no $DISPLAY"))
    assert not _es_fallo_de_entorno(tk.TclError('unknown color name "#917AC3x"'))
    assert not _es_fallo_de_entorno(tk.TclError('unknown option "-bg"'))


@pytest.fixture
def ventana(tmp_path, monkeypatch):
    """Una ventana real, sin mostrarla, y sin diálogos modales."""
    from app import gui as modulo

    # Los messagebox bloquearían la prueba esperando un clic.
    vistos: list[tuple[str, str]] = []
    for nombre in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(
            modulo.messagebox,
            nombre,
            lambda titulo, mensaje, _n=nombre: vistos.append((_n, mensaje)),
        )
    monkeypatch.setattr(modulo.messagebox, "askokcancel", lambda *a, **k: True)

    try:
        v = modulo.Ventana()
    except tk.TclError as error:
        if not _es_fallo_de_entorno(error):
            raise  # es un bug de la ventana, no falta de display: que falle
        pytest.skip(f"No hay entorno gráfico: {error}")
    v.raiz.withdraw()
    v.mensajes = vistos
    try:
        yield v
    finally:
        v.detener.set()
        if v.hilo is not None:
            v.hilo.join(20)
        try:
            v.raiz.destroy()
        except tk.TclError:
            pass  # la prueba ya la cerró


def esperar(ventana, condicion, segundos: float = 60) -> bool:
    """Bombea la ventana hasta que se cumpla la condición."""
    import time

    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        ventana.raiz.update()
        if condicion():
            return True
        time.sleep(0.02)
    return False


def reporte(construir_reporte, expedientes):
    return construir_reporte(
        [
            fila_datos(
                formula_enlace(exp, IDS[exp]), marca=f"M{n}", oposicion=OPOSICION[exp]
            )
            for n, exp in enumerate(expedientes)
        ]
    )


# --- Arranque ----------------------------------------------------------------


def test_la_ventana_arranca_con_valores_por_defecto_usables(ventana):
    """El usuario solo debería tener que elegir el Excel."""
    assert ventana.salida.get()
    assert ventana.hilos.get() == "4"
    assert ventana.reusar.get() is True
    assert estado_de(ventana.boton_iniciar) == "normal"
    assert estado_de(ventana.boton_detener) == "disabled"
    assert estado_de(ventana.boton_abrir) == "disabled"


def test_iniciar_sin_excel_avisa_y_no_arranca_nada(ventana):
    ventana._iniciar()

    assert ventana.hilo is None
    assert ventana.mensajes and ventana.mensajes[0][0] == "showerror"
    assert "Elija el Excel" in ventana.mensajes[0][1]
    assert estado_de(ventana.boton_iniciar) == "normal"


def test_un_excel_que_no_existe_no_revienta(ventana, tmp_path):
    ventana.entrada.set(str(tmp_path / "fantasma.xlsx"))

    ventana._iniciar()

    assert ventana.hilo is None
    assert ventana.mensajes[0][0] == "showerror"


def test_las_comillas_que_pega_windows_no_estorban(ventana, tmp_path, construir_reporte):
    """Copiar «como ruta de acceso» en Windows envuelve la ruta en comillas."""
    entrada = reporte(construir_reporte, ["SD2022/0000017"])
    ventana.entrada.set(f'"{entrada}"')
    ventana.salida.set(str(tmp_path / "salida"))

    ventana._iniciar()

    assert ventana.hilo is not None, "no reconoció la ruta entrecomillada"


# --- Corrida completa desde la ventana ---------------------------------------


@pytest.mark.usefixtures("hay_fixtures_http")
def test_una_corrida_entera_desde_la_ventana(
    ventana, tmp_path, construir_reporte, monkeypatch
):
    from app import gui as modulo

    monkeypatch.setattr(
        modulo, "ejecutar", _ejecutar_offline(tmp_path), raising=True
    )
    ventana.entrada.set(str(reporte(construir_reporte, list(EXPEDIENTES_GRABADOS))))
    ventana.salida.set(str(tmp_path / "salida"))

    ventana._iniciar()
    assert estado_de(ventana.boton_detener) == "normal"
    assert esperar(ventana, lambda: estado_de(ventana.boton_abrir) == "normal")

    assert ventana.ultima_salida is not None and ventana.ultima_salida.is_file()
    assert "Terminado" in ventana.estado.get()
    assert "Registros 4" in ventana.contadores.get()
    assert estado_de(ventana.boton_iniciar) == "normal"
    assert estado_de(ventana.boton_detener) == "disabled"
    assert any(clase == "showinfo" for clase, _ in ventana.mensajes)


@pytest.mark.usefixtures("hay_fixtures_http")
def test_detener_a_mitad_deja_la_ventana_utilizable(
    ventana, tmp_path, construir_reporte, monkeypatch
):
    from app import gui as modulo

    monkeypatch.setattr(modulo, "ejecutar", _ejecutar_offline(tmp_path), raising=True)
    ventana.entrada.set(
        str(reporte(construir_reporte, list(EXPEDIENTES_GRABADOS) * 12))
    )
    ventana.salida.set(str(tmp_path / "salida"))

    ventana._iniciar()
    assert esperar(ventana, lambda: ventana.barra["value"] >= 2)
    ventana._detener()

    assert esperar(ventana, lambda: estado_de(ventana.boton_iniciar) == "normal")
    assert "Detenido" in ventana.estado.get()
    assert ventana.ultima_salida.is_file(), "no se escribió el Excel parcial"
    # Y se puede volver a empezar sin reiniciar el programa.
    assert estado_de(ventana.boton_detener) == "disabled"


def test_un_fallo_del_pipeline_llega_como_mensaje_y_no_como_traza(
    ventana, tmp_path, construir_reporte, monkeypatch
):
    from app import gui as modulo

    def reventar(*_a, **_k):
        raise RuntimeError("SIPI no responde")

    monkeypatch.setattr(modulo, "ejecutar", reventar)
    ventana.entrada.set(str(reporte(construir_reporte, ["SD2022/0000017"])))
    ventana.salida.set(str(tmp_path / "salida"))

    ventana._iniciar()
    assert esperar(ventana, lambda: estado_de(ventana.boton_iniciar) == "normal")

    assert ("showerror", "SIPI no responde") in ventana.mensajes
    assert "no pudo completarse" in ventana.estado.get()
    assert "Traceback" not in ventana.registro.get("1.0", "end")


# --- Plomería entre hilos ----------------------------------------------------


def test_el_worker_solo_empuja_a_la_cola_y_nunca_toca_un_widget(ventana):
    """El contrato del módulo. Si se rompe, tkinter cuelga sin avisar."""
    from app.gui import _Aviso

    ventana.cola.put(_Aviso("progreso", Progreso(total=10, expedientes=3, pdfs=9)))
    # `_drenar` se reprograma con `after(150)`: hay que dejar pasar el tiempo,
    # no solo bombear eventos.
    assert esperar(ventana, lambda: ventana.barra["value"] == 3, segundos=5)

    assert ventana.barra["value"] == 3
    assert ventana.barra["maximum"] == 10
    assert "PDFs 9" in ventana.contadores.get()


def test_el_registro_no_crece_sin_limite(ventana):
    """987 expedientes dejan decenas de miles de líneas; el widget se arrastra."""
    from app.gui import MAX_LINEAS_REGISTRO

    for numero in range(MAX_LINEAS_REGISTRO + 500):
        ventana._escribir(f"línea {numero}")

    lineas = [x for x in ventana.registro.get("1.0", "end").splitlines() if x]
    assert len(lineas) <= MAX_LINEAS_REGISTRO
    # Se poda por arriba: lo que interesa es lo último que pasó.
    assert lineas[-1] == f"línea {MAX_LINEAS_REGISTRO + 499}", "podó por el lado malo"
    assert "línea 0" not in lineas


def test_el_puente_de_logging_convierte_texto_en_aviso(ventana):
    from app.gui import _ColaDeTexto

    destino: queue.Queue = queue.Queue()
    _ColaDeTexto(destino).put_nowait("14:02:11 WARN algo")

    aviso = destino.get_nowait()
    assert aviso.clase == "log" and "WARN" in str(aviso.carga)


def test_una_carga_inesperada_en_la_cola_no_tumba_la_ventana(ventana):
    from app.gui import _Aviso

    ventana.cola.put(_Aviso("clase_que_no_existe", object()))
    esperar(ventana, lambda: ventana.cola.empty(), segundos=5)

    assert ventana.raiz.winfo_exists()


def test_el_progreso_sin_total_no_divide_por_cero(ventana):
    from app.gui import _Aviso

    ventana.cola.put(_Aviso("progreso", Progreso(total=0)))
    esperar(ventana, lambda: ventana.cola.empty(), segundos=5)

    assert ventana.raiz.winfo_exists()


# --- Cierre ------------------------------------------------------------------


def test_cerrar_con_una_corrida_activa_pide_confirmacion_y_la_detiene(
    ventana, tmp_path, construir_reporte, monkeypatch
):
    from app import gui as modulo

    arrancado = threading.Event()
    soltar = threading.Event()

    def lento(*_a, **kwargs):
        arrancado.set()
        soltar.wait(30)
        return Resultado(progreso=Progreso(total=1), ruta_excel=tmp_path / "x.xlsx")

    monkeypatch.setattr(modulo, "ejecutar", lento)
    ventana.entrada.set(str(reporte(construir_reporte, ["SD2022/0000017"])))
    ventana.salida.set(str(tmp_path / "salida"))
    ventana._iniciar()
    assert arrancado.wait(20)

    ventana._al_cerrar()  # askokcancel devuelve True en la fixture

    assert ventana.detener.is_set(), "no se pidió al pipeline que parara"
    soltar.set()


def test_cerrar_sin_corrida_no_pregunta_nada(ventana, monkeypatch):
    from app import gui as modulo

    preguntas = []
    monkeypatch.setattr(
        modulo.messagebox, "askokcancel", lambda *a, **k: preguntas.append(a) or True
    )

    ventana._al_cerrar()

    assert preguntas == []


# --- Utilidades --------------------------------------------------------------


def test_abrir_carpeta_crea_la_carpeta_y_llama_al_explorador(tmp_path, monkeypatch):
    from app import gui as modulo

    llamadas = []
    monkeypatch.setattr(modulo.subprocess, "Popen", lambda cmd: llamadas.append(cmd))
    destino = tmp_path / "no" / "existe"

    modulo.abrir_carpeta(destino)

    assert destino.is_dir()
    assert llamadas and str(destino) in llamadas[0]


def _ejecutar_offline(tmp_path):
    """`pipeline.ejecutar` con la sesión grabada y la carpeta temporal de la prueba."""
    from app.pipeline import ejecutar as real

    def envoltorio(entrada, **kwargs):
        kwargs["fabrica_sesion"] = SesionGrabadaMulti
        kwargs["temp"] = tmp_path / "temp"
        return real(entrada, **kwargs)

    return envoltorio
