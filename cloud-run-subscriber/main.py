"""
Entrypoint del servicio Cloud Run.

Inicializa la app Flask vía la factory y la expone para gunicorn:
    gunicorn main:app
"""

import logging
import os

from src.infrastructure.http.flask_app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
