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


class ModelsEndpointTests(unittest.TestCase):
    def serve(self, payload):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def serve_paths(self, routes):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = routes.get(self.path)
                if payload is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def test_openai_models_endpoint_reads_ids_from_data(self):
        base_url = self.serve({"data": [{"id": "llama3.2"}, {"id": "qwen2.5"}]})
        self.assertEqual(
            [m["id"] for m in sync_models.get_openai_compatible_models(base_url)],
            ["llama3.2", "qwen2.5"],
        )

    def test_null_data_means_no_available_models(self):
        base_url = self.serve({"object": "list", "data": None})
        self.assertEqual(sync_models.get_openai_compatible_models(base_url), [])

    def test_embedding_only_models_are_not_chat_models(self):
        base_url = self.serve({"data": [{"id": "text-embedding-nomic"}]})
        self.assertEqual(sync_models.get_openai_compatible_models(base_url), [])

    def test_lm_studio_key_field_is_supported(self):
        base_url = self.serve({"models": [{"key": "model-a"}]})
        self.assertEqual(
            [m["id"] for m in sync_models.get_openai_compatible_models(base_url)],
            ["model-a"],
        )

    def test_discover_models_prefers_router_models_endpoint(self):
        base_url = self.serve_paths({
            "/models": {"data": [{"id": "registered-a"}, {"id": "registered-b"}]},
            "/v1/models": {"object": "list", "data": []},
        })
        models, source = sync_models.discover_models(base_url)
        self.assertEqual([m["id"] for m in models], ["registered-a", "registered-b"])
        self.assertTrue(source.endswith("/models"))

    def test_discover_models_falls_back_to_v1_models(self):
        base_url = self.serve_paths({"/v1/models": {"data": [{"id": "only-v1"}]}})
        models, source = sync_models.discover_models(base_url)
        self.assertEqual([m["id"] for m in models], ["only-v1"])
        self.assertTrue(source.endswith("/v1/models"))

    def test_check_health_reads_status(self):
        base_url = self.serve_paths({"/health": {"status": "ok"}})
        self.assertEqual(sync_models.check_health(base_url), "ok")

    def test_check_health_returns_none_when_unreachable(self):
        base_url = self.serve_paths({})
        self.assertIsNone(sync_models.check_health(base_url))

    def test_looks_like_llamacpp_by_name_or_port(self):
        self.assertTrue(sync_models.looks_like_llamacpp("llamacpp", "http://host:9999"))
        self.assertTrue(sync_models.looks_like_llamacpp("remote", "http://host:8080"))
        self.assertFalse(sync_models.looks_like_llamacpp("mac-ollama", "http://host:11434"))

    def test_opencode_provider_uses_v1_and_preserves_unrelated_provider(self):
        config = {"provider": {"unrelated": {"models": {"keep": {}}}}}
        sync_models.sync_opencode(config, "mac-ollama", "http://host:11434", [{"id": "llama"}])
        self.assertEqual(config["provider"]["mac-ollama"]["options"]["baseURL"], "http://host:11434/v1")
        self.assertEqual(list(config["provider"]["mac-ollama"]["models"]), ["llama"])
        self.assertIn("unrelated", config["provider"])

    def test_host_arguments_expand_to_both_service_ports(self):
        self.assertEqual(sync_models.default_endpoints("192.0.2.10", "games.lan"), {
            "mac-ollama": "http://192.0.2.10:11434",
            "mac-lmstudio": "http://192.0.2.10:1234",
            "games-ollama": "http://games.lan:11434",
            "games-lmstudio": "http://games.lan:1234",
        })

    def test_llamacpp_host_expands_to_port_8080(self):
        self.assertEqual(
            sync_models.default_endpoints(llamacpp_host="100.x.y.z"),
            {"llamacpp": "http://100.x.y.z:8080"},
        )

    def test_no_host_arguments_produce_no_default_endpoints(self):
        self.assertEqual(sync_models.default_endpoints(), {})


if __name__ == "__main__":
    unittest.main()
