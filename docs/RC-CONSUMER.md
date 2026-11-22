# MCP/Skill Release Candidate consumer gate — NO-GO

## Exact integrated Core

This clean MCP integration branch sources the product tree from green MCP draft #60 `f94654b8ea494b8c269d07abe67faaa85edc1638` (2/2 original MCP CI #45040204967), then replaces **both** Core checkouts with the final Core integration SHA `faaa46f20ead67effe74de0a96867187be8f086a`. This SHA includes a clean product-tree snapshot from green Core #78 and documentation plus canonical Git blob SHA256 validation.

Both Linux `build-and-protocol-smoke` and Windows `windows-standalone` must pass on **this exact MCP HEAD**; earlier product-stack CI cannot substitute. MCP builds Core NuGet packages from its pinned checkout and verifies Core `docs/rc-status.json` NO-GO gate before packaging. Neither client may silently use an older Core package/ref.

## Contract

The server is read-only and does not grant filesystem editing, arbitrary project execution, compilation with implicit references, browser runtime or release permissions. `verify_artifact` binds analysis/parent/edited candidate and source/target tree hashes, with separate verification stages. Missing POM helper/locator, NUnit `SetUpFixture`, inherited lifecycle or other source-required operations yields `rejected_incomplete`; matching AST is `blocked_unverified`, never full behavioral acceptance.

P2/P3 public portfolio includes 3 unrelated SHA-pinned sources; they are **not** executed, and parity remains UNKNOWN. The independent bounded synthetic browser oracle has 8 positive real Selenium/Playwright cases and 2 negatives (red inverted guard, green NUnit missing Click with observable difference). It is not general business-equivalence proof.

**HARD RELEASE BLOCKER:** [Core Windows Chromium orphan #59](https://github.com/levencode-labs/selenium-playwright-migrator-core/issues/59) remains OPEN and lacks an instrumented stock handler witness, source-backed product fix and original 12-second gate before/after proof. Core #77 is unbuilt test-owned overlay only; host-owned Job Object is not a substitute. Do not merge to main, release, publish NuGet, weaken acceptance or claim product FIX.

## New bounded source-projected public POM candidate (separate DRAFT)

Core [draft #83](https://github.com/levencode-labs/selenium-playwright-migrator-core/pull/83) exact source SHA `90d4c420857433bcfdd68eaa31de52c494f6a112` passed its complete [28-job CI #45046448926](https://github.com/levencode-labs/selenium-playwright-migrator-core/actions/runs/45046448926) **28/28 SUCCESS** (attempt 1). Original Windows P47 remained unchanged and green on this run only; the native-LIVE orphan #59 remains OPEN and unfixed. Five shipped Core NuGet packages were independently verified: outer ZIP #14764092035 SHA256 `00ae8463182f4948818e184b1c4ab7cd50578817b103e3951e1ce6db108059b1`, inner CRC and embedded exact source HEAD, MIT, canonical URLs and meaningful descriptions PASS.

The preceding initial #83 CI #45045881201 legitimately FAILED 26/28 due to a new synthetic C# CSS-string escape comparison. The stricter replacement uses Roslyn to inspect the actual locator literal; no job was dropped and the historical red run remains preserved.

The Core [actual external-generated POM receipt](https://github.com/levencode-labs/selenium-playwright-migrator-core/pull/83) uses the originally pinned public `desh2001/Selenium-NUnit-Automation` HomePage/TextInputPage, but now derives Playwright method statements through the actual Core `pom-plan --emit-target` rather than hand-writing them. The generated target SHA256 `1701bae5dc5aa4051d0d4960fea6d77c8b5676276a5c8e4dc045650191271ebf` matches across Linux/Windows; original Selenium and projected Playwright produced identical bounded DOM/application events in a controlled localhost NUnit harness. Missing-Click NUnit PASS was rejected by external oracle; wrong-selector NUnit FAIL and stale source-tree rejection were observed. Raw checkout `SourceTreeHash` differs by LF/CRLF; canonical Git blob hashes agree. **Original TestFixture/DriverManager execution, complete lifecycle, helper graph, other two public projects and full `migrator-acceptance/v1` CandidateId remain UNKNOWN or not_run.** This is not a complete migration.

This MCP follow-up pins both Linux/Windows Core feed checkouts **exactly** to `90d4c420857433bcfdd68eaa31de52c494f6a112` and adds a real read-only stdio smoke for `IWebElement` property actions, literal LinkText, rendered Text return, negative properties and stale source hash. MCP continues to return effect/hashes ONLY, not source C#, selector strings or target statements; `runtimeVerified=false`, `canAutoApply=false`. It must independently pass all original 2 MCP CI jobs on the final MCP SHA; a run result cannot be assumed from an earlier release-engineering PR.

**RC remains NO-GO** until Windows #59 root cause, instrumented runtime witness, genuine product-owned before/after P47 cleanup and full independently verified public-project migration are achieved. No main merge, tag, NuGet publication or release.
