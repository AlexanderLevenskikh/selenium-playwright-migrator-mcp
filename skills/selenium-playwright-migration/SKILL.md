---
name: selenium-playwright-migration
description: Agent workflow for safe migration of Selenium C# NUnit tests to Playwright .NET using the Migrator MCP tools.
---

# Selenium → Playwright migration skill

Use for C# NUnit test suites. Do not claim xUnit source, Python, Java or full behavioral parity in this alpha.

## Workflow

1. Call `analyze_migration` with the narrowest source scope and optional project adapter config. Read `discoveryStatus`, `files`, `findings`, `declaredTests` and `parsedTests`.
2. Stop or narrow scope if discovery is `partial`. In particular, `MULTIPLE_FIXTURES`, `UNSUPPORTED_SOURCE_FRAMEWORK`, and `DECLARATION_COUNT_MISMATCH` must be resolved or reported; never treat the omitted tests as migrated.
3. For a reported finding, call `explain_finding` with the finding ID and expected analysis ID. Treat suggested next actions as review guidance, not proven mappings.
4. For supported inputs, call `preview_migration` with `expectedAnalysisId`. If stale, start fresh with analyze. Preview is read-only.
5. Inspect returned generated source and TODOs; do not invent selectors or infer project-specific helper semantics from names.
6. Make changes yourself only in an explicitly authorized target workspace. Preserve assertions, data cases and lifecycle behavior. MCP alpha never applies patches.
7. Call `verify_artifact` with the current analysis/candidate IDs to parse the generated draft. After editing the candidate in a separate target directory, call it again with `targetRoot` to verify those exact file bytes and obtain a **new candidate ID**. The target tree must contain exactly the expected .cs filenames and must not overlap a directory source scope.
8. For in-memory Roslyn compilation set `runCompile=true` and supply `referenceDlls` pointing to DLLs inside the workspace (an explicit empty list means only .NET framework references). Missing references result in `blocked`; an actual Roslyn compiler failure is `failed`. This is **not** a full MSBuild/product compilation.
9. Separately run real target-project build and, where available, tests/runtime checks using normal development tools. Record commands, exit codes and artifact identity.
10. Do not represent successful generation as successful compilation, nor compilation as behavior preservation. If no actual check was run, report `not_run`.
11. Summarize transformed tests, unresolved cases and independently observed verification results.

## Evidence labels

`syntax` means an AST match, `recognized` means a parser/adapter finding, and `diagnostic` means an error observed by tooling. None is itself a behavioral proof.

An edited candidate never inherits a previous successful syntax or compilation result. Runtime and observables always remain `not_run` in this MCP alpha.\n\nNever suppress unsupported actions just to improve completion metrics. Do not turn TODO-only generated files into successes. Do not fabricate JSON PASS results or reuse evidence after any source/config/target change.

## Existing Playwright NUnit input (preview.3)

When analysis returns `ALREADY_PLAYWRIGHT_SOURCE`, treat the project as **already in the target format**. Do not call migration preview expecting translated code, do not apply synthesized edits, and do not count this as a failed Selenium migration. Recommend independent target-project build/test and source-focused code review. `MIXED_SELENIUM_PLAYWRIGHT_SOURCE` requires choosing a Selenium-only source scope before migration. These are conservative source-framework findings, not build or browser verifications.

## POM navigation and LocalStorage mapping (preview.5)

- `POM_NAVIGATION_REQUIRES_MAPPING` means the source `Navigation.Open*Page()` returns a Selenium Page Object. Inspect its implementation (including URL and factory) before adding an explicit `Methods` mapping. The parser now retains the assignment result variable; only an explicit target declaration will bind it. Mapping a URL alone must NOT unblock downstream project-specific POM members.
- `LOCAL_STORAGE_REQUIRES_MAPPING` means a source storage helper (Clear/SetItem/RemoveItem/SettingPeriod) needs a verified Playwright equivalent. Check browser origin, pre-navigation ordering, state lifetime and value serialization before choosing `Page.EvaluateAsync`, `Page.AddInitScriptAsync` or context storage state. Do not blindly map a Selenium JavaScript helper to a Playwright call.
- A preview with rendered TODOs must have `FullyConvertedTests` reduced accordingly. Build/test passes never override incomplete transformation status or missing runtime observables.

## Grounded selector mapping

When `POM_NAVIGATION_REQUIRES_MAPPING`, `UNRESOLVED_SYMBOL` or table/selector TODOs dominate, call `inspect_pom_sources` on the explicit source directory, with relevant `pageTypes`. Examine the returned `predicates`, `helperSourcePath`, `sourceLine` and `sourceTreeHash`.

Only transfer `proposedPlaywrightExpression` into an explicit `UiTargets` mapping after checking source selector extension semantics, the actual DOM, the relevant Page Object's context, locator uniqueness and the downstream control method's side effects. Keep `requires_review` proposals out of generated executable tests until validated. For `LocalStorage`, verify origin and pre-navigation timing; discovering a key name does not prove a safe browser-storage rewrite.

This tool never applies mappings, compiles a project or executes test/browser behavior.

## Table operations

For source `Items.ElementAt(N).Click()`, check that a reviewed locator mapping produces a real `ClickAsync()` in the target, not only a locator variable. For a `TABLE_ROW_OPERATION_REQUIRES_MAPPING` finding, inspect the complete source chain (including assertions and terminal operations) before proposing a target statement. Never delete the assertion or count the method as fully converted because the generated test compiles.

## Complex POM and storage call paths

