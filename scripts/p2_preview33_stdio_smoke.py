#!/usr/bin/env python3
"""Preview.33 MCP read-only stdio regression. No private selector, target C#
or customer source leaves the workspace in a tool response.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

PAGE = """
using System;
using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;
namespace Fictional.P33;
public sealed partial class Page {
    private readonly IWebDriver driver;
    public Page(IWebDriver driver) { this.driver = driver; }
    public void Select(string search, string confirm) { InputAndConfirm(search, confirm); }
    public void LoaderGone() {
        new WebDriverWait(driver, TimeSpan.FromMilliseconds(75))
            .Until(d => d.FindElements(By.Id("private-loader")).Count == 0);
    }
    public void RetryGone() {
        for (var attempt = 0; attempt < 2; attempt++) {
            try {
                new WebDriverWait(driver, TimeSpan.FromMilliseconds(75))
                    .Until(d => d.FindElements(By.Id("private-loader")).Count == 0);
                break;
            } catch (WebDriverTimeoutException) {
                if (attempt == 1) throw;
            }
        }
    }
    public void HiddenNotDetached() {
        new WebDriverWait(driver, TimeSpan.FromMilliseconds(75))
            .Until(d => !d.FindElement(By.Id("private-loader")).Displayed);
    }
    public void UnsafeDynamic(string confirm) {
        InputAndConfirm(Environment.GetEnvironmentVariable("PRIVATE")!, confirm);
    }
}
"""
HELPERS = """
using OpenQA.Selenium;
using NUnit.Framework;
namespace Fictional.P33;
public sealed partial class Page {
    private void InputAndConfirm(string a, string b) {
        driver.FindElement(By.Id("private-search")).SendKeys(a);
        if (b == "yes") {
            driver.FindElement(By.Id("private-confirm")).Click();
        } else {
            Assert.That(driver.FindElements(By.Id("private-confirm")).Count,
                Is.GreaterThan(0));
        }
    }
}
"""

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: p2_preview33_stdio_smoke.py <MCP dll/executable>")
    executable = str(Path(sys.argv[1]).resolve())
    expect(Path(executable).is_file(), "MCP server missing")
    with tempfile.TemporaryDirectory(prefix="fictional-p33-mcp-") as workspace:
        root = Path(workspace) / "pom"
        root.mkdir()
        (root / "Page.cs").write_text(PAGE, encoding="utf-8")
        (root / "Helpers.cs").write_text(HELPERS, encoding="utf-8")
        source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in root.glob("*.cs")}
        env = dict(os.environ, MIGRATOR_WORKSPACE=workspace)
        process = subprocess.Popen(
            ["dotnet", executable] if executable.endswith(".dll") else [executable],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env)
        start_reader(process)
        try:
            send(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18",
                                      "capabilities": {},
                                      "clientInfo": {"name": "preview33",
                                                     "version": "0.1"}}})
            expect("serverInfo" in receive(process, 1), "initialize failed")
            send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            send(process, {"jsonrpc": "2.0", "id": 2,
                           "method": "tools/list", "params": {}})
            names = {t["name"] for t in receive(process, 2)["tools"]}
            expect({"inspect_pom_sources", "inspect_pom_action_plan"} <= names,
                   "Read-only POM tools missing")
            baseline = value(call(process, 3, "inspect_pom_sources", {
                "sourceDirectory": "pom", "pageTypes": ["Page"]}))
            snapshot = baseline["sourceTreeHash"]
            expect(len(snapshot) == 64, "Missing SHA-256 source identity")

            def inspect(number, method):
                return value(call(process, number, "inspect_pom_action_plan", {
                    "sourceDirectory": "pom",
                    "sourceType": "Fictional.P33.Page",
                    "sourceMethod": method,
                    "expectedSourceTreeHash": snapshot}))

            combo = inspect(4, "Select")
            expect(combo["status"] == "requires_review"
                   and not combo["runtimeVerified"] and not combo["canAutoApply"]
                   and combo["execution"] == "read_only_not_run"
                   and any(a["effect"] == "private_helper_inline"
                           for a in combo["actions"])
                   and any("helper:InputAndConfirm@" in a["controlFlowPath"]
                           for a in combo["actions"])
                   and any(a["sourcePath"] == "Helpers.cs"
                           for a in combo["actions"])
                   and any("if:false@" in a["controlFlowPath"]
                           for a in combo["actions"]),
                   "Cross-file 2-arg source facts or review boundary lost")
            loader = inspect(5, "LoaderGone")
            expect(loader["status"] == "requires_review"
                   and any(a["effect"] == "detached_wait"
                           for a in loader["actions"]),
                   "Source count-zero DOM wait not detected")
            retry = inspect(6, "RetryGone")
            expect(retry["status"] == "requires_review"
                   and retry["retry"]["boundedLoops"] == 1
                   and retry["retry"]["sourceBackedTerminalRethrows"] == 1
                   and any(a["effect"] == "detached_wait"
                           for a in retry["actions"]),
                   "Retry terminal failure or wait state lost")
            for number, method in ((7, "HiddenNotDetached"),
                                   (8, "UnsafeDynamic")):
                blocked = inspect(number, method)
                expect(blocked["status"] == "blocked" and blocked["blockers"],
                       method + " must fail closed")
            for response in (combo, loader, retry):
                raw = str(response)
                expect("targetStatements" not in response
                       and "adapterCandidate" not in response
                       and all("targetStatement" not in action
                               for action in response["actions"])
                       and "private-search" not in raw
                       and "private-confirm" not in raw
                       and "private-loader" not in raw,
                       "Private source locator/target leaked over stdio")
            expect(source_hashes == {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.glob("*.cs")}, "MCP mutated source bytes")
            (root / "Helpers.cs").write_text(HELPERS + "\n// changed", encoding="utf-8")
            stale = call(process, 9, "inspect_pom_action_plan", {
                "sourceDirectory": "pom", "sourceType": "Page",
                "sourceMethod": "Select", "expectedSourceTreeHash": snapshot})
            expect(stale.get("isError"), "Stale source identity was accepted")
            print("POM_PREVIEW33_READ_ONLY_MCP_STDIO_PASSED")
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

if __name__ == "__main__":
    main()
