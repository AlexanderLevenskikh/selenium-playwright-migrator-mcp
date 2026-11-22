# RC package provenance and exact source identity

The earlier green Core #79/MCP #61 NuGet artifacts were independently inspected: all ZIP CRC passed, MIT and preview.48 were present. Four Core packages used placeholder descriptions; Core and MCP package metadata named the former AlexanderLevenskikh GitHub owner, and the recorded commit was the GitHub synthetic PR merge ref, not the immutable intended product source head.

[Core packaging draft #82](https://github.com/levencode-labs/selenium-playwright-migrator-core/pull/82) enforces the five canonical Core nupkg identities, descriptions, URLs, license and source-HEAD SHA. MCP CI pins Core a0d0f2719fd73fc6c6e9f8dba7491687fc1694be exactly in BOTH Linux/Windows jobs, packs the Core feed with its actual SHA, and reads all five resulting NuGet metadata files. The MCP tool-package validator reads the real resulting .nupkg on Linux, checks exact source SHA, canonical URL, MIT, DotnetTool identity, binary and Playwright/Node license notices. Windows executes identical portable negative metadata controls and real self-contained stdio integration.

The two GitHub pull_request checkouts of MCP sources are source-HEAD pinned for package provenance. The original CI job count (2/2), Core Windows P47 original 12-second gate, NUnit/behavior tests and release NO-GO remain untouched.

**No claim of reproducible binary hash across fresh runners** or independently completed third-party-license/vulnerability audit follows from these metadata tests. No publication, main merge or tag is authorized until P1 Windows native-LIVE before/after product cleanup, real Core-produced full-project equivalence and final release checklist all pass.
