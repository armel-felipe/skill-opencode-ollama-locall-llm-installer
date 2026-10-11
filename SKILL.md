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

From the skill's root directory:

```bash
python3 scripts/sync_ollama_models.py
```

Pass a LAN IP, Tailscale IP, or hostname with `--mac-host` and/or `--games-host`.
The script probes both Ollama and LM Studio ports for each supplied host. Host
values are passed at run time and are not stored in skill files. If neither
host is supplied, no endpoint is queried.
It then
updates only endpoint providers that returned models in
`~/.config/opencode/opencode.json[c]` and in
`~/.pi/agent/models.json` if that file already exists. Existing per-model
settings are preserved for IDs still present; unrelated providers stay
untouched. It supports JSONC comments and API results shaped as OpenAI
`data: [...]` or LM Studio `models: [...]`. Empty `data: null` means zero
models. Embedding IDs are excluded from chat model lists.

Example: use a local-network address for Mac and a Tailscale address for Games:

```bash
python3 scripts/sync_ollama_models.py \
  --mac-host 192.168.1.20 \
  --games-host 100.x.y.z
```

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
