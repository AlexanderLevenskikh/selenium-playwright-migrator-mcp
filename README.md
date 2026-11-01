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

The Linux/Windows MCP CI regression uses a **separate, trusted Core AssemblyCli** to materialize one public synthetic target project, then runs real `dotnet build` and two NUnit tests. MCP verifies the same generated content hash without inheriting CLI runtime claims, rejects a missing namespace `SetUpFixture`, and rejects injected `Unlisted.cs`. The existing 13 + 3 synthetic Chromium/NUnit workflows remain independent. This is synthetic framework validation; private customer-application builds and business observables are not run.

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

## Preview.20 — fast source graph preflight and explicit library packages

MCP consumes Core `0.1.0-preview.20` from pinned Core SHA `26fd8bd5b2773366e3811a537d6f2b4a3f0f79a6` (local versioned NuGet only, no Core source ProjectReference). `plan_target_solution` now validates all source projects, library dependencies and explicit approval profiles **before** expensive NUnit planning. A blocking graph returns `SOLUTION_NUNIT_PLANNING_DEFERRED`; no NUnit output is materialized and no build/runtime success is implied.

A reviewer can explicitly authorize *source-exact* literal shared NuGet dependencies using adapter JSON `TargetSolutionReviewedPackages: [{ SourceProject, Reviewed: true, Packages: [{ Id, Version }] }]`. IDs/versions must match source exactly; changes, floating versions, unsafe Selenium/NUnit/Playwright package profiles and unreviewed projects are rejected. The target csproj and project ledger include only approved packages. MCP remains read-only and never runs restore, build or tests on private sources. CI uses synthetic dependencies and tests both positive and fail-closed behavior on Windows/Linux.

## Preview.21 — accurate source inventory even when solution generation is blocked

MCP consumes Core `0.1.0-preview.21` at pinned main revision
`82edf421f0cd15eef99899315bd2f6cc6e3372c5`. Source project
`declaredTests` now reports the number of NUnit **method declarations** even
when `candidateId` is null because target generation was deferred.
The count does not expand `TestCase` data or imply generated/runnable tests.
The target solution schema is `migrator-target-solution/v1alpha3`.

Source-backed blockers found during fast graph validation include nested
`SetUpFixture`, assembly-level parallel scheduling, `Ignore`/`Explicit`,
dynamic `TestCaseSource` and xUnit. These must be verified or explicitly
resolved, not dropped or guessed. MCP remains read-only. CI uses synthetic
project graphs and real NUnit assemblies on Linux and Windows; no customer
files or business endpoints are used.

## preview.22 — explicit NUnit entry-project selection

