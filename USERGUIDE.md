# Selenium → Playwright Migrator MCP — User Guide (RC candidate)

**Pre-release / production NO-GO.** This MCP stdio server exposes conservative read-only migration analysis, preview, review, and exact-candidate verification. The server cannot perform automatic edits or establish general Selenium→Playwright behavioral parity; Windows Chromium orphan [Core issue #59](https://github.com/levencode-labs/selenium-playwright-migrator-core/issues/59) remains unresolved.

## 1. Supported workflow

Use a trusted **absolute existing** local workspace path for `MIGRATOR_WORKSPACE`. MCP tool arguments are workspace-relative; recursive symlinks/reparse points are rejected. The server is not an OS sandbox and should not be used with untrusted customer secrets.

1. `analyze_migration({source:"relative/scope"})`: inspect full NUnit test/lifecycle inventory; record `analysisId` and `sourceTreeHash`; resolve every blocker.
2. `preview_migration({source:"relative/scope", expectedAnalysisId:"EXACT_ANALYSIS_ID"})`: obtain a conservative generated candidate and `candidateId`.
3. After explicit human/agent source-backed review, edit the target **outside MCP** in a separate workspace-relative directory; avoid changing source bytes.
4. `verify_artifact({source:"relative/scope",expectedAnalysisId:"EXACT_ANALYSIS_ID",candidateId:"PARENT_CANDIDATE_ID",targetRoot:"separate/target"})`: obtains a new content-addressed target candidate ID, exact target tree hash and the mandatory `migrator-acceptance/v1` lineage. Do not reuse previous acceptance after any source/target edit.
5. Read `rejected_incomplete` as **STOP**: missing source operations, selectors, arguments, helper actions, NUnit `SetUpFixture`, inherited lifecycle or exception paths. `blocked_unverified` / `candidate_unverified` means **review required**, not equivalent. Separate syntax/compile/testDiscovery/runner/realBrowser/behavioralEquivalence stages remain independent and `not_run` is not PASS.

`runCompile=true` permits only in-memory Roslyn compilation with explicit `referenceDlls` (use `[]` for framework-only); this is not a project build or browser execution. MCP does **not** run user code/browser/NUnit automatically or publish target source.

## 2. Development setup from GitHub (no release publication)

Clone this **RC branch** and the matching Core repository at the SHA in `.github/workflows/mcp-ci.yml`. The CI itself builds five Core NuGet packages locally, restores the version-matched MCP package feed, tests Linux MCP stdio and a self-contained Windows executable. Run:

```bash
dotnet build Migrator.Mcp/Migrator.Mcp.csproj -c Release
MIGRATOR_WORKSPACE=/absolute/path/to/trusted-tests dotnet run --project Migrator.Mcp/Migrator.Mcp.csproj -c Release --no-build
```

The build above requires the exact local version-matched Core packages, as in `.github/workflows/mcp-ci.yml`; a fresh checkout without a feed may not restore. For Windows, set `MIGRATOR_WORKSPACE` in your PowerShell session and launch the complete self-contained `Migrator.Mcp.exe` folder from successful CI artifacts. Never infer that published public packages exist.

## 3. Evidence, negative controls and limitations

CI includes real MCP JSON-RPC checks for missing `SetUpFixture`, inherited NUnit base and multi-hop private helper Click: a flattened target must be `rejected_incomplete`, while structurally corresponding target stays `blocked_unverified`. Pinned Core CI separately runs eight real Selenium/Playwright localhost cases and two negative mutations. The public external projects are only source-inspected (exact Git blob bytes): behavioral parity `UNKNOWN`.

The original Core P47 Windows SIGTERM/12-second gate and recorded native-LIVE failures are not changed by this MCP. No product cleanup fix, automatic apply, customer-project runtime authorization, merge or release is claimed. See [RC consumer gates](docs/RC-CONSUMER.md).
