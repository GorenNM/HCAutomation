"""Pruebas del extractor: el catálogo de casos adversariales.

Los textos base son las resoluciones reales grabadas. Las variantes están
deformadas a propósito para reventar el análisis, no para que pase.

Regla del proyecto: si algo de aquí se pone en rojo, se arregla el extractor.
Nunca se relaja la aserción.
"""

from __future__ import annotations

import time

import pytest

from app.models import Opositor, TipoDoc
from app.parser.extractor import (
    asignar_fundadas,
    extraer,
    extraer_marca,
    extraer_motivos,
    zona_de_conclusion,
    extraer_naturaleza,
    extraer_opositores,
    hay_oposicion,
    limpiar_nombre,
)
from app.utils.text import normalizar
from tests.conftest import texto_grabado

# --- Los tres documentos reales ----------------------------------------------


def test_sd2022_0000017_sin_oposicion_un_motivo():
    datos = extraer(texto_grabado("SD2022-0000017_TM9"), apelacion=True)

    assert datos.naturaleza == "Nominativa"
    assert datos.presenta_oposicion is False
    assert datos.opositores == []
    assert datos.motivos == ["136a"]
    assert datos.apelacion is True
    assert datos.avisos == []


def test_sd2022_0001545_es_el_caso_de_la_negacion_lexica():
    """CASO 1 — el más importante de todo el proyecto.

    El texto dice que SÍ está comprendido en 136a y que NO lo está en 136b.
    Un regex sin la negación devolvería ['136a', '136b'] y el Excel final
    afirmaría lo contrario de lo que dice la resolución.
    """
    datos = extraer(texto_grabado("SD2022-0001545_TM128"))

    assert datos.motivos == ["136a"]
    assert "136b" not in datos.motivos
    assert any("NO está comprendido en 136b" in a for a in datos.avisos)


def test_sd2022_0001545_opositor_completo():
    datos = extraer(texto_grabado("SD2022-0001545_TM128"))

    assert datos.presenta_oposicion is True
    assert len(datos.opositores) == 1
    opositor = datos.opositores[0]
    # El nombre conserva el punto final de 'S.A.' y no lo parte la cabecera de
    # página que en el PDF cae justo en medio de este nombre.
    assert opositor.nombre == "Grupo Diagnostico S.A. Dimed S.A."
    assert opositor.articulos == ["136a", "136b"]
    assert opositor.fundada == "SI"


def test_sd2022_0097089_dos_motivos_y_dos_opositores():
    datos = extraer(texto_grabado("SD2022-0097089_TM128"))

    assert datos.motivos == ["136a", "136h"]
    assert [o.nombre for o in datos.opositores] == [
        "SOCIETE DES PRODUITS NESTLE SA",
        "KRAFT FOODS SCHWEIZ HOLDING GMBH",
    ]
    assert datos.opositores[0].articulos == ["136a", "136h"]
    assert datos.opositores[1].articulos == ["136a"]
    assert all(o.fundada == "SI" for o in datos.opositores)


def test_el_mismo_opositor_repetido_por_clase_no_se_duplica():
    """En 0097089 cada opositor aparece una vez por clase (6 declaraciones)."""
    datos = extraer(texto_grabado("SD2022-0097089_TM128"))
    assert len(datos.opositores) == 2


# --- Casos 2 y 3: la negación, llevada al límite -----------------------------


def test_caso_2_negacion_con_verbo_lejano():
    """'no se encuentra incurso en la causal relativa…' — hay 5 palabras de por
    medio entre el 'no' y el verbo. Es una forma real del expediente 0001545."""
    texto = normalizar(
        "esta Dirección considera que el signo solicitado no se encuentra incurso "
        "en la causal relativa de irregistrabilidad contemplada en el artículo 136 "
        "literal b) de la Decisión 486."
    )
    motivos, avisos = extraer_motivos(texto)

    assert motivos == []
    assert any("136b" in a for a in avisos)


