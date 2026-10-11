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

The script reads supported variables from `.env` in the current working
directory. Set `LOCAL_LLM_MAC_HOST` and/or `LOCAL_LLM_GAMES_HOST` there to your
private hostnames/IPs; already-exported shell values take precedence. Set
`LOCAL_LLM_ENV_FILE` to use another path. Without a configured host, no
endpoint is queried. Run `python3 scripts/sync_ollama_models.py` from the
canonical skill root in this repository or from the installed skill directory. It updates only
providers that returned models in OpenCode and, if present, pi-agent. Existing
settings for available model IDs are preserved, unrelated providers are not
modified, and embedding model IDs are excluded.

For custom targets, repeat `--endpoint NAME=URL`; any override list replaces the
default set. Set `LOCAL_LLM_API_KEY` in the environment if bearer auth is
required. Never store credentials in skill files.

Refresh OpenCode `/models` or restart OpenCode and pi-agent after syncing. The
script never starts services, loads/pulls models, or changes network settings.
