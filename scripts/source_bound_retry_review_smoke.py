#!/usr/bin/env python3
"""End-to-end MCP stdio regression for source-bound retry review.
Synthetic source only. No private selector, page, URL or application data.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def main(binary):
    with tempfile.TemporaryDirectory(prefix="source-bound-retry-") as tmp:
        root = pathlib.Path(tmp)
        (root / "WaitHelper.cs").write_text("""
public class WaitHelper {
    public void AwaitReady() {
        var limit = 2;
        var retry = 0;
        while (retry < limit)
            try {
                if (problem.Displayed().Get()) {
                    problem.ExecuteJs("window.location.reload()");
                    busy.Visible.Wait().EqualTo(false);
                }
                ready.Visible.Wait().EqualTo(true);
                busy.Visible.Wait().EqualTo(false);
                break;
            } catch (WebDriverTimeoutException) {
                retry++;
                if (retry == limit) Assert.Fail("not ready");
            }
    }
}
""", encoding="utf-8")
        command = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0","id":1,"method":"initialize",
                        "params":{"protocolVersion":"2025-06-18",
                                  "capabilities":{},
                                  "clientInfo":{"name":"source-bound-retry","version":"1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize failed")
            send(proc, {"jsonrpc":"2.0","method":"notifications/initialized"})
            inspection = value(call(proc, 2, "inspect_pom_sources",
                                    {"sourceDirectory":".", "pageTypes":["WaitHelper"]}))
            helper = next(h for h in inspection["helpers"] if h["method"] == "AwaitReady")
            expect(helper["numericLocalConstants"]["limit"] == "2",
                   "Immutable numeric retry limit must be exposed as evidence")
            identity = {
                "sourceDirectory":".",
                "sourceType":"WaitHelper",
                "sourceMethod":"AwaitReady",
                "sourceLine":helper["sourceLine"],
                "expectedSourceTreeHash":inspection["sourceTreeHash"]
            }
            statements = [
                "var retry = 0;",
                "while (retry < 2) {",
                "try {",
                'if (await Page.Locator("#bad").IsVisibleAsync()) {',
                "await Page.ReloadAsync();",
                'await Page.Locator("#busy").WaitForAsync(new() { State = WaitForSelectorState.Hidden });',
                "}",
                'await Page.Locator("#ready").WaitForAsync(new() { State = WaitForSelectorState.Visible });',
                'await Page.Locator("#busy").WaitForAsync(new() { State = WaitForSelectorState.Hidden });',
                "break;",
                "} catch (System.TimeoutException) {",
                "retry++;",
                'if (retry == 2) Assert.Fail("not ready");',
                "}",
                "}"
            ]

            def review(req_id, candidate):
                return value(call(proc, req_id, "review_pom_mapping",
                                  dict(identity, targetStatements=candidate)))

            good = review(3, statements)
            expect(good["status"] == "requires_review" and not good["missingObligations"]
                   and not good["behaviorallyVerified"],
                   "Complete synthetic retry must remain review-required, not approved")
            expect(sum(x["effect"] == "reload" for x in good["obligations"]) == 1,
                   "Literal JS reload must be a source reload obligation")

            wrong_wait = review(4, [
                line.replace("WaitForSelectorState.Hidden","WaitForSelectorState.Visible")
                for line in statements
            ])
            expect(wrong_wait["status"] == "rejected_incomplete"
                   and "source_wait_visibility_inverted" in wrong_wait["reviewFlags"],
                   "Visibility direction inversion must be rejected")

            wrong_failure = review(5, [
                line.replace("if (retry == 2)", "if (retry == 3)")
                for line in statements
            ])
            expect(wrong_failure["status"] == "rejected_incomplete"
                   and "source_retry_failure_guard_changed" in wrong_failure["reviewFlags"],
                   "Retry-exhaustion guard must be checked")

            wrong_reload = review(6, [
                line.replace("await Page.ReloadAsync();", 'await Page.Locator("#noop").ClickAsync();')
                for line in statements
            ])
            expect(wrong_reload["status"] == "rejected_incomplete"
                   and any(o["effect"] == "reload" for o in wrong_reload["missingObligations"]),
                   "Source JS reload cannot be silently dropped")

            print("Source-bound retry MCP protocol passed", flush=True)
        finally:
            proc.terminate()
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: source_bound_retry_review_smoke.py <MCP.dll|executable>")
    binary = pathlib.Path(sys.argv[1]).resolve()
    expect(binary.exists(), "MCP executable not found")
    main(binary)