def test_caso_3_doble_negacion_no_se_cuenta_como_motivo():
    """Ante una construcción ambigua, no adivinar: no contarla y avisar."""
    texto = normalizar(
        "no es cierto que no esté comprendido en la causal de irregistrabilidad "
        "establecida en el artículo 136 literal a) de la Decisión 486."
    )
    motivos, avisos = extraer_motivos(texto)

    assert motivos == []
    assert avisos, "una doble negación tiene que dejar rastro"


def test_la_misma_causal_afirmada_y_negada_gana_la_afirmacion():
    texto = normalizar(
        "el signo está comprendido en la causal de irregistrabilidad establecida "
        "en el artículo 136 literal a). Sin embargo, no está comprendido en la "
        "causal de irregistrabilidad establecida en el artículo 136 literal a) Ibidem."
    )
    motivos, _ = extraer_motivos(texto)
    assert motivos == ["136a"]


# --- Caso 4: texto sin tildes ------------------------------------------------


def test_caso_4_texto_sin_tildes_se_analiza_igual():
    """Algunos PDFs pierden los acentos al extraer el texto."""
    texto = normalizar(
        "Que por escrito presentado el dia 2 de enero de 2022, Pieter Heshusius "
        "solicito el registro de la Marca MALTAVITAN (Nominativa) para distinguir "
        "productos. En consecuencia, la marca esta comprendida en la causal de "
        "irregistrabilidad establecida en el articulo 136 literal a) de la Decision 486."
    )
    datos = extraer(texto)

    assert datos.naturaleza == "Nominativa"
    assert datos.motivos == ["136a"]


# --- Caso 5: palabras partidas por el salto de línea -------------------------


def test_caso_5_palabra_partida_por_guion_al_final_de_linea():
    crudo = (
        "la marca está comprendida en la causal de irregis-\ntrabilidad "
        "establecida en el artí-\nculo 136 literal a) de la Decisión."
    )
    motivos, _ = extraer_motivos(normalizar(crudo))
    assert motivos == ["136a"]


# --- Caso 6: más de dos opositores -------------------------------------------


def _oposicion(nombre: str, literal: str = "a") -> str:
    return (
        f"Que publicado en la Gaceta No. 955, {nombre}, presentó oposición con "
        f"fundamento en la causal de irregistrabilidad establecida en el literal "
        f"{literal}) del artículo 136 de la Decisión 486. "
    )


def test_caso_6_tres_opositores_se_avisan_los_sobrantes():
    texto = normalizar(
        _oposicion("ALFA S.A.")
        + _oposicion("BETA LTDA")
        + _oposicion("GAMMA GMBH")
        + "ARTÍCULO 5: Negar el registro de la Marca X."
    )
    datos = extraer(texto)

    assert len(datos.opositores) == 3
    aviso = next(a for a in datos.avisos if "3 opositores" in a)
    assert "GAMMA GMBH" in aviso
    assert "ALFA" not in aviso  # los dos primeros sí se registran


# --- Casos 7 y 8: cantidad de motivos ----------------------------------------


def test_caso_7_cinco_motivos_distintos():
    texto = normalizar(
        "el signo está comprendido en las causales de irregistrabilidad "
        "establecidas en el artículo 136 literales a), b), c), h) y d) de la "
        "Decisión 486."
    )
    motivos, _ = extraer_motivos(texto)
    assert motivos == ["136a", "136b", "136c", "136h", "136d"]


def test_caso_8_el_motivo_repetido_sale_una_sola_vez():
    frase = (
        "está comprendido en la causal de irregistrabilidad establecida en el "
        "artículo 136 literal a) de la Decisión 486. "
    )
    motivos, _ = extraer_motivos(normalizar(frase * 3))
    assert motivos == ["136a"]


# --- Caso 9: parcialmente fundada --------------------------------------------


def test_caso_9_parcialmente_fundada_cuenta_como_si_y_avisa():
    texto = normalizar(
        _oposicion("ALFA S.A.")
        + "ARTÍCULO 1. Declarar parcialmente fundada la oposición interpuesta por "
        "ALFA S.A. ARTÍCULO 2. Negar el registro de la Marca X."
    )
    datos = extraer(texto)

    assert datos.opositores[0].fundada == "SI"
    assert any("PARCIALMENTE" in a for a in datos.avisos)


