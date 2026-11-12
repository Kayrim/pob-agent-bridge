# PoB Agent Bridge

A **local MCP server for Path of Building Community**. Let an AI agent calculate
builds, read the current build, switch sets, adjust configuration and export XML
without navigating PoB's UI or taking screenshots.

**Windows x64 · Python 3.10+ x64 · no Python runtime dependencies · MIT**

This is an independent community project, not an official Path of Building or
Grinding Gear Games integration. It uses **your installed PoB engine and data**;
it does not supply new patch data or certify that a build works in game.

## Quick start

Install [Path of Building Community](https://github.com/PathOfBuildingCommunity/PathOfBuilding/releases)
and [64-bit Python](https://www.python.org/downloads/windows/). Use a writable PoB
installation directory. The directory must contain `Launch.lua` and `lua51.dll`.

Download and extract this project's latest release, then run in its folder:

```powershell
python -m pip install .
pob-agent-bridge --pob-dir "C:/Games/Path of Building" health
```

You can also run from the source folder without installing Python packages:

```powershell
python -m pob_bridge --pob-dir "C:/Games/Path of Building" health
```

`health` is read-only. **Calculations work without installing the GUI hook and
without a running PoB window.** Put an exported build XML inside your PoB folder,
for example `C:/Games/Path of Building/builds/example.xml`, then run:

```powershell
pob-agent-bridge --pob-dir "C:/Games/Path of Building" calculate builds/example.xml
```

All relative build paths are relative to the **PoB directory**, not this repository
or your shell's current directory. Absolute XML paths must also resolve inside
that directory. Parent directories for exported XML must already exist.

## Connect your AI agent through MCP

Give any stdio-capable MCP client this command and these arguments:

```text
Command: pob-agent-bridge
Arguments: --pob-dir "C:/Games/Path of Building" mcp
```

For clients that use an `mcpServers` JSON config:

```json
{
  "mcpServers": {
    "pob": {
      "command": "pob-agent-bridge",
      "args": ["--pob-dir", "C:/Games/Path of Building", "mcp"]
    }
  }
}
```

Replace the directory with your own. If the client cannot find the executable,
use the absolute Python path with `"args": ["-m", "pob_bridge", "--pob-dir", ...,
"mcp"]` after installing into that Python environment. Restart/reconnect the MCP
client after changing its configuration. See [the integration guide](docs/AGENT-INTEGRATION.md)
and [ready-to-edit config](examples/mcp.json).

For Codex, see [Codex setup](docs/CODEX.md) and the [TOML example](examples/codex.toml).

Try this prompt:

> Use the PoB tools. Start with pob_health, then calculate builds/example.xml.
> Report the engine/tree version, life, resistances and damage assumptions.
> Prefer isolated calculations. Ask before replacing a live build, and export
> changes to a new filename. Do not infer game performance from a single DPS value.

## Tools

| Tool | Purpose | Needs running GUI? |
|---|---|---|
| `pob_health` | Inspect installation, hook, heartbeat and pending request | No |
| `pob_calculate` | Calculate XML in a separate native-engine process | No |
| `pob_pending` | Inspect outcome of the last live request | No |
| `pob_status` | Read live sets, gems, points and stats | Yes |
| `pob_load` | Back up current live build, then load XML | Yes |
| `pob_select` | Select tree, skills, items, configuration set, main group or view | Yes |
| `pob_config` | Change scalar configuration inputs and recalculate | Yes |
| `pob_export` | Export live build to a new XML file; refuses overwrite | Yes |

`pob_calculate` accepts `path`, optional `tree`, `skills`, `items`, `configSet`,
`mainSkillGroup`, and `values`. The same set IDs are accepted by `pob_select`.
IDs are **1-based IDs reported by PoB**, not guessed positions. `pob_config`
accepts `{ "values": { "enemyIsBoss": "Pinnacle" } }`; use valid keys from your
PoB's configuration schema or exported XML. Unknown keys are not guaranteed to
affect calculations. The bridge does not invent items, nodes or gem groups;
your agent can prepare XML with its ordinary file tools and calculate/load it.

## Optional live-window control

Close PoB normally first so your unsaved work is preserved. Install the removable
hook, then **open PoB using your normal Windows shortcut**:

```powershell
pob-agent-bridge --pob-dir "C:/Games/Path of Building" install
# Open PoB normally (it may then be inactive or minimised), then run:
pob-agent-bridge --pob-dir "C:/Games/Path of Building" status
pob-agent-bridge --pob-dir "C:/Games/Path of Building" load builds/example.xml
pob-agent-bridge --pob-dir "C:/Games/Path of Building" select --tree 1 --skills 1 --items 1 --config-set 1 --view CALCS
pob-agent-bridge --pob-dir "C:/Games/Path of Building" export builds/example-agent-copy.xml
```

**PoB can stay inactive or minimised.** Version 0.2 uses a private Windows message
timer on PoB's own thread to service the mailbox every 100 ms. It finishes mode
changes and recalculates through PoB's non-drawing APIs before replying. It does
not move the mouse, change focus, force drawing frames or add a network listener.
`pob_health` reports `backgroundService: true` once the new bridge is running.
After upgrading, rerun `install` and restart PoB normally once. Old in-memory
bridge versions still require an active window. `pob_calculate` continues to work
without a running GUI or an installed hook.

Installation copies bridge Lua files into `agent-bridge/`, saves a hash-named
original `Launch.lua` under `agent-bridge/runtime/`, and inserts one marked frame
startup hook. It does not alter calculation formulas. PoB updates may remove that hook;
rerun installation and restart after checking compatibility. If the hook location
or an existing hook differs, installation refuses to guess.

To remove the hook:

```powershell
pob-agent-bridge --pob-dir "C:/Games/Path of Building" uninstall
```

Restart PoB afterward. Backups remain; uninstall removes only this exact hook.
The optional `launch` command inherits the caller's process restrictions. **If an
AI agent launches PoB inside its sandbox, PoB may be unable to save to Documents**
even though your Windows account can write there. Open the GUI normally; reserve
`pob_calculate` for unattended work. `launch --keep-alive` only prevents child-process
cleanup; it does not remove sandbox restrictions or grant file access.

### Cannot save the build file

If PoB reports that the save folder is not writable, first check its displayed
path. If the app was launched by a sandboxed agent, preserve the open build with
`pob_export` to a **new XML path inside the PoB directory**, verify the export,
then close PoB normally and reopen it using your usual Windows shortcut. Restore
the exported build and save again. Keep the backup until saving is confirmed.
Do not discard the only copy of unsaved work, change folder permissions blindly,
or assume this error always has the same cause.

## Timeouts and local access

Live requests are serialized. A timed-out request may still execute later.
**Do not blindly retry**: use `pob_pending`, inspect the result and check
`pob_health` / `agent-bridge/runtime/last-error.json` if servicing has stopped.
New requests are blocked while a
previous outcome is unknown. There is no automatic destructive retry/cancel.

The bridge opens **no TCP port**, has no remote listener and needs no API key.
Its MCP transport is local stdin/stdout. Local processes with access to the PoB
directory can access its mailbox; this is not a sandbox against your own Windows
user. Only connect trusted agents. It exposes no arbitrary Lua execution tool.
Exports refuse existing files, and loads preserve a uniquely named build backup.

If a crashed client leaves `agent-bridge/runtime/client.lock`, first confirm no
client is running and inspect `request.json` / `response.json`. Only then remove
that stale lock. Runtime files and backups are local and are excluded from Git.

## Compatibility and tests

Tested on **Windows x64, Python 3.12 and PoB Community 2.67.2**. The bundled
headless wrapper is from that PoB release. Newer PoB versions may require wrapper
or internal-API changes; inspect the engine/tree version in every result. macOS,
Linux native calculation, PoB 2 and complete coverage of all build types are not
claimed. Unit tests also run on Linux; that does not imply native support there.
If XML needs a version-conversion dialog, isolated calculation refuses it; open
and resave it with your installed PoB first.

MCP uses newline-delimited JSON-RPC stdio, with initialize negotiation for protocol
versions through `2025-11-25`. Newer clients need legacy fallback. No HTTP/MCP
Apps endpoint is implemented.

```powershell
python -m unittest discover -s tests -v
# Optional real installed-engine smoke test; never touches your live GUI build:
$env:POB_TEST_DIR = "C:/Games/Path of Building"
python -m unittest discover -s tests -v
```

The suite covers reversible installation, refusal of unknown hooks, path escapes,
argument validation, pending-request preservation, protocol/error responses and,
when enabled, a real native calculation plus an invalid-tree error over MCP,
and load/select/config/export handlers exercised against isolated native objects.
Timer regressions forbid drawing and check both idle operation and deferral
during nested UI callbacks.
The packaged bridge was also verified through Codex's actual MCP client: eight
tools discovered, native calculation, live status, set selection and export.
The 0.2 background operations passed while the user kept PoB minimised.
Normal PoB saving was confirmed after reopening the GUI normally. See
[verification details](docs/VERIFICATION.md). Wider version/build compatibility
still needs community testing. Do not use calculated max hit as a survival guarantee.

## Contributing

Issues and PRs are welcome. Include PoB version, Windows/Python architecture,
tool arguments, and sanitized errors. Never upload runtime backups, private
builds or account paths. Please add focused regression coverage for API changes.

The project bundles one upstream MIT headless wrapper, with attribution in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). PoB itself, game data, binaries,
personal builds and credentials are **not** bundled.
