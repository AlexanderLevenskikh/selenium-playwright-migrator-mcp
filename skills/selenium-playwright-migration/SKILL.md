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
