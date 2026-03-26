"""
Adaptador de entrada HTTP: expone el caso de uso como endpoint Flask
para recibir mensajes push de Pub/Sub en Cloud Run.

Funciones de esta capa:
  - Parsear el request HTTP
  - Delegar al caso de uso
  - Traducir el resultado en respuesta HTTP
  - No contener lógica de negocio
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request

from ...application.procesar_venta_use_case import ProcesarVentaUseCase
from ..bigquery.bigquery_venta_repository import BigQueryVentaRepository
from ..pubsub.pubsub_message_decoder import PubSubMessageDecoder

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Factory de la aplicación Flask.
    Construye el grafo de dependencias (composition root) e inyecta
    los adaptadores en el caso de uso.
    """
    app = Flask(__name__)

    # ── Composition root ─────────────────────────────────────────────────
    project_id = os.environ["GCP_PROJECT_ID"]
    dataset_id = os.environ.get("BQ_DATASET", "ventas_ds")
    table_id   = os.environ.get("BQ_TABLE",   "ventas_procesadas")

    decoder    = PubSubMessageDecoder()
    repository = BigQueryVentaRepository(project_id, dataset_id, table_id)
    use_case   = ProcesarVentaUseCase(decoder, repository)

    # ── Rutas ─────────────────────────────────────────────────────────────

    @app.route("/pubsub", methods=["POST"])
    def pubsub_handler():
        envelope = request.get_json(silent=True)
        if not envelope:
            logger.warning("Request sin JSON body.")
            return jsonify({"error": "bad_request"}), 400

        result = use_case.ejecutar(envelope)

        if not result.exitoso:
            # 200 para mensajes inválidos → Pub/Sub no reintenta (ACK implícito)
            # 500 para errores de infraestructura → Pub/Sub reintentará (NACK)
            if result.mensaje_error and result.mensaje_error.startswith("persistence_error"):
                return jsonify({"error": result.mensaje_error}), 500
            return jsonify({"status": "skipped", "detail": result.mensaje_error}), 200

        return jsonify({"status": "ok", "info": result.orden_info}), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "ventas-subscriber"}), 200

    return app
