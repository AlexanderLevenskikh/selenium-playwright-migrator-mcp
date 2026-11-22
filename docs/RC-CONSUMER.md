# MCP/Skill Release Candidate consumer gate — NO-GO

## Exact integrated Core

This clean MCP integration branch sources the product tree from green MCP draft #60 `f94654b8ea494b8c269d07abe67faaa85edc1638` (2/2 original MCP CI #45040204967), then replaces **both** Core checkouts with the final Core integration SHA `faaa46f20ead67effe74de0a96867187be8f086a`. This SHA includes a clean product-tree snapshot from green Core #78 and documentation plus canonical Git blob SHA256 validation.

Both Linux `build-and-protocol-smoke` and Windows `windows-standalone` must pass on **this exact MCP HEAD**; earlier product-stack CI cannot substitute. MCP builds Core NuGet packages from its pinned checkout and verifies Core `docs/rc-status.json` NO-GO gate before packaging. Neither client may silently use an older Core package/ref.

## Contract

The server is read-only and does not grant filesystem editing, arbitrary project execution, compilation with implicit references, browser runtime or release permissions. `verify_artifact` binds analysis/parent/edited candidate and source/target tree hashes, with separate verification stages. Missing POM helper/locator, NUnit `SetUpFixture`, inherited lifecycle or other source-required operations yields `rejected_incomplete`; matching AST is `blocked_unverified`, never full behavioral acceptance.

P2/P3 public portfolio includes 3 unrelated SHA-pinned sources; they are **not** executed, and parity remains UNKNOWN. The independent bounded synthetic browser oracle has 8 positive real Selenium/Playwright cases and 2 negatives (red inverted guard, green NUnit missing Click with observable difference). It is not general business-equivalence proof.

**HARD RELEASE BLOCKER:** [Core Windows Chromium orphan #59](https://github.com/levencode-labs/selenium-playwright-migrator-core/issues/59) remains OPEN and lacks an instrumented stock handler witness, source-backed product fix and original 12-second gate before/after proof. Core #77 is unbuilt test-owned overlay only; host-owned Job Object is not a substitute. Do not merge to main, release, publish NuGet, weaken acceptance or claim product FIX.
