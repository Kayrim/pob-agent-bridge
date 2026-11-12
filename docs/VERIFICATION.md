# Verification record

Checked 11 November 2026 on Windows x64 with 64-bit Python 3.12 and Path of
Building Community 2.67.2, using its native 3.29 tree/game data.

- Codex's real app-server MCP client connected and discovered all eight tools.
- `pob_health` returned the installation and hook state.
- `pob_calculate` returned native-engine build statistics through that client.
- `pob_status` read the running GUI, including its selected configuration set.
- `pob_select` changed live sets/view and returned recalculated statistics.
- `pob_export` preserved the current unsaved build before restarting the GUI.
- PoB's own Save button wrote a valid XML to the normal Documents build folder
  after the app was reopened normally. MCP subsequently reported `unsaved: false`.
- Matching starter sets were restored and saved; no private build is included here.

The 0.2 automated suite has eleven tests when native tests are enabled: eight
portable tests and three optional Windows native-engine tests. The native checks
also exercise load/select/config/export mailbox handlers in an isolated engine,
without manipulating a user's open GUI build.

The 12 November 2026 idle regression first failed against 0.1.2: after a load
with no `OnFrame` calls, the reply reported the previous level-one build instead
of the level-ten fixture. It passes after the non-drawing lifecycle change.
A second native test services load/select/config/export solely by dispatching
the real Windows timer's messages, with no bridge ticks or render frames. It
checks updated damage, heartbeat progress, same-thread ownership and timer
cleanup; every drawing API is forbidden in that test. It also simulates a native
dialog's nested message loop and proves requests wait until the enclosing Lua
UI callback returns, preserving callback results including nil values.
A transport test covers
Windows sharing violations before publishing a request, without resending it.

The final 0.2.0 build was also tested through Codex's configured app-server MCP
connection while the user kept PoB minimised. Live status, preserving the open
build, loading a larger build, selecting its second attack, changing resistance
configuration, exporting and restoring the starter all succeeded. Status took
0.03–0.11 s, selection/configuration 0.19–0.22 s, the single-build load 0.80 s and
the larger multi-loadout master restore 2.23 s on this machine. These are observed
end-to-end timings, not performance guarantees. No runtime error was recorded.

GitHub CI runs the portable suite, package installation and CLI help on Windows
and Ubuntu with Python 3.10 and 3.12. Native tests are skipped there because PoB
is not bundled. Linux CI success does not mean Linux native-engine support.

This is evidence of the listed operations on this configuration, not a promise
of compatibility with future PoB releases, every MCP client, all build types, or
the accuracy of unverified game mechanics. Native calculation uses the installed
game data, regardless of the league named in an imported build.
