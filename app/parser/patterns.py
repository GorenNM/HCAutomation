"""Todas las expresiones regulares del proyecto, en un solo archivo.

Cuando la SIC cambie la redacción de sus resoluciones, este es el único módulo
que hay que tocar. Cada patrón lleva al lado el texto real contra el que se
verificó, sacado de los expedientes grabados en `tests/fixtures/`.

Todos se aplican sobre el texto ya normalizado por `pdf_text.texto_de_pdf`
(una sola línea, espacios simples, sin cabeceras de página) y con IGNORECASE.
"""

from __future__ import annotations

import re

# --- Piezas reutilizables ----------------------------------------------------

# 'a)'  ·  'a) y b)'  ·  'a), b) y h)'
_LISTA_LITERALES = r"[a-z]\)(?:\s*(?:,|y|e)\s*[a-z]\))*"

_CONECTOR = r"(?:l[oa]s?\s+|el\s+)?"

# 'la causal' · 'las causales' · y la forma que usa media SIC para no elegir:
#   'está comprendido en la (s) causal (es) de irregistrabilidad establecida en…'
# Sin admitir los '(s)' se pierde el motivo entero del expediente (visto en
# SD2022/0008040, donde la resolución sí niega por 136a).
_CAUSAL = r"(?:la|las)\s+(?:\(s\)\s+)?causal(?:es)?\s+(?:\(es\)\s+)?"

# La referencia legal aparece en dos órdenes distintos, y a veces sin literal:
#   'artículo 136 literal a)'            · 'artículo 136 literales a) y h)'
#   'literales a) y b) del artículo 136' · 'literal a) del artículo 136'
#   'artículo 147'                       (causales sin literal: 147, 154, 172)
def _referencia(sufijo: str) -> str:
    return (
        rf"(?:art[íi]culo\s+(?P<art_a{sufijo}>\d+)\s+"
        rf"literal(?:es)?\s+(?P<lits_a{sufijo}>{_LISTA_LITERALES})"
        rf"|literal(?:es)?\s+(?P<lits_b{sufijo}>{_LISTA_LITERALES})\s+"
        rf"del\s+art[íi]culo\s+(?P<art_b{sufijo}>\d+)"
        rf"|art[íi]culo\s+(?P<art_c{sufijo}>\d+))"
    )


def codigos_de_referencia(coincidencia: re.Match[str], sufijo: str = "") -> list[str]:
    """'136' + 'a) y h)' -> ['136a', '136h'];  '147' sin literal -> ['147']."""
    grupos = coincidencia.groupdict()
    articulo = (
        grupos.get(f"art_a{sufijo}")
        or grupos.get(f"art_b{sufijo}")
        or grupos.get(f"art_c{sufijo}")
    )
    if not articulo:
        return []
    literales = grupos.get(f"lits_a{sufijo}") or grupos.get(f"lits_b{sufijo}")
    if not literales:
        return [articulo]
    return [f"{articulo}{letra}" for letra in re.findall(r"([a-z])\)", literales)]


# --- Naturaleza y marca solicitada -------------------------------------------

# 'solicitó el registro de la Marca MALTAVITAN (Nominativa) para distinguir…'
# Aparece una sola vez, en el CONSIDERANDO. Las demás menciones con paréntesis
# son marcas de terceros citadas como antecedente, por eso se ancla al verbo.
SOLICITUD = re.compile(
    r"solicit[óo]\s+(?:el\s+)?registro\s+de\s+la\s+marca\s+"
    r"(?P<marca>.{1,80}?)\s*"
    r"\((?P<naturaleza>Nominativa|Mixta|Figurativa|Tridimensional|3D)\)",
    re.IGNORECASE,
)

# --- Oposiciones -------------------------------------------------------------

# 'no se presentaron oposiciones por parte de terceros'  (TM9)
SIN_OPOSICION = re.compile(
    r"no\s+se\s+presentaron\s+oposicion(?:es)?", re.IGNORECASE
)

# 'presentó oposición'  (TM128)
HAY_OPOSICION = re.compile(r"present[óo]\s+oposici[óo]n", re.IGNORECASE)

