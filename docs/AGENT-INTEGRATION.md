# Connecting an agent

The host needs Windows x64, a writable installed PoB Community directory and
64-bit Python 3.10+. Install this project into the Python environment your MCP
client starts. No OpenAI, Anthropic or other model API is called by this server.

## Three ways to start stdio

Installed entry point:

```text
pob-agent-bridge --pob-dir "C:/Games/Path of Building" mcp
```

Installed Python module (use a full path to python.exe if needed):

```text
python -m pob_bridge --pob-dir "C:/Games/Path of Building" mcp
```

Source checkout, with no pip install (set the client's working directory to it):

```text
python -m pob_bridge --pob-dir "C:/Games/Path of Building" mcp
```

Alternatively set `POB_DIR` in the server environment and omit `--pob-dir`.
Do not expose this local stdio process over HTTP or attach it to an untrusted
agent. Client-specific registration UI varies; the server command/arguments
are the same. It advertises eight tools through `tools/list`.

Codex users can follow [the Codex-specific walkthrough](CODEX.md).

## Suggested agent procedure

1. Call `pob_health`. Resolve an invalid installation before attempting work.
2. Prefer `pob_calculate` for review/comparison. Its XML path must be inside PoB.
3. Inspect `pobVersion` and `latestTreeVersion`; do not claim newer game data.
4. For live work, ensure the hook is installed and restarted, PoB is active and
   there is no pending request. Call `pob_status` to discover actual set IDs.
5. Select matching tree/skills/items/configuration together. These are distinct
   IDs, not necessarily identical numbers. Return to `pob_status` after errors.
6. Export to a new filename, and report the backup/export paths to the user.
7. After a timeout use `pob_pending`; an unknown result is not a failed mutation.

Open the live GUI through the user's normal shortcut. Starting it as a child of
a sandboxed agent can prevent saving to Documents. `launch --keep-alive` addresses
process lifetime, not file permissions. Preserve unsaved work before any restart.

Example isolated tool arguments:

```json
{
  "path": "builds/example.xml",
  "tree": 1,
  "skills": 1,
  "items": 1,
  "configSet": 1,
  "mainSkillGroup": 1,
  "values": { "enemyIsBoss": "Pinnacle" }
}
```

Use the values appropriate to the exported build; don't apply those IDs to an
unknown build. The included `examples/minimal.xml` is a synthetic smoke-test
fixture, not a playable or recommended build. Copy it under PoB to try a calculation.

## Without MCP

Agents with a terminal can invoke the same CLI. Successful output is JSON;
command errors return a nonzero exit status. `mcp` reserves stdout for JSON-RPC.
The subprocess used for native calculation has a 60-second limit. Live requests
normally time out after 15 seconds. No progress/streaming or task API is exposed.

MCP transport reference:
https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#stdio
