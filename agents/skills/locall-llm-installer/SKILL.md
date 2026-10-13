---
name: locall-llm-installer
description: >-
  Use when the user mentions updating, refreshing, syncing, or installing local
  Ollama, LM Studio, or llama.cpp server models in OpenCode or pi-agent, adding
  a newly pulled/downloaded model, removing a deleted one, or fixing a local
  model list.
---

# locall-llm-installer

Keeps OpenCode and optional pi-agent model lists synchronized with models
returned by the configured endpoints: Ollama `/api/tags`, LM Studio
`/api/v1/models`, llama.cpp router `/models`, and the OpenAI-compatible
`/v1/models` fallback.

## When to use

Trigger whenever the user wants to update, sync, or install local Ollama, LM
Studio, or llama.cpp server models into OpenCode or pi-agent, or when a local
model is missing from a model picker. The script only touches its named
endpoint providers and leaves unrelated providers/settings alone.

## How it works

The bundled script `scripts/sync_ollama_models.py`:

1. Accepts `--mac-host`, `--games-host`, and/or `--llamacpp-host` at invocation
   time. Each supplied LAN IP, Tailscale IP, or hostname is checked on Ollama
   `11434`, LM Studio `1234`, and llama.cpp `18080`; host values are not stored
   in the skill.
2. Queries each service's native model endpoint — Ollama `/api/tags`, LM Studio
   `/api/v1/models`, llama.cpp router `/models` — and falls back to the
   OpenAI-compatible `/v1/models`. Collects non-embedding IDs.
3. For llama.cpp endpoints, probes `GET /health` first and reports the status.
4. Skips unreachable endpoints and any endpoint with no models. **Never start
   a server, load a model, or pull a model to make an endpoint respond.**
5. Locates `~/.config/opencode/opencode.json` or `.jsonc`, parses JSONC, and
   updates only the provider sections for endpoints that returned models.
6. If `~/.pi/agent/models.json` exists, updates the matching endpoint providers
   there as well; the file is never created if absent. Existing settings for
   models that remain available are preserved.
7. If all endpoints fail or return no models, exits without writing either
   config.

## Running it

The script is cross-platform (Windows, macOS, Linux). It resolves the
config directory via `Path.home()`, so it works regardless of where the
skill was installed. Run it from the skill directory:

```bash
python scripts/sync_ollama_models.py --mac-host <LAN-or-Tailscale-host> --games-host <LAN-or-Tailscale-host> --llamacpp-host <LAN-or-Tailscale-host>
```

Use local-network or Tailscale hosts as the argument values. With no host or
custom `--endpoint`, the script queries nothing. For nonstandard URLs/ports,
pass repeated `--endpoint NAME=URL`; do not combine custom endpoints with host
flags. Optional bearer authentication uses `LOCAL_LLM_API_KEY` from the
environment.

If you are not inside the skill directory, point to the script relative to
the skill location. The skill lives in one of these places depending on how
it was installed:

- Global (skills.sh / `npx skills add`): `~/.agents/skills/locall-llm-installer/`
- Global (manual): `~/.config/opencode/skills/locall-llm-installer/`
- Project: `.opencode/skills/locall-llm-installer/`

So, for example, on macOS:

```bash
python ~/.agents/skills/locall-llm-installer/scripts/sync_ollama_models.py
```

and on Windows (PowerShell):

```powershell
python "$env:USERPROFILE\.agents\skills\locall-llm-installer\scripts\sync_ollama_models.py"
```

The script prints each endpoint's discovered IDs and updated config paths. An
empty `/v1/models` response (including `{"data": null}`) or an unavailable
endpoint is skipped without attempting to start anything. If all endpoints
are empty/unavailable, it leaves OpenCode and pi-agent configs untouched.

## llama.cpp server (remote, e.g. over Tailscale)

llama.cpp's server is OpenAI-compatible. Point the skill at the host running
it; the configured port is `18080`:

```bash
python scripts/sync_ollama_models.py --llamacpp-host <IP_TAILSCALE>
# or an explicit endpoint:
python scripts/sync_ollama_models.py --endpoint llamacpp=http://<IP_TAILSCALE>:18080
```

- Base URL written to config: `http://<IP_TAILSCALE>:18080/v1`
- Discovery: `GET /models` (router mode — lists every registered model,
  including ones not loaded in memory) then `GET /v1/models` (OpenAI-compatible).
- Connectivity: `GET /health` is probed and its status printed.
- Auth: `Bearer` token from `LOCAL_LLM_API_KEY`, only if the server requires it.

Model identifiers are preserved exactly as the server reports them. The script
does **not** infer a context window or tool support — it writes only the model
`id`/`name`, so pick the model in the client's picker after syncing.

## Installing on another machine (GitHub)

The skill is portable. To share it and install it on another machine (e.g. a
MacBook), push the `locall-llm-installer/` folder to a GitHub repo, then run:

```bash
npx skills add <owner>/<repo> --skill locall-llm-installer --global --yes --agent opencode
```

This copies the skill to `~/.agents/skills/locall-llm-installer/` on the new
machine. No path changes are needed — the script resolves everything from
`Path.home()` at runtime.

## After syncing

Tell the user to restart OpenCode (or run `/models`) and restart pi-agent to
reload the updated model lists. If an endpoint has no models, do not start it;
ask its owner to enable the server or load/download models only if they want
that endpoint to become available.
