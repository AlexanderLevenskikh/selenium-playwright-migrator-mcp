# P2 MCP/Skill exact-Core acceptance consumer

Core [draft #68](https://github.com/levencode-labs/selenium-playwright-migrator-core/pull/68) has immutable head `a5393624497f9fad9bedc17a84605caa9e2df857`, and [full Core CI #45020552823](https://github.com/levencode-labs/selenium-playwright-migrator-core/actions/runs/45020552823) passed 28/28. The original 28-job matrix was unchanged. The source/target real-NUnit synthetic counterexample artifact #14753617777 contains **two Passed TRX** despite a missing Click.

This MCP PR is a separately pinned **consumer validation**, NOT a release or merge of Core #68. Its Linux and Windows MCP CI both checkout the exact unmerged Core SHA from Levencode Labs, pack NuGet libraries locally, build a standalone MCP tool and verify `verify_artifact` response over actual MCP stdio JSON-RPC. No new execution rights, mutation or pre-existing P1 Windows fix is claimed.

## Fail-closed contract regression

- Generated candidate: `acceptance.schemaVersion=migrator-acceptance/v1`, exact analysis/candidate/target SHA, no `accepted` result; unexecuted NUnit discovery/runner/browser/behavior stages remain `not_run`.
- Edited target: intentionally removed original `[Test]` declaration while retaining compilable code. Roslyn `syntax=passed` and `compile=passed`, but `acceptance.status=rejected_incomplete`, missing source lineage reported, distinct candidate ID, behavior remains `not_run`.
- Skill explicitly disallows success on prior Core versions that omit acceptance; no legacy fallback to green NUnit.
- Existing Linux/Windows CI matrices, stdio tests, packaging and smoke scripts remain enabled unchanged; no private ArBilling source or secrets are uploaded.

**No merge/release** until exact-head MCP 2/2 CI is green and Core P1 #59 remains independently resolved. MCP compatibility is not browser behavior parity.
