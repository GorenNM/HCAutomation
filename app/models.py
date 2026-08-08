"""Modelo de dominio. Sin lógica: solo datos y derivaciones triviales."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TipoDoc(str, Enum):
    """Tipos de documento del Histórico de Documentos del expediente.

    La clasificación se hace por el texto de la columna 'Documento', nunca por
    la posición en la tabla: el número de documentos varía entre 3 y 5.
    """

    TM9 = "TM9"  # Niega sin oposición
    TM128 = "TM128"  # Niega con oposición
    TM6 = "TM6"  # Resumen de la solicitud
    APELACION = "APELACION"
    OTRO = "OTRO"

    @property
    def es_resolucion(self) -> bool:
        """Documentos de los que se extrae información."""
        return self in (TipoDoc.TM9, TipoDoc.TM128)


@dataclass(frozen=True)
class SourceRow:
    """Una fila del Excel de entrada."""

    expediente: str
    case_url: str
    marca: str
    titular: str
    niza: str
    descripcion: str
    bajo_oposicion: str
    fila: int  # fila real del Excel, para poder señalarla en un error


@dataclass(frozen=True)
class DocumentLink:
    tipo: TipoDoc
    etiqueta: str  # texto crudo: 'TM128 - Niega con oposición'
    url: str
    resolucion_nr: str | None = None
    fecha: str | None = None


@dataclass
class Opositor:
    nombre: str
    articulos: list[str] = field(default_factory=list)
    fundada: str | None = None  # 'SI' | 'NO' | None


@dataclass
class ExtractedData:
    naturaleza: str | None = None
    presenta_oposicion: bool = False
    opositores: list[Opositor] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)
    apelacion: bool | None = None
    avisos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputRecord:
    """Una fila del Excel de salida = expediente x motivo de negación."""

    source: SourceRow
    extracted: ExtractedData
    motivo: str | None
    motivo_indice: int
    motivos_total: int