def test_infundada_se_registra_como_no():
    texto = normalizar(
        _oposicion("ALFA S.A.")
        + "ARTÍCULO 1. Declarar infundada la oposición interpuesta por ALFA S.A. "
        "ARTÍCULO 2. Negar el registro de la Marca X."
    )
    datos = extraer(texto)
    assert datos.opositores[0].fundada == "NO"


def test_si_no_se_declara_nada_la_fundada_queda_vacia_y_se_avisa():
    texto = normalizar(_oposicion("ALFA S.A.") + "ARTÍCULO 2. Negar el registro.")
    datos = extraer(texto)

    assert datos.opositores[0].fundada is None
    assert any("fue fundada" in a for a in datos.avisos)


# --- Caso 10: la resolución concede ------------------------------------------


def test_caso_10_resolucion_que_concede_no_inventa_motivos():
    texto = normalizar(
        "solicitó el registro de la Marca BONITA (Mixta) para distinguir productos. "
        "El signo no está comprendido en ninguna causal. "
        "ARTÍCULO PRIMERO: Conceder el registro de la Marca BONITA (Mixta)."
    )
    datos = extraer(texto)

    assert datos.motivos == []
    assert any("concede el registro" in a for a in datos.avisos)


def test_niega_sin_causal_detectable_pide_revision_manual():
    texto = normalizar(
        "solicitó el registro de la Marca X (Mixta). "
        "Análisis de la causal de irregistrabilidad contenida en el literal b) del "
        "artículo 136. ARTÍCULO PRIMERO: Negar el registro de la Marca X."
    )
    datos = extraer(texto)

    assert datos.motivos == []
    aviso = next(a for a in datos.avisos if "Revisar a mano" in a)
    # El análisis de una causal no equivale a aplicarla, pero sirve de pista.
    assert "136b" in aviso


# --- Caso 11: nombres difíciles ----------------------------------------------


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("la sociedad Grupo Diagnostico S.A. Dimed S.A.", "Grupo Diagnostico S.A. Dimed S.A."),
        ("Gaceta No. 976, SOCIETE DES PRODUITS NESTLE SA", "SOCIETE DES PRODUITS NESTLE SA"),
        # Sufijo societario tras coma: es parte del nombre, no otro opositor.
        ("No. 955, JHO INTELLECTUAL PROPERTY HOLDINGS, LLC.", "JHO INTELLECTUAL PROPERTY HOLDINGS, LLC."),
        ("del 8 de marzo, 4LIFE TRADEMARKS, LLC.", "4LIFE TRADEMARKS, LLC."),
        ("955, SUEROS Y BEBIDAS REHIDRATANTES, S.A. DE C.V.", "SUEROS Y BEBIDAS REHIDRATANTES, S.A. DE C.V."),
        ("el señor JUAN PÉREZ & HIJOS", "JUAN PÉREZ & HIJOS"),
        ("las sociedades ALFA S.A.S", "ALFA S.A.S"),
    ],
)
def test_caso_11_limpieza_de_nombres(crudo, esperado):
    assert limpiar_nombre(crudo) == esperado


def test_caso_11_nombre_con_coma_y_ampersand_en_una_oposicion_real():
    texto = normalizar(_oposicion("QUÍMICOS Y LUBRICANTES, S.A. & CIA"))
    opositores, _ = extraer_opositores(texto)
    assert opositores[0].nombre == "QUÍMICOS Y LUBRICANTES, S.A. & CIA"


# --- Caso 12: texto vacío ----------------------------------------------------


@pytest.mark.parametrize("texto", ["", "   ", "\n\n\t"])
def test_caso_12_texto_vacio_no_lanza_excepcion(texto):
    datos = extraer(texto)

    assert datos.motivos == []
    assert datos.opositores == []
    assert datos.naturaleza is None
    assert datos.avisos, "el vacío tiene que avisarse, no pasar en silencio"


def test_texto_sin_nada_reconocible_avisa_de_todo():
    datos = extraer("El gato subió al tejado y se quedó mirando la luna.")

    assert datos.motivos == []
    assert any("naturaleza" in a for a in datos.avisos)
    assert any("Revisar a mano" in a for a in datos.avisos)


