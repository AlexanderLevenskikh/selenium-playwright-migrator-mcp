# P1 — Windows browser process ownership boundary

Core candidate: `d2f72424837498a1a64405a54a0b8ee49cbfeb84` (versioned `0.1.0-preview.50` packages).
Issue: https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core/issues/59

The historical Windows preview.47 run failed when two real Chrome descendants remained alive after the original 12-second unassisted gate. The PIDs were 5936 and 9024 with starts 2026-11-02 05:22:43/05:22:44 UTC; the GitHub runner subsequently terminated both. Do not reclassify that FAIL because later diagnostic runs pass.

The separate Core Win32 Job Object control proves only that a **synthetic** process with an observed parent and child is contained in a host-owned job (`IsProcessInJob`), survives parent exit while the host handle stays open, and exits after the host closes its last `KILL_ON_JOB_CLOSE` handle. This control does not run Playwright or Chromium in a Job Object, never kills the real observed browser tree, and executes after the unchanged full P47 test.

A safe future host-owned implementation needs race-free process creation/assignment, real Playwright-driver/Chrome descendant membership checks, nested Job Object and breakaway validation, then the **unchanged 12-second unassisted P47 check before any host kill**. Any surviving Chromium at that gate is still a P47 failure; separate post-gate cleanup cannot convert it to success.

MCP/Skill remains read-only/source-based. No automatic edits, process killing, unpublished ArBilling source, or private business E2E claims. Both PRs remain draft until full source-backed resolution and all required tests succeed.

## 2026-11-22 P1 real-subtree experiment — pending independent acceptance

Core PR #58 adds a separate `scripts/p2_preview47_real_chromium_job_object_probe.py`
with a real .NET NUnit testhost gated **before** `Playwright.CreateAsync`.
The host attempts `AssignProcessToJobObject` while the gate is closed;
only after identity-bound `IsProcessInJob` may a real Playwright Node driver
and Chrome launch. The Node PID is then terminated by the original Windows
`os.kill(SIGTERM)` mechanism. The same 12-second **unassisted** process
presence observation is recorded before the host closes the Job handle.
The separate evidence ZIP is `migrator-preview47-real-host-job-windows`.

This is an experimental **real-browser** check, not an accepted mitigation.
CI may demonstrate membership, show genuine survivors, or fail because of
nested-job limits, missing native identity, transient process roles, or
unobserved cleanup. All non-proven cases stay blocked. Never treat a
post-gate `KILL_ON_JOB_CLOSE` as original 12-second cleanup PASS. The original
November 2 PID 5936/9024 FAIL remains authoritative. No new production
process authority, API autoapply, or release is authorized by this probe.
Repin the MCP consumers only to a subsequently **merged** and fully verified
Core SHA, then rerun both OS jobs.

## P1-A: observed real Windows orphans, bounded post-gate host mitigation (2026-11-22)

The original unassisted Windows P47 **still fails on real Chrome**:
November 2 PIDs 5936/9024 (exact roles unknown), and November 21
PIDs 8596 (crashpad-handler) / 9640 (utility/storage.mojom.StorageService).
These two new native-live survivors were independently bound by FILETIME;
neither the earlier synthetic nor one successful real Node/Chrome Job probe
repairs the source cleanup contract.

Core draft `84042caf89c11792791f3cc47c107944330c80d3` adds an explicitly separate six-cycle real
Playwright Node/Chromium host Job experiment. The real NUnit testhost is
gated before Playwright.CreateAsync; the supervisor verifies actual
PID/CIM/native FILETIME and IsProcessInJob before Windows TerminateProcess
of the bound Node driver. **The original 12-second unassisted observation
runs before any host Job close.** For real survivors only, a separate
post-gate negative control checks the SAME native process remains LIVE
while the host retains the Job, and only then closes the last Job handle
and independently waits for exact FILETIME-matched native termination.
Any unassisted survivor ALWAYS makes the experiment fail, even if
post-gate host cleanup succeeds. Absent natural survivors the outcome is
NOT_OBSERVED, never a repair claim. Six predeclared cycles stop on the
first failure, not on the first success.

This is CI-only host-owned diagnostics, **not** a released migration runtime,
not a proof that the November orphan mechanism has been fixed, and not
process authority granted to MCP or Skill. Nested-job/breakaway and failure
to bind any PID remain BLOCKED. Preserve original CI/ZIPS, source hashes,
NUnit primary failures and the complete Linux/Windows CI matrix. Core
issue #59, Core PR #58 and MCP PR #54 remain OPEN/DRAFT until an actual
fixed source-backed case and full exact-head green CI authorize merge.

## P1-A2 — source-exact original P47 NUnit fixture host experiment

Core draft `6c51e8eeaf345918d42fae0555477840b0e6bf68` now uses a distinct `p1_preview47_source_exact_job_probe.py`
that obtains the **same** `p2_preview47_one_time_real_chromium.TEMPLATE`
runtime fixture, the exact `TypedTearDown` from preview.46 and exact
`OneTimeTearDown` from preview.47. The original source test's `Operation`,
`Page.GotoAsync`, `window.snapshot()`, real driver-loss ready/ack handshake,
primary NUnit assertion and per-test/context/browser cleanup are not replaced
by a simplified fixture. Source bytes and hook SHA-256 are recorded. The
**only** inserted C# code is a temporary host assignment handshake before
`Playwright.CreateAsync` — removing it must reproduce the original runtime
fixture byte-for-byte. The original P47 CI fixture and test remain unchanged.

The independent host Job owns the actual NUnit testhost before Playwright
creates Node/Chromium, verifies original PID/CIM/native FILETIME and
`IsProcessInJob` for live children, and kills the identity-bound Node by
the original Windows `os.kill(SIGTERM)` mechanism. Its separate **unchanged
12-second** unassisted presence gate is recorded BEFORE any host cleanup.
Only the same native-LIVE, pre-attested Chrome survivors may be used for the
separate post-gate 300-ms native-live hold and `KILL_ON_JOB_CLOSE` proof;
the FAIL from the unassisted gate is NEVER changed to PASS. Six immutable
source-backed stages alternate `disconnect_primary`,
`disconnect_pass` and `disconnect_primary_repeat`. A failed/blocked
stage stops immediately. If all six have **no** post-gate native-live Chrome,
the evidence status is UNKNOWN/NOT_OBSERVED (CI fails closed), not a
claimed mitigation. Do not rerun failures to select success.

This is still **CI-only host process ownership evidence**, not a
source-backed runtime cleanup repair and not Playwright behavioral equivalence.
Neither MCP nor Skill executes tests, assigns Windows Jobs, terminates
processes or upgrades a read-only `requires_review` finding into autoapply.
The real historical Chrome survivors (2026-11-02 PID5936/9024 and 2026-11-21
PID8596/9640 plus later verified descendants) stay preserved and #59 OPEN.
Full unchanged Core 28-job Linux/Windows CI must be green **and** the
source-backed defect resolved before merging Core; only then repin the
MCP consumers to the exact merged Core SHA and require MCP 2/2 green.
