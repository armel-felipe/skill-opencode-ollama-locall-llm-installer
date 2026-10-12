#!/usr/bin/env python3
"""Discover available remote Ollama/LM Studio/llama.cpp models and sync both clients.

Only HTTP GET requests are made (`/models`, `/v1/models`, `/health`). This
script never starts, stops, or loads models/servers. Empty or unavailable
endpoints are skipped; existing config for those endpoints is preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "opencode"
PI_CONFIG = Path.home() / ".pi" / "agent" / "models.json"
LLAMA_CPP_PORT = 8080


def parse_host(value: str) -> str:
    host = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise argparse.ArgumentTypeError("host must be a LAN/Tailscale IP or hostname without scheme or port")
    return host


def default_endpoints(
    mac_host: str | None = None,
    games_host: str | None = None,
    llamacpp_host: str | None = None,
) -> dict[str, str]:
    """Build optional host defaults from private environment configuration."""
    endpoints = {}
    for label, host in (("mac", mac_host), ("games", games_host)):
        if host:
            endpoints[f"{label}-ollama"] = f"http://{host}:11434"
            endpoints[f"{label}-lmstudio"] = f"http://{host}:1234"
    if llamacpp_host:
        endpoints["llamacpp"] = f"http://{llamacpp_host}:{LLAMA_CPP_PORT}"
    return endpoints


def endpoint_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def endpoint_models_url(base_url: str) -> str:
    return endpoint_root(base_url) + "/v1/models"


def llama_cpp_models_url(base_url: str) -> str:
    """llama.cpp router mode lists every registered model at ``/models``."""
    return endpoint_root(base_url) + "/models"


def _read_models(url: str, api_key: str | None = None) -> list[dict]:
    """Fetch and normalize model IDs from an OpenAI-compatible/LM Studio payload."""
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=4) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        raw_models = payload
    elif isinstance(payload, dict):
        raw_models = payload.get("data", payload.get("models", []))
    else:
        raise ValueError("model endpoint returned a non-object JSON response")
    if raw_models is None:
        return []
    if not isinstance(raw_models, list):
        raise ValueError("model endpoint did not contain a model list")

    models = []
    seen = set()
    for raw in raw_models:
        if not isinstance(raw, dict) or raw.get("type") == "embedding":
            continue
        model_id = raw.get("id") or raw.get("key") or raw.get("model")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        if "embed" in model_id.lower() or "embedding" in model_id.lower():
            continue
        if model_id not in seen:
            seen.add(model_id)
            models.append({"id": model_id})
    return models


def get_openai_compatible_models(base_url: str, api_key: str | None = None) -> list[dict]:
    """Normalize model IDs from OpenAI-compatible/LM Studio JSON responses."""
    return _read_models(endpoint_models_url(base_url), api_key)


def discover_models(base_url: str, api_key: str | None = None) -> tuple[list[dict], str]:
    """Discover models via the llama.cpp router ``/models``, then ``/v1/models``.

    Returns ``(models, source_url_or_error)``. The router path is tried first
    because it lists every registered model, including ones not currently loaded
    in memory. Model IDs are preserved exactly as reported; no context window or
    tool support is inferred.
    """
    errors = []
    for url in (llama_cpp_models_url(base_url), endpoint_models_url(base_url)):
        try:
            models = _read_models(url, api_key)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            errors.append(f"{url} ({exc})")
            continue
        if models:
            return models, url
    return [], "; ".join(errors) if errors else "no models"


def check_health(base_url: str, api_key: str | None = None) -> str | None:
    """Best-effort ``GET /health`` probe (llama.cpp). Returns status or None."""
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(endpoint_root(base_url) + "/health", headers=headers)
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("status"), str):
        return payload["status"]
    return "ok"


def looks_like_llamacpp(name: str, url: str) -> bool:
    """True when an endpoint is (or is named like) a llama.cpp server.

    Matches the ``llamacpp``/``llama-cpp``/``llama.cpp`` name forms only, so an
    Ollama endpoint (``mac-ollama``) is not mistaken for llama.cpp.
    """
    lowered = name.lower()
    if "llamacpp" in lowered or "llama-cpp" in lowered or "llama.cpp" in lowered:
        return True
    try:
        return urllib.parse.urlsplit(url).port == LLAMA_CPP_PORT
    except ValueError:
        return False


def find_config() -> Path | None:
    for name in ("opencode.json", "opencode.jsonc"):
        path = CONFIG_DIR / name
        if path.exists():
            return path
    return None


def strip_jsonc_comments(text: str) -> str:
    out = []
    i = 0
    in_string = False
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            out.append(char)
            if char == "\\":
                out.append(nxt)
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
        elif char == '"':
            in_string = True
            out.append(char)
            i += 1
        elif char == "/" and nxt == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif char == "/" and nxt == "*":
            i += 2
            while i < len(text) and text[i : i + 2] != "*/":
                i += 1
            i += 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def provider_v1_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root if root.endswith("/v1") else root + "/v1"


def sync_opencode(config: dict, endpoint: str, base_url: str, models: list[dict]) -> None:
    provider = config.setdefault("provider", {}).setdefault(endpoint, {})
    provider.setdefault("name", endpoint.replace("-", " ").title())
    provider.setdefault("npm", "@ai-sdk/openai-compatible")
    provider.setdefault("options", {})["baseURL"] = provider_v1_url(base_url)
    existing = provider.get("models", {})
    if not isinstance(existing, dict):
        existing = {}
    updated = {}
    for model in models:
        previous = existing.get(model["id"])
        entry = dict(previous) if isinstance(previous, dict) else {}
        entry.setdefault("name", model["id"])
        updated[model["id"]] = entry
    provider["models"] = updated


def sync_pi_config(config_path: Path, endpoint: str, base_url: str, models: list[dict]) -> bool:
    if not config_path.exists():
        return False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: could not parse pi-agent config {config_path}: {exc}", file=sys.stderr)
        return False

    provider = config.setdefault("providers", {}).setdefault(endpoint, {})
    provider.setdefault("api", "openai-completions")
    provider.setdefault("apiKey", os.environ.get("LOCAL_LLM_API_KEY", "local"))
    provider["baseUrl"] = provider_v1_url(base_url)
    old_models = provider.get("models", [])
    old_by_id = {
        row.get("id"): row for row in old_models
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    } if isinstance(old_models, list) else {}
    provider["models"] = [
        old_by_id.get(model["id"], {
            "id": model["id"], "name": model["id"],
            "reasoning": False, "input": ["text"],
        })
        for model in models
    ]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def parse_endpoint(value: str) -> tuple[str, str]:
    name, separator, url = value.partition("=")
    if not separator or not name.strip() or not url.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError("endpoint must be NAME=http(s)://HOST:PORT")
    return name.strip(), url.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync available local LLMs to OpenCode and pi-agent.")
    parser.add_argument("--mac-host", type=parse_host, help="LAN/Tailscale IP or hostname for Ollama :11434 and LM Studio :1234")
    parser.add_argument("--games-host", type=parse_host, help="LAN/Tailscale IP or hostname for Ollama :11434 and LM Studio :1234")
    parser.add_argument("--llamacpp-host", type=parse_host, help=f"llama.cpp server host (OpenAI-compatible, port {LLAMA_CPP_PORT})")
    parser.add_argument("--endpoint", action="append", type=parse_endpoint, help="custom endpoint; repeat as NAME=http://host:port")
    args = parser.parse_args()
    if args.endpoint and (args.mac_host or args.games_host or args.llamacpp_host):
        parser.error("use --endpoint or --mac-host/--games-host/--llamacpp-host, not both")
    endpoints = dict(args.endpoint) if args.endpoint else default_endpoints(args.mac_host, args.games_host, args.llamacpp_host)
    if not endpoints:
        print("No endpoints configured. Pass --mac-host/--games-host/--llamacpp-host or --endpoint.", file=sys.stderr)
        return 1
    discovered = {}
    api_key = os.environ.get("LOCAL_LLM_API_KEY")
    for name, url in endpoints.items():
        if looks_like_llamacpp(name, url):
            print(f"health {name}: {check_health(url, api_key) or 'unreachable'}")
        models, source = discover_models(url, api_key)
        if not models:
            print(f"skip {name}: no models ({source})", file=sys.stderr)
            continue
        discovered[name] = (url, models)
        print(f"found {len(models)} model(s) on {name} via {source}: {', '.join(m['id'] for m in models)}")

    if not discovered:
        print("No endpoints returned models; no servers started and configs unchanged.", file=sys.stderr)
        return 1

    config_path = find_config()
    if config_path is None:
        print(f"error: no OpenCode config found in {CONFIG_DIR}", file=sys.stderr)
        return 1
    try:
        config = json.loads(strip_jsonc_comments(config_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not parse {config_path}: {exc}", file=sys.stderr)
        return 1

    for name, (url, models) in discovered.items():
        sync_opencode(config, name, url, models)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {config_path}")

    updated_pi = []
    for name, (url, models) in discovered.items():
        if sync_pi_config(PI_CONFIG, name, url, models):
            updated_pi.append(name)
    if updated_pi:
        print(f"updated {PI_CONFIG}: {', '.join(updated_pi)}")
    else:
        print(f"pi-agent config not found; skipped ({PI_CONFIG})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