Before mapping `InputAndSelect`, `ValidateLoading`, `SetBeginDate` or similar helpers, inspect `helpers[].orderedCalls` and `controlFlow`: preserve all clicks, inputs, confirmations, waits and assertion/failure paths. Follow any `isReachablePrivateHelper` records (for example a blur helper). Never replace retry-and-reload with one wait merely because the method contains a visibility check.

Review `storageAndNavigationFlows`: `before_first_navigation` and `setup_before_test` storage writes require explicit browser-origin planning. No automatic `Page.EvaluateAsync` or `AddInitScriptAsync` substitution is authorized by lexical source evidence alone. Reinspect if `sourceTreeHash` changed.

Source `ExecuteJs`/`ExecuteJavaScript` and `EvaluateAsync` calls inside reachable private helpers now carry the `javascript_source_execution` review flag. Inspect the actual script and origin; do not silently replace or drop side effects because the public helper name sounds like a simple blur.

## Review candidate POM Methods mappings

For a selected source POM method, obtain its source hash and line from `inspect_pom_sources`. Draft **all** required target C# actions/expectations, then call `review_pom_mapping` with the unchanged hash and proposed concrete statements. Resolve every `missingObligations` finding; do not delete source assertions, retries, input steps or storage writes to get a shorter template.

`rejected_incomplete` means the candidate is missing a required effect/order; `blocked` means invalid/TODO target or ambiguous source. `requires_review` only means the obvious operation-category omissions were not detected. It NEVER authorizes skipping DOM locator, argument matching, browser origin, authentication or runtime observable checks. After any source change, rerun `inspect_pom_sources`; evidence is stale.

## Preserve source argument uses

When mapping multi-action helpers, the same parameter may feed both `FillAsync` and menu selection. Review `parameterFlows` to ensure every meaningful source argument occurrence is represented in target effect/filter calls. A hardcoded filter or a C# string with double-escaped CSS attribute quotes must not be accepted simply because syntax and click counts pass. DOM and timing still require independent verification.

## Preserve table assertions and custom Loader retry paths

For table sources `Items.ElementAt(N).Text.Get().Should().Be` and `Contain`, use inspected and reviewed root/row selectors via `UiTargets`; confirm emitted `ToHaveTextAsync` versus `ToContainTextAsync` semantics. If `TABLE_ASSERTION_REQUIRES_SETUP_REVIEW` appears, the test is incomplete despite its assertions being executable: complete the original fixture navigation, Page Object initialization and Loader paths separately.

For `Loader.ValidateLoading()`, inspect source control flow and only supply an exact zero-argument `Methods` mapping that preserves the bounded retries, reload side effects, visible/hidden state checks and failure path. The exact mapping overrides the generic wait fallback, but a green syntax test does not establish timeout equivalence. Use `System.TimeoutException` for Playwright .NET wait timeouts; verify the compiled target. Do not map the source retry loop to one happy-path wait and call the migration complete.


## Review retry and negation before accepting the test (preview.12)

- Never map source `Should().NotContain(expected)` into `ToHaveTextAsync` or a positive `ToContainTextAsync`. With an explicitly reviewed row mapping, retain index `Nth(N)` and use `Expect(locator).Not.ToContainTextAsync(expected)`; if source setup is not resolved keep `TABLE_ASSERTION_REQUIRES_SETUP_REVIEW`.
- For `Loader.ValidateLoading()`, inspect the actual source implementation and its reachable private helpers, not the name. `review_pom_mapping` counts state getter calls, loop exit, retry count updates, and checks for broadened catches, changed numerical retry-guard operators and conditional reload placement. A review that returns `requires_review` still does **not** establish matching exception types, timeouts, DOM state, backend recovery or browser behavior.
- Check wrong-value behavior in synthetic Chromium tests as separate negative controls. Preserve four evidence dimensions (`syntax`, `compile`, `runtime`, `observables`) and mark each `not_run` where applicable. Never suppress TODO to inflate `FullyConvertedTests`.

## Source-backed retry evidence (preview.13)

For Loader/retry POM helpers, compare immutable literal numeric limit declarations, the actual failure guard, conditional navigation side effects including literal JavaScript `window.location.reload()`, and every explicit `Visible.Wait().EqualTo(true/false)` expectation. A target `WaitForSelectorState.Visible` never preserves a source `EqualTo(false)`; mapping review rejects inversions. Treat an unspecified target wait state as unproven, even when action counts match. Run `inspect_pom_sources` and `review_pom_mapping` on the exact private source tree, not just a synthetic fixture. The protocol's `requires_review` means the structural ledger is a candidate, **not** accepted behavior.

## Fixture Page Object alias / lifecycle policy (preview.14)

For source `[SetUp]` patterns such as `var pagef = Navigation.OpenCatalogPage(); ...; page = pagef;`, the migrator can preserve the source Page Object identity relationship without creating a fake target Page Object. The navigation must have an explicit mapping that actually navigates `Page`, and all intervening source operations using the result must also be mapped. The renderer allows only separately grounded `Page.Locator(...)` / `Page.GetBy...` actions through a fixture alias. An unknown `page.*` helper stays blocked.

Every such alias has `FIXTURE_PAGE_ALIAS_REQUIRES_REVIEW` until the actual target setup, navigation, browser state and source POM lifetime are verified. Extra `SetUp`, `OneTimeSetUp`, `TearDown`, and `OneTimeTearDown` hooks are surfaced as unsupported instead of ignored; do not delete these TODOs to improve completion. Inherited lifecycle hooks remain a separate review boundary. Run actual target `dotnet build` and E2E after generated/edited source verification; static success cannot establish behavior.

## Inherited NUnit lifecycle source ledger (preview.15)