The Core \`0.1.0-preview.22\` dependency is built from pinned Core commit
\`24562c224b04b99d1db7f21f902f2c3b3f215b5e\`, never from a cross-repo
\`ProjectReference\`. \`plan_target_solution\` now also returns a source-backed
\`scope\` object from the v1alpha4 manifest. For a mixed repository with
independent API NUnit assemblies or generator projects, select one or more
NUnit **entry .csproj** in adapter JSON:

\`\`\`json
{
  "SourceProjectName": "Synthetic",
  "TargetSolutionEntryProjects": ["UiTests/UiTests.csproj"]
}
\`\`\`

The engine includes the *complete transitive closure* of literal in-root
\`ProjectReference\` edges automatically. It explicitly records every
excluded project in \`scope.excludedProjects\`. Tests in excluded assemblies
are **not converted or counted**; once-per-assembly \`SetUpFixture\` scopes
must never be flattened or borrowed from excluded test assemblies.
Any missing/dynamic/out-of-root reference or reachable test-to-test reference
is a blocker, not a reason to ignore the dependency. Nested project ownership
remains blocked even when a nested project is outside the entry selection.

MCP remains read-only: the separate Core CLI executes any expressly requested
target build/test. A synthetic Linux/Windows protocol regression validates the
source scope, excluded project ledger, a real selected 1/1 NUnit assembly
build/TRX, hash-locked read-only verification and fail-closed references.
Existing unscoped independent 2/2 runtime remains covered. This is **not**
private product E2E or behavioral-equivalence evidence.

## Preview.23 — source-bound NUnit assembly parallel scheduling

MCP consumes Core `0.1.0-preview.23` from exact merged Core main
`c1a5ae32dc0fa7762100641d3f72d6c3230960b6` on Linux and Windows (local NuGet feed, no source
ProjectReference). The read-only `plan_target_assembly` and
`plan_target_solution` tools expose `assemblyScheduling`: original
source file/line, source attribute expression, and fully-qualified
emitted target expression. This evidence is also in the exact
content-addressed target manifest; the generated
`Migrator.Generated.NUnitAssemblyScheduling.cs` is explicitly compiled
into its **own** NUnit target assembly, not copied into shared libraries
or unrelated NUnit assemblies.

The planner accepts only deterministic NUnit assembly attributes
`Parallelizable`, `NonParallelizable` and `LevelOfParallelism`
with a conservative syntax whitelist. Aliased, computed,
conflicting/duplicate, fixture-level and test-level source policies
produce explicit blockers. Never change concurrency just to make a
test compile. The source/target assembly runtime behavior is not
proven by the static ledger; observe NUnit real scheduling separately.

CI uses fictional assembly policies in independently generated
NUnit projects: exact file-ledger verification, reflection-observed
attributes and actual `dotnet build`/NUnit TRX on Linux and Windows.
Real private product E2E remains `not_run`.

## Preview.24 — NUnit lifecycle source evidence

MCP `0.1.0-preview.24` consumes pinned Core `99fbfdc7601041fab1ceb16efe7c39ffb36e4c57`. The read-only `inspect_nunit_lifecycle(sourceDirectory)` tool returns a content-hashed Roslyn source inventory of inherited NUnit hooks, private helper calls, nested setup fixtures, scoped DI/browser resources, listener/retry code and log/screenshot/disposal obligations. Every hook/effect includes source path, line and a SHA-256 fingerprint; no original C# body is returned. The tool never performs build, NUnit or browser execution; their statuses remain `not_run`.

Core also supports a *standalone* namespace-scoped `SetUpFixture` with just `OneTimeTearDown`, proven through synthetic `dotnet build` and NUnit runtime. An invalid nested `SetUpFixture` is still blocked, and no automatic DI/listener/pooled-browser/cleanup migration is asserted. All GitHub CI inputs remain fictional. Real application behavior requires separately observed tests.


## Preview.25 — preserve reviewed nested NUnit cleanup-only scope

MCP consumes pinned Core \`0.1.0-preview.25\` commit
\`e0944506c5768fb67b85045fec545ec92128bce1\`, via versioned NuGet.
A real synthetic source/target NUnit 3.14.0 and 4.3.2 experiment showed
that a public nested \`[SetUpFixture]\` with \`[OneTimeTearDown]\`
**does execute once after its namespace tests**, even when one
\`[OneTimeSetUp]\` fails. It must not be deleted, moved into ordinary
per-test teardown, or automatically promoted to an assembly-global hook.

The new read-only \`review_nested_nunit_cleanup\` tool accepts an exact
source type and \`sourceTreeHash\` from \`inspect_nunit_lifecycle\`, a list
of concrete, explicitly reviewed target cleanup invocation statements
and optionally a **caller-supplied** source runtime evidence SHA-256.
It returns the original namespace, containing type, source method
SHA-256, source effects, target candidate relative path and SHA-256,
plus precise issues, **without returning generated C# or private source**.
A structurally accepted candidate is \`requires_review\`, never
behaviorally verified. No source/target build, NUnit, browser execution
or materialization occurs inside MCP.

Missing/extra/unsafe actions, source changes, competing namespace
SetUpFixtures, unsupported nested source state and invalid candidate
shapes fail closed. Core's separate API provides the reviewed exact
nested C# candidate for trusted local tooling: it retains the original
outer type and nested SetUpFixture class, rather than flattening
NUnit cleanup scope. The existing full project planner remains blocked
until real source/target behavioral evidence and integration are available.

CI uses only invented NUnit fixture, DI cleanup, trace and migration
examples. No proprietary ArBilling code, URLs, selectors or
credentials are ever committed to GitHub.

## Preview.26 — source-attested Playwright fixture DI and browser lifetime

The read-only \`review_playwright_fixture_lifetime\` tool cross-checks the
exact source \`inspect_nunit_lifecycle\` tree hash, source abstract fixture
and its nested cleanup-only \`SetUpFixture\`, plus a separate source DI
container. Every source effect must have one explicitly reviewer-attested
\`bindings\` entry with the exact source path/line/expression SHA-256,
target role and \`reviewed: true\`. Roles include fixture DI services,
typed BrowserContext/Page, navigation, page-backed storage, failed-test
browser logs, failure screenshots, NUnit listener/retry review,
per-fixture disposal and nested global provider disposal.

The underlying Core reviewer checks that the source DI container
actually uses a NUnit-class-name fixture key, GetOrAdd/CreateScope,
TryRemove/Dispose and global Clear/Dispose. It rejects absent,
duplicate, obsolete, wrong-role, stale and unchecked bindings. A
complete structural review returns only candidate path/SHA-256,
source infrastructure method evidence and \`requires_review\` —
**never runnable C# or claimed target behavior**. Core's separate
review API can render a typed \`Microsoft.Playwright.IBrowserContext\`/
\`IPage\` NUnit base + nested cleanup envelope. The application must
supply a real DI-backed bridge to a shared browser/provider, navigation,
storage, failure logs/screenshots, scope release, retry policy and
global cleanup. No browser/credentials/selector targets are invented.

A source Selenium WebDriver pool is **not** proven equivalent to
a Playwright BrowserContext lifetime. Evidence for target build,
NUnit execution, browser E2E and original application behavior all
remain \`not_run\` or \`not_verified\` in this MCP review. Source
compilation and synthetic test fixture runtime cannot replace actual
customer runtime. No customer source or source bodies are returned
or uploaded to public CI.


## Preview.27 — concrete, source-bound Playwright/DI runtime artifact

The Core \`ReviewPlaywrightFixtureLifetime\` plan now exposes two exact,
SHA-256-locked review artifacts on complete source-to-role attestation:
the NUnit fixture adapter and a **concrete** generated
\`MigratorPlaywrightDiBridge\` implementation. The MCP tool
\`review_playwright_fixture_lifetime\` returns both file paths and hashes
(\`candidate\` and \`concreteBridge\`) **without** their generated C# bodies.

The concrete bridge accepts an explicit singleton \`IBrowser\` and
\`IServiceProvider\` or launches owned Chromium through
\`LaunchChromiumAsync\`. It opens an isolated \`IBrowserContext\` and
\`IPage\` per NUnit fixture, tracks console/page errors and failure-only
NUnit-attached browser logs/screenshots, releases DI scopes, always closes
fixture contexts including page creation/disposal failures and disposes
owned browser/provider only from the original nested suite cleanup.
No application URL, selector, account, credentials or DI service wiring
is inferred.

Retry is **explicit**: each target test must carry \`[Retry(N)]\`
matching bridge configuration. NUnit retries can execute teardown for
intermediate attempts, unlike a private listener that may replay only
the test command; one-to-one retry equivalence is not established by
matching a numeric count. A missing retry annotation is rejected rather
than silently enabling different behavior.

The source-backed review is still \`requires_review\`. MCP never runs
NuGet, NUnit, browser or application code and never materializes target
artifacts. Core CI compiles real Microsoft.Playwright and
Microsoft.Extensions.DependencyInjection types with recorded
\`IBrowser\` fakes and real NUnit/TRX success/failure/retry/cleanup
checks; actual browser launch and private product E2E remain
\`not_run\`. GitHub CI contains only fictional synthetic inputs.


## preview.28 — real Chromium acceptance via pinned Core

The MCP Linux release CI now runs the **actual** source-attested
\`MigratorPlaywrightDiBridge\` emitted by pinned Core using
\`Microsoft.Playwright\` and a separately installed Chromium browser.
The smoke starts a fictional loopback-only HTTP web application, checks
the actual DOM, browser JavaScript console, per-fixture
\`IBrowserContext\`/\`IPage\`, isolated localStorage, real PNG screenshot
and console log artifacts, NUnit explicit retry and final failure, and
fixture context/service scope cleanup before the shared browser and
provider close. The \`scripts/assert_real_chromium_evidence.py\` guard
requires all three real-browser scenarios and independent TRX/runtime
status, and rejects mock-only or customer-E2E claims. Linux CI preserves
a separate synthetic-browser JSON artifact. Windows continues the full
self-contained MCP protocol and NUnit regressions; it does not claim
to run Chromium unless separately evidenced.

MCP itself remains read-only. Its
\`review_playwright_fixture_lifetime\` returns exact SHA metadata for
both the NUnit adapter and concrete runtime bridge; it does not
generate runnable code bodies, open Chromium or connect to customer
systems. A successful synthetic browser smoke does **not** approve
private application DI registrations, credentials, original Selenium
browser-pool behavior or custom listener/teardown equivalence.


## preview.29 — read-only NUnit execution and case-source inspection

The new `inspect_nunit_execution(source, config?)` MCP tool emits only
relative source file paths, line numbers, SHA-256 of syntax nodes, target
attribute expressions, static *case inventory*, run-state (runnable,
ignored, explicit), reasons where source literals provide them, and
precise `NUNIT_*` blocking diagnostics. It never runs source C#.
`analyze_migration` and `preview_migration` also expose additive
`nunitAttributes` and `nunitCases` properties with versioned
analysis/preview schemas. **Static case count is not a claim about
NUnit-discovered cases.** NUnit default/explicit runs and TRX are
independent evidence, produced only by explicit CI/test commands.

Safe literal-only local static `TestCaseSource` arrays and expression-bodied
properties can be lowered to `[TestCase(...)]` when parameter arity and
primitive type compatibility are proven. Unsafe/remote/inherited/dynamic
sources, custom metadata chains and unsupported fixture-named run gates
remain blocked. NUnit `[Ignore("reason")]`, `[Explicit("reason")]`,
and per-`[TestCase]` skip/explicit arguments are preserved when statically
verified. Never activate an ignored or explicit test to satisfy CI.

Core synthetic acceptance compares real source/target NUnit3 discovery,
TRX statuses, explicit selection, a deliberately failing explicitly
selected test, and separate NUnit4 source baseline on Linux and Windows.
MCP CI runs a real stdio protocol regression with fictional fixtures in
both OSes, with the NuGet package bound to a pinned Core Git revision.
Customer applications remain private and must be retested separately with its source
tree hashes; no private runtime evidence is inferred from the synthetic
pipeline.


For this release the CI package feed is built from immutable, already
merged Core Git commit `313e5ab0cac3f92b746d8aaab6cf7b3cfd902151`
and consumes version `0.1.0-preview.29` through NuGet, not a cross-repo
source reference. The Core synthetic NUnit adapter emits
`UnitTestResult outcome="NotExecuted"` even when TRX
`Counters.notExecuted=0`; case-level outcomes are authoritative.
Static-only MCP responses never claim this execution evidence.

## preview.30 P2 — typed Page Object action planning

`inspect_pom_action_plan(sourceDirectory, sourceType, sourceMethod,
expectedSourceTreeHash, sourceLine?, receiver?)` runs a bounded, read-only
Roslyn semantic review of one source method. It returns **relative path,
source line, SHA-256, symbol identity, receiver/return types, ordered
effect kinds, target statement hashes and explicit blockers**, without
returning source method bodies, selectors, URLs or target code.
`status=requires_review` is never a declaration of runtime equivalence;
`status=blocked` yields no executable target sequence in the corresponding
Core plan. Dynamic selector expressions, unverified helper calls and
branching/loops are blocked. An input SHA mismatch fails before planning.

The Core API `PlanPomActions` and trusted local
`Migrator.AssemblyCli pom-inspect/pom-plan ... --emit-target` provide
optional review-required target Playwright templates derived only from
literal Roslyn-bound Selenium navigation/locator calls, element click,
clear, SendKeys, finite WebDriverWait visibility, NUnit text/count
assertions and literal-index table row clicks. No invented selectors,
URLs or browser state. They are **not installed automatically** into
adapter config or executed by MCP.

P2 CI runs isolated synthetic Linux/Windows NUnit discovery/TRX and
real Chromium on a loopback HTTP application. Source-side NUnit controls
validate case discovery/run-state but are not a Selenium browser run;
target-side Playwright validates actual browser actions and cleanup.
Do not claim source/target business behavior parity from equal NUnit
case names or outcome counts.

MCP consumes `SeleniumPlaywrightMigrator.Application` as a versioned
NuGet package pinned to a verified Core commit. Never add a cross-repo
source `ProjectReference`, never upload customer source, test results,
selectors or logs to public CI.

## preview.31 P2 — bounded structured POM source actions

The read-only `inspect_pom_action_plan` now reports ordered
`controlFlowPath` on every source-backed effect, distinguishing
`root`, `helper:<method>@<line>`, `if:true@<line>` and
`if:false@<line>`. The output also carries Roslyn-bound source
method/property symbols, source return/receiver types, relative source
path/line/SHA-256, and target statement SHA-256. It does **not** include
any source/target code, selectors, URL literals, environmental settings
or executable code. The tool never edits or executes the customer
application.

Supported reviewed candidates are the narrow semantic subset:
same-class zero-argument private non-virtual helper inlining,
`if/else` with symbol-bound `FindElements(By.literal).Count`
comparison or string parameter vs literal (plus short-circuit Boolean
composition), real Selenium navigation/click/clear/SendKeys,
`WebDriverWait` with literal/constant timeout or a **source-enforced**
`timeoutMs` bound via a first-statement argument range check, and
NUnit `Assert.That(..., Is.EqualTo/GreaterThan/LessThan)` table/text
comparisons. All target statements remain opt-in and review-required
through trusted Core APIs/CLI. No arbitrary C# evaluation occurs.

A dynamic URL, unknown helper, unbounded dynamic wait, opaque condition,
loop, side effect, unsupported exception path or missing branch blocks
the **entire** proposed target sequence, with no active TODO presented
as migrated. A source bound is proven by its exact source code; a
guess about a positive timeout or retry count is not sufficient.

Public CI includes real Chromium tests against a fictional localhost
application and NUnit source-control versus target discovery/TRX on
Linux and Windows. The baseline suite uses NUnit/HttpClient, **not**
Selenium WebDriver, so matching case names/outcomes do not establish
Selenium/Playwright business parity. Private ArBilling is `not_run`
unless original source archives are present locally.

## preview.32 — source-backed typed POM helpers and bounded retries

The read-only `inspect_pom_action_plan` returns source lines,
SHA-256 identities, typed Roslyn method symbols, ordered effects
and `controlFlowPath`, plus a redacted `retry` count summary
(`boundedLoops`, `sourceBackedTerminalRethrows`). It does not
return selectors, URLs, C# source bodies or executable Playwright
statements. `status=requires_review` is **not** behavioral approval.

The closed source-mapped subset now expands an immediate or nested
nonvirtual same-class private POM helper with **at most one string
argument**, only when Roslyn resolves that argument to a source
parameter or literal. Argument substitution edits C# identifier
tokens, never string literals, URL values or selector text.
Every reached helper must be fully translated. Unknown calls,
recursion, overloaded ambiguous dispatch and side effects block
the entire method rather than dropping a step.

A strictly bounded Selenium retry is accepted as a review-required
template only with an AST-proven `for (var attempt=0;
attempt<2; attempt++)`, a *single* `WebDriverWait.Until`
operation, `break` on success, exactly
`catch (WebDriverTimeoutException) { if (attempt == 1) throw; }`
on failure, and **2–4 literal attempts**. Source-derived wait
timeout is retained. Catch type and polling/actionability may differ
in Playwright, so Chromium success/failure validation is mandatory
before an agent may propose applying the mapping. Any changed
exception handler, larger/unbounded attempt count, extra body effect,
condition or dynamic wait remains blocked.

Public synthetic Core Linux/Windows CI now tests actual Playwright
Chromium against loopback-only HTML, including source-backed
nested ComboBox and source-bounded retry, selected terminal failure,
NUnit control vs target discovery/TRX and browser cleanup. The
source test is a synthetic NUnit/HttpClient control, *not*
Selenium WebDriver behavioral evidence. No customer archives,
selectors or private logs are uploaded to GitHub.

**Adapter integration caveat (preview.32):** source-backed zero-argument Page Object methods named like waits can be recognized by the Selenium frontend as `WaitForAction`. Use an explicit exact-source-call reviewed `MethodMapping` to apply the verified candidate; a `ParameterizedMethodMapping` for such a wait is not guaranteed to override the conservative `WAIT_REQUIRES_STATE_ASSERTION` fallback. This is validated in Core's real parser/adapter/renderer synthetic regression. The Playwright .NET timeout catch is `System.TimeoutException`, not an invented `Microsoft.Playwright.TimeoutException`. Both behavioral equivalence and completion remain review-required.


## preview.33 — cross-file typed POM and detached Loader (review only)

This MCP tool consumes \`SeleniumPlaywrightMigrator.Application
0.1.0-preview.33\` from an exact Core commit pinned in
\`.github/workflows/mcp-ci.yml\` (no cross-repository ProjectReference).
\`inspect_pom_action_plan\` now reports source-line/SHA and ordered typed
effects for private partial-class helper chains with up to two independently
bound source literal/parameter \`string\`/\`int\` arguments, numeric
parameter guards, \`!\` and short-circuit conditions. No helper name is
treated as proof of its implementation.

One new supported source wait is a finite Selenium
\`WebDriverWait.Until(d => d.FindElements(By.literal).Count == 0)\`.
It yields a \`detached_wait\` **review-required** effect only when the
actual lambda driver receiver is proven; \`!FindElement(...).Displayed\`
(hidden but still present), an unrelated captured driver, dynamic
selectors, retry catch filters and unknown side effects remain blocked.
Do not substitute Playwright auto-wait for business-state semantics.

Synthetic MCP stdio Linux/Windows tests assert no raw selectors, C#
target statement or adapter candidate escapes the read-only tool.
Core's Linux/Windows Chromium and NUnit source-control tests are
separate evidence; the control suite uses HttpClient and does not prove
full Selenium-to-Playwright browser equivalence. Private ArBilling
is not included in public CI. No automatic mapping approval.


## preview.34 — actual Selenium WebDriver browser parity (separate Core CI)

Core preview.34 adds *real* Selenium WebDriver + ChromeDriver and Playwright .NET
synthetic NUnit runs on the same Chrome for Testing executable and localhost
app. This supersedes the old HttpClient stand-in **for those cases only**:
positive browser DOM/event/ComboBox/Loader/retry snapshots are compared, and
selected actual terminal timeout exceptions and screenshots are tested.

The **mandatory negative counterexample** is a changing DOM: an immediate
source NUnit FindElements.Count assertion fails, while Playwright
Expect(locator).ToHaveCountAsync retries and passes. Thus structurally
source-backed assertion mapping is not automatically equivalent. Agents must
treat this as a review blocker, not report a successful complete migration.
The MCP protocol remains read-only, redacted and source-only, even if Core
browser CI passes. No browser execution or original selectors are returned
over MCP, and no automatic adapter promotion is permitted.

The preview.34 MCP package is 0.1.0-preview.34, using exact Core SHA pinned
in both Linux and Windows jobs of the MCP workflow. The synthetic read-only
stdio regression checks assertion provenance, target redaction, source
immutability, unsafe side-effect blockers and stale hash rejection.
Private customer E2E remains not_run; source-loop retry attempts are not
independently instrumented at runtime.


## preview.35 — source-backed immediate Count/Text assertion facts

Core preview.35 replaces auto-retrying Playwright \`ToHaveCountAsync\`
for NUnit Count \`EqualTo\` with one \`locator.CountAsync()\` snapshot
and immediate NUnit EqualTo. GreaterThan and LessThan remain single-read.
For typed \`IWebElement.Text\`, source projections take one DOM
\`EvaluateAllAsync<string>(...innerText...)\` read instead of
auto-retrying \`ToHaveTextAsync\`. All candidates remain
\`requires_review\` and have \`CanAutoApply=false\`.

In the public same-Chrome real Selenium/Playwright controls, a delayed
Count update and changing visible text must now fail on BOTH engines.
Two known text gaps remain: hidden Selenium rendered text versus DOM
innerText, and different exception types for missing elements. These
are **not** behavioral equivalence. The MCP reply reports only
non-sensitive source assertion counts and explicit unresolved parity
statuses; it does not return target code, selectors or source bodies.
Only a trusted local Core API with \`--emit-target\` may reveal a
reviewable draft. MCP is read-only and executes no user/browser code.

The package is \`0.1.0-preview.35\` from one exact Core commit pinned
in Linux and Windows CI, never a cross-repository ProjectReference.
Private ArBilling remains not_run.


## preview.36 — rendered-text subset and honest MCP review boundary

Core preview.36 implements a narrow **review-only** candidate for
Selenium \`IWebElement.Text\`: a one-shot Playwright DOM query checks
CSS display:none and visibility:hidden/collapse on the source element
and its ancestors, then returns \`""\` for measured hidden cases.
It collapses ordinary spaces/tabs in the measured normal-white-space
subset. For \`pre\`, \`pre-wrap\` or \`break-spaces\`, the candidate
explicitly throws a review marker rather than guessing the Selenium
rendered-text algorithm. Missing elements fail, but Selenium
NoSuchElementException and PlaywrightException are not interchangeable.

Core CI runs **actual** C# Selenium WebDriver and Playwright .NET on
the **same Chrome for Testing binary** against a public localhost test
app on Linux and Windows. The positive hidden/normal-whitespace cases
are validated against original Selenium. The preserved-white-space
control intentionally remains source Passed vs target Failed, with
manual review required; no auto-apply approval is introduced.

The MCP read-only tool reports only source action counts and
fixed, non-sensitive parity limitations. It does **not** return
selectors, source bodies, generated target code or call the browser.
No privately uploaded ArBilling tests or credentials are used.
Versioned \`0.1.0-preview.36\` MCP consumes the exact Core SHA
pinned in the Linux/Windows workflow without ProjectReference.


## preview.37 — source-only pre/pre-wrap and Unicode Text evidence

Core preview.37 extends the bounded \`IWebElement.Text\`
\`EvaluateAllAsync<string>\` source candidate to simple direct-leaf,
single-line CSS \`pre\` and \`pre-wrap\` and the measured Unicode subset:
NBSP to regular space, U+200B zero-width removal, and unchanged
combining characters. **These claims are based solely on specific
public synthetic real Selenium/Playwright Chromium comparisons.**
The candidate still requires review, is not runtime-certified by
MCP and is never auto-applied. No Selenium dependency or business
logic is guessed in the target.

Unknown CSS \`break-spaces\`, multiline/mixed pre, text-transform
and unverified Unicode spacing deliberately fail closed in the
draft. Missing-element exceptions are not identity-equivalent:
Selenium NoSuchElementException vs PlaywrightException. A matching
normal NUnit result is insufficient to approve a migration that
catches the source exception.

The MCP \`inspect_pom_action_plan\` response only exposes fixed
source-only flags, source SHA/line and effect counts, **never raw
selectors, private source or generated target C#**. Linux/Windows
stdio protocol tests verify this boundary, unknown effects and
stale source hashes. The independent versioned MCP package consumes
exact Core SHA via NuGet, without ProjectReference, version
\`0.1.0-preview.37\`. Private ArBilling: not_run.


## preview.38 — strict source-bound NoSuchElement and WebDriverTimeout catches

MCP \`inspect_pom_action_plan\` reports **read-only, source-only** exception
facts from the Core Roslyn projector. A syntactically and semantically
proven single immediate \`FindElement(...).Text\` NUnit assertion may
have a typed \`catch (NoSuchElementException)\`, and a finite
\`WebDriverWait.Until\` may have a typed
\`catch (WebDriverTimeoutException)\`. The catch must contain a single
source-backed immediate count assertion or a bare \`throw;\`.
This *does not* mean Selenium and Playwright external CLR exception
types are equal. They are not: NoSuchElementException ->
PlaywrightException, WebDriverTimeoutException -> System.TimeoutException.
Consequently, **outer source catch chains require manual review**.

The Playwright missing-element catch is guarded by the exact emitted
JavaScript error marker. It must not swallow unrelated Playwright errors.
A broad catch, catch filter, catch variable read, arbitrary side
effects, multiple catches or an unproven click/wait must fail closed
with no generated active target. All candidates remain
\`requires_review\`, \`canAutoApply=false\`,
\`runtimeVerified=false\`.

The stdio tool emits only source path/line/SHA, effect kinds, bounded
counts and **fixed non-sensitive limitation strings**; no selector,
source method body, target C#, credentials or browser execution.
Linux/Windows synthetic stdio regressions check typed facts, blockers,
stale source rejection and no leakage. Core has independent real same-
Chrome Selenium/Playwright evidence for recovery, rethrow and non-
swallowed assertion errors. No private ArBilling tests run.
MCP \`0.1.0-preview.38\` consumes versioned Core Application NuGet
from exact Core SHA pinned in both OS CI (no ProjectReference).


## preview.39 — source-backed external TestBase/NUnit catches

In preview.38 a locally valid NoSuchElementException/Timeout
rethrow can still alter an **outer** NUnit test or TestBase catch,
because the Playwright target throws a different CLR type.
Preview.39 adds exact Roslyn source-symbol caller tracking across
the captured Page Object, TestBase, and NUnit methods. If a
caller chain has a relevant Selenium-specific, broad or filtered
catch, the complete Core action plan is **blocked**. The returned
blocker includes source path, line and SHA-256 of the caller catch,
but MCP exposes no source body or target statements.

The MCP \`inspect_pom_action_plan\` tool adds a strictly source-only
\`externalCatchChains\` summary: number of in-scope catch blocks,
unresolved call graph paths, and fixed scope limitations. It cannot
prove the absence of dynamically dispatched or out-of-scope callers.
\`noFindingsProvesExceptionParity=false\`, \`CanAutoApply=false\`,
\`RuntimeVerified=false\`; no additional browser/side-effectful
tool is provided. The entire original source tree remains unchanged,
stale source SHA is rejected and private selector text is redacted.

Public Linux/Windows stdio cases check typed Page→TestBase→NUnit
call chains, blocked external filters and rethrows, unrelated
unblocked cases, no private C# or target leakage. The Core
same-Chrome real Selenium/Playwright browser counterexample is
independent evidence of changed NUnit behavior if an external
handler were dropped. The comparison deliberately does not
auto-apply or synthesize an exception adapter. NuGet version
\`0.1.0-preview.39\` pins exact Core SHA on both platforms.
Private ArBilling remains not_run.


## preview.40-A — source-only external exception catch contract

Core now offers a separate, read-only, opt-in external exception catch
contract proposal for one exact Page Object method. All PlanPomActions
blocking behavior from preview.39 remains unchanged. A proposal requires
a single source-typed inner NoSuchElementException/WebDriverTimeoutException
rethrow, fully projectable FindElement.Text or finite WebDriverWait, one
symbol-resolved synchronous TestBase chain, and exactly one outer NUnit
catch with no filter/finally and no other actions.

The only output is a reviewed C# catch CLAUSE, never an invented test or
a general Selenium exception adapter. External filters, used exception
variables, broad/mismatched catches, additional actions, multiple
propagation paths, dynamic dispatch and rethrow beyond the boundary
fail closed. **Only empty external catches** can yield a reviewed
clause. Source-typed NUnit Count recovery is blocked because the
CountAsync snippet would require an unverified target async method
and a source-proven Playwright IPage receiver. An accepted empty catch
remains review-only and does not preserve external Selenium CLR identity.

MCP exposes inspect_pom_external_exception_contract as strictly
read-only source SHA/line and exception-type metadata. It deliberately
omits TargetCatchClause/source bodies/locators and can never run tests,
auto-apply a snippet, or certify browser parity. Linux/Windows stdio
tests independently check positive and negative source graphs, stale
snapshots and redaction. MCP package 0.1.0-preview.40 consumes versioned
Core NuGet from an exact pinned SHA on both operating systems.
Private ArBilling not_run.

## preview.41-A — exact async NUnit/TestBase Count and IPage evidence

`inspect_pom_external_async_count_contract` is a separate opt-in,
strictly source-backed and read-only proposal. It requires the exact
SourceTreeHash, one Page Object local typed NoSuch/Timeout rethrow,
one synchronous TestBase forwarder, an NUnit [Test] outer typed
FindElements.Count equality, and an explicitly named **real**
Microsoft.Playwright.IPage readonly field assigned from an IPage-typed
constructor parameter. Missing target binding, filters, additional paths,
dynamic dispatch and stale hashes are blocked with zero target.

Core locally proposes three review-only async Task method conversions
and a Count catch clause, never automatically edits code. MCP reveals
only source paths/lines/SHA, typed exception facts and required async
conversions; no target code, source bodies, selectors or browser execution.
Core CLI shows snippets only with explicit --emit-target. The historical
preview.40 API still blocks nonempty catches. Real Linux/Windows Chrome
parity requires separate Core CI evidence; same browser context and
constructor injection are not inferred from type identity. Private
ArBilling not_run. CI must re-pin both MCP platforms to merged Core main
before merge.

### preview.41 final Core pin and additional fail-closed case

Both MCP Linux and Windows workflows use exact merged Core main
`594ccf9cab2c4d871958c0c2eb56594cc628e146` (`SeleniumPlaywrightMigrator.Application` 0.1.0-preview.41).
A call from a constructor into the selected TestBase chain is not
captured as a normal method caller and must return `blocked`, zero
partial candidates. All proposals remain review-only; ArBilling not_run.



## preview.42-A — source-backed browser context ownership and NUnit cleanup

Before proposing a reviewed external async Count catch, run
\`inspect_pom_external_lifecycle_count_contract\` on an **exact**
captured source tree. Supply four explicit field identifiers:
pageField, contextField, browserField, playwrightField. Roslyn demands
actual Microsoft.Playwright assembly symbols, a single sealed NUnit
fixture, exactly one OneTimeSetUp/SetUp/TearDown/OneTimeTearDown
async Task method, and direct source assignments from browser →
context → page → SourcePage constructor → inherited TestBase field.
The Page Object must retain the same IPage/IBrowserContext in
readonly fields through exact constructor parameters.

TearDown must \`await IPage.CloseAsync\` with context.CloseAsync in
\`finally\`, and OneTimeTearDown must close browser with Playwright
Dispose in \`finally\`. Extra writers, missing/filtered handlers,
unresolved field paths, additional lifecycle methods and unknown
effects are **blocked**, with no partial candidates. This is
source attestation, **not** automatic NUnit fixture implementation:
failed OneTimeSetUp cleanup, arbitrary external assemblies, DI
container semantics and target runtime parity remain unverified.
The prior preview.40/41 endpoints are not widened.

MCP tool output is strictly read-only source field names,
SHA-256/line/type and proof flags. It never carries original source
bodies, selectors, target snippets or runtime/execution claims.
The trusted local Core CLI uses an explicit --emit-target flag.
Core public same-Chrome Linux/Windows browser jobs, not MCP metadata,
are responsible for real failure/success cleanup evidence. ArBilling
not_run. CI uses versioned NuGet 0.1.0-preview.42 and must pin final
merged Core main SHA on both OS before MCP merges.



### preview.42 final cross-repository acceptance
Both Linux and Windows MCP workflow jobs now pin exact **merged**
Core \`e937f078485e9c55b3a28d50fc73d0c2aaa47c3d\`
with versioned \`SeleniumPlaywrightMigrator.Application\`
0.1.0-preview.42 NuGet, never a ProjectReference. The new MCP
negative protocol controls block a second SourcePage constructor
invocation and unexpected Context.CloseAsync outside the attested
lifecycle; all partial candidates remain empty. Source/target browser
parity is only proven for public synthetic tests in Core.



## preview.43-A — source-only failure-atomic setup cleanup

New read-only \`inspect_pom_failure_atomic_count_contract\` requires a
captured exact SourceTreeHash, one fully qualified Page Object method,
and four **explicit** Page/Context/Browser/IPlaywright field identifiers.
It proves the exact Playwright source initialization in both NUnit
OneTimeSetUp and per-test SetUp occurs inside \`try\`, followed by
reverse-order null-guarded independent cleanup attempts and a terminal
bare rethrow in the sole \`catch\` block. Cleanup failures are deliberately
suppressed, so the original failure has precedence, even when two cleanup
attempts throw. No cleanup failure telemetry is inferred or transmitted.

The full older source-proven same-Context constructor, Page Object,
TestBase, NUnit teardown and exception contract is still mandatory.
Unknown hooks/receivers, missing guards, lost rethrows, extra effects,
stale hashes, and ambiguous call paths are blocked with **no partial**
candidate. The preview.40–42 tools remain unchanged. Source bodies,
selectors, target C#, exception messages and runtime browser operations
never leave MCP stdio. Trusted local Core CLI requires \`--emit-target\`
to reveal C# snippets for manual review. \`CanAutoApply=false\`,
\`RuntimeVerified=false\`. Failed external APIs might never return an
owned resource; cleanup of such internal resources is not proven.
Real success/failure and leak checks are limited to public Core
Chromium CI, not to the MCP result or private ArBilling.

During development the packaged MCP 0.1.0-preview.43 jobs use exact
temporary Core feature SHA. Re-pin both OS to merged Core main after
Core CI and evidence complete, run both MCP jobs again and merge
only if 2/2 jobs succeed on final HEAD.
