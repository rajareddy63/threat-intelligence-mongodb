import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LOG_PATH = os.getenv("WEBHOOK_LOG_PATH", "/logs/webhook-alerts.jsonl")


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Webhook body must be a JSON object")
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(payload) + "\n")
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_error(400, str(exc))
            return
        self.send_response(202)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, _format: str, *args: object) -> None:
        print(_format % args, flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8099), WebhookHandler)
    print("Test webhook sink listening on 0.0.0.0:8099", flush=True)
    server.serve_forever()
