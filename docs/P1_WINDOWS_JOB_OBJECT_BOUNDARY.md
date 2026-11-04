# P1 — Windows browser process ownership boundary

Core candidate: `d2f72424837498a1a64405a54a0b8ee49cbfeb84` (versioned `0.1.0-preview.50` packages).
Issue: https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core/issues/59

The historical Windows preview.47 run failed when two real Chrome descendants remained alive after the original 12-second unassisted gate. The PIDs were 5936 and 9024 with starts 2026-11-02 05:22:43/05:22:44 UTC; the GitHub runner subsequently terminated both. Do not reclassify that FAIL because later diagnostic runs pass.

The separate Core Win32 Job Object control proves only that a **synthetic** process with an observed parent and child is contained in a host-owned job (`IsProcessInJob`), survives parent exit while the host handle stays open, and exits after the host closes its last `KILL_ON_JOB_CLOSE` handle. This control does not run Playwright or Chromium in a Job Object, never kills the real observed browser tree, and executes after the unchanged full P47 test.

A safe future host-owned implementation needs race-free process creation/assignment, real Playwright-driver/Chrome descendant membership checks, nested Job Object and breakaway validation, then the **unchanged 12-second unassisted P47 check before any host kill**. Any surviving Chromium at that gate is still a P47 failure; separate post-gate cleanup cannot convert it to success.

MCP/Skill remains read-only/source-based. No automatic edits, process killing, unpublished ArBilling source, or private business E2E claims. Both PRs remain draft until full source-backed resolution and all required tests succeed.
