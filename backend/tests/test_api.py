import json
import os
import subprocess
import sys
import unittest

import support  # noqa: F401  # isort: skip  # must run before app imports

from fastapi.testclient import TestClient

from app.main import app

HEALTH_URL = "/api/v1/health"


class ApiTests(unittest.TestCase):
    def test_health(self) -> None:
        with TestClient(app) as client:
            response = client.get(HEALTH_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "Plan2World API"})

    def test_all_api_routes_are_versioned(self) -> None:
        api_paths = set(app.openapi()["paths"])
        self.assertEqual({p for p in api_paths if not p.startswith("/api/v1/")}, set())
        self.assertEqual(api_paths, {"/api/v1/health", "/api/v1/segment", "/api/v1/generate-3d"})

    def test_old_unversioned_health_is_gone(self) -> None:
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code, 404)

    def test_docs_served_by_scalar(self) -> None:
        self.check_docs_mode("true")

    def test_docs_hidden_in_production(self) -> None:
        self.check_docs_mode("false")

    def check_docs_mode(self, dev: str) -> None:
        code = """
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    docs = client.get("/docs")
    print(json.dumps({
        "status": docs.status_code,
        "html": docs.text,
        "schema_status": client.get("/openapi.json").status_code,
        "redoc_status": client.get("/redoc").status_code,
        "health_status": client.get("/api/v1/health").status_code,
        "cache": docs.headers.get("cache-control"),
    }))
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "DEV": dev, "SEGMENTATION_ENABLED": "false"},
            check=True,
            capture_output=True,
            text=True,
        )
        response = json.loads(result.stdout)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["health_status"], 200)
        self.assertEqual(response["redoc_status"], 404)
        if dev == "true":
            self.assertEqual(response["schema_status"], 200)
            self.assertIn("@scalar/api-reference", response["html"])
        else:
            self.assertEqual(response["schema_status"], 404)
            self.assertNotIn("@scalar/api-reference", response["html"])
            self.assertNotIn("/openapi.json", response["html"])
            self.assertIn("We're working on it!", response["html"])
            self.assertIn("@keyframes build", response["html"])
            self.assertIn("prefers-reduced-motion", response["html"])
            self.assertEqual(response["cache"], "no-store")

    def test_allowed_origin(self) -> None:
        with TestClient(app) as client:
            for origin in ("http://localhost:5173", "http://localhost:8080"):
                with self.subTest(origin=origin):
                    response = client.get(HEALTH_URL, headers={"Origin": origin})
                    self.assertEqual(
                        response.headers["access-control-allow-origin"], origin
                    )

    def test_preflight(self) -> None:
        with TestClient(app) as client:
            response = client.options(
                HEALTH_URL,
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:5173"
        )

    def test_untrusted_origin(self) -> None:
        with TestClient(app) as client:
            response = client.get(
                HEALTH_URL, headers={"Origin": "https://untrusted.example"}
            )
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
