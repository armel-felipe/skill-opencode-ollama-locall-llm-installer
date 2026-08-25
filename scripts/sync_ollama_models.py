#!/usr/bin/env python3
"""Sync installed Ollama models into the global opencode config.

Reads the model list from `ollama list`, then updates only the
`provider.ollama.models` section of the opencode config file
(~/.config/opencode/opencode.json or opencode.jsonc, whichever exists).
All other keys in the config are left untouched.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "opencode"


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


def get_ollama_models() -> list[str]:
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"error: could not run `ollama list`: {e}", file=sys.stderr)
        sys.exit(1)
    models = []
    for line in out.splitlines()[1:]:
        if line.strip():
            models.append(line.split()[0])
    return models


def main() -> None:
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

    models = get_ollama_models()
    if not models:
        print("error: `ollama list` returned no models", file=sys.stderr)
        sys.exit(1)

    provider = config.setdefault("provider", {})
    ollama = provider.setdefault("ollama", {})
    ollama.setdefault("npm", "@ai-sdk/openai-compatible")
    ollama.setdefault("name", "Ollama (local)")
    ollama.setdefault("options", {"baseURL": "http://localhost:11434/v1"})

    existing = ollama.get("models", {})
    if not isinstance(existing, dict):
        existing = {}

    new_models = {}
    for m in models:
        entry = existing.get(m, {})
        if not isinstance(entry, dict):
            entry = {}
        limit = entry.get("limit")
        if isinstance(limit, dict):
            if not (
                isinstance(limit.get("context"), (int, float))
                and isinstance(limit.get("output"), (int, float))
            ):
                entry.pop("limit", None)
        entry.setdefault("name", m)
        new_models[m] = entry

    ollama["models"] = new_models

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
    print(f"synced {len(models)} model(s): {', '.join(models)}")


if __name__ == "__main__":
    main()
