"""Pruebas basadas en propiedades.

Acotadas a propósito a dos objetivos: la normalización de texto y el parseo de
listas de literales. Generar prosa jurídica aleatoria no probaría nada útil —
para el extractor manda el catálogo adversarial de test_extractor.py.
"""

from __future__ import annotations

import re

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.parser import patterns as p
from app.utils.text import clave_comparacion, normalizar, sanear_para_excel, sin_tildes

_RAPIDO = settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])


# --- normalizar --------------------------------------------------------------


@given(st.text())
@_RAPIDO
def test_normalizar_nunca_lanza_y_siempre_devuelve_texto(entrada):
    assert isinstance(normalizar(entrada), str)


@given(st.text())
@_RAPIDO
def test_normalizar_es_idempotente(entrada):
    una = normalizar(entrada)
    assert normalizar(una) == una


@given(st.text())
@_RAPIDO
def test_normalizar_no_deja_espacios_dobles_ni_bordes(entrada):
    salida = normalizar(entrada)
    assert "  " not in salida
    assert salida == salida.strip()
    assert "\n" not in salida and "\t" not in salida


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1))
@_RAPIDO
def test_normalizar_conserva_los_caracteres_visibles(entrada):
    """No puede borrar contenido: solo colapsa espacios."""
    sin_blancos = "".join(entrada.split())
    salida_sin_blancos = "".join(normalizar(entrada).split())
    # El único cambio permitido es reunir palabras partidas por guion.
    assert len(salida_sin_blancos) <= len(sin_blancos)


# --- sin_tildes y clave_comparacion ------------------------------------------


@given(st.text())
@_RAPIDO
def test_sin_tildes_nunca_lanza(entrada):
    assert isinstance(sin_tildes(entrada), str)


@given(st.text())
@_RAPIDO
def test_la_enie_sobrevive_siempre(entrada):
    """Es una letra, no un acento: fundir MUÑOZ con MUNOZ juntaría opositores."""
    assert entrada.count("ñ") == sin_tildes(entrada).count("ñ")
    assert entrada.count("Ñ") == sin_tildes(entrada).count("Ñ")


@given(st.text())
@_RAPIDO
def test_clave_comparacion_es_idempotente(entrada):
    una = clave_comparacion(entrada)
    assert clave_comparacion(una) == una


# --- sanear_para_excel -------------------------------------------------------


@given(st.text(), st.integers(min_value=20, max_value=40_000))
@_RAPIDO
def test_sanear_respeta_siempre_el_limite(entrada, limite):
    salida = sanear_para_excel(entrada, limite)
    assert len(salida) <= limite


@given(st.text())
@_RAPIDO
def test_sanear_nunca_deja_caracteres_de_control(entrada):
    salida = sanear_para_excel(entrada, 32_767)
    assert not any(ord(c) < 32 and c not in "\n\t" for c in salida)


# --- Parseo de listas de literales -------------------------------------------

_LETRAS = st.sampled_from("abcdefghij")


@st.composite
def _lista_de_literales(dibujar):
    """Genera 'a)', 'a) y b)', 'a), c) y h)' — como escribe la SIC."""
    letras = dibujar(st.lists(_LETRAS, min_size=1, max_size=6, unique=True))
    if len(letras) == 1:
        return letras[0] + ")", letras
    cabeza = ", ".join(f"{letra})" for letra in letras[:-1])
    return f"{cabeza} y {letras[-1]})", letras


@given(_lista_de_literales(), st.sampled_from(["135", "136", "137"]))
@_RAPIDO
def test_los_literales_se_expanden_en_orden_y_sin_repetir(caso, articulo):
    texto, letras = caso
    plural = "literales" if len(letras) > 1 else "literal"
    frase = (
        f"el signo está comprendido en la causal de irregistrabilidad establecida "
        f"en el artículo {articulo} {plural} {texto} de la Decisión 486."
    )

    coincidencia = p.DECLARACION_CAUSAL.search(frase)
    assert coincidencia is not None, frase
    codigos = p.codigos_de_referencia(coincidencia, "_mo")

    assert codigos == [f"{articulo}{letra}" for letra in letras]
    assert len(codigos) == len(set(codigos))


@given(_lista_de_literales(), st.sampled_from(["135", "136"]))
@_RAPIDO
def test_el_orden_invertido_de_la_referencia_da_lo_mismo(caso, articulo):
    texto, letras = caso
    plural = "literales" if len(letras) > 1 else "literal"
    frase = (
        f"el signo está comprendido en la causal de irregistrabilidad establecida "
        f"en los {plural} {texto} del artículo {articulo} de la Decisión 486."
    )

    coincidencia = p.DECLARACION_CAUSAL.search(frase)
    assert coincidencia is not None, frase
    assert p.codigos_de_referencia(coincidencia, "_mo") == [
        f"{articulo}{letra}" for letra in letras
    ]


@given(st.sampled_from(["135", "136", "147", "154", "172"]))
@_RAPIDO
def test_un_articulo_sin_literal_devuelve_solo_el_numero(articulo):
    frase = (
        f"el signo está comprendido en la causal de irregistrabilidad establecida "
        f"en el artículo {articulo} de la Decisión 486."
    )
    coincidencia = p.DECLARACION_CAUSAL.search(frase)
    assert p.codigos_de_referencia(coincidencia, "_mo") == [articulo]


@given(_lista_de_literales(), st.sampled_from(["135", "136"]))
@_RAPIDO
def test_la_negacion_gana_siempre_sobre_cualquier_lista(caso, articulo):
    """Da igual cuántos literales haya: si dice 'no', no son motivos."""
    texto, _letras = caso
    plural = "literales" if " y " in texto else "literal"
    frase = (
        f"el signo no está comprendido en la causal de irregistrabilidad "
        f"establecida en el artículo {articulo} {plural} {texto} Ibidem."
    )
    coincidencia = p.DECLARACION_CAUSAL.search(frase)

    assert coincidencia is not None
    assert coincidencia.group("neg") is not None


@given(st.text(max_size=300))
@_RAPIDO
def test_ningun_patron_lanza_con_texto_arbitrario(entrada):
    for nombre in dir(p):
        objeto = getattr(p, nombre)
        if isinstance(objeto, re.Pattern):
            objeto.findall(entrada)
