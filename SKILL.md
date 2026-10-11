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
| `mac-ollama` | Mac host, Ollama `11434` | `http://$LOCAL_LLM_MAC_HOST:11434/v1/models` |
| `mac-lmstudio` | Mac host, LM Studio `1234` | `http://$LOCAL_LLM_MAC_HOST:1234/v1/models` |
| `games-ollama` | Games host, Ollama `11434` | `http://$LOCAL_LLM_GAMES_HOST:11434/v1/models` |
| `games-lmstudio` | Games host, LM Studio `1234` | `http://$LOCAL_LLM_GAMES_HOST:1234/v1/models` |

If an endpoint is unreachable, invalid, or has no usable chat models, skip it.
Do not overwrite its existing config and **do not start a server or load/pull a
model** to make it respond. If every endpoint is empty/unavailable, both config
files remain unchanged.

## Run

From the skill's root directory:

```bash
python3 scripts/sync_ollama_models.py
```

Set `LOCAL_LLM_MAC_HOST` and/or `LOCAL_LLM_GAMES_HOST` to your private hostnames
or IPs to enable default targets. If neither is set, no endpoint is queried.
The script probes each configured host's Ollama and LM Studio ports, then
updates only endpoint providers that returned models in
`~/.config/opencode/opencode.json[c]` and in
`~/.pi/agent/models.json` if that file already exists. Existing per-model
settings are preserved for IDs still present; unrelated providers stay
untouched. It supports JSONC comments and API results shaped as OpenAI
`data: [...]` or LM Studio `models: [...]`. Empty `data: null` means zero
models. Embedding IDs are excluded from chat model lists.

To target a custom endpoint set without environment variables, repeat
`--endpoint NAME=URL`; passing any overrides replaces the defaults:

```bash
python3 scripts/sync_ollama_models.py \
  --endpoint mac-ollama=http://mac-host:11434 \
  --endpoint games-lmstudio=http://games-host:1234
```

If an endpoint needs bearer authentication, set `LOCAL_LLM_API_KEY` in the
environment. Never store credentials in the skill or repository.

## After syncing

Refresh `/models` or restart OpenCode; restart pi-agent to reload its model
catalog. If a model is missing, check network/VPN access and whether its owner
already has that server/model available. Do not start anything automatically.

## Test

```bash
python3 -m unittest discover -s tests -v
```