# --- Caso 13: no puede haber ReDoS -------------------------------------------


@pytest.mark.parametrize(
    "basura",
    [
        "a" * 500_000,
        "artículo " * 60_000,
        "literal a) " * 40_000,
        "no está comprendido en la causal de irregistrabilidad " * 8_000,
        ("a) y " * 20_000) + "b)",
    ],
    # Etiquetas cortas a propósito: sin ellas pytest usa la entrada entera como
    # identificador y genera IDs de medio megabyte que revientan el reporte.
    ids=["letras", "articulos", "literales", "frase_negada", "lista_infinita"],
)
def test_caso_13_texto_enorme_no_dispara_backtracking(basura):
    """Varios patrones tienen cuantificadores anidados: son candidatos a ReDoS.

    El tope es duro a propósito. Si esto se pone en rojo hay que arreglar el
    regex, no subir el límite.
    """
    inicio = time.monotonic()
    extraer(basura)
    duracion = time.monotonic() - inicio

    assert duracion < 2.0, f"tardó {duracion:.2f} s con {len(basura)} caracteres"


def test_caso_13_cinco_megas_de_texto_real_repetido():
    base = texto_grabado("SD2022-0001545_TM128")
    enorme = base * (5_000_000 // len(base) + 1)

    inicio = time.monotonic()
    datos = extraer(enorme)
    duracion = time.monotonic() - inicio

    assert duracion < 10.0, f"tardó {duracion:.2f} s con {len(enorme)} caracteres"
    assert datos.motivos == ["136a"]


# --- Casos 14 y 15: referencias legales fuera de lo previsto -----------------


def test_caso_14_literal_inexistente_se_registra_tal_cual():
    """No se descarta en silencio: si la SIC escribe 'literal z)', se anota."""
    texto = normalizar(
        "está comprendido en la causal de irregistrabilidad establecida en el "
        "artículo 136 literal z) de la Decisión 486."
    )
    motivos, _ = extraer_motivos(texto)
    assert motivos == ["136z"]


@pytest.mark.parametrize("articulo", ["147", "154", "172", "135"])
def test_caso_15_articulo_sin_literal(articulo):
    texto = normalizar(
        "el signo está comprendido en la causal de irregistrabilidad establecida "
        f"en el artículo {articulo} de la Decisión 486."
    )
    motivos, _ = extraer_motivos(texto)
    assert motivos == [articulo]


def test_los_dos_ordenes_de_la_referencia_legal_dan_lo_mismo():
    directo = normalizar(
        "está comprendido en la causal de irregistrabilidad establecida en el "
        "artículo 136 literales a) y h)."
    )
    invertido = normalizar(
        "está comprendido en la causal de irregistrabilidad establecida en los "
        "literales a) y h) del artículo 136."
    )
    assert extraer_motivos(directo)[0] == extraer_motivos(invertido)[0] == [
        "136a",
        "136h",
    ]


# --- Naturaleza y oposición: piezas sueltas ----------------------------------


@pytest.mark.parametrize(
    "naturaleza", ["Nominativa", "Mixta", "Figurativa", "Tridimensional", "3D"]
)
def test_todas_las_naturalezas_conocidas(naturaleza):
    texto = normalizar(
        f"solicitó el registro de la Marca EJEMPLO ({naturaleza}) para distinguir."
    )
    assert extraer_naturaleza(texto) == naturaleza.capitalize().replace("3d", "3D")


def test_la_naturaleza_se_toma_de_la_marca_solicitada_no_de_las_citadas():
    """El documento cita marcas de terceros con su naturaleza entre paréntesis."""
    texto = normalizar(
        "solicitó el registro de la Marca IDIME (Mixta) para distinguir servicios. "
        "La opositora es titular de la marca DIME (Nominativa) y de DIME PLUS "
        "(Figurativa)."
    )
    assert extraer_naturaleza(texto) == "Mixta"
    assert extraer_marca(texto) == "IDIME"


def test_marca_con_parentesis_en_el_nombre():
    texto = normalizar("solicitó el registro de la Marca ACME (PLUS) (Mixta) para.")
    assert extraer_naturaleza(texto) == "Mixta"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("no se presentaron oposiciones por parte de terceros", False),
        ("no se presentaron oposicion es", False),
        ("la sociedad ALFA presentó oposición con fundamento", True),
        ("presentó oposición frente a las clases 30 y 32", True),
        ("el expediente no menciona nada del asunto", False),
    ],
)
def test_deteccion_de_oposicion(texto, esperado):
    assert hay_oposicion(normalizar(texto)) is esperado


