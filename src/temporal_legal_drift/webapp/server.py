"""Dependency-free local HTTP server for the research dashboard."""

from __future__ import annotations

import json
import mimetypes
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .service import DashboardService


MAX_REQUEST_BYTES = 60 * 1024 * 1024


def serve_dashboard(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    root = root.resolve()
    web_root = root / "web"
    if not (web_root / "index.html").is_file():
        raise ValueError(f"Dashboard assets are missing from {web_root}")
    service = DashboardService(root)

    class Handler(DashboardRequestHandler):
        project_root = root
        static_root = web_root
        dashboard_service = service

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Temporal Legal Drift dashboard: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class DashboardRequestHandler(BaseHTTPRequestHandler):
    project_root: Path
    static_root: Path
    dashboard_service: DashboardService

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        api_routes = {
            "/api/overview": self.dashboard_service.overview,
            "/api/gates": self.dashboard_service.gates,
            "/api/corpus": self.dashboard_service.corpus,
            "/api/demo": self.dashboard_service.demo,
            "/api/architecture": self.dashboard_service.architecture,
        }
        try:
            if path in api_routes:
                self._json(HTTPStatus.OK, api_routes[path]())
                return
            if path.startswith("/corpus/"):
                self._serve_file(self.project_root / "data/corpus/pdfs", path.removeprefix("/corpus/"))
                return
            asset = "index.html" if path in {"", "/"} else path.lstrip("/")
            self._serve_file(self.static_root, asset)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._request_json()
            if path == "/api/scenarios":
                self._json(HTTPStatus.CREATED, self.dashboard_service.submit_scenario(body))
            elif path == "/api/compare":
                self._json(HTTPStatus.OK, self.dashboard_service.compare_amendments(body))
            elif path == "/api/uploads":
                self._json(HTTPStatus.CREATED, self.dashboard_service.upload_evidence(body))
            elif path == "/api/actions/check-gates":
                self._json(HTTPStatus.OK, self.dashboard_service.gates())
            elif path == "/api/actions/run-tests":
                self._json(HTTPStatus.OK, self.dashboard_service.run_tests())
            elif path == "/api/actions/score-demo":
                self._json(HTTPStatus.OK, self.dashboard_service.score_demo())
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown API route"})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except (OSError, KeyError, subprocess.SubprocessError) as error:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _request_json(self) -> dict[str, object]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        length = int(raw_length)
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body exceeds the 60 MB limit")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def _serve_file(self, base: Path, relative: str) -> None:
        requested = (base / relative).resolve()
        try:
            requested.relative_to(base.resolve())
        except ValueError:
            self._json(HTTPStatus.FORBIDDEN, {"error": "Invalid file path"})
            return
        if not requested.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "File not found"})
            return
        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        payload = requested.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header(
            "Cache-Control",
            "no-store" if requested.suffix in {".html", ".css", ".js"} else "public, max-age=300",
        )
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: HTTPStatus, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)
