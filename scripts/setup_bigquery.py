#!/usr/bin/env python3
"""
Crea el dataset y tabla en BigQuery con el schema correspondiente a los datos transformados (campos mes separado + region_code).

python setup_bigquery.py --project tech-test-fif
python setup_bigquery.py --project tech-test-fif --dataset ventas_ds --table ventas_procesadas

"""

from __future__ import annotations

import argparse
import logging

from google.cloud import bigquery
from google.cloud.exceptions import Conflict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = [
    bigquery.SchemaField(
        "producto", "STRING", mode="REQUIRED",
        description="Nombre del producto",
    ),
    bigquery.SchemaField(
        "region", "STRING", mode="REQUIRED",
        description="Región de venta (texto original)",
    ),

    # Transformación 1: codificación de región
    bigquery.SchemaField(
        "region_code", "INTEGER", mode="REQUIRED",
        description="Label-encoding de la región (0=Región 1, 1=Región 2, …, -1=desconocida)",
    ),

    # Transformación 2: campo 'mes' separado en mes_nombre + mes_num + anno
    bigquery.SchemaField(
        "mes_nombre", "STRING", mode="REQUIRED",
        description="Nombre del mes en español (ej. 'Enero')",
    ),
    bigquery.SchemaField(
        "mes_num", "INTEGER", mode="REQUIRED",
        description="Número del mes 1-12",
    ),
    bigquery.SchemaField(
        "mes_og", "string", mode="REQUIRED",
        description="Nombre del mes y Año",
    ),
    bigquery.SchemaField(
        "anno", "INTEGER", mode="REQUIRED",
        description="Año de la venta (ej. 2022)",
    ),

    # Métrica
    bigquery.SchemaField(
        "ventas_mensuales", "FLOAT", mode="REQUIRED",
        description="Ventas del mes para ese producto/región",
    ),

    # Auditoría
    bigquery.SchemaField(
        "procesado_en", "TIMESTAMP", mode="NULLABLE",
        description="Timestamp UTC en que Cloud Run procesó el mensaje",
    ),
]


def crear_dataset(client: bigquery.Client, project: str, dataset_id: str) -> None:
    ref     = bigquery.DatasetReference(project, dataset_id)
    dataset = bigquery.Dataset(ref)
    dataset.location    = "US"
    dataset.description = "Dataset de ventas procesadas desde Pub/Sub (pipeline BI)"

    try:
        client.create_dataset(dataset)
        logger.info("✓ Dataset creado: %s.%s", project, dataset_id)
    except Conflict:
        logger.info("  Dataset ya existe: %s.%s", project, dataset_id)


def crear_tabla(
    client: bigquery.Client,
    project: str,
    dataset_id: str,
    table_id: str,
) -> None:
    table_ref = f"{project}.{dataset_id}.{table_id}"
    table     = bigquery.Table(table_ref, schema=SCHEMA)

    # Partición por anno
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.YEAR,
        field=None,
    )

    # Clustering: producto y región son los filtros más comunes en reportes BI
    table.clustering_fields = ["producto", "region", "anno"]

    table.description = (
        "Ventas mensuales por producto y región. "
        "Campo 'mes' original separado en mes_nombre/mes_num/anno. "
        "Región codificada con label-encoding en region_code."
    )

    try:
        client.create_table(table)
        logger.info("✓ Tabla creada: %s", table_ref)
    except Conflict:
        logger.info("  Tabla ya existe: %s", table_ref)


def crear_vista_looker(
    client: bigquery.Client,
    project: str,
    dataset_id: str,
) -> None:
    """
    Vista optimizada para Looker Studio con campos derivados.
    """
    view_ref = f"{project}.{dataset_id}.v_looker_ventas"
    sql = f"""
SELECT
  producto,
  region,
  region_code,
  mes_nombre,
  mes_num,
  mes_og,
  anno,
  ventas_mensuales,
  procesado_en,

  -- Campo de fecha para ejes de tiempo en Looker Studio
  DATE(anno, mes_num, 1)                        AS fecha_completa,

  -- Trimestre
  CONCAT(CAST(anno AS STRING), '-Q',
    CAST(CEIL(mes_num / 3) AS STRING))          AS trimestre,

  -- Año como string (útil para identificar por color en gráficos)
  CAST(anno AS STRING)                          AS anno_str

FROM `{project}.{dataset_id}.ventas_procesadas`
"""
    view = bigquery.Table(view_ref)
    view.view_query = sql
    view.description = "Vista consolidada para Looker Studio con campos derivados."

    try:
        client.create_table(view)
        logger.info("✓ Vista creada: %s", view_ref)
    except Conflict:
        # Actualizar la vista si ya existe
        client.update_table(view, ["view_query"])
        logger.info("  Vista actualizada: %s", view_ref)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea dataset, tabla y vista en BigQuery para el pipeline de ventas."
    )
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--dataset", default="ventas_ds",        help="Nombre del dataset")
    parser.add_argument("--table",   default="ventas_procesadas", help="Nombre de la tabla")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project)

    logger.info("Inicializando BigQuery en proyecto '%s'...", args.project)
    crear_dataset(client, args.project, args.dataset)
    crear_tabla(client, args.project, args.dataset, args.table)
    crear_vista_looker(client, args.project, args.dataset)

    logger.info("─" * 55)
    logger.info("Setup completo.")
    logger.info("  Tabla : %s.%s.%s", args.project, args.dataset, args.table)
    logger.info("  Vista : %s.%s.v_looker_ventas", args.project, args.dataset)


if __name__ == "__main__":
    main()
