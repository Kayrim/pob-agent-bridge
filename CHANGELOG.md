# Changelog

## 0.2.0

- Service live requests with a same-thread Windows message timer while PoB is
  inactive or minimised, without drawing frames, changing focus or sending input.
- Finish mode changes and native recalculation before acknowledging load,
  selection and configuration requests; remove the two-draw-frame dependency.
- Wait for active Lua UI callbacks, including native modal-dialog loops, before
  servicing requests. Clean up the timer and private messages on shutdown.
- Report background-service state and runtime errors. Retry Windows sharing
  violations only before the request is published, retaining its identity.
- Add zero-frame and real timer regressions. Eleven tests pass with native
  checks enabled; live operations also pass through Codex MCP with PoB minimised.

After upgrading, rerun `install` and restart PoB normally once. Preserve open
work first. The MCP command and eight tool schemas remain compatible.

## 0.1.2

- Add Codex CLI registration, a copy-paste TOML configuration and real-connection
  verification instructions.
- Recommend normal user launch for live PoB. Document the save-folder failure
  caused by inherited agent-sandbox restrictions and a backup-first recovery.
- Record packaged-bridge verification through Codex and distinguish it from
  isolated engine tests and portable CI. No calculation or tool behavior changed.

## 0.1.1

- Canonicalize temporary test roots so Windows runner profiles with 8.3 short
  path aliases exercise the same path rules as the configured CLI.
- Keep the MCP server's reported version tied to the Python package version.

## 0.1.0

- Standalone local MCP server and CLI, with explicit PoB directory configuration.
- Eight typed tools including headless calculations, GUI status/selection/config,
  backup-before-load, export without overwrite, health and pending-request inspection.
- Bundled headless wrapper and native DLL runner; no dependency on private research.
- Optional reversible Lua hook for live Windows PoB control.
- Argument validation and protection against overwriting an unresolved request.
- Packaging, client configuration examples, unit tests and opt-in native smoke test.

Initial compatibility target: Windows x64 / PoB Community 2.67.2. Wider live-GUI
and future-release compatibility needs community testing.
