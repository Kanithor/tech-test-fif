"""
Adaptador de salida: implementa el puerto VentaRepository usando BigQuery.
"""

from __future__ import annotations

import logging

from google.cloud import bigquery

from ...domain.ports import VentaRepository
from ...domain.venta_record import VentaRecord

logger = logging.getLogger(__name__)


class BigQueryVentaRepository(VentaRepository):
    """
    Adaptador que persiste VentaRecord en una tabla BigQuery.
    Implementa el puerto de salida VentaRepository.
    """

    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self._table_ref = f"{project_id}.{dataset_id}.{table_id}"
        self._client = bigquery.Client()
        logger.info("BigQueryVentaRepository inicializado → %s", self._table_ref)

    def guardar(self, venta: VentaRecord) -> None:
        """
        Inserta la fila en BigQuery.
        Raises:
            RuntimeError: si BigQuery reporta errores de inserción.
        """
        fila = venta.to_bq_row()
        errors = self._client.insert_rows_json(self._table_ref, [fila])
        if errors:
            raise RuntimeError(f"BigQuery insert_rows_json errors: {errors}")
