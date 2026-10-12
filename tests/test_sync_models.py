import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_ollama_models.py"
spec = importlib.util.spec_from_file_location("sync_models", SCRIPT)
sync_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_models)


class GlobalSyncModelsTests(unittest.TestCase):
    def serve(self, routes, expected_auth=None):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if expected_auth and self.headers.get("Authorization") != expected_auth:
                    self.send_response(401)
                    self.end_headers()
                    return
                status, payload = routes.get(self.path, (404, {"error": "not found"}))
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def test_router_models_include_unloaded_registered_models_and_keep_ids(self):
        base_url = self.serve({
            "/models": (200, {"data": [
                {"id": "org/model:Q4_K_M", "status": "loaded", "n_ctx": 32768},
                {"id": "second-model", "status": "unloaded"},
            ]}),
            "/v1/models": (200, {"data": []}),
        })
        models, source = sync_models.discover_models(base_url)
        self.assertEqual([row["id"] for row in models], ["org/model:Q4_K_M", "second-model"])
        self.assertEqual(models[0]["status"], "loaded")
        self.assertEqual(models[1]["status"], "unloaded")
        self.assertTrue(source.endswith("/models"))
        self.assertNotIn("context", models[0])

    def test_falls_back_to_openai_v1_models(self):
        base_url = self.serve({"/v1/models": (200, {"data": [{"id": "plain-server-model"}]})})
        models, source = sync_models.discover_models(base_url)
        self.assertEqual([row["id"] for row in models], ["plain-server-model"])
        self.assertTrue(source.endswith("/v1/models"))

    def test_skips_embeddings(self):
        base_url = self.serve({"/v1/models": (200, {"data": [
            {"id": "text-embedding-model"}, {"id": "chat-model"},
        ]})})
        models, _ = sync_models.discover_models(base_url)
        self.assertEqual([row["id"] for row in models], ["chat-model"])

    def test_bearer_auth_is_used_for_health_and_discovery(self):
        base_url = self.serve({
            "/health": (200, {"status": "ok"}),
            "/models": (200, {"data": [{"id": "private-model"}]}),
        }, expected_auth="Bearer test-secret")
        self.assertEqual(sync_models.check_health(base_url, "test-secret"), "ok")
        models, _ = sync_models.discover_models(base_url, "test-secret")
        self.assertEqual([row["id"] for row in models], ["private-model"])

    def test_health_returns_none_for_unreachable_or_unauthorized(self):
        base_url = self.serve({"/health": (200, {"status": "ok"})}, expected_auth="Bearer required")
        self.assertIsNone(sync_models.check_health(base_url))

    def test_default_endpoints_include_llamacpp(self):
        endpoints = sync_models.default_endpoints(
            mac_host="192.0.2.10", games_host="games.tailnet", llamacpp_host="100.64.0.8"
        )
        self.assertEqual(endpoints["mac-ollama"], "http://192.0.2.10:11434")
        self.assertEqual(endpoints["mac-lmstudio"], "http://192.0.2.10:1234")
        self.assertEqual(endpoints["games-ollama"], "http://games.tailnet:11434")
        self.assertEqual(endpoints["games-lmstudio"], "http://games.tailnet:1234")
        self.assertEqual(endpoints["llamacpp"], "http://100.64.0.8:8080")

    def test_host_expansion_includes_llamacpp_and_explicit_port(self):
        endpoints = sync_models._host_endpoints("100.64.0.8")
        self.assertEqual(endpoints["100.64.0.8-llamacpp"], "http://100.64.0.8:8080")
        self.assertEqual(sync_models._host_endpoints("server:8188"), {"server-8188": "http://server:8188"})

    def test_llamacpp_detection_does_not_mistake_ollama(self):
        self.assertTrue(sync_models._looks_like_llamacpp("llamacpp", "http://host:9999"))
        self.assertTrue(sync_models._looks_like_llamacpp("remote", "http://host:8080"))
        self.assertFalse(sync_models._looks_like_llamacpp("mac-ollama", "http://host:11434"))


if __name__ == "__main__":
    unittest.main()
