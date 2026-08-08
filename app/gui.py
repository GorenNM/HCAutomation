"""Ventana de la aplicación (§11 del plan).

Lo único que ve el usuario final: elegir el Excel, pulsar Iniciar, mirar la
barra. Todo lo demás tiene un valor por defecto que ya funciona.

**La regla que gobierna este módulo: los widgets de tkinter solo se tocan desde
el hilo de la ventana.** El pipeline corre en un hilo aparte y se comunica por
una `queue.Queue`; `_drenar()` la vacía con `root.after(150, …)`. Saltarse esto
cuelga tkinter de forma intermitente e imposible de reproducir.
"""

from __future__ import annotations

import logging
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tkinter import BooleanVar, Frame, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from app import config
from app.pipeline import Progreso, Resultado, ejecutar
from app.utils.logging_setup import configurar

log = logging.getLogger(__name__)

INTERVALO_DRENADO_MS = 150
MAX_LINEAS_REGISTRO = 2_000

# Gris neutro y un solo acento: el mismo morado con el que el Excel marca las
# filas sin opositor, para que ventana y salida se lean como una sola cosa.
FONDO = "#F4F5F7"
TARJETA = "#FFFFFF"
BORDE = "#D9DDE3"
TEXTO = "#1F2430"
SUAVE = "#69707D"
ACENTO = "#917AC3"
COLOR_AVISO = "#B7791F"
COLOR_ERROR = "#C0392B"

# (atributo de Progreso, rótulo). El orden es el del embudo: de lo que se lee
# a lo que hay que revisar a mano.
FICHAS = (
    ("expedientes", "Expedientes"),
    ("pdfs", "PDFs"),
    ("registros", "Filas"),
    ("avisos", "Avisos"),
    ("errores", "Errores"),
)


def reloj(segundos: float) -> str:
    """`754` → `12:34`; a partir de una hora, `1:05:20`."""
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, sobrantes = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{sobrantes:02d}"
    return f"{minutos}:{sobrantes:02d}"


@dataclass
class _Aviso:
    """Mensaje del hilo worker hacia la ventana. Solo datos, nunca widgets."""

    clase: str  # 'progreso' | 'log' | 'fin' | 'error'
    carga: object = None


class _ColaDeTexto:
    """Traductor: `logging_setup` empuja texto suelto, la ventana espera `_Aviso`.

    Solo necesita `put_nowait`, que es lo único que usa `ColaHandler`.
    """

    def __init__(self, destino: queue.Queue[_Aviso]) -> None:
        self.destino = destino

    def put_nowait(self, linea: str) -> None:
        self.destino.put(_Aviso("log", linea))