Inspect the complete Roslyn source class hierarchy before accepting inherited `SetUp`, `TearDown`, `OneTimeSetUp` or `OneTimeTearDown`. Core renders at most one hook of each kind in the generated fixture: base-to-derived setup, derived-to-base cleanup, reached-level guards for partial setup failures, and nested `try/finally` for cleanup. Review all `NUNIT_LIFECYCLE_*` markers, especially unknown base classes, hidden/overridden methods, multiple same-kind methods in a single class and invalid signatures. An ambiguous plan generates an inconclusive NUnit SetUp instead of a fake successful test.

A syntactically valid or compilable lifecycle has `NUNIT_LIFECYCLE_REQUIRES_REVIEW` until actual NUnit target execution confirms failure paths, per-test state, external `SetUpFixture` scope and browser observables. Do not suppress markers or transfer a source lifecycle to xUnit without an explicit target design. Inherited lifecycle currently does not support the experimental IR V2 rendering path, which fails closed.

## Namespace/assembly SetUpFixture scope handling (preview.16)

NUnit `[SetUpFixture]` methods are **once per target assembly/namespace**, not per migrated test. `analyze_migration` must discover each source SetUpFixture even when its file has zero test methods. `preview_migration` generates a distinct target SetUpFixture class in the original namespace (no automatic `.Playwright` suffix), and dependent test fixtures preserve the namespace nesting. Migrate the full source suite, not an isolated test file, and include each separately generated scope class in the same target NUnit assembly. Never paste its OneTimeSetUp/OneTimeTearDown statements into each test's setup.

Review `NUNIT_SETUPFIXTURE_DEPENDENCY_REQUIRES_REVIEW` and `NUNIT_SETUPFIXTURE_SCOPE_REQUIRES_REVIEW`. Multiple setup fixtures in one scope, nonpublic stateful classes, illegal per-test hooks, unresolved or Page-dependent operations and changed namespaces are blockers. A missing OneTimeTearDown mapping must block before the setup starts; do not report a passing test first and fail only in cleanup. A scoped setup cannot safely use the Playwright `Page` property because NUnit SetUpFixture is independent of individual PageTest instances.

Source inventory and generated C# syntax are necessary evidence. Target assembly compilation, actual once-per-scope NUnit execution, setup-failure handling, runtime and application observables must each be independently checked. No unsupported scope is ever accepted by reducing TODO counts.

## Full target assembly artifact and completeness (preview.17)

After reviewing `preview_migration`, invoke `plan_target_assembly` on the entire **source SDK project root**. Confirm `ready_for_build`, exact parent `analysisId`/`candidateId`, all separately generated `[SetUpFixture]` files (including global and nested namespace scopes), and the deterministic `Migrator.Generated.Tests.csproj` with explicit `Compile Include` items. Do not treat individual migrated test files as a complete NUnit project.

Use the Core `Migrator.AssemblyCli` explicitly for atomic materialization into a **new target directory outside source**. The `plan` operation is read-only; `generate --build` runs real dotnet build; `generate --build --test` also runs NUnit only with explicit approval and requires an actual nonzero, fully passing TRX. No implicit target-file discovery, package code injection, blind overwrites, or side-effectful MCP calls. Re-run `verify_target_assembly` to confirm the target file set and content-addressed manifest. If even one scoped SetUpFixture or Compile item is missing, stop: a passed isolated file compilation is not assembly completion.

`build_passed_review_required` and `runtime_passed_review_required` are still **not** source/target business equivalence. Real product authentication, DOM selectors, Page Object setup, browser state and observables need separate E2E evidence. Never upload private source/config, generated selectors or credentials to public GitHub CI.

## Multiple NUnit project assemblies and shared libraries (preview.18)

A multi-`.csproj` source is **not one NUnit assembly**. Invoke `plan_target_solution` on the root of the entire source graph, inspect every source/target `ProjectReference` and the `kind` of each generated project. Every NUnit source project must have a distinct target NUnit assembly with its own assembly-global `SetUpFixture`. Target-safe shared libraries remain separate library projects, compiled from source-backed unchanged code with explicit references; they must not carry NUnit test lifecycle or Selenium driver dependencies.

Confirm the exact `.slnx` project inventory, content hashes, `Compile Include` entries, and root/namespace scope boundary before accepting `ready_for_build`. Resolve blocked cycles, missing/outside references, test-project-to-test-project references, duplicate assembly IDs, nested project ownership, dynamic MSBuild/imports or unsafe external packages rather than silently dropping them. A test that compiles outside the intended assembly is not an equivalent NUnit test.

MCP `plan_target_solution` and `verify_target_solution` are read-only. Only the separately trusted Core `Migrator.AssemblyCli solution-generate --build --test` can create a new target solution and execute compilation and per-assembly NUnit TRX checks. Both stages are opt-in and all source projects are re-hashed before final results. A successful NUnit run is `runtime_passed_review_required` until real business/browser observables and production credentials have been independently reviewed. Never upload private Selenium or target project output to public CI.

## NUnit execution gates (preview.19)

If `analyze_migration` reports `NUNIT_EXECUTION_GATE_REQUIRES_REVIEW` for source `[Ignore]`, `[Explicit]` or named skip/opt-in NUnit data-case attributes, stop migration of the affected fixture. Never remove or silently discard the source execution gate: that could enable a test previously skipped or require explicit opt-in. `Preview` intentionally emits **zero runnable files** for such a blocked fixture. Check project-wide inherited attributes and dynamic `TestCaseData` cases manually as well; this syntax-level safety guard is not a complete NUnit semantic evaluation. No compiler or browser passing result can override the original execution-selection requirement.

