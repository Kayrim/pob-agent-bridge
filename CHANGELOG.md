# Changelog

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
