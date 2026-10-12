# locall-llm-installer

Portable OpenCode/pi-agent skill that discovers available local LLMs through
OpenAI-compatible APIs and synchronizes their model catalogs.

## Default targets

| Machine | Service | Endpoint |
|---|---|---|
| Host via `--mac-host` | Ollama `11434` | `http://HOST:11434/v1/models` |
| Host via `--mac-host` | LM Studio `1234` | `http://HOST:1234/v1/models` |
| Host via `--games-host` | Ollama `11434` | `http://HOST:11434/v1/models` |
| Host via `--games-host` | LM Studio `1234` | `http://HOST:1234/v1/models` |
| Host via `--llamacpp-host` | llama.cpp `8080` | `http://HOST:8080/models` then `/v1/models` |

Unavailable endpoints and empty model lists are skipped. The script never
starts/stops a server, loads a model, or downloads one. If every endpoint is
empty or unavailable, it leaves the OpenCode and pi-agent config files
unchanged. Embedding-only models are omitted from chat model choices.

## llama.cpp over Tailscale

llama.cpp's server is OpenAI-compatible. Point the skill at the host running it
(default port `8080`):

```bash
python3 ~/.agents/skills/locall-llm-installer/scripts/sync_ollama_models.py \
  --llamacpp-host 100.a.b.c
```

The script writes `http://HOST:8080/v1` as the provider base URL, discovers
models via the router `GET /models` (every registered model, loaded or not) with
a `GET /v1/models` fallback, and probes `GET /health`. Model IDs are kept exactly
as reported; no context window or tool support is assumed.

## Install

```bash
npx skills add github:armel-felipe/skill-opencode-ollama-locall-llm-installer
```

The installer places the skill under `~/.agents/skills/locall-llm-installer/`.
The script uses `Path.home()` to locate user configs and has no third-party
Python dependencies.

## Run

```bash
python3 ~/.agents/skills/locall-llm-installer/scripts/sync_ollama_models.py \
  --mac-host 192.168.1.20 \
  --games-host 100.x.y.z \
  --llamacpp-host 100.a.b.c
```

Use a LAN IP, Tailscale IP, or hostname as each argument. Each host checks its
service ports (`11434` for Ollama, `1234` for LM Studio, `8080` for llama.cpp).
No address is stored in the skill or repository. For custom URLs/ports, use
repeated `--endpoint NAME=URL` instead of host flags.

The script updates discovered endpoint providers in `~/.config/opencode/` and,
if it exists, `~/.pi/agent/models.json`. Existing settings for models still
available are preserved; unrelated providers are not modified.

For servers requiring bearer authentication, set `LOCAL_LLM_API_KEY` in the
environment; do not put secrets in repository files.

After syncing, refresh OpenCode `/models` or restart OpenCode and pi-agent.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
