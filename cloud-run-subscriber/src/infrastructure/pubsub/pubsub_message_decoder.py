"""
Adaptador de entrada: decodifica el envelope JSON que Pub/Sub push
envía a Cloud Run y extrae el payload de datos.
"""

from __future__ import annotations

import base64
import json
import logging

from ...domain.ports import MessageDecoder

logger = logging.getLogger(__name__)


class PubSubMessageDecoder(MessageDecoder):
    """
    Implementa MessageDecoder para el formato de push de Pub/Sub.

    Formato esperado (envelope):
    {
      "message": {
        "data": "<base64>",       ← payload JSON codificado
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "..."
    }
    """

    def decode(self, raw_message: dict) -> dict:
        if "message" not in raw_message:
            raise ValueError("El envelope no contiene la clave 'message'.")

        message = raw_message["message"]

        if "data" not in message:
            raise ValueError("El mensaje no contiene la clave 'data'.")

        try:
            decoded_bytes = base64.b64decode(message["data"])
            payload = json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Error decodificando base64/JSON: {e}") from e

        if not isinstance(payload, dict):
            raise ValueError("El payload decodificado no es un objeto JSON.")

        logger.debug(
            "Mensaje decodificado — messageId=%s publishTime=%s",
            message.get("messageId", "?"),
            message.get("publishTime", "?"),
        )

        return payload
