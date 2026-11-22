# P2/P3 consumer — real public Page Object property slice, no release approval

This MCP/Agent Skill extension consumes a single exactly pinned Core candidate
that has its own **unchanged 28-job Linux/Windows CI**. MCP retains both of its
existing jobs: Linux packaged dotnet-tool / real stdio / standalone executable
and Windows self-contained / real stdio / NUnit/Chromium. Both build and verify
the exact same five Core local NuGet packages, with source-head provenance.

## What changed in Core

The selected public source
`desh2001/Selenium-NUnit-Automation@edacb9feb41a7e21d9b6bf6924f24c11698a4427`
defines `HomePage.GoToTextInput()` with `By.LinkText`, plus
`TextInputPage.EnterText()`, `ClickButton()` and `GetButtonText()`
with typed `IWebElement` expression-bodied properties.

Core now proposes only source-symbol-resolved, single-driver, read-only
property locator actions; exact LinkText link-role candidates; and a single
string `IWebElement.Text` return. Mutable/virtual/inherited aliases, dynamic
selectors, multiple driver receiver candidates, partial text/unknown return
paths block. `GetByRole(Link, Exact)` vs Selenium LinkText and
`InnerTextAsync` vs Selenium Text remain explicit review-required behaviors,
not automatic equivalence.

## MCP protocol contract

The new `scripts/p2_public_property_stdio_smoke.py` creates an owned synthetic
source with those public-like patterns, then calls actual
`inspect_pom_sources` / `inspect_pom_action_plan` against a running MCP
process over JSON-RPC stdio. It requires hash-bound positive source effects in
exact order, `requires_review`, no executable C# statements, no source
selector literal disclosure, no runtime certification and no autoapply.
Writable/dynamic/unresolved string getters must fail closed, and a source
property mutation must invalidate the old `SourceTreeHash`. The same smoke
runs in both existing Linux and Windows jobs.

Core's separate CI explicitly compiles *actual Core pom-plan emitted* target
methods and compares them with the two immutable original public POM source
files on the same Chrome/loopback HTML, with a missing Click green NUnit
false-positive and wrong selector failing NUnit. The original complete upstream
NUnit lifecycle and build/scripts remain `not_run`, no third-party project
execution is authorized. The other two public repositories remain source-only.

No full `migrator-acceptance/v1` CandidateId or transitive independent
project behavioral acceptance is inferred. `canAutoApply=false`,
`acceptedForRC=false`, `fullRealProjectBehavioralEquivalence=unknown`.
P1 Windows native-LIVE Chromium orphan #59 has not been product-fixed; the
instrumented handler remains unbuilt. **NO FIX CLAIM / NO MERGE / NO RELEASE.**
