P1-N exact source compatibility research check (NO FIX CLAIM)

This disposable draft is based on MCP main 9069a6f019426362e10fe0ff992011c00a59e0c0 and alters ONLY the two exact Core checkout refs for existing Linux/Windows MCP package, standalone, stdio and real-browser smoke. Both refs are pinned to Core P1-N research draft #77 SHA b065d9d4b3d5bc664ec51b0008d40f4412a35410. No MCP protocol or product semantics are changed, no execution permissions added, original Core Windows P47 unaffected.

The Core changes are only a test-owned instrumentation overlay generator and offline synthetic regressions. The packaged migrator is not instrumented, and this MCP 2/2 test cannot prove a Windows orphan fix, live Crashpad clients, pending uploads, or behavioral equivalence. CI results will be archived in the PR; close unmerged after verification if no code remains useful. Original exact Core 28/28 CI remains a separate gate. No merge/release.