# Verificado contra las formas reales:
#   '…la sociedad Grupo Diagnostico S.A. Dimed S.A., presentó oposición con
#    fundamento en las causal de irregistrabilidad contenidas en los literales
#    a) y b) del artículo 136…'                          (el 'las causal' es del original)
#   '…NESTLE SA, presentó oposición frente a las clases 30 y 32, con fundamento
#    en las causales … establecidas en los literales a) y h) del artículo 136…'
#   '…KRAFT … presentó oposición frente a las clases 5, 30, 31 y 32, con
#    fundamento en la causal … establecida en el literal a) del artículo 136…'
#   '…NORDIC PHARMACEUTICAL COMPANY S.A.C. presentó oposición con fundamento
#    en el literal a) del artículo 136 y artículo 147 de la Decisión 486 de
#    2000.'                     (SD2022/0004420 — sin «las causales de irregistrabilidad»)
#   '…MIGUEL DELIO MONTES MONTES presentó oposición contra la solicitud de
#    registro con fundamento en lo dispuesto en el literal a) del artículo
#    136…'                                                        (SD2022/0004110)
#   '…GENIVERA DE JESÚS CARVAJAL AREIZA presentó oposición contra la solicitud
#    de registro con base en lo dispuesto en el literal a) del artículo 136…'
#                                                                 (SD2022/0004110)
# La fórmula «las causales de irregistrabilidad establecidas en» es opcional:
# media SIC la escribe y la otra media va directa a la referencia legal.
_FUNDAMENTO = (
    r"con\s+(?:fundamento|base)\s+en\s+"
    r"(?:lo\s+dispuesto\s+en\s+)?"
    r"(?:" + _CAUSAL + r"(?:relativas?\s+)?de\s+irregistrabilidad\s+"
    r"(?:establecid|contenid|contemplad)[oa]s?\s+en\s+)?"
)

OPOSICION = re.compile(
    r"(?P<antes>[^;:]{0,160}?)"
    r"present[óo]\s+oposici[óo]n"
    r"[^.;:]{0,200}?"
    + _FUNDAMENTO
    + _CONECTOR
    + _referencia("_op"),
    re.IGNORECASE,
)

# Una referencia legal puede continuar con otra de OTRO artículo, cosa que
# `_referencia` no captura porque sus grupos con nombre no pueden repetirse:
#   'el literal b) del artículo 135 y el literal a) del artículo 136'  (SD2022/0005052)
#   'el literal a) del artículo 136 y artículo 147'                    (SD2022/0004420)
# Se aplica con `.match()` exactamente donde terminó la referencia anterior,
# vía `referencias_encadenadas`.
OTRA_REFERENCIA = re.compile(
    r"(?:\s*,\s*(?:y\s+|e\s+)?|\s+(?:y|e)\s+)" + _CONECTOR + _referencia("_sig"),
    re.IGNORECASE,
)


def referencias_encadenadas(texto: str, pos: int) -> list[str]:
    """Códigos de las referencias que encadenan con una ya capturada en `pos`."""
    codigos: list[str] = []
    while coincidencia := OTRA_REFERENCIA.match(texto, pos):
        codigos.extend(
            codigo
            for codigo in codigos_de_referencia(coincidencia, "_sig")
            if codigo not in codigos
        )
        pos = coincidencia.end()
    return codigos

# 'ARTÍCULO 1. Declarar fundada la oposición interpuesta por parte de la
#  sociedad Grupo Diagnóstico S.A. Dimed S.A. ARTÍCULO 2. Negar…'
# 'Declarar fundada la oposición interpuesta por NESTLE SA, frente a la clase 30…'
# 'Declarar infundada la oposición interpuesta por MARYCOLOR S.A.S., en contra
#  de la clase 3, por las razones expuestas…'   (SD2022/0005052 — sin el corte
#  en 'en contra de', el "nombre" se tragaba media frase de la parte resolutiva)
# El corte NO puede ser un punto: los nombres traen 'S.A.' y quedarían partidos.
DECLARACION_OPOSICION = re.compile(
    r"declarar\s+(?P<sentido>parcialmente\s+fundada|fundada|infundada)\s+"
    r"la[s]?\s+oposici[óo]n(?:es)?\s+"
    r"(?:interpuesta[s]?\s+)?(?:por\s+)?(?:parte\s+de\s+)?"
    r"(?P<nombre>[^;:]{3,200}?)"
    r"(?=\s*(?:,?\s*frente\s+a|,?\s*en\s+contra\s+de|art[íi]culo\s|$))",
    re.IGNORECASE,
)

# --- Motivos de negación -----------------------------------------------------

