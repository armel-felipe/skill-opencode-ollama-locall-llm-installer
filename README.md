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

Set `LOCAL_LLM_MAC_HOST` and/or `LOCAL_LLM_GAMES_HOST` to your own private
hostname/IP before running. Without these variables, pass explicit
`--endpoint NAME=URL` values; the skill does not hard-code private network
addresses in this public repository.

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
