"""
Puertos (interfaces abstractas).

El dominio declara los contratos; la infraestructura los implementa.
El dominio nunca importa código de infraestructura.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .venta_record import VentaRecord


class VentaRepository(ABC):
    """Puerto de salida: persistencia de registros de venta."""

    @abstractmethod
    def guardar(self, venta: VentaRecord) -> None:
        """Persiste un VentaRecord.  Lanza RuntimeError si falla."""
        ...


class MessageDecoder(ABC):
    """Puerto de entrada: decodifica un mensaje entrante en un dict crudo."""

    @abstractmethod
    def decode(self, raw_message: dict) -> dict:
        """
        Extrae y decodifica el payload del mensaje.
        Lanza ValueError si el formato es inesperado.
        """
        ...
