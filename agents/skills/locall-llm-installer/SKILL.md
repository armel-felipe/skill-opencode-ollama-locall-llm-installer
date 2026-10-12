---
name: locall-llm-installer
description: >-
  Use when syncing, refreshing, or repairing local Ollama, LM Studio, or
  llama.cpp server model lists in OpenCode or pi-agent, including deployments on
  multiple LAN/Tailscale hosts or when models are missing from a picker.
---

# locall-llm-installer

Synchronize model IDs actually returned by the configured endpoints into
OpenCode and, when present, pi-agent. The script performs only read-only
discovery and local config writes; it never starts/stops servers, loads models,
or downloads models.

## Endpoints

| Provider ID | Host | URL queried |
|---|---|---|
| `mac-ollama` | host passed with `--mac-host`, Ollama `11434` | `http://HOST:11434/v1/models` |
| `mac-lmstudio` | host passed with `--mac-host`, LM Studio `1234` | `http://HOST:1234/v1/models` |
| `games-ollama` | host passed with `--games-host`, Ollama `11434` | `http://HOST:11434/v1/models` |
| `games-lmstudio` | host passed with `--games-host`, LM Studio `1234` | `http://HOST:1234/v1/models` |
| `llamacpp` | host passed with `--llamacpp-host`, llama.cpp `8080` | `http://HOST:8080/models` then `/v1/models` |

For each endpoint the script tries the llama.cpp router `GET /models` first
(lists every registered model, including ones not loaded in memory), then the
OpenAI-compatible `GET /v1/models`. llama.cpp endpoints also get a `GET /health`
probe. Model IDs are preserved exactly as reported; no context window or tool
support is inferred.

If an endpoint is unreachable, invalid, or has no usable chat models, skip it.
Do not overwrite its existing config and **do not start a server or load/pull a
model** to make it respond. If every endpoint is empty/unavailable, both config
files remain unchanged.

## Run

From the skill's root directory:

```bash
python3 scripts/sync_ollama_models.py
```

Pass a LAN IP, Tailscale IP, or hostname with `--mac-host`, `--games-host`,
and/or `--llamacpp-host`. Each host is probed on its service ports. Host values
are passed at run time and are not stored in skill files. If no host is
supplied, no endpoint is queried.

Example: a local-network address for Mac, a Tailscale address for Games, and a
remote llama.cpp server over Tailscale:

```bash
python3 scripts/sync_ollama_models.py \
  --mac-host 192.168.1.20 \
  --games-host 100.x.y.z \
  --llamacpp-host 100.a.b.c
```

It updates only endpoint providers that returned models in
`~/.config/opencode/opencode.json[c]` and in `~/.pi/agent/models.json` if that
file already exists. Existing per-model settings are preserved for IDs still
present; unrelated providers stay untouched. It supports JSONC comments and API
results shaped as OpenAI `data: [...]` or LM Studio `models: [...]`. Empty
`data: null` means zero models. Embedding IDs are excluded from chat model lists.

For custom URLs/ports, repeat `--endpoint NAME=URL`; this cannot be combined
with the host flags. If authentication is required, set `LOCAL_LLM_API_KEY` in
the process environment, not in the skill.

## After syncing

Refresh `/models` or restart OpenCode; restart pi-agent to reload its model
catalog. If a model is missing, check network/VPN access and whether its owner
already has that server/model available. Do not start anything automatically.

## Test

```bash
python3 -m unittest discover -s tests -v
```
