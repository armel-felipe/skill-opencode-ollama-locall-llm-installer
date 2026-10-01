---
name: locall-llm-installer
description: >-
  Syncs locally installed Ollama models into the global OpenCode config and,
  when present, pi-agent's models.json. Use this whenever the user mentions
  updating, refreshing, syncing, or installing local Ollama models, adding a
  newly pulled model, removing a deleted one, or fixing a local model list.
---

# locall-llm-installer

Keeps the model lists of the global OpenCode config and optional pi-agent
config in sync with the models actually installed in Ollama.

## When to use

Trigger whenever the user wants to update, sync, or install local Ollama
models into OpenCode or pi-agent, or when a local model is missing from a
model picker. The script only touches the Ollama provider sections — it never
modifies other providers or unrelated settings.

## How it works

The bundled script `scripts/sync_ollama_models.py`:

1. Locates the global opencode config file. It looks for
   `~/.config/opencode/opencode.json` first, then
   `~/.config/opencode/opencode.jsonc`, and uses whichever exists.
2. Runs `ollama list` to capture every installed model.
   Duplicate tags are deduplicated because pi-agent identifies models by name.
3. Parses the config (tolerating `//` and `/* */` comments in `.jsonc`).
4. Updates **only** the `provider.ollama.models` map: each installed model
   becomes a key, preserving any existing per-model settings and defaulting
   the display `name` to the model id. The `npm`, `name`, and `options`
   fields of the provider are only added if absent.
5. For each model, runs `ollama show <model>` to read its maximum context
   length and sets `limit.context` to that value (so OpenCode sends the
   correct `num_ctx` to Ollama instead of a conservative default). If a
   valid `limit.output` already exists it is kept; otherwise it defaults to
   a quarter of the context length.
6. Writes the config back, preserving the original file format
   (`.json` or `.jsonc`).
7. If `~/.pi/agent/models.json` exists, updates only
   `providers.ollama.models`: each installed model becomes a pi-agent model
   entry, preserving existing entries by `id`. If the file does not exist, it
   is skipped without an error and is never created.

## Running it

The script is cross-platform (Windows, macOS, Linux). It resolves the
config directory via `Path.home()`, so it works regardless of where the
skill was installed. Run it from the skill directory:

```bash
python scripts/sync_ollama_models.py
```

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

The script prints the config paths it updated and the list of synced models.
If `ollama list` fails or returns nothing, the script exits with an error and
leaves the config untouched.

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

Tell the user to restart opencode (or run `/models`) so the updated model
list is picked up. If a model still does not appear, check that Ollama is
running (`ollama serve`) and that the model was pulled with `ollama pull`.
