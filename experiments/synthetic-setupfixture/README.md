# Synthetic scoped NUnit SetUpFixture regression

Public isolated `net10.0` project for real NUnit/Playwright browser mechanics. It contains an assembly-global `[SetUpFixture]`, a `SyntheticScope` parent, and a `SyntheticScope.Inner` nested `[SetUpFixture]`. Two ordered Chromium tests live in `SyntheticScope.Inner`, and one in the similarly named sibling namespace `SyntheticScopeElse`.

The suite verifies that each one-time entry/exit happens exactly once and in hierarchical order. Browser tests use local `data:text/html` pages only. This is **not an ArBilling E2E** or proof of source-to-target equivalence.

CI builds this independent test project, installs Chromium for the exact Playwright version and requires **3/3 executed and passing NUnit cases**, in addition to the existing **13/13** ComboBox/Loader/fixture workflow.
