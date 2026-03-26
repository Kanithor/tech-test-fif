"""
Caso de uso: recibir un mensaje, transformar los datos y persistirlos.
Depende únicamente de abstracciones del dominio (puertos).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..domain.ports import MessageDecoder, VentaRepository
from ..domain.venta_record import VentaRecord

logger = logging.getLogger(__name__)


@dataclass
class ProcesarVentaResult:
    exitoso: bool
    orden_info: str
    mensaje_error: str | None = None


class ProcesarVentaUseCase:
    """
    Orquesta el flujo completo:
      1. Decodificar mensaje
      2. Construir VentaRecord (aplica transformaciones del dominio)
      3. Persistir en repositorio
    """

    def __init__(
        self,
        decoder: MessageDecoder,
        repository: VentaRepository,
    ) -> None:
        self._decoder = decoder
        self._repository = repository

    def ejecutar(self, raw_message: dict) -> ProcesarVentaResult:
        # ── 1. Decodificar ───────────────────────────────────────────────
        try:
            datos = self._decoder.decode(raw_message)
        except ValueError as e:
            logger.warning("Mensaje con formato inválido: %s", e)
            return ProcesarVentaResult(
                exitoso=False,
                orden_info="desconocido",
                mensaje_error=f"decode_error: {e}",
            )

        info = f"{datos.get('producto','?')} / {datos.get('region','?')} / {datos.get('mes','?')}"

        # ── 2. Construir entidad (transforma datos) ──────────────────────
        try:
            venta = VentaRecord.from_raw(datos)
        except ValueError as e:
            logger.warning("Registro inválido omitido [%s]: %s", info, e)
            return ProcesarVentaResult(
                exitoso=False,
                orden_info=info,
                mensaje_error=f"validation_error: {e}",
            )

        # ── 3. Persistir ────────────────────────────────────────────────
        try:
            self._repository.guardar(venta)
        except RuntimeError as e:
            logger.error("Error persistiendo [%s]: %s", info, e)
            return ProcesarVentaResult(
                exitoso=False,
                orden_info=info,
                mensaje_error=f"persistence_error: {e}",
            )

        logger.info("✓ Procesado: %s | mes_num=%d anno=%d region_code=%d",
                    info, venta.mes_num, venta.anno, venta.region_code)

        return ProcesarVentaResult(exitoso=True, orden_info=info)
