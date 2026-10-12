#!/usr/bin/env python3
"""Discover explicitly supplied Ollama/LM Studio hosts and sync both clients."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "opencode"
PI_CONFIG = Path.home() / ".pi" / "agent" / "models.json"
DEFAULT_LM_STUDIO_URL = "http://localhost:1234"
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
    endpoints = {}
    for label, host in (("mac", mac_host), ("games", games_host)):
        if host:
            endpoints[f"{label}-ollama"] = f"http://{host}:11434"
            endpoints[f"{label}-lmstudio"] = f"http://{host}:1234"
    if llamacpp_host:
        endpoints["llamacpp"] = f"http://{llamacpp_host}:{LLAMA_CPP_PORT}"
    return endpoints


def find_config() -> Path | None:
    for name in ("opencode.json", "opencode.jsonc"):
        p = CONFIG_DIR / name
        if p.exists():
            return p
    return None


def strip_jsonc_comments(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_string:
            out.append(c)
            if c == "\\":
                out.append(nxt)
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            i += 2
            while i < n and not (text[i] == "*" and text[i + 1 : i + 2] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def get_ollama_models() -> list[dict]:
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"could not run `ollama list`: {e}") from e
    models = []
    seen = set()
    for line in out.splitlines()[1:]:
        if line.strip():
            model = line.split()[0]
            if model not in seen:
                seen.add(model)
                metadata = {"id": model}
                context = get_model_context(model)
                if context is not None:
                    metadata["context"] = context
                models.append(metadata)
    return models


def get_model_context(model: str) -> int | None:
    """Return the model's maximum context length from `ollama show`.

    Parses the `context length` line, e.g. `context length      262144`.
    Returns None if it cannot be determined.
    """
    try:
        out = subprocess.run(
            ["ollama", "show", model], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    m = re.search(r"context\s+length\s+(\d+)", out)
    if not m:
        return None
    return int(m.group(1))


def fetch_json(url: str, api_key: str | None = None) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response was not a JSON object")
    return payload


def lm_studio_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def lm_studio_v1_url(base_url: str) -> str:
    return lm_studio_root(base_url) + "/v1"


def get_lm_studio_models(base_url: str, api_key: str | None) -> list[dict]:
    """Return downloaded LM Studio LLMs and best-effort metadata."""
    root = lm_studio_root(base_url)
    urls = [f"{root}/api/v1/models", f"{root}/v1/models"]
    last_error: Exception | None = None
    payload = None
    for url in urls:
        try:
            payload = fetch_json(url, api_key)
            break
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last_error = exc
    if payload is None:
        raise RuntimeError(f"could not query LM Studio at {root}: {last_error}")

    raw_models = payload.get("models", payload.get("data", []))
    if not isinstance(raw_models, list):
        raise ValueError("LM Studio model response did not contain a list")

    models = []
    seen = set()
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "embedding":
            continue
        model_id = raw.get("key") or raw.get("id") or raw.get("model")
        if not isinstance(model_id, str) or not model_id or model_id in seen:
            continue
        seen.add(model_id)
        model = {"id": model_id}
        for field in ("max_context_length", "context_length", "max_context"):
            if isinstance(raw.get(field), int) and raw[field] > 0:
                model["context"] = raw[field]
                break
        capabilities = raw.get("capabilities")
        if isinstance(capabilities, dict):
            model["vision"] = bool(
                capabilities.get("vision")
                or capabilities.get("image_input")
            )
            model["reasoning"] = bool(capabilities.get("reasoning"))
        models.append(model)
    return models


def sync_pi_config(
    config_path: Path,
    provider_name: str,
    models: list[dict],
    base_url: str | None = None,
    api_key: str | None = None,
    override_url: bool = False,
) -> bool:
    """Sync one provider's models into pi-agent's optional models.json."""
    if not config_path.exists():
        return False

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: could not parse pi-agent config {config_path}: {e}", file=sys.stderr)
        return False

    providers = config.setdefault("providers", {})
    provider = providers.setdefault(provider_name, {})
    if provider_name == "lmstudio":
        provider.setdefault("api", "openai-completions")
        provider.setdefault("apiKey", api_key or "lm-studio")
        if override_url and base_url:
            provider["baseUrl"] = lm_studio_v1_url(base_url)
        else:
            provider.setdefault(
                "baseUrl", lm_studio_v1_url(base_url or DEFAULT_LM_STUDIO_URL)
            )
    existing = provider.get("models", [])
    if not isinstance(existing, list):
        existing = []
    existing_by_id = {
        item.get("id"): item
        for item in existing
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    synced = []
    for model in models:
        model_id = model["id"]
        entry = existing_by_id.get(model_id)
        if not isinstance(entry, dict):
            entry = {
                "id": model_id,
                "name": model_id,
                "reasoning": False,
                "input": ["text"],
            }
        if model.get("vision") and "image" not in entry.get("input", []):
            entry["input"] = ["text", "image"]
        if model.get("reasoning"):
            entry["reasoning"] = True
        synced.append(entry)
    provider["models"] = synced
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return True


def update_opencode_provider(
    config: dict,
    provider_name: str,
    models: list[dict],
    base_url: str | None = None,
    override_url: bool = False,
) -> None:
    providers = config.setdefault("provider", {})
    provider = providers.setdefault(provider_name, {})
    if provider_name == "ollama":
        provider.setdefault("npm", "@ai-sdk/openai-compatible")
        provider.setdefault("name", "Ollama (local)")
        provider.setdefault("options", {"baseURL": "http://localhost:11434/v1"})
    else:
        provider.setdefault("npm", "@ai-sdk/openai-compatible")
        provider.setdefault("name", "LM Studio (local)")
        provider.setdefault("options", {})
        if override_url and base_url:
            provider["options"]["baseURL"] = lm_studio_v1_url(base_url)
        else:
            provider["options"].setdefault(
                "baseURL", lm_studio_v1_url(base_url or DEFAULT_LM_STUDIO_URL)
            )

    existing = provider.get("models", {})
    if not isinstance(existing, dict):
        existing = {}
    new_models = {}
    for model in models:
        model_id = model["id"]
        entry = existing.get(model_id, {})
        if not isinstance(entry, dict):
            entry = {}
        ctx = model.get("context")
        if isinstance(ctx, int) and ctx > 0:
            limit = entry.get("limit")
            if not isinstance(limit, dict):
                limit = {}
            limit["context"] = ctx
            if not isinstance(limit.get("output"), (int, float)) or limit["output"] <= 0:
                limit["output"] = max(1, ctx // 4)
            entry["limit"] = limit
        entry.setdefault("name", model_id)
        new_models[model_id] = entry
    provider["models"] = new_models
    # Never keep a whitelist: it would hide models the endpoint reports.
    provider.pop("whitelist", None)


def legacy_main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync local Ollama and LM Studio models into OpenCode and pi-agent."
    )
    parser.add_argument(
        "--source",
        choices=("ollama", "lmstudio", "both"),
        default="both",
        help="provider to sync (default: both; unavailable servers are skipped)",
    )
    parser.add_argument(
        "--lmstudio-url",
        default=None,
        help="LM Studio server root URL (default: LM_STUDIO_BASE_URL or http://localhost:1234)",
    )
    args = parser.parse_args()

    config_path = find_config()
    if config_path is None:
        print(
            "error: no opencode config found in "
            f"{CONFIG_DIR} (expected opencode.json or opencode.jsonc)",
            file=sys.stderr,
        )
        sys.exit(1)

    raw = config_path.read_text(encoding="utf-8")
    try:
        config = json.loads(strip_jsonc_comments(raw))
    except json.JSONDecodeError as e:
        print(f"error: could not parse {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    sources = ("ollama", "lmstudio") if args.source == "both" else (args.source,)
    synced_sources = []
    errors = []
    for source in sources:
        if source == "ollama":
            try:
                models = get_ollama_models()
                if not models:
                    raise RuntimeError("`ollama list` returned no models")
                update_opencode_provider(config, "ollama", models)
                if sync_pi_config(PI_CONFIG, "ollama", models):
                    print(f"updated {PI_CONFIG} (ollama)")
                synced_sources.append((source, models))
            except (RuntimeError, OSError) as exc:
                errors.append(f"ollama: {exc}")
        else:
            explicit_url = args.lmstudio_url or os.environ.get("LM_STUDIO_BASE_URL")
            base_url = explicit_url or DEFAULT_LM_STUDIO_URL
            api_key = os.environ.get("LM_STUDIO_API_KEY")
            try:
                models = get_lm_studio_models(base_url, api_key)
                if not models:
                    raise RuntimeError("LM Studio returned no LLM models")
                update_opencode_provider(
                    config, "lmstudio", models, base_url, override_url=bool(explicit_url)
                )
                if sync_pi_config(
                    PI_CONFIG,
                    "lmstudio",
                    models,
                    base_url,
                    api_key,
                    override_url=bool(explicit_url),
                ):
                    print(f"updated {PI_CONFIG} (lmstudio)")
                synced_sources.append((source, models))
            except (RuntimeError, OSError, ValueError) as exc:
                errors.append(f"lmstudio: {exc}")

    if not synced_sources:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    if config_path.suffix == ".jsonc":
        body = json.dumps(config, indent=2, ensure_ascii=False)
        body = body.replace("\n  \"$schema\"", "\n  \"$schema\"", 1)
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if '"$schema"' in line:
                lines.insert(i + 1, "  // Updated by locall-llm-installer")
                break
        body = "\n".join(lines)
    else:
        body = json.dumps(config, indent=2, ensure_ascii=False)

    config_path.write_text(body + "\n", encoding="utf-8")
    print(f"updated {config_path}")
    for source, models in synced_sources:
        print(f"synced {source} {len(models)} model(s): {', '.join(m['id'] for m in models)}")
    for error in errors:
        print(f"warning: {error}", file=sys.stderr)


# The endpoint-aware entrypoint intentionally replaces the earlier single-host
# sync behavior while retaining its JSON/JSONC parsing helpers above.
def _endpoint_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root[:-3] if root.endswith("/v1") else root


def _rows_from_payload(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("models", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return rows
    return []


def _normalize_model(row) -> dict | None:
    if not isinstance(row, dict) or row.get("type") == "embedding":
        return None
    model_id = row.get("key") or row.get("id") or row.get("model") or row.get("name")
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    model_id = model_id.strip()
    if "embed" in model_id.lower():
        return None
    entry = {"id": model_id}
    display = row.get("display_name")
    if isinstance(display, str) and display.strip() and display.strip() != model_id:
        entry["display_name"] = display.strip()
    mtype = row.get("type")
    if isinstance(mtype, str) and mtype:
        entry["type"] = mtype
    # llama.cpp router mode reports a load state per registered model; keep it
    # for display only. Never infer a context window or tool support from it.
    status = row.get("status") or row.get("state")
    if isinstance(status, str) and status.strip():
        entry["status"] = status.strip()
    return entry


def discover_models(base_url: str, api_key: str | None = None) -> tuple[list[dict], str]:
    """Query an endpoint the way its own API exposes models.

    Tries the native paths first (LM Studio ``/api/v1/models``, Ollama
    ``/api/tags``, llama.cpp router ``/models``) and falls back to the
    OpenAI-compatible ``/v1/models``. The llama.cpp router ``/models`` path is
    preferred over ``/v1/models`` because it lists every registered model,
    including ones not currently loaded in memory.
    Returns ``(models, source_url_or_error)``.
    """
    root = _endpoint_root(base_url)
    candidates = (
        f"{root}/api/v1/models",
        f"{root}/api/tags",
        f"{root}/models",
        f"{root}/v1/models",
    )
    errors = []
    for url in candidates:
        try:
            payload = fetch_json(url, api_key)
        except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            errors.append(f"{url} ({exc})")
            continue
        models = []
        seen = set()
        for row in _rows_from_payload(payload):
            entry = _normalize_model(row)
            if entry and entry["id"] not in seen:
                seen.add(entry["id"])
                models.append(entry)
        if models:
            return models, url
    return [], "; ".join(errors) if errors else "no models"


def check_health(base_url: str, api_key: str | None = None) -> str | None:
    """Best-effort ``GET /health`` probe (llama.cpp). Returns status or None."""
    root = _endpoint_root(base_url)
    try:
        payload = fetch_json(f"{root}/health", api_key)
    except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError):
        return None
    status = payload.get("status")
    return status if isinstance(status, str) and status.strip() else "ok"


def _looks_like_llamacpp(name: str, url: str) -> bool:
    """True when an endpoint is (or is named like) a llama.cpp server."""
    lowered = name.lower()
    if any(marker in lowered for marker in ("llamacpp", "llama-cpp", "llama.cpp")):
        return True
    try:
        return urllib.parse.urlsplit(url).port == LLAMA_CPP_PORT
    except ValueError:
        return False


def _host_endpoints(host: str) -> dict[str, str]:
    """Expand a bare host (or host:port) into named endpoints."""
    value = host.strip()
    if not value:
        return {}
    if "://" in value:
        value = value.split("://", 1)[1]
    if ":" in value:
        name, port = value.rsplit(":", 1)
        return {f"{name}-{port}": f"http://{value}"}
    return {
        f"{value}-ollama": f"http://{value}:11434",
        f"{value}-lmstudio": f"http://{value}:1234",
        f"{value}-llamacpp": f"http://{value}:{LLAMA_CPP_PORT}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover models on any Ollama/LM Studio/llama.cpp endpoint and sync them into OpenCode and pi-agent."
    )
    parser.add_argument(
        "--host", action="append", metavar="HOST[:PORT]",
        help="host or host:port to probe (Ollama :11434, LM Studio :1234, llama.cpp :8080); repeatable",
    )
    parser.add_argument(
        "--mac-host", type=parse_host,
        help="alias for --host, named mac-ollama/mac-lmstudio",
    )
    parser.add_argument(
        "--games-host", type=parse_host,
        help="alias for --host, named games-ollama/games-lmstudio",
    )
    parser.add_argument(
        "--llamacpp-host", type=parse_host,
        help=f"llama.cpp server host (OpenAI-compatible, port {LLAMA_CPP_PORT})",
    )
    parser.add_argument(
        "--endpoint", action="append", metavar="NAME=URL",
        help="explicit endpoint; repeat as NAME=http://host:port",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="only list the models each endpoint reports; write no config",
    )
    args = parser.parse_args()
    if args.endpoint and (args.host or args.mac_host or args.games_host or args.llamacpp_host):
        parser.error("use --endpoint or --host/--mac-host/--games-host/--llamacpp-host, not both")

    endpoints: dict[str, str] = {}
    if args.endpoint:
        for item in args.endpoint:
            name, separator, url = item.partition("=")
            if not separator or not name.strip() or not url.startswith(("http://", "https://")):
                parser.error("--endpoint must be NAME=http(s)://HOST:PORT")
            endpoints[name.strip()] = url.rstrip("/")
    else:
        endpoints.update(default_endpoints(args.mac_host, args.games_host, args.llamacpp_host))
        for host in args.host or []:
            endpoints.update(_host_endpoints(host))
    if not endpoints:
        print(
            "No endpoints configured. Pass --host, --mac-host/--games-host/--llamacpp-host or --endpoint.",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = os.environ.get("LOCAL_LLM_API_KEY")
    discovered: dict[str, tuple[str, list[dict]]] = {}
    for name, base_url in endpoints.items():
        if _looks_like_llamacpp(name, base_url):
            health = check_health(base_url, api_key)
            print(f"health {name}: {health or 'unreachable'}")
        models, source = discover_models(base_url, api_key)
        if not models:
            print(f"skip {name}: no models ({source})", file=sys.stderr)
            continue
        discovered[name] = (base_url, models)
        print(f"found {len(models)} model(s) on {name} via {source}:")
        for model in models:
            label = model.get("display_name")
            status = model.get("status")
            suffix = ""
            if label:
                suffix += f"  ({label})"
            if status:
                suffix += f"  [{status}]"
            print(f"  - {model['id']}{suffix}")

    if not discovered:
        print("No endpoints returned models; no servers started and configs unchanged.", file=sys.stderr)
        sys.exit(0 if args.list else 1)

    if args.list:
        print("\n--list: discovery only; no config written.")
        return

    config_path = find_config()
    if config_path is None:
        print(f"error: no opencode config found in {CONFIG_DIR}", file=sys.stderr)
        sys.exit(1)
    try:
        config = json.loads(strip_jsonc_comments(config_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not parse {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    providers = config.setdefault("provider", {})
    for name, (base_url, models) in discovered.items():
        provider = providers.setdefault(name, {})
        # A stale whitelist hides installed models from the picker; drop it so
        # every model the endpoint reports stays visible.
        provider.pop("whitelist", None)
        provider.setdefault("name", name.replace("-", " ").title())
        provider.setdefault("npm", "@ai-sdk/openai-compatible")
        options = provider.setdefault("options", {})
        root = base_url.rstrip("/")
        options["baseURL"] = root if root.endswith("/v1") else root + "/v1"
        existing = provider.get("models", {})
        if not isinstance(existing, dict):
            existing = {}
        updated = {}
        for model in models:
            prior = existing.get(model["id"])
            entry = dict(prior) if isinstance(prior, dict) else {}
            entry.setdefault("name", model["id"])
            updated[model["id"]] = entry
        provider["models"] = updated

    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {config_path}")

    if PI_CONFIG.exists():
        try:
            pi_config = json.loads(PI_CONFIG.read_text(encoding="utf-8"))
            pi_providers = pi_config.setdefault("providers", {})
            for name, (base_url, models) in discovered.items():
                provider = pi_providers.setdefault(name, {})
                provider.setdefault("api", "openai-completions")
                provider.setdefault("apiKey", os.environ.get("LOCAL_LLM_API_KEY", "local"))
                root = base_url.rstrip("/")
                provider["baseUrl"] = root if root.endswith("/v1") else root + "/v1"
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
            PI_CONFIG.write_text(json.dumps(pi_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"updated {PI_CONFIG}")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: could not update pi-agent config {PI_CONFIG}: {exc}", file=sys.stderr)
    else:
        print(f"pi-agent config not found; skipped ({PI_CONFIG})")


if __name__ == "__main__":
    main()
