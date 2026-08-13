"""Event replay engine."""
import json
import logging
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from qsip.config import Config
from qsip.replay import EventArchiver, ReplayEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReplayHandler(BaseHTTPRequestHandler):
    cfg = Config.from_env()
    try:
        archiver = EventArchiver(
            cfg.minio_endpoint,
            cfg.minio_access_key,
            cfg.minio_secret_key,
        )
        engine = ReplayEngine(cfg.kafka_brokers, archiver)
    except Exception:
        archiver = None
        engine = None

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/replay":
            self._respond(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        try:
            params = json.loads(body) if body else {}
        except Exception:
            self._respond(400, {"error": "bad json"})
            return

        source = params.get("source")
        event_type = params.get("event_type")
        date_from = datetime.fromisoformat(params["date_from"])
        date_to = datetime.fromisoformat(params["date_to"])
        if self.engine is None:
            self._respond(503, {"error": "replay engine not available (minio disabled)"})
            return
        topic = params.get("topic", "raw-events")
        count = self.engine.replay(source, event_type, date_from, date_to, topic)
        self._respond(200, {"replayed": count})

    def do_GET(self):
        self._respond(200, {"status": "replay engine ready"})

    def _respond(self, code: int, payload: dict):
        import json
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):
        logger.info(format, *args)


if __name__ == "__main__":
    import json
    port = int(os.getenv("PORT", "8087"))
    server = HTTPServer(("0.0.0.0", port), ReplayHandler)
    logger.info("replay server on port %s", port)
    server.serve_forever()
