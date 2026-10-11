# locall-llm-installer

Portable OpenCode/pi-agent skill that discovers available local LLMs through
OpenAI-compatible `/v1/models` APIs and synchronizes their model catalogs.

## Default targets

| Machine | Service | Endpoint |
|---|---|---|
| Mac host (`LOCAL_LLM_MAC_HOST`) | Ollama `11434` | `http://$LOCAL_LLM_MAC_HOST:11434/v1/models` |
| Mac host (`LOCAL_LLM_MAC_HOST`) | LM Studio `1234` | `http://$LOCAL_LLM_MAC_HOST:1234/v1/models` |
| Games host (`LOCAL_LLM_GAMES_HOST`) | Ollama `11434` | `http://$LOCAL_LLM_GAMES_HOST:11434/v1/models` |
| Games host (`LOCAL_LLM_GAMES_HOST`) | LM Studio `1234` | `http://$LOCAL_LLM_GAMES_HOST:1234/v1/models` |

Unavailable endpoints and empty model lists are skipped. The script never
starts/stops a server, loads a model, or downloads one. If all four endpoints
are empty or unavailable, it leaves the OpenCode and pi-agent config files
unchanged. Embedding-only models are omitted from chat model choices.

## Install

```bash
npx skills add github:armel-felipe/skill-opencode-ollama-locall-llm-installer
```

The installer places the skill under `~/.agents/skills/locall-llm-installer/`.
The script uses `Path.home()` to locate user configs and has no third-party
Python dependencies.

## Run

```bash
python3 ~/.agents/skills/locall-llm-installer/scripts/sync_ollama_models.py
```

By default, the script reads `LOCAL_LLM_MAC_HOST`, `LOCAL_LLM_GAMES_HOST`,
and optionally `LOCAL_LLM_API_KEY` from `.env` in the current working
directory. Already-exported shell values override `.env`; set
`LOCAL_LLM_ENV_FILE` to read a different file. Example private `.env`:

```dotenv
LOCAL_LLM_MAC_HOST=your-mac-host-or-private-ip
LOCAL_LLM_GAMES_HOST=your-games-host-or-private-ip
# Optional, only if an endpoint requires bearer authentication:
# LOCAL_LLM_API_KEY=your-local-api-key
```

Do not commit `.env` or place actual network addresses or credentials in this
public repository. The repo ignores `.env`; `.env.example` contains placeholders
only. Without configured hosts, pass explicit `--endpoint NAME=URL` values.

The script updates discovered endpoint providers in `~/.config/opencode/` and,
if it exists, `~/.pi/agent/models.json`. Existing settings for models still
available are preserved; unrelated providers are not modified.

Supply `--endpoint NAME=URL` one or more times to replace the default target
set. For servers requiring bearer authentication, set `LOCAL_LLM_API_KEY` in
the environment; do not put secrets in repository files.

After syncing, refresh OpenCode `/models` or restart OpenCode and pi-agent.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
