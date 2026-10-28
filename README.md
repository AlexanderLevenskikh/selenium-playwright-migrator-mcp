# Selenium → Playwright Migrator MCP

Standalone **MCP stdio server and agent skill** for Selenium C# NUnit → Playwright .NET migration. It uses the versioned [Migrator Core](https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core) NuGet API rather than referencing the engine source projects.

Imported from [selenium-playwright-ast-migrator](https://github.com/AlexanderLevenskikh/selenium-playwright-ast-migrator), pinned source commit `a8b102072196f85bf85d785795aef22296c4deca`.

## MCP tools

- `analyze_migration(source, config?)`: source inventory, blockers, hashes and findings.
- `explain_finding(source, findingId, config?, expectedAnalysisId?)`: source excerpt, diagnostic evidence and suggested next action.
- `preview_migration(source, config?, expectedAnalysisId?)`: read-only conservative target draft, hashes, TODOs and residual findings.
- `verify_artifact(source, expectedAnalysisId, candidateId, targetRoot?, config?, runCompile?, referenceDlls?)`: syntax and optional Roslyn assembly compilation of **exact** generated or agent-edited target bytes. Edited candidates have new content-addressed revision IDs and their generated parent.

The server **never applies edits**. No compile/run/behavior claims are made for preview. Runtime/browser and product-project build verification remain roadmap items. Inputs with multiple fixtures or unsupported xUnit source are counted but blocked.

## Local build before Core is published to NuGet

CI uses Core commit `660a3ecd60b32d2091759ac93f9ea871cf46c309` for the local package feed, verified independently in its own repository. To reproduce the build:

```bash
git clone https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core.git core
git -C core checkout 660a3ecd60b32d2091759ac93f9ea871cf46c309
mkdir -p artifacts/nuget
for project in Migrator.Core Migrator.Roslyn Migrator.SeleniumCSharp Migrator.PlaywrightDotNet Migrator.Application; do
  dotnet pack "core/$project/$project.csproj" -c Release -o artifacts/nuget
done
dotnet restore Migrator.Mcp/Migrator.Mcp.csproj --source "$PWD/artifacts/nuget" --source https://api.nuget.org/v3/index.json
dotnet build Migrator.Mcp/Migrator.Mcp.csproj -c Release --no-restore
MIGRATOR_WORKSPACE=/absolute/path/to/selenium-tests dotnet run --project Migrator.Mcp/Migrator.Mcp.csproj -c Release --no-build
```

Core packages are **preview build artifacts**, not yet published to public NuGet.

## Install MCP as a dotnet tool (preview)

The MCP CI now packs `SeleniumPlaywrightMigrator.Mcp` as a versioned .NET tool and validates the **installed executable** with the same MCP protocol smoke. Until public NuGet publication, download the MCP package artifact from CI and provide the Core package feed if required:

```bash
dotnet tool install SeleniumPlaywrightMigrator.Mcp --version 0.1.0-preview.5 \
  --tool-path ./.tools --add-source ./artifacts/mcp --add-source ./artifacts/nuget \
  --add-source https://api.nuget.org/v3/index.json
MIGRATOR_WORKSPACE=/absolute/path/to/selenium-tests \
  ./.tools/selenium-pw-migrator-mcp
```

The `MIGRATOR_WORKSPACE` environment variable is mandatory. For an MCP client, set `command` to the absolute path of the installed `selenium-pw-migrator-mcp` executable and `args` to an empty list. No prebuilt public distribution is claimed until release.

## MCP client configuration

```json
{
  "mcpServers": {
    "selenium-playwright-migrator": {
      "command": "dotnet",
      "args": ["/absolute/path/to/mcp/Migrator.Mcp/bin/Release/net10.0/Migrator.Mcp.dll"],
      "env": {
        "MIGRATOR_WORKSPACE": "/absolute/path/to/selenium-tests"
      }
    }
  }
}
```

The environment variable must contain an **absolute existing workspace** path. Tool arguments use workspace-relative paths. Stdout is reserved for MCP JSON-RPC.

See the included [agent skill](skills/selenium-playwright-migration/SKILL.md). The integration smoke validates initialize, tool discovery/calls, path boundaries, stale analyses and unsupported source shapes.

License: MIT. Preview API and schema contracts may change before `v1.0`.

## Candidate verification and evidence limits

`verify_artifact` **never writes code**, runs scripts, starts tests, loads referenced assemblies as executable code or claims behavioral equivalence. Generated previews and edited trees are checked against fresh analysis/candidate IDs before capturing the exact C# bytes. The returned `candidate.targetTreeHash` and per-file SHA-256 bind evidence to the revision. A later edit receives another ID, even if an earlier candidate compiled.

- `syntax`: `passed` or `failed` after Roslyn parsing of captured files.
- `compile`: `not_run`, `blocked` (missing profile or invalid syntax), `passed`, or `failed`. `runCompile=true` requires `referenceDlls` (use `[]` to request .NET framework-only compile). This emits a temporary in-memory assembly; it does not perform a target-project `dotnet build`.
- `runtime` / `observables`: always `not_run` until separate verification profiles are implemented.
- `targetRoot`: workspace-relative directory **outside any directory source scope**, with exactly the preview's .cs filenames. It may be populated and edited by the calling agent's own editor, not by MCP.

The MCP protocol smoke exercises generated/edited candidates, semantic and syntax failures, blocked missing references, stale parent, and extra target files.

## Recursive source-scope safety

Before calling Core, MCP checks a recursive source directory for symbolic links/reparse points and rejects the scope if any are present (`SOURCE_SYMLINK_REJECTED`). This is intentionally conservative: even an in-workspace symlink is refused until a verified traversal policy is implemented. A single-file path still follows the normal workspace boundary check.

The recursive preflight is limited to 40 directory levels and 100,000 entries; choose a narrower scope for exceptionally large trees. It is a local defensive check, **not a general sandbox or an atomic filesystem snapshot**. Only grant the MCP server access to workspaces you trust.

## Standalone Linux and Windows executables

On every CI run, the MCP repository also builds a **self-contained, non-trimmed** executable for `linux-x64` and `win-x64`. Both are checked with the same real MCP stdio protocol suite, including edited-candidate verification. Roslyn requires physical runtime reference assemblies, so the ZIP/TAR contains the executable and its co-located runtime DLLs rather than a single-file bundle. Download their archives from the successful [MCP CI Actions run](https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-mcp/actions/workflows/mcp-ci.yml).

For Linux (extract the **entire** archive, not just the executable):
```bash
tar -xzf selenium-playwright-migrator-mcp-linux-x64.tar.gz -C ./migrator-mcp
MIGRATOR_WORKSPACE=/absolute/path/to/your/repo ./migrator-mcp/Migrator.Mcp
```

For Windows, extract `selenium-playwright-migrator-mcp-win-x64.zip` and use `Migrator.Mcp.exe` as the MCP client command, with `MIGRATOR_WORKSPACE` set to the absolute test-project root. No separate Core installation is necessary for either self-contained binary.

These are **CI preview artifacts**, not signed releases or public NuGet publications. They are built from pinned Core package sources; the MCP process still requires a trusted local workspace and does not provide an operating-system sandbox.

## Already-Playwright project safety (preview.3)

The engine supports **Selenium C# NUnit → Playwright .NET**, not Playwright → Playwright migration. `analyze_migration` now reports `ALREADY_PLAYWRIGHT_SOURCE` and counts tests without converting them if existing Playwright project references or strong Playwright assertions are detected. `MIXED_SELENIUM_PLAYWRIGHT_SOURCE` blocks ambiguous mixed test suites. `preview_migration` returns `blocked` and no target files for these inputs. MCP protocol smoke covers a synthetic existing Playwright NUnit project without copying private user files.

This is a fail-closed source guard, **not a project build/test/behavior verification**. Use a separate target-project verification workflow to evaluate existing Playwright code.

## Core preview.5 migration-quality safeguards

The source parser preserves result-producing `Navigation.Open*Page()` calls as structured invocations. Without a verified adapter mapping the generated output is blocked with `POM_NAVIGATION_REQUIRES_MAPPING` and source-line evidence. `LocalStorage.SetItem/RemoveItem/Clear/SettingPeriod` emits `LOCAL_STORAGE_REQUIRES_MAPPING`, not an assumed browser-storage translation.

`FullyConvertedTests` now incorporates renderer-emitted TODOs per test method and shared setup, correcting a false-green case found in a private Selenium/NUnit pilot. The private project is never uploaded to GitHub; a synthetic equivalent is tested through real MCP stdio and self-contained Windows/Linux distributions.

## POM selector inspection (preview.6)

`inspect_pom_sources(sourceDirectory, pageTypes?, pageVariable?)` inspects local Page Object classes and the actual selector-extension implementations using Roslyn. Returns source path/line evidence, proven HTML attributes, direct and one-level nested locator candidates and source-derived LocalStorage helper method evidence. Restrict `pageTypes` to a few relevant Page Object type names to keep the output concise.

Every locator with `proposedPlaywrightExpression` is explicitly tagged `requires_review`. Missing or conflicting selector helpers return `insufficient_evidence`; no unapproved selectors are added to `adapter-config.json` or code. A human/agent must verify the DOM and helper semantics before copying a proposed mapping to `UiTargets` and re-running `preview_migration`. Source hashes invalidate evidence after file edits. Private project code is never shipped with the tool.

## Table-row action preservation (preview.7)

Core now treats source `Items.ElementAt(N).Click()` as a side-effecting click and generates `await locator.Nth(N).ClickAsync()` when the row locator is explicitly and correctly mapped. Unsupported chains such as `Items.ElementAt(N).Should().NotBe(...)` produce `TABLE_ROW_OPERATION_REQUIRES_MAPPING` rather than an inert locator variable. The real MCP stdio smoke checks both cases. A successful syntax or build step is not behavioral equivalence.

## Multi-step POM lineage (preview.8)

The read-only `inspect_pom_sources` response now includes `helpers[].orderedCalls`, `controlFlow`, `methodSha256`, `reviewFlags` and bounded same-class private-helper implementations. `storageAndNavigationFlows` records NUnit test/setup storage operations relative to first in-method navigation, but **does not infer runtime browser origin**. The evidence schema is now `migrator-pom-evidence/v1alpha2`. Source order is not execution order through loops/exception branches.

This intentionally creates **no executable mapping**. Use the evidence to prepare explicit reviewed `Methods` and `UiTargets` mappings with source semantics preserved; green build and reduced TODO counts alone are not acceptance.

## Review proposed POM Methods mappings (preview.9)

After `inspect_pom_sources`, call `review_pom_mapping(sourceDirectory, sourceType, sourceMethod, expectedSourceTreeHash, targetStatements, sourceLine?)` with **concrete candidate C# statements**. The tool walks the source-backed method ledger, follows same-class helpers and checks whether clicks, inputs, waits, assertions, script/storage effects and control-flow constructs remain represented **in order**.

The tool rejects source actions missing from the proposed target (`rejected_incomplete`), syntax-invalid drafts and TODO placeholders (`blocked`), and stale hashes. Even a category-complete mapping is only `requires_review`: no assertion about selector equality, argument values, application state, browser origin or behavioral equivalence is made. The tool never saves/applies the statements. It prevents shrinking a five-step ComboBox to one FillAsync, dropping DatePicker's JavaScript blur, replacing a Loader retry loop with one wait, or writing only one of five LocalStorage keys.

Use an exact sourceLine when a Page Object class overloads a method name. This tool is a conservative validation gate before adding a reviewed Methods config, not automatic generation or acceptance.

## Synthetic ComboBox runtime and source-argument safety (preview.10)

Core now keeps authored C# quote escapes intact when substituting a `ParameterizedMethods` argument and rejects incomplete source parameter propagation through `review_pom_mapping.parameterFlows`. A separate synthetic HTML/Playwright NUnit experiment checks a real click–wait–fill–select–confirm flow in Chromium, including a negative case without the final confirmation. It is deliberately **not** an ArBilling business-backend test.

## Reviewed Loader and table assertions (Core preview.11)

Source `page.Table.Items.ElementAt(N).Text.Get().Should().Be/Contain` can now be preserved as executable `ToHaveTextAsync` or `ToContainTextAsync` when an explicit, grounded `UiTargets` row locator is present. If the Selenium fixture setup still blocks the source Page Object alias, the emitted assertion carries `TABLE_ASSERTION_REQUIRES_SETUP_REVIEW` and does **not** increase `FullyConvertedTests`. Never remove the marker merely to obtain passing NUnit tests.

When a project-specific zero-argument `Loader.ValidateLoading()` is parsed as a generic wait, an exact `Methods.SourceMethod` mapping now takes precedence. A reviewed mapping may preserve its loop, conditional reload, state waits and catch path, but must retain `RequiresReview` until actual source/timeouts/DOM are checked. In Playwright .NET, wait operations throw `System.TimeoutException`, not `Microsoft.Playwright.TimeoutException`. Run `verify_artifact` for exact C# syntax and independently compile/test the configured target project.

The synthetic browser experiment exercises both positive retry recovery and an exhausted-retry negative control, with two separate table text assertions. These artificial tests cannot certify the private ArBilling browser/backend.


## Preview.12 — conservative Loader review and negated table checks

Core is consumed from the versioned `0.1.0-preview.12` NuGet package, built from an exact pinned Core commit in CI. A `Should().NotContain(value)` table-row assertion now keeps its negative semantics in executable Playwright assertions. The source-backed reviewer tracks conditional state checks, retry counter increments and loop exits; it rejects altered numeric retry guards, broadened catch-all handlers and conditional reloads moved out of their branch. Typed Selenium-to-Playwright timeout exception translation still requires review.

Eight real Chromium synthetic tests (3 ComboBox, 5 Loader/table) are required: three new negative assertion controls confirm that intentionally wrong equality, substring and negated-substring expectations fail. MCP stdio also checks that an unmigrated fixture setup remains partial and that the generated assertions retain explicit review markers. These public fixtures **do not certify ArBilling**; target project build, authenticated browser execution and observable equivalence remain separate.

## Preview.13 — source-backed Loader retry review

The MCP tool consumes a **versioned** Core `0.1.0-preview.13` package and pins the exact merged Core revision in CI on both Linux and Windows. `inspect_pom_sources` now exposes immutable numeric local aliases, allowing `review_pom_mapping` to compare source `while(attempt < limit)` with target `while(attempt < 2)` when the source limit is explicitly initialized to 2. The reviewer also identifies literal `window.location.reload()` JavaScript as a reload action and rejects target waits that invert explicit source visible/hidden expectations. Missing state evidence still requires review.

The new real stdio protocol regression verifies those contract fields and deliberate wrong-mapping rejection without private Selenium sources. Review status is never a certificate of authenticated browser equivalence. CI Core packages are standalone NuGet dependencies; no `ProjectReference` is used.

## Preview.14 — source fixture Page Object lifecycle

Core preview.14 is installed as a versioned NuGet dependency built from pinned Core commit `b5b5e28af08241b00b3b28d0cc5b110e617a1fe2`. New `fixture_lifecycle_smoke.py` exercises real MCP stdio `analyze_migration`, `preview_migration` and `verify_artifact` on a **synthetic** NUnit SetUp that navigates, runs an explicit Loader mapping and assigns a source POM local to a fixture field. The generated code preserves executable target-side mapped table assertions and clicks; unknown Page Object methods remain blocked. Removing the Loader mapping must invalidate the field binding. Source-level field alias preservation remains `requires_review`; no false `FullyConvertedTests` increase.

A separate Chromium/NUnit fixture adds three real browser tests for SetUp-before-test navigation, initial-state restoration, and a missing-navigation negative control. CI now requires eleven executed, passing synthetic tests. This does not prove ArBilling setup, inherited NUnit hooks, browser origin, selectors or business behavior.

## Preview.15 — inherited NUnit fixture lifecycle

Core `0.1.0-preview.15` is consumed exclusively through versioned NuGet packages built from pinned Core main `8df82c3a2384f2597a61bb52221d605ed8a61e99`. The real MCP stdio regression processes a synthetic SDK-style project containing separate base, intermediate and derived fixture sources, then checks `analyze_migration`, `preview_migration`, `verify_artifact`, ordered SetUp/TearDown/OneTime hooks and partial-failure cleanup guards. A duplicate same-level setup must remain `partial`, produce `NUNIT_LIFECYCLE_SAME_LEVEL_ORDER` and an inconclusive setup. The reviewer never returns behavioral approval from matching source action counts.

The synthetic Chromium workflow requires **13 real NUnit tests**: eleven existing ComboBox/Loader/fixture tests plus two that exercise genuine NUnit inherited hooks and reverse teardown. Real browser execution here proves only the framework mechanics on synthetic fixtures; it is not an ArBilling E2E or source/target equivalence check.

Lifecycle methods on unavailable source bases, overrides, hidden methods, unpaired cleanup and conflicting target host configuration are conservatively blocked by Core. Exact NUnit failure paths, namespace SetUpFixtures and external app state still require target-specific review.

## Preview.16 — NUnit assembly and namespace SetUpFixture

MCP now consumes versioned Core `0.1.0-preview.16` pinned to main commit `e6de7b9262ee12339189e8b7d6b30c43bae9faef` on both Linux and Windows. The `scoped_setupfixture_smoke.py` real JSON-RPC stdio test uses three independent, fictional `SetUpFixture` source files (assembly-global, parent namespace, nested namespace), two test fixtures and a synthetic adapter. It checks `analyze_migration`, `preview_migration`, `verify_artifact`, distinct generated scope artifacts, target namespace containment, one-time action nonduplication, and source-backed dependency TODOs. Same-scope duplicates and a lost OneTimeTearDown must block before suite setup effects run.

An independent synthetic NUnit/Playwright .NET test project in `experiments/synthetic-setupfixture` executes three real Chromium tests with assembly, parent and nested namespace `SetUpFixture` hooks and a similarly prefixed sibling namespace. It verifies one-time setup, inverse cleanup and actual browser interactions without a customer backend. The existing synthetic ComboBox 13/13 test suite remains separate. Real ArBilling compilation, browser execution and observables remain `not_run` for this milestone.

## Preview.17 — complete generated NUnit target assembly

MCP consumes the **versioned Core `0.1.0-preview.17`** package from pinned Core main SHA `b0bde62986fc8c4dd8bfcb1b516be70c30e2807a`, never from an MCP `ProjectReference`.

The new read-only tools are:
- `plan_target_assembly(source, config?, expectedAnalysisId?, expectedCandidateId?)`: returns an exact content-addressed source/target assembly manifest with generated fixture and SetUpFixture paths, CSProj path and SHA-256 hashes, source scope diagnostics, and `ready_for_build` vs `blocked`. It does **not** dump private generated source, write files or run code.
- `verify_target_assembly(source, targetRoot, expectedAnalysisId, candidateId, config?)`: checks every target `.cs`, the generated `.csproj`, SHA manifest, explicit MSBuild `Compile Include` closure and scoped fixture dependencies in an existing workspace target directory. Missing/extra or modified files are rejected. `build` and `nUnitRuntime` remain `not_run`.

To actually create, compile or run a generated test assembly, use the **explicit Core CLI** with `plan`, `generate --build --test`, and `verify --build`. For safety MCP remains read-only and never executes MSBuild or application tests on its own.

The Linux/Windows MCP CI regression uses a **separate, trusted Core AssemblyCli** to materialize one public synthetic target project, then runs real `dotnet build` and two NUnit tests. MCP verifies the same generated content hash without inheriting CLI runtime claims, rejects a missing namespace `SetUpFixture`, and rejects injected `Unlisted.cs`. The existing 13 + 3 synthetic Chromium/NUnit workflows remain independent. This is synthetic framework validation; private ArBilling builds and business observables are not run.

## Preview.18 — multi-project NUnit solutions

MCP consumes versioned Core `0.1.0-preview.18` pinned to merged Core main SHA `793c19e2f24190d0c255cfa85d72ef630a91810f`, on Linux and Windows; no source `ProjectReference` into Core.

Read-only tools:
- `plan_target_solution(source, config?, expectedSourceTreeHash?)`: returns the complete source-backed multi-project graph, target `Migrator.Generated.slnx`, per-project target `.csproj` paths, distinct NUnit assembly and `SetUpFixture` inventories, original/rewritten library `ProjectReference` edges, per-file SHA-256 and a content-addressed manifest. Does not send generated C# source bodies or execute commands.
- `verify_target_solution(source, targetRoot, expectedSourceTreeHash, expectedPlanId, config?)`: verifies exact target files, hashes, `.slnx` membership, explicit `Compile Include` inventory and `ProjectReference` graph, including per-test-assembly `SetUpFixture` closure. Build/NUnit status remains `not_run`.

For actual materialization and test execution, use the separate **trusted Core CLI**:
```bash
dotnet run --project Migrator.AssemblyCli -- solution-plan ./solution --config ./adapter.json
dotnet run --project Migrator.AssemblyCli -- solution-generate ./solution ./fresh-target --config ./adapter.json --build --test
dotnet run --project Migrator.AssemblyCli -- solution-verify ./solution ./fresh-target --config ./adapter.json --build
```

CI performs a real MCP stdio plan, separately runs Core CLI to generate a synthetic 3-project graph (two independent NUnit assemblies and a shared library), executes `dotnet build` and requires two passing NUnit TRX reports (1/1 per assembly), then uses MCP to verify hash-locked contents without claiming it ran the tests. Negative MCP checks reject stale source SHA, missing `SetUpFixture`, unexpected C# file and an NUnit test-project-to-test-project reference. Full Core smoke additionally checks transitive shared libraries and multi-project cycles. All source is fictional. Real ArBilling .NET solution compilation/browser/observables remain unrun.

## preview.19 — fail-closed NUnit Ignore/Explicit safety

MCP now consumes Core `0.1.0-preview.19` from pinned Core revision `461436a5c1fcedae99ee4efada8329add07ba0a4` through versioned NuGet packages (no source ProjectReference). An original fixture or test with `[Ignore]`, `[Explicit]` or an `Ignore`/`Explicit` named argument on NUnit case/fixture attributes is inventory-counted but blocked with `NUNIT_EXECUTION_GATE_REQUIRES_REVIEW`. This prevents a skipped/opt-in source test from becoming a runnable Playwright test merely because the renderer dropped its execution gate. Do not override it with mapping shortcuts; preserve and independently verify the original NUnit execution selection first.

Synthetic MCP stdio regression tests both an ignored fixture and an explicit data case on the packaged Linux and Windows tools. No customer source or private selector/configuration is included in GitHub or CI.
