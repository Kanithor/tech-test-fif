#!/usr/bin/env python3
"""
Simulador de envío de datos a Google Cloud Pub/Sub.
Lee el CSV fila a fila y publica cada registro como mensaje JSON.

Uso:
    python publisher.py --project tech-test-fif --topic ventas-topic
    python publisher.py --project tech-test-fif --topic ventas-topic --csv ../sample-data/ventas.csv --delay 0.3

Requisitos:
    pip install google-cloud-pubsub pandas
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd
from google.cloud import pubsub_v1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ventas-publisher")


# ─── Carga de datos ───────────────────────────────────────────────────────────

def cargar_ventas(csv_path: str) -> list[dict]:
    """
    Carga el CSV y devuelve lista de objetos con tipos primitivos
    seguros para serialización JSON.
    """
    df = pd.read_csv(csv_path)

    # Columnas esperadas
    columnas_requeridas = {"producto", "region", "mes", "ventas_mensuales"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"El CSV no contiene las columnas: {faltantes}")

    df["ventas_mensuales"] = df["ventas_mensuales"].astype(float)
    df["producto"]         = df["producto"].astype(str).str.strip()
    df["region"]           = df["region"].astype(str).str.strip()
    df["mes"]              = df["mes"].astype(str).str.strip()

    return df.to_dict(orient="records")


# ─── Publicación ──────────────────────────────────────────────────────────────

def publicar_mensaje(
    publisher: pubsub_v1.PublisherClient,
    topic_path: str,
    registro: dict,
    indice: int,
) -> str:
    """
    Agrega metadatos de trazabilidad y publica el mensaje en Pub/Sub.
    Retorna el message_id asignado por GCP.
    """
    registro["_publicado_en"] = datetime.now(tz=timezone.utc).isoformat()
    registro["_seq"]          = indice

    payload = json.dumps(registro, ensure_ascii=False).encode("utf-8")
    future  = publisher.publish(topic_path, data=payload)
    return future.result(timeout=30)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publica registros del CSV de ventas en un tópico Pub/Sub."
    )
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--topic",   required=True, help="Nombre del tópico Pub/Sub")
    parser.add_argument(
        "--csv",
        default="../sample-data/ventas.csv",
        help="Ruta al CSV de ventas",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Segundos de espera entre mensajes para simular streaming (default: 0.2)",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Máximo de registros a publicar; 0 = todos (default: 0)",
    )
    args = parser.parse_args()

    topic_path = f"projects/{args.project}/topics/{args.topic}"

    logger.info("Cargando CSV: %s", args.csv)
    registros = cargar_ventas(args.csv)
    total = len(registros)

    if args.limite > 0:
        registros = registros[: args.limite]
        logger.info("Limitando a %d registros (total en CSV: %d).", args.limite, total)
    else:
        logger.info("Total registros a publicar: %d", total)

    publisher = pubsub_v1.PublisherClient()
    logger.info("Publicando en tópico: %s", topic_path)
    logger.info("─" * 55)

    exitosos = 0
    fallidos  = 0

    for i, registro in enumerate(registros, start=1):
        try:
            msg_id = publicar_mensaje(publisher, topic_path, registro, i)
            logger.info(
                "[%4d/%d] ✓ %s | %s | %s — msg_id=%s",
                i, len(registros),
                registro["producto"],
                registro["region"],
                registro["mes"],
                msg_id,
            )
            exitosos += 1
        except Exception as e:
            logger.error(
                "[%4d/%d] ✗ Error: %s — %s",
                i, len(registros), registro.get("producto", "?"), e,
            )
            fallidos += 1

        if args.delay > 0 and i < len(registros):
            time.sleep(args.delay)

    logger.info("─" * 55)
    logger.info(
        "Publicación completa — Exitosos: %d | Fallidos: %d | Total: %d",
        exitosos, fallidos, exitosos + fallidos,
    )


if __name__ == "__main__":
    main()