## Reviewed shared NuGet dependencies and early project-graph validation (preview.20)

Before attempting full multi-project migration, invoke `plan_target_solution` and inspect all source graph issues. If `SOLUTION_NUNIT_PLANNING_DEFERRED` appears, the planner deliberately skipped resource-intensive NUnit generation: fix the source graph first, **not** the missing output files. A shared library with literal NuGet packages needs an explicit `TargetSolutionReviewedPackages` adapter JSON section with source-relative `SourceProject`, `Reviewed: true` and **exact source** `Id` / pinned `Version` values. Only approve after source/target dependency and package trust review. The approval is config-hashed and will be invalidated if package IDs or versions change. Never add broad approvals, fake packages or browser/test-framework dependencies to make the plan green. `ready_for_build` is still not dotnet build, NUnit runtime or behavioral equivalence. Keep customer adapter files and source out of public GitHub/CI.

## Preflight source test count and NUnit contract (preview.21)

With `plan_target_solution`, report `declaredTests` and `candidateId` separately.
A nonzero source declaration count with null candidate means **source tests
found, target not generated**. It is never a success or executable fixture.
If fast source preflight reports
`SOLUTION_NESTED_SETUPFIXTURE_UNSUPPORTED`,
`SOLUTION_ASSEMBLY_SCHEDULING_REQUIRES_REVIEW`,
`SOLUTION_NUNIT_EXECUTION_GATE_REQUIRES_REVIEW`,
`SOLUTION_DYNAMIC_TEST_DATA_REQUIRES_REVIEW` or
`SOLUTION_UNSUPPORTED_XUNIT_SOURCE`, inspect the original NUnit structure,
assembly-level parallel scheduling, skip gates, and data-provider lifetime.
Do not flatten one-time hooks into per-test code, switch test frameworks
silently, drop skipped cases, or infer data from method names.
Each source graph scope and adapter hash must be rechecked before any build.

## Explicit project-entry scope for mixed solutions (preview.22)

