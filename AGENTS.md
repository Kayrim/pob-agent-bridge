# Working on PoB Agent Bridge

- This is a local stdio MCP server. Do not add an unauthenticated network listener.
- Keep stdout exclusively JSON-RPC in MCP mode. Send diagnostics to stderr.
- Do not bundle PoB binaries, game data, private builds, credentials or runtime files.
- Preserve the upstream wrapper's notices; its pinned version is in the README.
- Unit checks: `python -m unittest discover -s tests -v`.
- Native checks: set `POB_TEST_DIR` to a writable Windows PoB installation, then run
  the same command. They must not manipulate an existing GUI build.
- A pending request with no matching response has an unknown outcome. Never
  overwrite or retry it automatically. Keep path and scalar-argument validation.
- Changes to live PoB APIs require compatibility review and clear test evidence.
- Do not treat an agent-launched GUI as unrestricted. It can inherit a sandbox
  and lose access to the user's save folder. Prefer normal user launch and isolated
  calculations; preserve current work before restarting a live app.
- Client setup and tool usage are in `docs/AGENT-INTEGRATION.md` and `examples/mcp.json`.
