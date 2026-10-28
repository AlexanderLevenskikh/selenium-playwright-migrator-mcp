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