# EL PATRÓN CRÍTICO DEL PROYECTO. Formas reales, positivas y negativas:
#   'está comprendida en la causal de irregistrabilidad establecida en el
#    artículo 136 literal a) de la Decisión 486'
#   'está comprendido en las causales de irregistrabilidad establecidas en el
#    artículo 136 literales a) y h)'
#   'NO está comprendido en la causal de irregistrabilidad establecida en el
#    artículo 136 literal b) Ibidem'
#   'NO se encuentra incurso en la causal relativa de irregistrabilidad
#    contemplada en el artículo 136 literal b)'
# El grupo 'neg' es obligatorio evaluarlo: sin él, los dos últimos ejemplos
# añadirían 136b como motivo de negación diciendo el texto lo contrario.
DECLARACION_CAUSAL = re.compile(
    r"(?P<neg>\bno\s+)?"
    # Las formas verbales varían: 'está', 'esté', 'se encuentra', 'resulta'.
    # Si alguna falta, el 'no' deja de ser adyacente y la causal negada se
    # cuenta como motivo — exactamente el error que este patrón evita.
    r"(?:se\s+)?(?:encuentr[ae]n?|hall[ae]n?|est[áaée]n?|result[ae]n?)?\s*"
    r"(?:comprendid|incurs)[oa]s?\s+en\s+"
    + _CAUSAL
    + r"(?:relativas?\s+)?de\s+irregistrabilidad\s+"
    r"(?:establecid|contenid|contemplad)[oa]s?\s+en\s+" + _CONECTOR
    + _referencia("_mo"),
    re.IGNORECASE,
)

# 'Análisis de la causal de irregistrabilidad contenida en el literal b) del
#  artículo 136.'  → indica causal ESTUDIADA, no necesariamente aplicada.
# Solo se usa para avisar cuando no se encontró ninguna conclusión.
ANALISIS_CAUSAL = re.compile(
    r"an[áa]lisis\s+de\s+la\s+causal\s+de\s+irregistrabilidad\s+"
    r"(?:contenid|establecid|contemplad)[oa]s?\s+en\s+" + _CONECTOR
    + _referencia("_an"),
    re.IGNORECASE,
)

# Cierre del análisis y comienzo de la parte resolutiva:
#   'En mérito de lo expuesto esta Dirección, RESUELVE'
# Medido sobre 50 resoluciones reales: aparece **exactamente una vez** en las 50.
# 'Conclusión', que sería el marcador natural, solo sale en 16 de las 50.
CIERRE_ANALISIS = re.compile(r"en\s+m[ée]rito\s+de\s+lo\s+expuesto", re.IGNORECASE)

# Plan B si falta lo anterior. Sin IGNORECASE a propósito: es un encabezado en
# mayúsculas, y en minúscula 'resuelve' es un verbo corriente del texto.
RESUELVE = re.compile(r"\bRESUELVE\b")

# 'ARTÍCULO PRIMERO: Negar el registro de la Marca MALTAVITAN…'
NIEGA_REGISTRO = re.compile(
    r"art[íi]culo\s+\S{1,10}\s*[.:]\s*negar\s+el\s+registro", re.IGNORECASE
)

# 'ARTÍCULO PRIMERO: Conceder el registro…' — si aparece esto y no hay motivos,
# es que la resolución no niega nada y no hay que inventar causales.
CONCEDE_REGISTRO = re.compile(
    r"art[íi]culo\s+\S{1,10}\s*[.:]\s*conceder\s+el\s+registro", re.IGNORECASE
)

# --- Limpieza de nombres de opositor -----------------------------------------

# 'la sociedad Grupo Diagnostico…' → 'Grupo Diagnostico…'
PREFIJO_PERSONA = re.compile(
    r"^(?:l[ao]s?\s+sociedad(?:es)?|el\s+se[ñn]or(?:a)?|la\s+se[ñn]ora|"
    r"l[ao]s?\s+empresas?|el|la|los|las)\s+",
    re.IGNORECASE,
)

# Sufijos societarios que van tras una coma y NO deben tomarse por otro nombre:
# 'JHO INTELLECTUAL PROPERTY HOLDINGS, LLC.' es un solo opositor.
SUFIJO_SOCIETARIO = re.compile(
    r"^(?:S\.?A\.?S?\.?|LTDA\.?|INC\.?|LLC\.?|GMBH|CORP\.?|CO\.?|S\.?L\.?|"
    r"LIMITED|COMPANY|DE\s+C\.?V\.?|N\.?V\.?|B\.?V\.?|PLC|AG|KG|SRL|SPA)\b",
    re.IGNORECASE,
)
