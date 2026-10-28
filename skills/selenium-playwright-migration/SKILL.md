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