class Ventana:
    """Estado y widgets. Una sola instancia por proceso."""

    def __init__(self) -> None:
        self.cola: queue.Queue[_Aviso] = queue.Queue()
        self.detener = threading.Event()
        self.hilo: threading.Thread | None = None
        self.ultima_salida: Path | None = None
        self.inicio = 0.0  # monotonic; 0 = no ha arrancado ninguna corrida

        self.raiz = Tk()
        self.raiz.title(f"{config.NOMBRE_APP} {config.VERSION}")
        self.raiz.geometry("620x640")
        self.raiz.minsize(560, 560)

        self.entrada = StringVar()
        self.salida = StringVar(value=str(config.dir_salida()))
        self.hilos = StringVar(value=str(config.HILOS_DEFECTO))
        self.reusar = BooleanVar(value=True)
        self.estado = StringVar(value="Elija el Excel del reporte y pulse «Iniciar».")
        self.contadores = StringVar(value="")
        self.porcentaje = StringVar(value="0 %")
        self.detalle = StringVar(value="")
        self.tiempos = StringVar(value="")
        self.fichas = {clave: StringVar(value="0") for clave, _ in FICHAS}

        self._construir()
        self.raiz.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.raiz.after(INTERVALO_DRENADO_MS, self._drenar)

    # --- Construcción --------------------------------------------------------

    def _estilos(self) -> None:
        """`clam` es el único tema de ttk que respeta los colores que se le piden.

        Con `vista`, el de Windows, los widgets los pinta el sistema y toda esta
        paleta se ignora **en silencio**: se ve nativo pero no se ve como esto.
        """
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        self.raiz.configure(bg=FONDO)

        estilo.configure(".", background=FONDO, foreground=TEXTO, font=("Segoe UI", 10))
        estilo.configure("Tarjeta.TLabel", background=TARJETA)
        estilo.configure("Suave.TLabel", foreground=SUAVE, background=FONDO)
        estilo.configure("SuaveTarjeta.TLabel", foreground=SUAVE, background=TARJETA)
        estilo.configure(
            "Titulo.TLabel", font=("Segoe UI", 15, "bold"), foreground=TEXTO
        )
        estilo.configure(
            "Paso.TLabel", font=("Segoe UI", 9, "bold"), foreground=ACENTO
        )
        estilo.configure(
            "Porcentaje.TLabel",
            font=("Segoe UI", 22, "bold"),
            foreground=ACENTO,
            background=TARJETA,
        )
        estilo.configure(
            "Cifra.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground=TEXTO,
            background=TARJETA,
        )
        estilo.configure(
            "Rotulo.TLabel", font=("Segoe UI", 8), foreground=SUAVE, background=TARJETA
        )
        estilo.configure(
            "Barra.Horizontal.TProgressbar",
            troughcolor="#E7E9EE",
            bordercolor="#E7E9EE",
            background=ACENTO,
            lightcolor=ACENTO,
            darkcolor=ACENTO,
            thickness=16,
        )
        estilo.configure("Principal.TButton", font=("Segoe UI", 10, "bold"))
        estilo.map(
            "Principal.TButton",
            background=[("!disabled", ACENTO), ("disabled", "#C9CDD4")],
            foreground=[("!disabled", "#FFFFFF"), ("disabled", "#8A9099")],
        )

    def _tarjeta(self, padre) -> Frame:
        """Un `tk.Frame`, no `ttk`: el borde de un color concreto solo se pide así."""
        return Frame(
            padre,
            bg=TARJETA,
            highlightthickness=1,
            highlightbackground=BORDE,
            padx=12,
            pady=10,
        )

    def _construir(self) -> None:
        self._estilos()
        marco = ttk.Frame(self.raiz, padding=14)
        marco.pack(fill="both", expand=True)
        marco.columnconfigure(1, weight=1)

        cabecera = ttk.Frame(marco)
        cabecera.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Label(cabecera, text=config.NOMBRE_APP, style="Titulo.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            cabecera,
            text="Elija el reporte de SIPI y pulse Iniciar. "
            "El Excel se escribe solo al terminar.",
            style="Suave.TLabel",
        ).pack(anchor="w")

        self._fila_ruta(marco, 1, "Excel de entrada", self.entrada, self._elegir_entrada)
        self._fila_ruta(marco, 2, "Carpeta de salida", self.salida, self._elegir_salida)

        opciones = ttk.Frame(marco)
        opciones.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 4))
        ttk.Label(opciones, text="Descargas en paralelo").pack(side="left")
        ttk.Spinbox(
            opciones,
            from_=1,
            to=config.HILOS_MAX,
            width=4,
            textvariable=self.hilos,
            state="readonly",
        ).pack(side="left", padx=(6, 18))
        ttk.Checkbutton(
            opciones, text="Reusar PDFs ya descargados", variable=self.reusar
        ).pack(side="left")

        botones = ttk.Frame(marco)
        botones.grid(row=4, column=0, columnspan=3, pady=10)
        self.boton_iniciar = ttk.Button(
            botones,
            text="Iniciar",
            command=self._iniciar,
            width=16,
            style="Principal.TButton",
        )
        self.boton_iniciar.pack(side="left", padx=6)
        self.boton_detener = ttk.Button(
            botones, text="Detener", command=self._detener, width=16, state="disabled"
        )
        self.boton_detener.pack(side="left", padx=6)

        tarjeta = self._tarjeta(marco)
        tarjeta.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 10))
        tarjeta.columnconfigure(0, weight=1)

        # Fila superior: el porcentaje grande a la izquierda del estado, que es
        # lo que se mira de reojo desde el otro lado de la mesa.
        arriba = Frame(tarjeta, bg=TARJETA)
        arriba.grid(row=0, column=0, sticky="ew")
        arriba.columnconfigure(1, weight=1)
        ttk.Label(arriba, textvariable=self.porcentaje, style="Porcentaje.TLabel").grid(
            row=0, column=0, rowspan=2, sticky="w", padx=(0, 12)
        )
        ttk.Label(
            arriba, textvariable=self.estado, style="Tarjeta.TLabel", anchor="w"
        ).grid(row=0, column=1, sticky="ew")
        ttk.Label(
            arriba, textvariable=self.detalle, style="SuaveTarjeta.TLabel", anchor="w"
        ).grid(row=1, column=1, sticky="ew")

        self.barra = ttk.Progressbar(
            tarjeta, mode="determinate", maximum=1, style="Barra.Horizontal.TProgressbar"
        )
        self.barra.grid(row=1, column=0, sticky="ew", pady=(10, 4))
        ttk.Label(
            tarjeta, textvariable=self.tiempos, style="SuaveTarjeta.TLabel"
        ).grid(row=2, column=0, sticky="w")

        # Las cinco cifras, cada una con su rótulo debajo: la línea corrida de
        # antes («Expedientes 412 · PDFs 1103 · …») obligaba a leerla entera
        # para encontrar el número que se buscaba.
        fichas = Frame(tarjeta, bg=TARJETA)
        fichas.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.cifras: dict[str, ttk.Label] = {}
        for columna, (clave, rotulo) in enumerate(FICHAS):
            fichas.columnconfigure(columna, weight=1)
            cifra = ttk.Label(
                fichas, textvariable=self.fichas[clave], style="Cifra.TLabel"
            )
            cifra.grid(row=0, column=columna, sticky="w")
            self.cifras[clave] = cifra
            ttk.Label(fichas, text=rotulo, style="Rotulo.TLabel").grid(
                row=1, column=columna, sticky="w"
            )

        ttk.Label(marco, text="Registro", style="Suave.TLabel").grid(
            row=8, column=0, sticky="w"
        )
        self.registro = ScrolledText(
            marco,
            height=14,
            wrap="word",
            state="disabled",
            bg=TARJETA,
            fg=TEXTO,
            font=("Consolas", 9),
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDE,
            padx=8,
            pady=6,
        )
        self.registro.grid(row=9, column=0, columnspan=3, sticky="nsew")
        marco.rowconfigure(9, weight=1)

        self.boton_abrir = ttk.Button(
            marco,
            text="Abrir carpeta de salida",
            command=self._abrir_salida,
            state="disabled",
        )
        self.boton_abrir.grid(row=10, column=0, columnspan=3, sticky="e", pady=(10, 0))

    def _fila_ruta(self, marco, fila: int, etiqueta: str, variable, comando) -> None:
        ttk.Label(marco, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=variable).grid(
            row=fila, column=1, sticky="ew", padx=6
        )
        ttk.Button(marco, text="…", width=3, command=comando).grid(row=fila, column=2)

    # --- Diálogos ------------------------------------------------------------

    def _elegir_entrada(self) -> None:
        elegido = filedialog.askopenfilename(
            title="Elija el Excel del reporte",
            filetypes=[("Libros de Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
        )
        if elegido:
            self.entrada.set(elegido)

    def _elegir_salida(self) -> None:
        elegido = filedialog.askdirectory(title="Elija la carpeta de salida")
        if elegido:
            self.salida.set(elegido)

    def _abrir_salida(self) -> None:
        carpeta = (
            self.ultima_salida.parent if self.ultima_salida else Path(self.salida.get())
        )
        try:
            abrir_carpeta(carpeta)
        except OSError as error:
            messagebox.showwarning(
                config.NOMBRE_APP, f"No se pudo abrir «{carpeta}»: {error}"
            )

    # --- Arranque y parada ---------------------------------------------------

    def _corriendo(self) -> bool:
        return self.hilo is not None and self.hilo.is_alive()

    def _iniciar(self) -> None:
        entrada = Path(self.entrada.get().strip('" '))
        if not entrada.is_file():
            messagebox.showerror(
                config.NOMBRE_APP,
                "Elija el Excel del reporte antes de iniciar.\n\n"
                f"No existe el archivo:\n{entrada}",
            )
            return
        if self._corriendo():
            return

        salida = Path(self.salida.get()) if self.salida.get().strip() else None
        self.detener = threading.Event()
        self.inicio = time.monotonic()
        self._limpiar_registro()
        self.barra.configure(maximum=1, value=0)
        self.porcentaje.set("0 %")
        self.detalle.set("")
        self.tiempos.set("")
        for variable in self.fichas.values():
            variable.set("0")
        self.estado.set("Leyendo el reporte…")
        self.boton_iniciar.configure(state="disabled")
        self.boton_detener.configure(state="normal")
        self.boton_abrir.configure(state="disabled")

        try:
            archivo = configurar(salida or config.dir_salida(), _ColaDeTexto(self.cola))
            self._escribir(f"Registro completo en {archivo}")
        except OSError as error:  # carpeta de salida inservible
            self._fallo(f"No se pudo preparar la carpeta de salida: {error}")
            return

        self.hilo = threading.Thread(
            target=self._trabajar,
            args=(entrada, salida, int(self.hilos.get()), self.reusar.get()),
            name="pipeline",
            daemon=True,
        )
        self.hilo.start()

    def _detener(self) -> None:
        self.detener.set()
        self.boton_detener.configure(state="disabled")
        self.estado.set("Deteniendo… se termina lo que está en curso.")

    def _trabajar(self, entrada, salida, hilos, reusar) -> None:
        """Corre en el hilo worker. **Aquí no se toca ningún widget.**"""
        try:
            resultado = ejecutar(
                entrada,
                salida=salida,
                hilos=hilos,
                reusar=reusar,
                detener=self.detener,
                al_progresar=lambda estado: self.cola.put(_Aviso("progreso", estado)),
            )
            self.cola.put(_Aviso("fin", resultado))
        except Exception as error:  # noqa: BLE001 - nada puede matar el hilo en silencio
            log.exception("La corrida terminó con error")
            self.cola.put(_Aviso("error", str(error)))

    # --- Hilo de la ventana --------------------------------------------------

    def _drenar(self) -> None:
        try:
            while True:
                aviso = self.cola.get_nowait()
                self._atender(aviso)
        except queue.Empty:
            pass
        finally:
            self.raiz.after(INTERVALO_DRENADO_MS, self._drenar)

    def _atender(self, aviso: _Aviso) -> None:
        if aviso.clase == "log":
            self._escribir(str(aviso.carga))
        elif aviso.clase == "progreso":
            self._pintar_progreso(aviso.carga)
        elif aviso.clase == "fin":
            self._terminar(aviso.carga)
        elif aviso.clase == "error":
            self._fallo(str(aviso.carga))

    def _pintar_progreso(self, estado: Progreso) -> None:
        if estado.total:
            self.barra.configure(maximum=estado.total, value=estado.expedientes)
            self.porcentaje.set(f"{estado.expedientes * 100 // estado.total} %")
        self.estado.set(f"Procesando {estado.expedientes} de {estado.total}")
        self.detalle.set(f"Ahora: {estado.actual or '…'}")
        self.tiempos.set(self._tiempos(estado))

        for clave, _ in FICHAS:
            self.fichas[clave].set(f"{getattr(estado, clave):,}".replace(",", "."))
        # Avisos y errores solo se tiñen cuando hay alguno: en verde no dicen
        # nada y en rojo permanente el usuario deja de verlos.
        self.cifras["avisos"].configure(
            foreground=COLOR_AVISO if estado.avisos else TEXTO
        )
        self.cifras["errores"].configure(
            foreground=COLOR_ERROR if estado.errores else TEXTO
        )

        self.contadores.set(
            f"Expedientes {estado.expedientes} · PDFs {estado.pdfs} · "
            f"Registros {estado.registros} · Advertencias {estado.avisos} · "
            f"Errores {estado.errores}"
        )

    def _tiempos(self, estado: Progreso) -> str:
        """Transcurrido y estimado. El estimado sale del ritmo real, no de una
        constante: SIPI va a velocidades muy distintas según la hora."""
        if not self.inicio:
            return ""
        transcurrido = time.monotonic() - self.inicio
        texto = f"Transcurrido {reloj(transcurrido)}"
        if estado.expedientes and estado.total > estado.expedientes:
            falta = transcurrido / estado.expedientes * (
                estado.total - estado.expedientes
            )
            return f"{texto} · faltan ~{reloj(falta)}"
        return texto

    def _terminar(self, resultado: Resultado) -> None:
        self.ultima_salida = resultado.ruta_excel
        self._pintar_progreso(resultado.progreso)
        self.boton_iniciar.configure(state="normal")
        self.boton_detener.configure(state="disabled")
        self.boton_abrir.configure(state="normal")

        cabecera = "Detenido por el usuario" if resultado.cancelado else "Terminado"
        self.estado.set(f"{cabecera}. {len(resultado.registros)} filas escritas.")
        # Ya no queda nada por delante: un «faltan ~3 min» congelado en pantalla
        # después de terminar es de lo que más desconcierta.
        self.detalle.set(str(resultado.ruta_excel.name))
        self.tiempos.set(f"Duración total {reloj(time.monotonic() - self.inicio)}")
        self._escribir(f"{cabecera}: {resultado.ruta_excel}")
        for problema in resultado.errores:
            self._escribir(f"AVISO  {problema}")

        messagebox.showinfo(
            config.NOMBRE_APP,
            f"{cabecera}.\n\n"
            f"Expedientes procesados: {resultado.progreso.expedientes}\n"
            f"PDFs descargados: {resultado.progreso.pdfs}\n"
            f"Filas generadas: {len(resultado.registros)}\n"
            f"Avisos: {len(resultado.errores)}\n\n"
            f"Archivo:\n{resultado.ruta_excel}",
        )

    def _fallo(self, mensaje: str) -> None:
        self.boton_iniciar.configure(state="normal")
        self.boton_detener.configure(state="disabled")
        self.estado.set("La corrida no pudo completarse.")
        self._escribir(f"ERROR  {mensaje}")
        messagebox.showerror(config.NOMBRE_APP, mensaje)

    # --- Registro ------------------------------------------------------------

    def _escribir(self, linea: str) -> None:
        self.registro.configure(state="normal")
        self.registro.insert("end", linea + "\n")
        # Sin poda, una corrida de 987 expedientes deja decenas de miles de
        # líneas en el widget y la ventana se arrastra.
        sobrantes = int(self.registro.index("end-1c").split(".")[0]) - MAX_LINEAS_REGISTRO
        if sobrantes > 0:
            self.registro.delete("1.0", f"{sobrantes + 1}.0")
        self.registro.see("end")
        self.registro.configure(state="disabled")

    def _limpiar_registro(self) -> None:
        self.registro.configure(state="normal")
        self.registro.delete("1.0", "end")
        self.registro.configure(state="disabled")

    # --- Cierre --------------------------------------------------------------

    def _al_cerrar(self) -> None:
        if self._corriendo():
            if not messagebox.askokcancel(
                config.NOMBRE_APP,
                "Hay una extracción en curso.\n\n"
                "Si cierra ahora se detendrá y el Excel quedará con lo procesado "
                "hasta este momento. ¿Cerrar de todos modos?",
            ):
                return
            self.detener.set()
            # El hilo es daemon: no bloquea la salida si tarda en soltar la red.
            self.hilo.join(timeout=10)
        self.raiz.destroy()

    def abrir(self) -> None:
        self.raiz.mainloop()


def abrir_carpeta(carpeta: Path) -> None:
    """Abre el explorador de archivos del sistema en esa carpeta."""
    carpeta.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(carpeta)])  # noqa: S603,S607
    elif sys.platform == "darwin":  # pragma: no cover - no es el objetivo
        subprocess.Popen(["open", str(carpeta)])  # noqa: S603,S607
    else:  # pragma: no cover - WSL, solo para desarrollo
        subprocess.Popen(["xdg-open", str(carpeta)])  # noqa: S603,S607


def main() -> None:
    Ventana().abrir()