If a source repository includes unrelated API tests, generators or tooling,
create a *reviewed* adapter with \`TargetSolutionEntryProjects\` containing
normalized relative paths to the intended NUnit test project(s). Call
\`plan_target_solution\`; confirm \`scope.entryProjects\`,
\`scope.includedProjects\`, \`scope.excludedProjects\` and all
\`ProjectReference\` edges. Review exclusions explicitly: they are out of
scope, not completed tests. Never remove a required dependency or an NUnit
\`SetUpFixture\` merely to make the plan green. A test-to-test reference
in the transitive closure is a blocker, not permission to collapse assembly
boundaries. Re-run plan after any adapter/source change. The source-tree hash
covers the entire workspace, while the adapter hash binds exact entries,
so target materialization/verification must use current IDs.

Only the trusted Core CLI performs \`solution-generate --build --test\`.
Run it with deliberate approval in a separate non-overlapping target tree;
verify per-assembly TRX counts and real browser/product observables
independently. MCP planning alone is not compilation, runtime or behavior.

## Assembly-level NUnit scheduling provenance (preview.23)

Before accepting a target NUnit assembly, inspect the returned
`assemblyScheduling` ledger from `plan_target_solution` or
`plan_target_assembly`. Verify the source file, line, original expression,
target expression, owning NUnit project, and generated compile item
`Migrator.Generated.NUnitAssemblyScheduling.cs`. The exact target
must contain the file when the original assembly has a source-backed
scheduling policy. Do not migrate such attributes into a shared library
or repeat them in individual test fixture methods.

A source `Parallelizable`, `NonParallelizable` or
`LevelOfParallelism` with aliases, computed expressions, conflicts or
duplicate declarations is blocked rather than guessed. A fixture/test
scheduling attribute is *not* interchangeable with an assembly attribute.
A generated syntax or build pass does not prove observed concurrency,
fixture lifetime, thread safety, retries, setup/teardown behavior or
business observables; explicitly run real NUnit and application E2E
before declaring equivalence.

## NUnit TestBase and cleanup review (preview.24)

Call `inspect_nunit_lifecycle(sourceDirectory)` before migrating inherited NUnit hooks, suite setup, DI/browser ownership, logs, screenshots, retries or cleanup. Review source-line and SHA evidence for every OneTimeSetUp, SetUp, TearDown and OneTimeTearDown obligation, including reached private helpers. Never move a nested SetUpFixture into assembly scope automatically. Only a standalone namespace/assembly setup fixture may use the reviewed teardown-only form. Inspector output is source-only: build, NUnit and browser evidence remain `not_run`. Reinspect whenever sourceTreeHash changes.


## Preserve nested NUnit cleanup scopes (preview.25)

Synthetic NUnit 3 and 4 source tests demonstrate that a nested
\`[SetUpFixture]\` may execute one-time cleanup after namespace tests,
including failure paths. Do not drop this hook or turn it into per-test
teardown. Call \`inspect_nunit_lifecycle\`, select the exact nested
\`sourceType\`, then call \`review_nested_nunit_cleanup\` with the current
\`sourceTreeHash\` and **all** concrete, reviewed target invocation
statements. Use the source hook's method fingerprint and effect
categories as review evidence. Stale or conflicting/ambiguous mappings
must remain blocked.

\`requires_review\` means only that a source-attested structural
candidate can be drafted. MCP intentionally does not return runnable
C# or claim any build, NUnit or browser execution. The source runtime
hash, if supplied, is a caller assertion, not a validated test report.
Do not enable the candidate in the complete target solution without
source and target NUnit execution counts, cleanup sequencing,
original DI/browser disposal semantics, and failure-path observables.
A real customer source hook cannot be mapped by guessing a
\`FullDispose()\` replacement.

## Playwright fixture ownership review (preview.26)

For a Selenium TestBase owning browser resources through DI, first call
\`inspect_nunit_lifecycle\` and inspect all base and nested cleanup
hooks/effects. Then call \`review_playwright_fixture_lifetime\` with
exact fully-qualified source base, nested cleanup and source
infrastructure DI type names, current \`sourceTreeHash\` and **one
source-backed** \`bindings\` entry per effect. Each binding must carry
the original \`sourceKind\`, \`sourcePath\`, \`sourceLine\`,
\`expressionSha256\`, approved \`targetRole\`, and \`reviewed: true\`.
Do not approve any role based only on the source method's spelling.

Require separate fixture BrowserContext/Page ownership, failure-only
log/screenshot capture before fixture release, and nested once-per-suite
global disposal, with observed NUnit/DI error paths. The existing
MCP review never runs build/tests or writes code. Its
\`requires_review\` candidate is NOT actual browser or application
equivalence. A concrete bridge must implement retries, navigation,
storage, pooled browser/provider ownership, and artifact timing
before enabling reviewed code in the target solution.


## Concrete Playwright/DI bridge review (preview.27)

Call \`inspect_nunit_lifecycle\` and
\`review_playwright_fixture_lifetime\` with exact current source
hashes and every source path/line/expression SHA binding. On
\`requires_review\` inspect both \`candidate\` and
\`concreteBridge\` SHA-256 metadata, preserving their distinct
types and NUnit nested cleanup ownership. The second artifact is a
concrete, type-checked DI-backed IBrowser/BrowserContext/IPage runtime,
not a fully configured customer provider. It must be configured with
a real application \`IServiceProvider\`, owned or injected
\`IBrowser\`, browser launch options and private artifact directory
and reviewed against actual source browser pooling.

Require explicit method-level \`[Retry(N)]\` and source/target
comparison before approving retry semantics. NUnit retries may
record intermediate failure screenshots even when the eventual
test case passes; never claim that an equal retry count proves
listener parity. Capture logs before screenshot; close contexts
even when page creation or scope disposal fails; keep global
browser/provider cleanup only in the original nested
OneTimeTearDown scope. Treat source role review as structural
evidence, not build/NUnit/browser/behavioral proof. Never publish
customer sources or source review mappings in public CI.


## Chromium integration acceptance and private E2E boundary (preview.28)

Before declaring a concrete Playwright bridge runnable, verify the
versioned real-Chromium synthetic CI record
\`migrator-real-chromium-smoke/v1\`: installed browser, local HTTP app,
source-backed Core candidate, two independent contexts and localStorage
isolation, real console/screenshot artifacts, observed NUnit retry
attempt counts, final failure, scope/context close counts and the nested
global browser/provider cleanup. Do not rely on the old fake-IBrowser
synthetic runtime as a replacement.

When reviewing a private source, re-run
\`inspect_nunit_lifecycle\` and
\`review_playwright_fixture_lifetime\` with current source hashes,
and keep nested-cleanup / Ignore / Explicit / TestCaseSource blockers
visible. Actual private application browser E2E remains \`not_run\`
until its own service/DI/credentials environment and behavior are
verified. Never publish customer source, mappings or evidence in CI.


## NUnit gates and TestCaseSource (preview.29)

Call `inspect_nunit_execution` on the narrowest source directory before
allowing any test assembly to be generated. Read `discoveryStatus`,
`staticallyResolvedNUnitCases`, `blockedNUnitSources`, each
`NUnitAttributes`/case lineage, source line and SHA-256, and the
per-case run-state/reason. Never count an NUnit annotated C# method as a
parameterized runtime case count. An `NUNIT_TEST_CASE_SOURCE_UNSAFE`,
`NUNIT_INHERITED_GATE_REQUIRES_REVIEW`,
`NUNIT_EXECUTION_GATE_REQUIRES_REVIEW` or named fixture gate requires
review: do not generate a runnable target for that source file.

No arbitrary source C# may be invoked for read-only inspection. Only
literal-only local static source arrays/properties attested by Core can
be lowered to `[TestCase]`. Retain `[Ignore]` and `[Explicit]` at
their proven fixture/method/case scope, preserving source reasons and
never automatically selecting explicit tests. Inspect generated target
expressions and exact file-set hashes.

Only treat runtime as proven after actual `dotnet test` and NUnit
discovery/TRX comparison, with a deliberately failing selected test,
separate explicit filter, observable execution indicators, and verified
exit codes. TRX may omit an explicit case or its skip reason; report that
limitation instead of inventing discovery or runtime evidence. NUnit3
and NUnit4 are not interchangeable without a runtime comparison.
Keep every private customer file, selector, URL and ZIP out of GitHub.


At preview.29 prefer per-case NUnit TRX `UnitTestResult` outcomes over
aggregate `Counters.notExecuted` (which may be zero for multiple skipped
tests). Pin package consumers to verified Core
`313e5ab0cac3f92b746d8aaab6cf7b3cfd902151` and NuGet
`0.1.0-preview.29`; never reference Core source projects across
repositories. In a source-only MCP review continue reporting
`runtimeStatus=not_run` until an explicit trusted CLI runs NUnit.

## P2 — source-backed Page Object actions (preview.30)

1. Inspect the narrowest C# source project with `inspect_pom_sources` and
   retain its exact `sourceTreeHash`. For each required POM method call,
   run `inspect_pom_action_plan` with exact source type/method and that hash.
2. Inspect ordered typed effects (navigation, click, clear, input SendKeys,
   finite visible wait, text/count assertion, table-row click), relative
   source lines and SHA-256, target SHA and blockers. Require the source
   declaration line for ambiguous overloads.
3. **Never** infer selectors from field names or tests, invent URL/origin,
   replace multi-step ComboBox with a Fill-only action, drop Loader/retry
   side effects or change assertion polarity. A branch, unknown helper,
   nonliteral selector, missing type/symbol or dynamic wait blocks the
   entire source method. Do not count a partially projected method as
   fully migrated.
4. `requires_review` means source-backed candidate **only**. The MCP
   tool deliberately hides source/target C# bodies and literals; trusted
   local Core/CLI may emit target statements via explicit `--emit-target`
   for user review. Only add these to an adapter when the receiver,
   argument flow, DOM behavior, timeouts, return values and source setup
   have been reviewed. Inspect `review_pom_mapping` obligations as well.
5. Execute an isolated, genuine Chromium localhost scenario and source/
   target NUnit discovery/TRX, including selected Explicit success/failure,
   skipped cases, browser console and screenshot and context teardown.
   Syntax success and matching TRX do not prove Selenium-to-Playwright UI
   equivalence. Keep private application execution status `not_run`
   until the real private build/NUnit/browser stages are executed.

Never publish private customer source, URLs, selectors, environment
settings, evidence archives or browser artifacts in public repos/CI.

## P2 / preview.31 — conditional Page Objects and guarded waits

For a POM method with conditional actions, a loader or a nested
ComboBox helper, first obtain the exact snapshot from
`inspect_pom_sources`, then call `inspect_pom_action_plan` with the
source tree hash. Read the ordered source relative lines, SHA-256 and
`controlFlowPath` values. Treat each `if:true` and `if:false` as
required source obligations; never replace a conditional ComboBox
selection with an unconditional click/fill.

Accept only compiler-proven Selenium `FindElements(By.literal).Count`
guards and string parameter comparisons to literals. A same-class
private no-arg helper is followable only when it can be completely
inlined; recursion and unverified dispatch are blocked. A dynamic
`WebDriverWait` timeout needs an exact source runtime guard with
finite 1..300000 ms range and matching parameter identity; otherwise
block the method. Literal/constant waits still need browser review.
NUnit `Is.GreaterThan` and `Is.LessThan` must preserve strict
inequality, not silently become `ToHaveCountAsync(n)`.

Read-only MCP does not disclose target statements, selectors or URLs.
Trusted local Core `pom-plan ... --emit-target` can produce an
adapter candidate for **manual review**; never auto-apply or report
`FullyConverted`. Reject any blocked method as an entire unit,
not merely its unsupported branch.

Compare NUnit case discovery and actual TRX records (including
`NotExecuted` and selected Explicit failure/success) and run real
Playwright Chromium against a separately isolated synthetic localhost
app. Record console/screenshot/cleanup, keep product browser parity
`not_verified` and private customer runs `not_run` without the
original source and proper environment. Never publish private data.

## preview.32 — nested typed POM helpers and bounded Loader retry

1. Capture exact source tree hash using `inspect_pom_sources`.
   Inspect each page helper using `inspect_pom_action_plan`.
   Read `controlFlowPath`, typed Roslyn symbol, source line/SHA,
   effects and `retry` metadata; never infer behavior from names.
2. Inline private same-class nonvirtual helpers only if *all*
   statements are source-backed and their zero/one string argument
   maps to the actual source parameter or literal. Preserve nested
   argument flow, selector literals and both conditional branches.
   A partial helper or changed source hash blocks the entire method.
3. Accept a retry proposal only for an AST-matched finite 2–4-attempt
   Selenium loop with one WebDriverWait, success `break`,
   WebDriverTimeoutException catch and exact final-attempt rethrow.
   Reject broad catch, missing terminal rethrow, extra side effects,
   dynamic attempt count, unbounded loop or unsupported wait.
   Retain exact source timeout and exception-path evidence.
4. This remains **review_required**; no invented selectors,
   timeouts, retries, URLs, click/selection ordering or side effects.
   Core's local `pom-plan --emit-target` yields an opt-in
   reviewed candidate. MCP deliberately never returns private
   source or target code or selectors.
5. Check actual Chromium success/failure, source-control and target
   NUnit discovery and per-case TRX on Linux/Windows and screenshot,
   browser console and context/IBrowser cleanup. Do not equate
   source-control NUnit/HttpClient with Selenium browser parity.
   Keep private ArBilling build/runtime/browser and fresh source
   SHA/declared methods/cases `not_run` unless its archives exist.

**Exact mapping rule for wait-prefixed helpers:** inspect the source method and its `WaitForAction` classification. For a no-argument `page.WaitReadyRetry()`, configure the exact reviewed `Methods.SourceMethod = "page.WaitReadyRetry()"` with its source-backed `TargetStatements` and `RequiresReview=true`. Do not assume `ParameterizedMethods` overrides an explicitly recognized wait. If the parser still emits `WAIT_REQUIRES_STATE_ASSERTION`, stop and report the test as blocked rather than declaring conversion success. Keep the documented .NET timeout catch `System.TimeoutException` and runtime-verify the retry failure path.


## preview.33 — source-bound cross-file helpers and DOM-absence waits

For private helpers in the same partial Page Object class, Roslyn may now bind
up to two literal or owning-method \`string\`/\`int\` parameters. Check every
argument's symbol, exact source path/SHA, ordered effects and both conditional
arms. Parameter swaps must remain independent; no free-form substitutions,
dynamic calls, constructors, getters, overrides or side effects are accepted.

\`WebDriverWait.Until(d => d.FindElements(By.literal).Count == 0)\` is
a *candidate* for \`WaitForSelectorState.Detached\` with an explicit
source timeout and the lambda receiver resolved to its own IWebDriver
parameter. This is not a general hidden-loader mapping:
\`!FindElement(...).Displayed\` requires an existing hidden element and
**must remain blocked** rather than becoming Playwright Hidden/Detached.
Other collection predicates, captured drivers, selector guesses, unbounded
or filtered retries remain blocked. Numeric guards and \`!\`, \`&&\`, \`||\`
must preserve short-circuit order, polarity and every branch.

Inspect \`actions[].controlFlowPath\`, \`retry\` and \`blockers\`.
The MCP stdio interface remains read-only and redacted: never expose the
candidate's raw target C#, selectors or source body. Use trusted Core CLI
with \`--emit-target\` only in an approved local workspace. The public
preview.33 synthetic Chromium/NUnit suite proves specific success/failure
paths and \`System.TimeoutException\` on actual Playwright .NET; its
source NUnit control uses HttpClient, **not Selenium WebDriver**. Do not
claim behavioral equivalence, automatic migration or private ArBilling
validation from equal discovery/TRX or browser smoke alone.


## preview.34 — mandatory real Selenium baseline and assertion-gap guard

Before marking Selenium-to-Playwright behavioral equivalence, run *both*
actual Selenium WebDriver with ChromeDriver and Playwright .NET on the same
browser executable and localhost/prod-approved fixture; compare source/target
DOM, ordered application effects, ComboBox positive/missing paths, Loader
detached state, real retry recovery/terminal failure, exact exception
identities, NUnit outcomes, real screenshots and resource cleanup.
Capture browser binary/version and source/target SHA as immutable evidence.
Core's synthetic suite verifies a narrow public fixture only; it does not
certify private ArBilling or business behavior.

**Do not auto-approve NUnit Count -> Playwright ToHaveCountAsync.**
NUnit Assert.That(FindElements(...).Count,Is.EqualTo(N)) examines a
synchronous snapshot, whereas Playwright Expect(locator).ToHaveCountAsync
may auto-retry. A delayed DOM insertion makes Selenium FAIL and Playwright
PASS on the same Chrome and app: an **actual known semantic difference**,
not a migration success. A matching selector and green target NUnit result
cannot resolve this. Require separate reviewed equivalent assertion
semantics before approving; otherwise keep requires_review/blocked. A
source retry loop literal 2 attempts is not independent proof of the
number of attempts observed at runtime. Source/target timeout exception
types differ (WebDriverTimeoutException vs System.TimeoutException) and
must be separately verified. MCP inspection stays read-only; never execute
customer browser code from stdio tools or leak private target code.


## preview.35 — immediate assertion semantics, strict review boundary

Do not translate source \`Assert.That(FindElements(...).Count,
Is.EqualTo(n))\` to \`Expect(locator).ToHaveCountAsync(n)\`: it
auto-retries and changed a real Selenium FAIL into a Playwright PASS
in preview.34. Source-backed Count EqualTo, GreaterThan and LessThan
now use one immediate \`CountAsync()\` read and NUnit comparison.
Verify the exact selected DOM and two real runtime outcomes.

Do not translate typed \`IWebElement.Text\` equality to
\`ToHaveTextAsync\`, whose auto-retry can hide a failing source.
The preview.35 candidate evaluates the selected DOM immediately and
compares with NUnit. **This does not prove full Selenium .Text parity**.
For a missing element, Selenium and Playwright throw distinct exception
types; for a hidden element, rendered Selenium .Text can differ from
DOM innerText. These cases require manual review/blocked approval and
real source/target runtime evidence. Never claim equivalence from just
matched positive visible-text cases. No CSS, XPath, URL, timeout,
browser condition or side effect may be guessed.

MCP \`inspect_pom_action_plan\` remains strictly read-only and
redacted. Check \`assertions.sourceImmediateCountSnapshots\`,
\`sourceImmediateTextSnapshots\`, \`hiddenTextParity\` and
\`missingElementExceptionParity\`; the status is source-only
\`requires_review\`, never auto-apply or runtime certified.


## preview.36 — source-backed CSS hidden/normal-whitespace Text subset

Use actual Selenium WebDriver \`IWebElement.Text\` as the source
behavior, not DOM innerText intuition. The Core preview.36 candidate
reads a typed source locator exactly once via Playwright
EvaluateAllAsync<string>, handles measured direct/ancestor CSS
display:none and visibility:hidden/collapse as empty text, and
normalizes the narrow tested CSS normal-space/tab subset. It does
**not** implement the complete WebDriver rendered-text atom.

CSS preserved white-space (\`pre\`, \`pre-wrap\`, \`break-spaces\`)
must fail closed with \`POM_TEXT_PRESERVED_WHITESPACE_REVIEW\`.
Missing element exception types are not equivalent and remain
manual review. Other visibility inheritance, pseudo-elements,
shadow DOM, bidirectional Unicode, complex whitespace, accessibility
text and product-specific state are not implied by synthetic success.
Never broaden the supported subset based on a method name or guess
a selector, timeout or state. Preserve source path/line/SHA and
unapproved \`requires_review\`; never count as fully migrated.

MCP \`inspect_pom_action_plan\` is read-only/source-only with no
raw C# or private locators. The \`assertions\` summary includes fixed
\`measuredCssHiddenSubset\`, \`normalWhitespaceSubset\` and
\`preservedWhitespace\` limitations, not observed browser truth.
Real comparison, NUnit/TRX and screenshots belong to trusted Core CI.


## preview.37 — Unicode/preserved-space rendered text and exceptions

For a source NUnit assertion using WebDriver \`IWebElement.Text\`,
preserve the **immediate** source snapshot, source selector, method,
literal/parameter provenance, and SHA. The preview.37 Core candidate
handles only the measured direct-leaf, single-line CSS pre/pre-wrap
and specific NBSP, U+200B, and combining Unicode cases in the
public same-Chrome Selenium WebDriver/Playwright .NET fixture.

**Do not infer** support for break-spaces, nested or multiline
preserved space, CSS text-transform, U+202F/narrow-NBSP or other
unverified Unicode whitespace. The candidate deliberately signals
a review error rather than fabricating an equivalent string.
Selenium NoSuchElementException catch semantics cannot be preserved
by a PlaywrightException without explicit reviewed exception
adaptation: treat it as a blocker for exception-sensitive source
methods. Do not introduce a hidden Selenium package dependency in
migrated Playwright code.

MCP tools cannot execute browser tests or approve mappings, and
source-only \`assertions\` metadata are **not** observed runtime
measurements. Inspect \`CanAutoApply=false\`,
\`RuntimeVerified=false\`, \`requires_review\`, exact source hashes,
the fixed CSS/Unicode coverage limitations and fail-closed
controls. No private source text, selectors or target code may
leave MCP stdio. Use actual real Selenium and Playwright on the
same browser for any semantic equivalence decision.


## preview.38 — NoSuchElementException and WebDriverTimeoutException

Source Roslyn syntax and exact symbol types decide whether a C#
\`catch\` candidate exists. Never replace every Selenium
\`NoSuchElementException\` with a broad PlaywrightException handler:
ClickAsync auto-wait failures, navigation, driver disposal, network
errors and user JavaScript exceptions are not source FindElement
missing behavior. The only admitted source operation is an immediate
typed \`FindElement(By.literal).Text\` NUnit assertion. Its projected
Playwright catch must filter the specific generated
\`POM_SOURCE_ELEMENT_ABSENT\` marker.

A typed finite \`WebDriverWait.Until\` with source
\`WebDriverTimeoutException\` can catch System.TimeoutException
*only for the attested projected wait*. A bare rethrow preserves the
Playwright exception **object**, not the Selenium CLR type. If an
external source caller catches NoSuchElementException or
WebDriverTimeoutException, the migrated API's thrown type is **not
identical**; do not approve without separate reviewed compatibility
work. Avoid any hidden runtime Selenium dependency in output.

Source catch filters, catch(Exception), catch variable inspection,
finally, additional effects, alternate thrown exception instances,
Click-related NoSuch catches and unknown source operations remain
blocked with no partial target. MCP \`exceptions\` data reports only
source-backed counts, fixed limits and review status; it is not
browser-executed evidence. The trusted Core same-Chrome Linux/Windows
synthetic benchmark is the test authority, not MCP tool metadata.
No private source body or selector leaves MCP stdio.


## preview.39 — external exception catch chains

Before offering a reviewed Playwright target for Selenium
\`NoSuchElementException\` or \`WebDriverTimeoutException\`, inspect
**all in-scope callers**, including inherited TestBase helpers and
NUnit test methods. The Core projector follows exact Roslyn method
symbols and blocks source methods whose caller chain catches Selenium
types, broad exceptions or catch filters. The returned blocker path,
line and SHA identify precisely which external handler requires a
separate migration decision. Never treat a locally valid \`throw;\`
as preserving the original Selenium exception CLR identity.

MCP \`inspect_pom_action_plan\` only reports source-only
\`externalCatchChains\` counts and deterministic blockers; it does
not return private selector values, source bodies or generated C#.
The absence of an in-scope caller blocker is not proof that
external assemblies, virtual/interface dispatch, delegates,
reflection or other unobserved flows are safe. Local functions,
dynamic dispatch and graph limits must fail closed.

For any source catch path depending on the Selenium CLR type,
DO NOT auto-insert a broad PlaywrightException handler or hidden
Selenium dependency. Require a manually reviewed contract with
independent real Selenium-vs-Playwright runtime evidence.
\`blocked\` has no target statements; otherwise proposals remain
\`requires_review\` with \`CanAutoApply=false\`. No private
ArBilling data may be committed to public evidence.


## preview.40-A — reviewed external exception contract proposals

Use inspect_pom_external_exception_contract for source-only, typed
outer TestBase/NUnit catch evidence, only after inspect_pom_sources
captures an exact SourceTreeHash. A proposal exists solely for a
single direct symbol-bound one-call synchronous forwarding chain,
one matching Selenium source catch, and an inner locally rethrown
FindElement.Text/finite WebDriverWait. Only an **empty external catch** admits a reviewed clause. Typed NUnit
FindElements.Count recovery is explicitly **blocked**: a projected
CountAsync needs an async outer NUnit method and source-verified Playwright
IPage receiver that this clause-only tool does not provide. No partial
or uncompiled external recovery is approved.

MCP intentionally does NOT return target catch C#, selectors, source
bodies or private values. The trusted local Core CLI may reveal the
C# clause only with explicit --emit-target. That C# is not a complete
migrated NUnit method and is never auto-applied; use manual source
review, independent browser checks and preserve target exception
identity limitations. The old PlanPomActions must still be blocked.

Do not infer external catch filters, broad catches, external throw,
multiple calls, dynamically dispatched paths or unknown catch effects.
Source absence in the captured tree is NOT evidence that callers in
other assemblies are safe. The source CLR NoSuchElementException and
WebDriverTimeoutException types are NOT preserved by PlaywrightException
and System.TimeoutException. Unknown remains blocked/review_required.
