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


def hay_oposicion(texto: str) -> bool:
    """La frase explícita manda sobre la ausencia de menciones."""
    if p.SIN_OPOSICION.search(texto):
        return False
    return bool(p.HAY_OPOSICION.search(texto))


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


def extraer_opositores(texto: str) -> tuple[list[Opositor], list[str]]:
    """Opositores en orden de aparición, con los artículos que invocaron.

    Primero se localiza la frase barata «presentó oposición» y solo alrededor
    de cada aparición se aplica el patrón completo. Buscarlo directamente sobre
    todo el texto costaba 11 s en un documento de 5 MB: el prefijo que captura
    el nombre se probaba en cada posición del documento.
    """
    avisos: list[str] = []
    por_clave: dict[str, Opositor] = {}
    ilegibles = 0
    huerfanos: list[list[str]] = []  # artículos de oposiciones sin nombre legible

    for ancla in p.HAY_OPOSICION.finditer(texto):
        inicio = max(0, ancla.start() - _VENTANA_ANTES)
        ventana = texto[inicio : ancla.end() + _VENTANA_DESPUES]
        coincidencia = p.OPOSICION.search(ventana)

        if coincidencia is None:
            # Hay oposición pero sin la fórmula «con fundamento en…».
            nombre = limpiar_nombre(texto[inicio : ancla.start()])
            articulos: list[str] = []
        else:
            nombre = limpiar_nombre(coincidencia.group("antes"))
            articulos = p.codigos_de_referencia(coincidencia, "_op")
            articulos += [
                codigo
                for codigo in p.referencias_encadenadas(ventana, coincidencia.end())
                if codigo not in articulos
            ]

        if nombre and not _parece_nombre(nombre):
            nombre = ""  # cola de una lista de productos, no un nombre
        if not nombre:
            ilegibles += 1
            if articulos:
                huerfanos.append(articulos)
            continue
        if not articulos:
            avisos.append(
                f"No se pudo determinar en qué artículos fundó su oposición "
                f"«{nombre}»."
            )
        clave = clave_comparacion(nombre)
        if clave in por_clave:
            # El mismo opositor puede repetir la frase una vez por clase.
            existentes = por_clave[clave].articulos
            existentes.extend(a for a in articulos if a not in existentes)
        else:
            por_clave[clave] = Opositor(nombre=nombre, articulos=list(articulos))

    opositores = list(por_clave.values())
    rescatados = False
    if not opositores and ilegibles:
        opositores = _opositores_del_resuelve(texto)
        rescatados = bool(opositores)
        if rescatados:
            avisos.append(
                "El nombre del opositor no se pudo leer junto a «presentó "
                "oposición»; se tomó de la parte resolutiva."
            )
            if len(opositores) == 1 and len(huerfanos) == 1:
                # Una sola oposición con artículos y un solo opositor
                # declarado: los artículos son suyos sin ambigüedad.
                opositores[0].articulos = list(huerfanos[0])
            else:
                avisos.extend(
                    f"No se pudo determinar en qué artículos fundó su oposición "
                    f"«{opositor.nombre}»."
                    for opositor in opositores
                )
    if ilegibles and not rescatados:
        avisos.append("Se detectó una oposición sin nombre de opositor legible.")

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
        codigos += [
            codigo
            for codigo in p.referencias_encadenadas(texto, coincidencia.end())
            if codigo not in codigos
        ]
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


def extraer(texto: str, apelacion: bool | None = None) -> ExtractedData:
    """Analiza la resolución completa. Nunca lanza excepción."""
    if not texto or not texto.strip():
        return ExtractedData(
            avisos=["El documento no tiene texto: no se pudo extraer nada."]
        )

    datos = ExtractedData(apelacion=apelacion)
    datos.naturaleza = extraer_naturaleza(texto)
    if datos.naturaleza is None:
        datos.avisos.append("No se pudo determinar la naturaleza de la marca.")

    datos.presenta_oposicion = hay_oposicion(texto)

    opositores, avisos_opositores = extraer_opositores(texto)
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