def test_la_frase_explicita_gana_a_la_mencion_suelta():
    """Si dice que no hubo oposiciones, eso manda aunque la palabra aparezca."""
    texto = normalizar(
        "no se presentaron oposiciones por parte de terceros. El estudio de "
        "oposición se realiza de oficio."
    )
    assert hay_oposicion(texto) is False


# --- Robustez de asignar_fundadas --------------------------------------------


def test_fundada_se_asigna_al_unico_opositor_aunque_el_nombre_no_case():
    texto = normalizar(
        _oposicion("LABORATORIOS ALFA S.A.")
        + "ARTÍCULO 1. Declarar fundada la oposición interpuesta por la opositora."
    )
    datos = extraer(texto)
    assert datos.opositores[0].fundada == "SI"


def test_fundada_de_un_tercero_desconocido_avisa_en_vez_de_asignar_al_azar():
    texto = normalizar(
        _oposicion("ALFA S.A.")
        + _oposicion("BETA LTDA")
        + "ARTÍCULO 1. Declarar fundada la oposición interpuesta por OMEGA CORP, "
        "frente a la clase 5."
    )
    avisos = asignar_fundadas(texto, extraer_opositores(texto)[0])

    assert any("OMEGA CORP" in a for a in avisos)
    assert any("no coincide" in a for a in avisos)


def test_sin_opositores_no_se_intenta_asignar_nada():
    assert asignar_fundadas("Declarar fundada la oposición interpuesta por X.", []) == []


@pytest.mark.parametrize(
    "frase",
    [
        # La forma real de SD2022/0008040, encontrada en la corrida de 50
        # expedientes: la SIC escribe los plurales entre paréntesis y sin
        # admitirlos se perdía el único motivo del expediente.
        "el signo objeto de la solicitud está comprendido en la (s) causal (es) de "
        "irregistrabilidad establecida en el artículo 136 literal a) de la Decisión 486.",
        "está comprendido en la causal de irregistrabilidad establecida en el "
        "artículo 136 literal a) de la Decisión 486.",
        "está comprendido en las causales de irregistrabilidad establecidas en el "
        "artículo 136 literal a) de la Decisión 486.",
    ],
)
def test_los_plurales_entre_parentesis_no_pierden_el_motivo(frase):
    motivos, _avisos = extraer_motivos(normalizar(frase))
    assert motivos == ["136a"]


def test_el_parentesis_no_rompe_la_negacion():
    """Lo mismo pero negado: sigue sin contar como motivo."""
    frase = normalizar(
        "el signo NO está comprendido en la (s) causal (es) de irregistrabilidad "
        "establecida en el artículo 136 literal b) Ibidem."
    )
    motivos, avisos = extraer_motivos(frase)

    assert motivos == []
    assert any("136b" in aviso for aviso in avisos)


# --- Zona de conclusión: el alegato del opositor no es la decisión -----------

_CONCLUSION = (
    "En consecuencia, el signo objeto de la solicitud está comprendido en la causal "
    "de irregistrabilidad establecida en el artículo 136 literal a) de la Decisión 486. "
    "En mérito de lo expuesto esta Dirección, RESUELVE ARTÍCULO PRIMERO: Negar el "
    "registro de la marca."
)

# Lo que el opositor alegó, transcrito por la resolución muy antes de decidir.
# Forma real de SD2022/0007247, con la coma entre el artículo y el literal.
_ALEGATO = (
    "Conforme con los argumentos expuestos anteriormente, se concluye que el signo "
    "solicitado a registro se encuentra incurso en la causal de irregistrabilidad "
    "contemplada en el artículo 136, literal h) de la Decisión 486. "
)


