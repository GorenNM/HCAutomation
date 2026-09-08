#!/usr/bin/env python
"""Vuelve a extraer los expedientes cacheados en salida/soportes/ y mide.

Sirve para comprobar el efecto de un cambio en el parser SIN volver a bajar
nada de SIPI: solo alcanza a los expedientes cuya resolución ya está en disco.
No sustituye a una corrida completa, pero da el antes/contra-referencia sobre
un subconjunto real.

    .venv/bin/python scripts/remedir_cache.py [salida_vieja.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.parser.extractor import extraer  # noqa: E402
from app.parser.pdf_text import texto_de_pdf  # noqa: E402
from scripts.comparar_salida import (  # noqa: E402
    OUT_DEFAULT,
    REF_DEFAULT,
    leer_out,
    leer_ref,
    norm,
    norm_motivo,
    norm_si_no,
    pct,
)

SOPORTES = Path("salida/soportes")


def resolucion_de(carpeta: Path) -> Path | None:
    """TM128 manda sobre TM9: si hubo oposición, es la que la relata."""
    for sufijo in ("_TM128.pdf", "_TM9.pdf"):
        encontrados = sorted(carpeta.glob(f"*{sufijo}"))
        if encontrados:
            return encontrados[0]
    return None


def extraido_de(carpeta: Path) -> dict | None:
    ruta = resolucion_de(carpeta)
    if ruta is None:
        return None
    apelacion = bool(list(carpeta.glob("*_APELACION.pdf"))) or None
    d = extraer(texto_de_pdf(ruta), apelacion=apelacion)
    ops = d.opositores + [None, None]
    return dict(
        naturaleza=norm(d.naturaleza),
        oposicion="SI" if d.presenta_oposicion else "NO",
        op1=norm(ops[0].nombre if ops[0] else ""),
        op2=norm(ops[1].nombre if ops[1] else ""),
        art1={norm_motivo(a) for a in (ops[0].articulos if ops[0] else [])} - {""},
        art2={norm_motivo(a) for a in (ops[1].articulos if ops[1] else [])} - {""},
        fund1={norm_si_no(ops[0].fundada)} - {""} if ops[0] else set(),
        fund2={norm_si_no(ops[1].fundada)} - {""} if ops[1] else set(),
        motivos={norm_motivo(m) for m in d.motivos} - {""},
        avisos=d.avisos,
    )


CAMPOS = ["naturaleza", "oposicion", "op1", "op2", "motivos", "art1", "art2",
          "fund1", "fund2"]


def de_referencia(g: dict) -> dict:
    v = g["vals"]
    return dict(
        naturaleza=norm(v["naturaleza"]), oposicion=norm_si_no(v["oposicion"]),
        op1=norm(v["op1"]), op2=norm(v["op2"]),
        motivos=g["motivos"], art1=g["art1"], art2=g["art2"],
        fund1=g["fund1"], fund2=g["fund2"],
    )


def de_salida_vieja(g: dict) -> dict:
    v = g["vals"]
    return dict(
        naturaleza=norm(v["naturaleza"]),
        oposicion=norm_si_no(v["oposicion"]) or "NO",
        op1=norm(v["op1"]), op2=norm(v["op2"]),
        motivos=g["motivos"], art1=g["art1"], art2=g["art2"],
        fund1=g["fund1"], fund2=g["fund2"],
    )


def cuenta(expedientes, izquierda, derecha) -> dict[str, int]:
    """Coincidencias por campo entre dos diccionarios de expediente -> campos."""
    marcador = {c: 0 for c in CAMPOS}
    for e in expedientes:
        for c in CAMPOS:
            if izquierda[e][c] == derecha[e][c]:
                marcador[c] += 1
    return marcador


def main() -> int:
    vieja_path = sys.argv[1] if len(sys.argv) > 1 else OUT_DEFAULT
    ref, _ = leer_ref(REF_DEFAULT)
    vieja = leer_out(vieja_path)

    nuevo: dict[str, dict] = {}
    for carpeta in sorted(SOPORTES.iterdir()):
        if not carpeta.is_dir():
            continue
        datos = extraido_de(carpeta)
        if datos is not None:
            nuevo[carpeta.name] = datos

    comunes = sorted(set(nuevo) & set(ref) & set(vieja))
    print(f"Expedientes con resolución cacheada : {len(nuevo)}")
    print(f"…y presentes en referencia y salida vieja: {len(comunes)}\n")

    antes = {e: de_salida_vieja(vieja[e]) for e in comunes}
    despues = {e: nuevo[e] for e in comunes}
    referencia = {e: de_referencia(ref[e]) for e in comunes}

    m_antes = cuenta(comunes, antes, referencia)
    m_despues = cuenta(comunes, despues, referencia)
    n = len(comunes)

    print(f"COINCIDENCIA CONTRA LA REFERENCIA   (n={n})")
    print(f"{'Campo':<14}{'antes':>8}{'':>3}{'después':>9}{'':>3}{'delta':>7}")
    for c in CAMPOS:
        d = m_despues[c] - m_antes[c]
        flecha = "+" if d > 0 else ""
        print(f"{c:<14}{pct(m_antes[c], n):>8}{'':>3}{pct(m_despues[c], n):>9}"
              f"{'':>3}{flecha}{d:>6}")

    limpios_antes = sum(
        all(antes[e][c] == referencia[e][c] for c in CAMPOS) for e in comunes
    )
    limpios_despues = sum(
        all(despues[e][c] == referencia[e][c] for c in CAMPOS) for e in comunes
    )
    print(f"\nExpedientes que coinciden en TODO: {limpios_antes} -> "
          f"{limpios_despues}  ({pct(limpios_antes, n)} -> {pct(limpios_despues, n)})")

    print("\nCAMBIOS respecto de la salida vieja, expediente a expediente:")
    for e in comunes:
        difs = [c for c in CAMPOS if antes[e][c] != despues[e][c]]
        if not difs:
            continue
        mejora = sum(despues[e][c] == referencia[e][c] for c in difs)
        empeora = sum(antes[e][c] == referencia[e][c] for c in difs)
        signo = "MEJOR" if mejora > empeora else "PEOR " if empeora > mejora else "=    "
        print(f"  {signo} {e}")
        for c in difs:
            print(f"        {c:<11} ref={referencia[e][c]!r}")
            print(f"        {'':<11} antes={antes[e][c]!r} -> ahora={despues[e][c]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
