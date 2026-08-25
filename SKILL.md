---
name: locall-llm-installer
description: >-
  Syncs locally installed Ollama models into the global opencode config
  (~/.config/opencode/opencode.json or opencode.jsonc). Use this whenever the
  user mentions updating, refreshing, syncing, or installing local Ollama
  models in opencode, adding a newly pulled model, removing a deleted one, or
  fixing the model list in their opencode config. Also use it when the user
  says "update my local models", "sync ollama", "refresh the model list", or
  asks why a local model is missing from the /models picker.
---

# locall-llm-installer

Keeps the `provider.ollama.models` section of the global opencode config in
sync with the models actually installed in Ollama.

## When to use

Trigger whenever the user wants to update, sync, or install local Ollama
models into opencode, or when a local model is missing from the `/models`
picker. This skill only touches the Ollama provider section of the config —
it never modifies other providers or unrelated settings.

## How it works

The bundled script `scripts/sync_ollama_models.py`:

1. Locates the global opencode config file. It looks for
   `~/.config/opencode/opencode.json` first, then
   `~/.config/opencode/opencode.jsonc`, and uses whichever exists.
2. Runs `ollama list` to capture every installed model.
3. Parses the config (tolerating `//` and `/* */` comments in `.jsonc`).
4. Updates **only** the `provider.ollama.models` map: each installed model
   becomes a key, preserving any existing per-model settings and defaulting
   the display `name` to the model id. The `npm`, `name`, and `options`
   fields of the provider are only added if absent.
5. Writes the config back, preserving the original file format
   (`.json` or `.jsonc`).

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

The script prints the config path it updated and the list of synced models.
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
