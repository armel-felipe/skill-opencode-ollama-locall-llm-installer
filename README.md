# locall-llm-installer

OpenCode skill that syncs locally installed Ollama, LM Studio, and llama.cpp
server models into the global OpenCode config (`~/.config/opencode/opencode.json`
or `opencode.jsonc`) and, when present, pi-agent's `~/.pi/agent/models.json`.

It updates **only** the matching `provider.<name>.models` sections — every other
key in your config is left untouched.

## What it does

- Runs `ollama list` and `ollama show` to capture every installed Ollama model.
- Queries LM Studio's `/api/v1/models` endpoint, falling back to `/v1/models`,
  to capture downloaded LLMs.
- Queries a llama.cpp server's router `/models` endpoint (falling back to
  `/v1/models`) to capture every registered model, including ones not loaded in
  memory, and probes `/health` for connectivity.
- Updates the `provider.ollama.models` map in the global opencode config.
- Updates the `provider.lmstudio.models` map using the OpenAI-compatible server
  at `http://localhost:1234/v1` by default.
- Updates the `provider.llamacpp.models` map using the OpenAI-compatible server
  at `http://<host>:18080/v1`.
- Updates the `providers.ollama.models` list in pi-agent when its config exists.
- Updates the `providers.lmstudio.models` list in pi-agent when its config exists.
- Updates the `providers.llamacpp.models` list in pi-agent when its config exists.
- Preserves any existing per-model settings (e.g. `limit`, `options`).
- Preserves the server's original model identifiers and never infers a context
  window or tool support.
- Removes invalid `limit` entries (missing `context` or `output`), which
  would otherwise prevent opencode from starting.
- Keeps the original file format (`.json` or `.jsonc`, comments included).
- Is idempotent — running it again never duplicates entries.

## Requirements

- [Ollama](https://ollama.com/) installed and running (`ollama serve`) when
  syncing Ollama.
- [LM Studio](https://lmstudio.ai/) installed with its local server running
  when syncing LM Studio (Developer tab or `lms server start`).
- A [llama.cpp](https://github.com/ggml-org/llama.cpp) server (`llama-server`)
  reachable on port `18080` when syncing llama.cpp.
- Python 3.10+.
- OpenCode with a global config at `~/.config/opencode/opencode.json` or
  `opencode.jsonc`.
- pi-agent is optional; if `~/.pi/agent/models.json` is absent, it is skipped.

## Usage

Run the bundled script from the skill directory, passing the host(s) to probe:

```bash
python scripts/sync_ollama_models.py --mac-host <host> --games-host <host> --llamacpp-host <host>
```

Each host is probed on Ollama `11434`, LM Studio `1234`, and llama.cpp `18080`.
Unavailable servers are skipped; a server that responds with no models is
skipped too. For nonstandard URLs/ports, pass repeated `--endpoint NAME=URL`
instead of host flags. Set `LOCAL_LLM_API_KEY` when a server requires a bearer
token.

### llama.cpp over Tailscale

```bash
python scripts/sync_ollama_models.py --llamacpp-host <IP_TAILSCALE>
# or explicitly:
python scripts/sync_ollama_models.py --endpoint llamacpp=http://<IP_TAILSCALE>:18080
```

The script writes `http://<IP_TAILSCALE>:18080/v1` as the provider base URL,
discovers models via the router `GET /models` (all registered models, loaded or
not) with a `GET /v1/models` fallback, and probes `GET /health`. Model IDs are
kept exactly as reported; no context window or tool support is assumed.

Or point to it directly. The skill lives in one of these places depending on
how it was installed:

- Global (skills.sh / `npx skills add`): `~/.agents/skills/locall-llm-installer/`
- Global (manual): `~/.config/opencode/skills/locall-llm-installer/`
- Project: `.opencode/skills/locall-llm-installer/`

Examples:

```bash
# macOS / Linux
python ~/.agents/skills/locall-llm-installer/scripts/sync_ollama_models.py
```

```powershell
# Windows (PowerShell)
python "$env:USERPROFILE\.agents\skills\locall-llm-installer\scripts\sync_ollama_models.py"
```

The script prints the config paths it updated and the list of synced models.
If all requested providers fail or return no models, it exits with an error and
leaves OpenCode untouched. Start LM Studio's server in Developer, or run
`lms server start`, before syncing it.

After syncing, restart opencode (or run `/models`) so the updated model list
is picked up.

## Installing the skill

### From this repo

```bash
npx skills add armel-felipe/locall-llm-installer --skill locall-llm-installer --global --yes --agent opencode
```

### From a local copy

```bash
npx skills add /path/to/locall-llm-installer --skill locall-llm-installer --global --yes --agent opencode
```

## How it works

1. Locates the global opencode config file (`opencode.json` first, then
   `opencode.jsonc`).
2. Runs `ollama list` and queries each endpoint's native model API — Ollama
   `/api/tags`, LM Studio `/api/v1/models`, llama.cpp router `/models` — falling
   back to the OpenAI-compatible `/v1/models`. llama.cpp endpoints also get a
   `GET /health` probe.
3. Parses the config, tolerating `//` and `/* */` comments in `.jsonc`.
4. Updates only the matching `provider.<name>.models` maps, preserving existing
   per-model settings and defaulting the display `name` to the model id.
5. Writes the config back, preserving the original file format.

## Cross-platform

The script resolves the config directory via `Path.home()`, so it works on
Windows, macOS, and Linux with no path changes.

## License

MIT