def test_el_alegato_del_opositor_no_cuenta_como_motivo():
    """Lo dice el opositor 40 000 caracteres antes, no la Dirección."""
    texto = normalizar(_ALEGATO + ("relleno del análisis. " * 3_000) + _CONCLUSION)

    motivos, _avisos = extraer_motivos(texto)

    assert motivos == ["136a"]
    assert "136" not in motivos, "se coló la referencia del alegato"


def test_lo_que_concluye_la_direccion_sigue_contando_aunque_no_esté_pegado():
    """Hasta 2 511 caracteres de distancia se han visto en resoluciones reales."""
    texto = normalizar(
        "esta Dirección considera que el signo solicitado no se encuentra incurso "
        "en la causal relativa de irregistrabilidad contemplada en el artículo 136 "
        "literal b) de la Decisión 486. " + ("consideración final. " * 150) + _CONCLUSION
    )

    motivos, avisos = extraer_motivos(texto)

    assert motivos == ["136a"]
    assert any("136b" in aviso for aviso in avisos), "se perdió la causal negada"


def test_sin_marcador_de_cierre_se_analiza_el_documento_entero():
    texto = normalizar(("relleno. " * 3_000) + _CONCLUSION.split("En mérito")[0])

    assert zona_de_conclusion(texto) == texto
    assert extraer_motivos(texto)[0] == ["136a"]


def test_un_resuelve_en_minusculas_no_sirve_de_ancla():
    """'resuelve' es un verbo corriente; el encabezado va en mayúsculas."""
    texto = normalizar(
        "el signo está comprendido en la causal de irregistrabilidad establecida en "
        "el artículo 136 literal a) Ibidem. " + ("la Dirección resuelve dudas. " * 500)
    )

    assert zona_de_conclusion(texto) == texto
    assert extraer_motivos(texto)[0] == ["136a"]


def test_si_la_ventana_deja_fuera_todo_se_reintenta_y_se_avisa():
    """Perder un motivo es peor que colar uno de más: el de más se ve en la fila."""
    texto = normalizar(
        "el signo está comprendido en la causal de irregistrabilidad establecida en "
        "el artículo 135 literal b) de la Decisión 486. "
        + ("relleno sin causales. " * 3_000)
        + "En mérito de lo expuesto esta Dirección, RESUELVE ARTÍCULO PRIMERO: "
        "Negar el registro."
    )

    motivos, avisos = extraer_motivos(texto)

    assert motivos == ["135b"]
    assert any("revisar esta fila a mano" in aviso.lower() for aviso in avisos)


def test_la_parte_resolutiva_no_se_recorta():
    """Si el ARTÍCULO PRIMERO repite la causal, sigue contando."""
    texto = normalizar(
        ("relleno. " * 2_000)
        + "En mérito de lo expuesto esta Dirección, RESUELVE ARTÍCULO PRIMERO: Negar "
        "el registro por estar comprendido en la causal de irregistrabilidad "
        "establecida en el artículo 136 literal a) de la Decisión 486."
    )

    assert extraer_motivos(texto)[0] == ["136a"]

# --- Bugs de las corridas del usuario (tests/propios, 2026-08-07) ------------
# Cada texto es un extracto fiel del PDF real, verificado contra la descarga.


