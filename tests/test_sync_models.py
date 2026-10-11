import importlib.util
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
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

    def test_opencode_provider_uses_v1_and_preserves_unrelated_provider(self):
        config = {"provider": {"unrelated": {"models": {"keep": {}}}}}
        sync_models.sync_opencode(config, "mac-ollama", "http://host:11434", [{"id": "llama"}])
        self.assertEqual(config["provider"]["mac-ollama"]["options"]["baseURL"], "http://host:11434/v1")
        self.assertEqual(list(config["provider"]["mac-ollama"]["models"]), ["llama"])
        self.assertIn("unrelated", config["provider"])

    def test_private_host_defaults_come_from_environment_not_repo_constants(self):
        with patch.dict(os.environ, {"LOCAL_LLM_MAC_HOST": "mac-host", "LOCAL_LLM_GAMES_HOST": "games-host"}):
            self.assertEqual(sync_models.default_endpoints(), {
                "mac-ollama": "http://mac-host:11434",
                "mac-lmstudio": "http://mac-host:1234",
                "games-ollama": "http://games-host:11434",
                "games-lmstudio": "http://games-host:1234",
            })

    def test_dotenv_loads_only_local_endpoint_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "# local-only\nLOCAL_LLM_MAC_HOST=mac-tailnet\nOTHER_SECRET=do-not-load\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                sync_models.load_env_file(env_path)
                self.assertEqual(os.environ["LOCAL_LLM_MAC_HOST"], "mac-tailnet")
                self.assertNotIn("OTHER_SECRET", os.environ)

    def test_existing_environment_values_override_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("LOCAL_LLM_MAC_HOST=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"LOCAL_LLM_MAC_HOST": "from-shell"}, clear=True):
                sync_models.load_env_file(env_path)
                self.assertEqual(os.environ["LOCAL_LLM_MAC_HOST"], "from-shell")


if __name__ == "__main__":
    unittest.main()
