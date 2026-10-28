# Independent migration evaluation

External sample: https://github.com/desh2001/Selenium-NUnit-Automation
Pinned commit: edacb9feb41a7e21d9b6bf6924f24c11698a4427

This is a **read-only external experiment**. The external sample has no identified
license, so the CI job checks it out temporarily and uploads only summary JSON
and build diagnostics, not the source or generated derivative files.

The workflow calls the **real MCP process over stdio**. It records separately:

1. Baseline `dotnet build` of the original Selenium/NUnit project.
2. MCP discovery, preview and (when available) finding explanation.
3. Syntax and framework-only Roslyn compilation of the exact generated target.
4. Independent `dotnet build` against Microsoft.Playwright.NUnit 1.63.0,
   using **raw, unedited** generated files.
5. Browser install and target `dotnet test` only when the raw target builds.

Two scopes are checked: the entire AssignmentProject/Tests directory
and an individual TextInputTests.cs pilot. Each result is captured with
its own source/config/target identities, test counts and diagnostic categories.

A green GitHub Actions run means **the experiment executed and evidence was
saved**, not that the migration succeeded. The actual stage statuses are
in evaluation.json inside the CI artifact public-nunit-migration-evidence.

For the second experiment, use the owner's unfinished example after its exact
repository URL/archive and intended source scope are available. Record pre-existing
failures separately from regressions caused by migration.
