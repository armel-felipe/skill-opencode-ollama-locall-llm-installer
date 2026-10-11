---
name: locall-llm-installer
description: >-
  Use when syncing, refreshing, or repairing local Ollama or LM Studio model
  lists in OpenCode or pi-agent, including deployments on multiple LAN/Tailscale
  hosts or when models are missing from a picker.
---

# locall-llm-installer

Synchronize model IDs actually returned by OpenAI-compatible `/v1/models`
endpoints into OpenCode and, when present, pi-agent. The script performs only
read-only discovery and local config writes; it never starts/stops servers,
loads models, or downloads models.

## Default endpoints

| Provider ID | Host | URL queried |
|---|---|---|
| `mac-ollama` | host passed with `--mac-host`, Ollama `11434` | `http://HOST:11434/v1/models` |
| `mac-lmstudio` | host passed with `--mac-host`, LM Studio `1234` | `http://HOST:1234/v1/models` |
| `games-ollama` | host passed with `--games-host`, Ollama `11434` | `http://HOST:11434/v1/models` |
| `games-lmstudio` | host passed with `--games-host`, LM Studio `1234` | `http://HOST:1234/v1/models` |

If an endpoint is unreachable, invalid, or has no usable chat models, skip it.
Do not overwrite its existing config and **do not start a server or load/pull a
model** to make it respond. If every endpoint is empty/unavailable, both config
files remain unchanged.

## Run

Pass a LAN IP, Tailscale IP, or hostname using `--mac-host` and/or
`--games-host`; each host is queried on ports `11434` and `1234`. Host values
are run-time arguments, not stored in skill files. With no hosts or custom
endpoints, nothing is queried. Run `python3 scripts/sync_ollama_models.py`
from the canonical skill root or installed skill directory. It updates only
providers with returned models in OpenCode and, if present, pi-agent. Existing
settings for available model IDs are preserved, unrelated providers are not
modified, and embedding IDs are excluded.

For custom URLs/ports, repeat `--endpoint NAME=URL`; do not combine that mode
with the host flags. Set `LOCAL_LLM_API_KEY` in the environment only if bearer
authentication is needed. Never store credentials in skill files.

Refresh OpenCode `/models` or restart OpenCode and pi-agent after syncing. The
script never starts services, loads/pulls models, or changes network settings.
