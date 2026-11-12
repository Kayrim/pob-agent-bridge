# Codex setup

Install the bridge into a known 64-bit Python environment first. A dedicated
virtual environment makes the executable path independent of the agent's PATH.
For example, from a normal PowerShell terminal after downloading a release:

```powershell
python -m venv "C:/Games/Path of Building/agent-bridge/.venv"
& "C:/Games/Path of Building/agent-bridge/.venv/Scripts/python.exe" -m pip install ./pob_agent_bridge-0.2.0-py3-none-any.whl
```

Use your actual writable PoB directory and downloaded wheel location.

## Register the local server

```powershell
codex mcp add pob -- "C:/Games/Path of Building/agent-bridge/.venv/Scripts/python.exe" -m pob_bridge --pob-dir "C:/Games/Path of Building" mcp
codex mcp get pob --json
```

Alternatively, add the [TOML example](../examples/codex.toml) to your Codex
configuration, replacing the paths. User-level configuration is normally
`~/.codex/config.toml`; trusted projects can use `.codex/config.toml`.
Use either registration method; don't add duplicate definitions.

For an already-open desktop chat, use Settings → MCP servers → Restart if the
new server/tools have not appeared. Reconnect the client after updating the
server environment. These configuration/restart steps follow the
[official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Verify the real connection

`codex mcp get` confirms configuration; it does **not** prove a successful tool call.
Ask Codex:

> Use pob_health, then pob_calculate on builds/example.xml. Report the server's
> engine and tree versions and the returned life and damage. Use the actual MCP
> tools; don't substitute a shell-only test or claim a live GUI connection from
> a successful isolated calculation.

The XML must already exist inside your PoB directory. For a synthetic smoke test,
copy this repository's `examples/minimal.xml` to `builds/example.xml` there.
The eight tools should be discoverable; `pob_health` and `pob_calculate` work with
the GUI closed. `pob_status` confirms a **live** connection only when the hooked
PoB window is running and responds. In 0.2 it may be inactive or minimised;
`pob_health` should also report `backgroundService: true`.

For live control, install the hook once, then open PoB using your normal Windows
shortcut. Ask Codex for `pob_status`. Read its reported IDs
before selecting matching sets. Set selection does not automatically change the
character's level. After any mutation, verify the result and save/export as needed.

After updating the Python package, run `install` again to refresh its Lua files
and restart PoB normally once. Reconnect the MCP client so it uses the updated
package. Keeping an old PoB process open keeps its old in-memory bridge code.

## Save-folder errors

An agent shell can give child GUI processes its sandbox restrictions. We observed
PoB unable to save to Documents even though the user had full folder access;
opening it normally restored saving. MCP itself does not require the GUI to be
started by the agent.

Preserve the open build with a verified export before restarting. Follow the
[save troubleshooting instructions](../README.md#cannot-save-the-build-file);
do not solve this by broadly weakening folder permissions or running everything
as Administrator.
