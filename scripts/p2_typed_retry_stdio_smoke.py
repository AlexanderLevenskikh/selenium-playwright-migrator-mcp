#!/usr/bin/env python3
"""Actual MCP stdio: isolated source AST, finite retries, typed helper forwarding."""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SOURCE = """
using System;
using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;
using NUnit.Framework;
namespace Fictional.P32;
public sealed class SyntheticPage {
    readonly IWebDriver driver;
    public SyntheticPage(IWebDriver driver) => this.driver = driver;
    public void Choose(string value) {
        Open();
        Input(value);
        if (driver.FindElements(By.CssSelector("[data-test='option']")).Count > 0) {
            driver.FindElements(By.CssSelector("[data-test='option']"))[0].Click();
        } else {
            Assert.That(driver.FindElements(By.CssSelector("[data-test='option']")).Count,
                Is.EqualTo(0));
        }
    }
    private void Open() { driver.FindElement(By.Id("picker")).Click(); }
    private void Input(string search) { TypeValue(search); }
    private void TypeValue(string text) {
        driver.FindElement(By.Id("search")).SendKeys(text);
    }
    public void RetryReady() {
        for (var attempt = 0; attempt < 2; attempt++) {
            try {
                new WebDriverWait(driver, TimeSpan.FromMilliseconds(120))
                    .Until(d => d.FindElement(By.Id("ready")).Displayed);
                break;
            } catch (WebDriverTimeoutException) {
                if (attempt == 1) throw;
            }
        }
    }
    public void UnsafeBadCatch() {
        for (var attempt = 0; attempt < 2; attempt++) {
            try {
                new WebDriverWait(driver, TimeSpan.FromMilliseconds(120))
                    .Until(d => d.FindElement(By.Id("ready")).Displayed);
                break;
            } catch (Exception) {
                if (attempt == 1) throw;
            }
        }
    }
    public void UnsafeBadHelper() { TypeValue(Environment.GetEnvironmentVariable("PRIVATE")!); }
    public void UnsafeRecursive(string text) { Recursive(text); }
    private void Recursive(string text) { Recursive(text); }
}
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: p2_typed_retry_stdio_smoke.py <MCP dll/executable>")
    executable = str(Path(sys.argv[1]).resolve())
    expect(Path(executable).is_file(), "Compiled MCP executable missing")
    with tempfile.TemporaryDirectory(prefix="fictional-p32-mcp-") as temp:
        root = Path(temp)
        source = root / "pom" / "SyntheticPage.cs"
        source.parent.mkdir()
        source.write_text(SOURCE, encoding="utf-8")
        unchanged = hashlib.sha256(source.read_bytes()).hexdigest()
        env = dict(os.environ, MIGRATOR_WORKSPACE=temp)
        proc = subprocess.Popen(
            ["dotnet", executable] if executable.endswith(".dll") else [executable],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env)
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18",
                                   "capabilities": {}, "clientInfo": {
                                       "name": "p2-preview32-typed-retry",
                                       "version": "0.1"}}})
            expect("serverInfo" in receive(proc, 1), "initialize failed")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = {x["name"] for x in receive(proc, 2)["tools"]}
            expect("inspect_pom_sources" in names
                   and "inspect_pom_action_plan" in names,
                   "Missing read-only POM inspection tools")
            baseline = value(call(proc, 3, "inspect_pom_sources",
                                  {"sourceDirectory": "pom",
                                   "pageTypes": ["SyntheticPage"]}))
            h = baseline["sourceTreeHash"]
            expect(len(h) == 64, "Source SHA-256 was not captured")

            def inspect(num, method):
                return value(call(proc, num, "inspect_pom_action_plan", {
                    "sourceDirectory": "pom",
                    "sourceType": "Fictional.P32.SyntheticPage",
                    "sourceMethod": method, "expectedSourceTreeHash": h}))

            combo = inspect(4, "Choose")
            expect(combo["schemaVersion"] == "migrator-pom-action/v1alpha3"
                   and combo["status"] == "requires_review"
                   and not combo["runtimeVerified"]
                   and not combo["canAutoApply"]
                   and combo["execution"] == "read_only_not_run",
                   "Preview32 source-only POM inspection was auto-approved")
            actions = combo["actions"]
            expect(any(x["effect"] == "private_helper_inline" for x in actions)
                   and any("helper:TypeValue@" in x["controlFlowPath"]
                           for x in actions)
                   and any(x["effect"] == "conditional_guard" for x in actions)
                   and any("if:true@" in x["controlFlowPath"] for x in actions)
                   and any("if:false@" in x["controlFlowPath"] for x in actions),
                   "Nested typed helper or conditional source effects lost")
            expect(all(x["sourcePath"] == "SyntheticPage.cs"
                       and x["sourceLine"] > 0 and len(x["sourceSha256"]) == 64
                       and len(x["targetSha256"]) == 64
                       and x["requiresReview"] for x in actions),
                   "Source line/SHA/target hash provenance missing")
            retry = inspect(5, "RetryReady")
            expect(retry["status"] == "requires_review"
                   and retry["retry"]["boundedLoops"] == 1
                   and retry["retry"]["sourceBackedTerminalRethrows"] == 1
                   and retry["retry"]["sourceOnly"]
                   and any(x["effect"] == "bounded_retry" for x in retry["actions"])
                   and any(x["effect"] == "visible_wait"
                           and "retry:try@" in x["controlFlowPath"]
                           for x in retry["actions"])
                   and any(x["effect"] == "retry_failure_rethrow"
                           and "retry:catch@" in x["controlFlowPath"]
                           for x in retry["actions"]),
                   "Exactly bounded 2-attempt retry/catch/throw source lineage missing")
            for number, method in (
                (6, "UnsafeBadCatch"), (7, "UnsafeBadHelper"), (8, "UnsafeRecursive")):
                result = inspect(number, method)
                expect(result["status"] == "blocked" and result["blockers"]
                       and result["provenSourceActions"] >= 0,
                       method + ": unsafe source changed into runnable POM")
            for response in (combo, retry):
                expect("targetStatements" not in response
                       and "adapterCandidate" not in response
                       and all("targetStatement" not in action
                               for action in response["actions"])
                       and "data-test='option'" not in str(response)
                       and "literal-choice" not in str(response),
                       "MCP leaked private source or target selectors/actions")
            expect(hashlib.sha256(source.read_bytes()).hexdigest() == unchanged,
                   "Read-only MCP mutated source bytes")
            source.write_text(SOURCE + "\n// stale", encoding="utf-8")
            stale = call(proc, 9, "inspect_pom_action_plan", {
                "sourceDirectory": "pom",
                "sourceType": "SyntheticPage", "sourceMethod": "Choose",
                "expectedSourceTreeHash": h})
            expect(stale.get("isError"), "Stale source hash was silently accepted")
            print("POM_PREVIEW32_TYPED_RETRY_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