def test_sd2022_0005052_la_nota_al_pie_no_es_el_opositor():
    """La lista de productos de la marca del opositor entra como nota al pie
    ENTRE el nombre y «presentó oposición» (9 400 caracteres de por medio).
    El programa sacaba «minerales y antioxidantes en cuanto suplementos
    nutricionales y dietéticos.» como Opositor 1; el nombre real solo está
    limpio en la parte resolutiva."""
    texto = normalizar(
        "Que publicado en la Gaceta de Propiedad Industrial No. 951, MARYCOLOR "
        "S.A.S. c; preparaciones que contienen vitamina d; suplementos "
        "nutricionales; vitaminas, minerales y antioxidantes en cuanto "
        "suplementos nutricionales y dietéticos. presentó oposición en contra "
        "de la clase 3 con fundamento en las causales de irregistrabilidad "
        "establecidas en el literal b) del artículo 135 y el literal a) del "
        "artículo 136 de la Decisión 486 de la Comisión de la Comunidad Andina. "
        "Conclusión En consecuencia, el signo objeto de la solicitud está "
        "comprendido en la causal de irregistrabilidad establecida en el "
        "literal a) del artículo 136 de la Decisión 486 de la Comisión de la "
        "Comunidad Andina. En mérito de lo expuesto esta Dirección, RESUELVE "
        "ARTÍCULO 1. Declarar infundada la oposición interpuesta por MARYCOLOR "
        "S.A.S., en contra de la clase 3, por las razones expuestas en la parte "
        "motiva de la presente resolución. ARTÍCULO 2. Negar el registro de la "
        "Marca MARIGOLD HEALT & CARE (Mixta)."
    )
    datos = extraer(texto)

    assert [o.nombre for o in datos.opositores] == ["MARYCOLOR S.A.S."]
    assert datos.opositores[0].articulos == ["135b", "136a"]
    assert datos.opositores[0].fundada == "NO"
    assert datos.motivos == ["136a"]
    assert any("se tomó de la parte resolutiva" in a for a in datos.avisos)


def test_sd2022_0004420_fundamento_sin_la_formula_de_causales():
    """'con fundamento en el literal a) del artículo 136 y artículo 147' — sin
    «las causales de irregistrabilidad establecidas en», y con un segundo
    artículo encadenado que no lleva literal."""
    texto = normalizar(
        "Que publicado en la Gaceta de Propiedad Industrial No. 954, NORDIC "
        "PHARMACEUTICAL COMPANY S.A.C. presentó oposición con fundamento en el "
        "literal a) del artículo 136 y artículo 147 de la Decisión 486 de 2000."
    )
    opositores, avisos = extraer_opositores(texto)

    assert [o.nombre for o in opositores] == ["NORDIC PHARMACEUTICAL COMPANY S.A.C."]
    assert opositores[0].articulos == ["136a", "147"]
    assert avisos == []


@pytest.mark.parametrize(
    "formula",
    [
        "con fundamento en lo dispuesto en",  # MIGUEL DELIO, SD2022/0004110
        "con base en lo dispuesto en",  # GENIVERA, SD2022/0004110
    ],
)
def test_sd2022_0004110_fundamento_con_lo_dispuesto_en(formula):
    texto = normalizar(
        "Que publicado en la Gaceta de Propiedad Industrial No. 951 del 28 de "
        "enero de 2022, MIGUEL DELIO MONTES MONTES presentó oposición contra "
        f"la solicitud de registro {formula} el literal a) del artículo 136 de "
        "la Decisión 486 de 2000."
    )
    opositores, avisos = extraer_opositores(texto)

    assert [o.nombre for o in opositores] == ["MIGUEL DELIO MONTES MONTES"]
    assert opositores[0].articulos == ["136a"]
    assert avisos == []


def test_referencias_encadenadas_en_la_conclusion():
    """'…comprendido en … el literal b) del artículo 135 y el literal a) del
    artículo 136' tiene que dar los dos motivos, no solo el primero."""
    texto = normalizar(
        "el signo solicitado está comprendido en las causales de "
        "irregistrabilidad establecidas en el literal b) del artículo 135 y el "
        "literal a) del artículo 136 de la Decisión 486."
    )
    motivos, _ = extraer_motivos(texto)

    assert motivos == ["135b", "136a"]


def test_el_nombre_del_resuelve_corta_en_en_contra_de():
    """Sin el corte, el «nombre» declarado era 'MARYCOLOR S.A.S., en contra de
    la clase 3, por las razones expuestas…' y no casaba con nada."""
    opositores = [Opositor(nombre="MARYCOLOR S.A.S.")]
    avisos = asignar_fundadas(
        normalizar(
            "RESUELVE ARTÍCULO 1. Declarar infundada la oposición interpuesta "
            "por MARYCOLOR S.A.S., en contra de la clase 3, por las razones "
            "expuestas en la parte motiva de la presente resolución."
        ),
        opositores,
    )

    assert opositores[0].fundada == "NO"
    assert avisos == []
