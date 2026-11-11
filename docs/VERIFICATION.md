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

The automated suite has nine tests when both native tests are enabled: seven
portable tests and two optional Windows native-engine tests. The native checks
also exercise load/select/config/export mailbox handlers in an isolated engine,
without manipulating a user's open GUI build.

GitHub CI runs the portable suite, package installation and CLI help on Windows
and Ubuntu with Python 3.10 and 3.12. Native tests are skipped there because PoB
is not bundled. Linux CI success does not mean Linux native-engine support.

This is evidence of the listed operations on this configuration, not a promise
of compatibility with future PoB releases, every MCP client, all build types, or
the accuracy of unverified game mechanics. Native calculation uses the installed
game data, regardless of the league named in an imported build.
