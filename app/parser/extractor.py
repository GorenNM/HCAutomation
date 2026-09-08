"""Del texto de la resolución a `ExtractedData`.

Reglas de la casa:

* Ninguna función lanza excepción por no encontrar algo. Lo que falta se
  devuelve vacío y se acumula un aviso; el usuario revisa la columna
  «Observaciones» y decide.
* Nada se infiere de la posición dentro del documento, solo de sus frases.
* Ante la duda, se avisa. Nunca se inventa un dato.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

from app.config import CLASE_OBJETIVO
from app.models import ExtractedData, Opositor
from app.parser import patterns as p
from app.utils.text import clave_comparacion, normalizar

log = logging.getLogger(__name__)

_MAX_OPOSITORES_REPORTADOS = 2

# Ventana alrededor de «presentó oposición» donde se busca el patrón completo.
# En los textos reales el nombre está a menos de 100 caracteres antes y la
# fórmula «con fundamento en…» a menos de 200 después.
_VENTANA_ANTES = 180
_VENTANA_DESPUES = 400

# Cuánto texto antes de «En mérito de lo expuesto» cuenta como conclusión de la
# Dirección. Ver `zona_de_conclusion` para de dónde sale el número.
_VENTANA_CONCLUSION = 8_000


# --- Piezas sueltas ----------------------------------------------------------


def extraer_naturaleza(texto: str) -> str | None:
    """'Nominativa' | 'Mixta' | 'Figurativa' | '3D'."""
    encontrado = p.SOLICITUD.search(texto)
    if not encontrado:
        return None
    naturaleza = encontrado.group("naturaleza").capitalize()
    return "3D" if naturaleza.lower() == "3d" else naturaleza


def extraer_marca(texto: str) -> str | None:
    encontrado = p.SOLICITUD.search(texto)
    return normalizar(encontrado.group("marca")) if encontrado else None


def clases_de_la_oposicion(texto: str, ancla: re.Match[str]) -> list[str]:
    """Clases a las que se dirige una oposición. Vacío = no lo dice."""
    alcance = p.ALCANCE_CLASES.match(texto, ancla.start())
    if alcance is None:
        return []
    return re.findall(r"\d{1,3}", alcance.group("clases"))


def _alcanza_la_clase(
    texto: str, ancla: re.Match[str], objetivo: Sequence[str]
) -> bool:
    """False solo si la oposición se dirige EXPRESAMENTE a otras clases.

    Una solicitud puede cubrir varias clases y el reporte de entrada trae solo
    las suyas. Sin esto, la oposición que SD2022/0038666 recibió «frente a la
    clase 25» se registraba como oposición a la clase 5.

    Callar la clase significa ir contra toda la solicitud, así que la ausencia
    de mención cuenta a favor de registrarla: perder una oposición real es peor
    que arrastrar una de más, que se ve al revisar la fila.
    """
    clases = clases_de_la_oposicion(texto, ancla)
    return not clases or any(c in clases for c in objetivo)


def hay_oposicion(
    texto: str, objetivo: Sequence[str] = (CLASE_OBJETIVO,)
) -> bool:
    """La frase explícita manda sobre la ausencia de menciones."""
    if p.SIN_OPOSICION.search(texto):
        return False
    return any(
        _alcanza_la_clase(texto, ancla, objetivo)
        for ancla in p.HAY_OPOSICION.finditer(texto)
    )


def limpiar_nombre(crudo: str) -> str:
    """Recorta el nombre del opositor del texto que lo rodea.

    El nombre viene precedido de la fecha de la Gaceta y a veces de «la
    sociedad». Se corta por la última coma, salvo que lo que siga sea un
    sufijo societario: 'JHO INTELLECTUAL PROPERTY HOLDINGS, LLC.' es un único
    opositor, y en el archivo de referencia el 18 % de los nombres son así.
    """
    # Se recortan comas y espacios, pero NUNCA el punto final: los nombres
    # acaban en 'S.A.' y quitárselo los deja mal escritos.
    nombre = normalizar(crudo).lstrip(" ,;.").rstrip(" ,;")
    nombre = p.PREAMBULO_GACETA.sub("", nombre).lstrip(" ,;.")
    partes = [parte.strip() for parte in nombre.split(",")]
    if len(partes) > 1:
        reconstruido = partes[-1]
        indice = len(partes) - 1
        while indice > 0 and p.SUFIJO_SOCIETARIO.match(partes[indice]):
            indice -= 1
            reconstruido = f"{partes[indice]}, {reconstruido}"
        nombre = reconstruido
    return p.PREFIJO_PERSONA.sub("", nombre).lstrip(" ,;.").rstrip(" ,;")


def _parece_nombre(nombre: str) -> bool:
    """Un nombre real de opositor (sociedad o persona) siempre trae mayúsculas.

    En SD2022/0005052 la lista de productos de la marca del opositor entra como
    nota al pie ENTRE el nombre y «presentó oposición» (9 400 caracteres de por
    medio), y la ventana capturaba «minerales y antioxidantes en cuanto
    suplementos nutricionales y dietéticos.» como si fuera el nombre. Ese
    fragmento va todo en minúsculas; ningún nombre real se escribe así.
    """
    return any(caracter.isupper() for caracter in nombre)


def _opositores_del_resuelve(texto: str) -> list[Opositor]:
    """Nombres según «Declarar (in)fundada la oposición interpuesta por X».

    Plan B cuando el nombre no se pudo leer junto a «presentó oposición»: la
    parte resolutiva repite el nombre limpio, sin notas al pie incrustadas.
    """
    encontrados: dict[str, Opositor] = {}
    for declaracion in p.DECLARACION_OPOSICION.finditer(texto):
        nombre = limpiar_nombre(declaracion.group("nombre"))
        if nombre and _parece_nombre(nombre):
            encontrados.setdefault(clave_comparacion(nombre), Opositor(nombre=nombre))
    return list(encontrados.values())


@dataclass
class _Oposicion:
    """Una aparición de «presentó oposición», tal cual sale del texto."""

    nombre: str  # '' si no se pudo leer
    articulos: list[str]
    clases: list[str]  # vacío = la resolución no acota la oposición a ninguna
    parcial: bool = False  # se leyeron artículos, pero quedaron más sin leer


def _oposiciones_del_texto(texto: str) -> list[_Oposicion]:
    """Una entrada por aparición de «presentó oposición», sin agrupar ni filtrar.

    Primero se localiza la frase barata «presentó oposición» y solo alrededor
    de cada aparición se aplica el patrón completo. Buscarlo directamente sobre
    todo el texto costaba 11 s en un documento de 5 MB: el prefijo que captura
    el nombre se probaba en cada posición del documento.
    """
    encontradas: list[_Oposicion] = []
    fin_anterior = 0

    for ancla in p.HAY_OPOSICION.finditer(texto):
        # La ventana nunca retrocede más allá de la oposición anterior: si dos
        # van a menos de _VENTANA_ANTES una de otra, `OPOSICION.search` devolvía
        # la primera y la segunda se quedaba con el nombre de aquella.
        inicio = max(fin_anterior, ancla.start() - _VENTANA_ANTES)
        ventana = texto[inicio : ancla.end() + _VENTANA_DESPUES]
        coincidencia = p.OPOSICION.search(ventana)
        parcial = False

        if coincidencia is None:
            # Hay oposición pero sin la fórmula «con fundamento en…».
            nombre = limpiar_nombre(texto[inicio : ancla.start()])
            articulos: list[str] = []
        else:
            nombre = limpiar_nombre(coincidencia.group("antes"))
            articulos = p.codigos_de_referencia(coincidencia, "_op")
            encadenadas, fin = p.referencias_encadenadas(ventana, coincidencia.end())
            articulos += [c for c in encadenadas if c not in articulos]
            # Si tras la última referencia leída sigue habiendo 'y el literal…',
            # es que quedaron artículos fuera y no sabemos cuáles.
            parcial = bool(p.REFERENCIA_COLGANTE.match(ventana, fin))

        if nombre and not _parece_nombre(nombre):
            nombre = ""  # cola de una lista de productos, no un nombre

        encontradas.append(
            _Oposicion(nombre, articulos, clases_de_la_oposicion(texto, ancla), parcial)
        )
        fin_anterior = ancla.end()

    return encontradas


def _rescatar_nombres(
    texto: str, oposiciones: list[_Oposicion]
) -> tuple[list[_Oposicion], list[str]]:
    """Nombres desde la parte resolutiva cuando ninguno se pudo leer arriba.

    Las clases se heredan de las apariciones ilegibles: el filtro por clase se
    aplica después, así que el rescate tiene que correr igualmente aunque la
    oposición acabe descartada. Si no, el aviso diría «Un opositor» en vez del
    nombre, que es justo el dato que hace falta para revisar la fila.
    """
    rescatados = _opositores_del_resuelve(texto)
    if not rescatados:
        return [], ["Se detectó una oposición sin nombre de opositor legible."]

    avisos = [
        "El nombre del opositor no se pudo leer junto a «presentó oposición»; "
        "se tomó de la parte resolutiva."
    ]
    clases: list[str] = []
    for oposicion in oposiciones:
        clases.extend(c for c in oposicion.clases if c not in clases)

    con_articulos = [o for o in oposiciones if o.articulos]
    if len(rescatados) == 1 and len(con_articulos) == 1:
        # Una sola oposición con artículos y un solo opositor declarado: los
        # artículos son suyos sin ambigüedad.
        articulos = list(con_articulos[0].articulos)
        parcial = con_articulos[0].parcial
    else:
        articulos, parcial = [], False

    return [
        _Oposicion(o.nombre, list(articulos), list(clases), parcial) for o in rescatados
    ], avisos


def extraer_opositores(
    texto: str, objetivo: Sequence[str] = (CLASE_OBJETIVO,)
) -> tuple[list[Opositor], list[str]]:
    """Opositores en orden de aparición, con los artículos que invocaron.

    Se leen todas las apariciones, se agrupan por nombre y solo al final se
    descartan las dirigidas a otras clases. Ese orden importa: un mismo
    opositor puede oponerse a varias clases en frases distintas, y basta con
    que una alcance la del reporte para que cuente.
    """
    avisos: list[str] = []
    oposiciones = _oposiciones_del_texto(texto)
    if not oposiciones:
        return [], avisos

    if not any(o.nombre for o in oposiciones):
        oposiciones, avisos_rescate = _rescatar_nombres(texto, oposiciones)
        avisos.extend(avisos_rescate)

    por_clave: dict[str, Opositor] = {}
    clases: dict[str, list[str]] = {}
    sin_acotar: set[str] = set()  # se opusieron a la solicitud entera
    parciales: set[str] = set()

    for oposicion in oposiciones:
        if not oposicion.nombre:
            continue
        clave = clave_comparacion(oposicion.nombre)
        # El mismo opositor puede repetir la frase una vez por clase.
        destino = por_clave.setdefault(clave, Opositor(nombre=oposicion.nombre))
        destino.articulos.extend(
            a for a in oposicion.articulos if a not in destino.articulos
        )
        vistas = clases.setdefault(clave, [])
        vistas.extend(c for c in oposicion.clases if c not in vistas)
        if not oposicion.clases:
            sin_acotar.add(clave)
        if oposicion.parcial:
            parciales.add(clave)

    opositores: list[Opositor] = []
    for clave, opositor in por_clave.items():
        if clave not in sin_acotar and not any(c in clases[clave] for c in objetivo):
            avisos.append(
                f"«{opositor.nombre}» se opuso solo a la(s) clase(s) "
                f"{', '.join(clases[clave])} y no a la {'/'.join(objetivo)}: "
                "no se registra."
            )
            continue
        if not opositor.articulos:
            avisos.append(
                f"No se pudo determinar en qué artículos fundó su oposición "
                f"«{opositor.nombre}»."
            )
        elif clave in parciales:
            avisos.append(
                f"«{opositor.nombre}» invoca más artículos de los que se pudieron "
                f"leer; solo se registró {', '.join(opositor.articulos)}. "
                "Revisar a mano."
            )
        opositores.append(opositor)

    return opositores, avisos


def asignar_fundadas(texto: str, opositores: list[Opositor]) -> list[str]:
    """Rellena `fundada` en cada opositor a partir de la parte resolutiva."""
    avisos: list[str] = []
    if not opositores:
        return avisos

    por_clave = {clave_comparacion(o.nombre): o for o in opositores}

    for coincidencia in p.DECLARACION_OPOSICION.finditer(texto):
        sentido = normalizar(coincidencia.group("sentido")).lower()
        valor = "NO" if sentido == "infundada" else "SI"
        nombre = limpiar_nombre(coincidencia.group("nombre"))
        clave = clave_comparacion(nombre)

        destino = por_clave.get(clave)
        if destino is None and len(opositores) == 1:
            # Un solo opositor: aunque el nombre no case exacto, es él.
            destino = opositores[0]
        if destino is None:
            avisos.append(
                f"«Declarar {sentido}» menciona a «{nombre}», que no coincide con "
                "ningún opositor detectado."
            )
            continue

        if sentido.startswith("parcialmente"):
            avisos.append(
                f"La oposición de «{destino.nombre}» se declaró PARCIALMENTE fundada; "
                "se registra como SI."
            )
        destino.fundada = valor

    for opositor in opositores:
        if opositor.fundada is None:
            avisos.append(
                f"No se encontró si la oposición de «{opositor.nombre}» fue fundada."
            )
    return avisos


def zona_de_conclusion(texto: str) -> str:
    """El tramo donde concluye la Dirección, no donde alega el opositor.

    Una resolución transcribe los argumentos de la oposición antes de
    analizarlos, y ahí aparecen frases idénticas a las de la conclusión —
    «se encuentra incurso en la causal … del artículo 136, literal h)» — pero
    dichas por el opositor, y a veces desmentidas después. Contarlas produce
    motivos que la resolución nunca declaró.

    La conclusión está siempre pegada al cierre del análisis. Medido sobre 50
    resoluciones reales: la frase más lejana que sí era de la Dirección estaba a
    2 511 caracteres de «En mérito de lo expuesto», y el alegato citado más
    cercano a 41 579. La ventana va en medio, con margen de sobra por los dos
    lados. No se recorta el final: la parte resolutiva puede repetir la causal.

    Si el documento no trae los marcadores, se devuelve entero: perder un motivo
    es peor que colar uno de más, porque el de más se ve al revisar la fila.
    """
    ancla = p.CIERRE_ANALISIS.search(texto) or p.RESUELVE.search(texto)
    if ancla is None:
        return texto
    return texto[max(0, ancla.start() - _VENTANA_CONCLUSION) :]


def _causales_de(texto: str) -> tuple[list[str], list[str]]:
    """(afirmadas, negadas) en orden de aparición, sin repetir."""
    afirmadas: list[str] = []
    negadas: list[str] = []
    for coincidencia in p.DECLARACION_CAUSAL.finditer(texto):
        codigos = p.codigos_de_referencia(coincidencia, "_mo")
        # '…en el literal b) del artículo 135 y el literal a) del artículo 136'
        encadenadas, _ = p.referencias_encadenadas(texto, coincidencia.end())
        codigos += [codigo for codigo in encadenadas if codigo not in codigos]
        destino = negadas if coincidencia.group("neg") else afirmadas
        destino.extend(codigo for codigo in codigos if codigo not in destino)
    return afirmadas, negadas


def extraer_motivos(texto: str) -> tuple[list[str], list[str]]:
    """Causales por las que se niega el registro.

    Aquí vive el riesgo principal del proyecto: una misma causal aparece
    afirmada en un párrafo y **negada** en otro. Solo cuentan las afirmadas, y
    solo las que declara la Dirección (ver `zona_de_conclusion`).
    """
    avisos: list[str] = []
    motivos, descartados = _causales_de(zona_de_conclusion(texto))

    if not motivos:
        # Red de seguridad: si acotar la zona dejó fuera todo, se reintenta con
        # el documento entero antes que devolver la fila vacía.
        completos, descartados_completos = _causales_de(texto)
        if completos:
            motivos, descartados = completos, descartados_completos
            avisos.append(
                "La causal no aparece cerca de la parte resolutiva; se tomó del "
                "cuerpo del documento. Conviene revisar esta fila a mano."
            )

    for codigo in descartados:
        if codigo not in motivos:
            avisos.append(
                f"La resolución dice expresamente que NO está comprendido en {codigo}: "
                "no se cuenta como motivo."
            )

    if not motivos:
        avisos.extend(_avisar_sin_motivos(texto))
    return motivos, avisos


def _avisar_sin_motivos(texto: str) -> list[str]:
    """Explica por qué no salió ningún motivo, en vez de callar."""
    if p.CONCEDE_REGISTRO.search(texto) and not p.NIEGA_REGISTRO.search(texto):
        return ["La resolución concede el registro: no hay motivo de negación."]

    analizadas: list[str] = []
    for coincidencia in p.ANALISIS_CAUSAL.finditer(texto):
        analizadas.extend(p.codigos_de_referencia(coincidencia, "_an"))

    if p.NIEGA_REGISTRO.search(texto):
        detalle = f" Se analizaron: {', '.join(dict.fromkeys(analizadas))}." if analizadas else ""
        return [
            "La resolución niega el registro pero no se pudo determinar la causal."
            + detalle
            + " Revisar a mano."
        ]
    return ["No se encontró ni negación ni concesión del registro. Revisar a mano."]


# --- Punto de entrada --------------------------------------------------------


def extraer(
    texto: str,
    apelacion: bool | None = None,
    objetivo: Sequence[str] = (CLASE_OBJETIVO,),
) -> ExtractedData:
    """Analiza la resolución completa. Nunca lanza excepción."""
    if not texto or not texto.strip():
        return ExtractedData(
            avisos=["El documento no tiene texto: no se pudo extraer nada."]
        )

    datos = ExtractedData(apelacion=apelacion)
    datos.naturaleza = extraer_naturaleza(texto)
    if datos.naturaleza is None:
        datos.avisos.append("No se pudo determinar la naturaleza de la marca.")

    datos.presenta_oposicion = hay_oposicion(texto, objetivo)

    opositores, avisos_opositores = extraer_opositores(texto, objetivo)
    datos.avisos.extend(avisos_opositores)
    datos.avisos.extend(asignar_fundadas(texto, opositores))

    if len(opositores) > _MAX_OPOSITORES_REPORTADOS:
        sobrantes = ", ".join(o.nombre for o in opositores[_MAX_OPOSITORES_REPORTADOS:])
        datos.avisos.append(
            f"Hay {len(opositores)} opositores; la salida solo tiene dos columnas. "
            f"Sin registrar: {sobrantes}."
        )
    datos.opositores = opositores

    if datos.presenta_oposicion and not opositores:
        datos.avisos.append(
            "El texto menciona una oposición pero no se pudo identificar al opositor."
        )

    motivos, avisos_motivos = extraer_motivos(texto)
    datos.motivos = motivos
    datos.avisos.extend(avisos_motivos)
    # Un mismo problema puede detectarse por varias vías; se informa una vez.
    datos.avisos = list(dict.fromkeys(datos.avisos))
    return datos
