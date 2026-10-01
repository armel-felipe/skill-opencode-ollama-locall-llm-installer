# locall-llm-installer

OpenCode skill that syncs your locally installed Ollama models into the global
OpenCode config (`~/.config/opencode/opencode.json` or `opencode.jsonc`) and,
when present, pi-agent's `~/.pi/agent/models.json`.

It updates **only** the `provider.ollama.models` section — every other key in
your config is left untouched.

## What it does

- Runs `ollama list` to capture every installed model.
- Updates the `provider.ollama.models` map in the global opencode config.
- Updates the `providers.ollama.models` list in pi-agent when its config exists.
- Preserves any existing per-model settings (e.g. `limit`, `options`).
- Removes invalid `limit` entries (missing `context` or `output`), which
  would otherwise prevent opencode from starting.
- Keeps the original file format (`.json` or `.jsonc`, comments included).
- Is idempotent — running it again never duplicates entries.

## Requirements

- [Ollama](https://ollama.com/) installed and running (`ollama serve`).
- Python 3.10+.
- OpenCode with a global config at `~/.config/opencode/opencode.json` or
  `opencode.jsonc`.
- pi-agent is optional; if `~/.pi/agent/models.json` is absent, it is skipped.

## Usage

Run the bundled script from the skill directory:

```bash
python scripts/sync_ollama_models.py
```

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
If `ollama list` fails or returns nothing, it exits with an error and leaves
the config untouched.

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
2. Runs `ollama list` to capture every installed model.
3. Parses the config, tolerating `//` and `/* */` comments in `.jsonc`.
4. Updates only the `provider.ollama.models` map: each installed model
   becomes a key, preserving existing per-model settings and defaulting the
   display `name` to the model id. The `npm`, `name`, and `options` fields of
   the provider are only added if absent.
5. Writes the config back, preserving the original file format.

## Cross-platform

The script resolves the config directory via `Path.home()`, so it works on
Windows, macOS, and Linux with no path changes.

## License

MIT
