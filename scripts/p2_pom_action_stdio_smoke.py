#!/usr/bin/env python3
"""Real MCP stdio regression: invented typed POM action projection, no source execution."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SOURCE = """
using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;
using NUnit.Framework;
namespace Fictional.Ui;
public sealed class FictionalCatalogPage {
    readonly IWebDriver driver;
    public FictionalCatalogPage(IWebDriver driver) => this.driver = driver;
    public void Open(string url) { driver.Navigate().GoToUrl(url); }
    public void Pick(string value) {
        driver.FindElement(By.Id("picker")).Click();
        driver.FindElement(By.Id("search")).Clear();
        driver.FindElement(By.Id("search")).SendKeys(value);
        driver.FindElement(By.CssSelector("[data-test='option']")).Click();
    }
    public void Ready() {
        new WebDriverWait(driver, System.TimeSpan.FromMilliseconds(900))
            .Until(d => d.FindElement(By.Id("ready")).Displayed);
    }
    public void Table() {
        Assert.That(driver.FindElements(By.CssSelector("[data-test='row']")).Count,
            Is.EqualTo(2));
    }
    public void Unsafe() {
        driver.FindElement(By.Id("picker")).Click();
        System.Threading.Thread.Sleep(4);
    }
    public void Dynamic() {
        driver.FindElement(By.CssSelector(System.Environment.GetEnvironmentVariable("ID")!)).Click();
    }
}
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: p2_pom_action_stdio_smoke.py <compiled MCP dll or executable>")
    executable = str(Path(sys.argv[1]).resolve())
    expect(Path(executable).exists(), "MCP executable missing")
    with tempfile.TemporaryDirectory(prefix="fictional-p2-pom-") as root:
        workspace = Path(root)
        src = workspace / "pom" / "FictionalCatalogPage.cs"
        src.parent.mkdir()
        src.write_text(SOURCE, encoding="utf-8")
        original_sha = hashlib.sha256(src.read_bytes()).hexdigest()
        env = dict(os.environ, MIGRATOR_WORKSPACE=str(workspace))
        proc = subprocess.Popen(["dotnet", executable] if executable.endswith(".dll")
                                else [executable], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18",
                                   "capabilities": {},
                                   "clientInfo": {"name": "p2-preview30", "version": "0.1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialization failed")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            send(proc, {"jsonrpc": "2.0", "id": 2,
                        "method": "tools/list", "params": {}})
            names = {tool["name"] for tool in receive(proc, 2)["tools"]}
            expect("inspect_pom_action_plan" in names, "Missing P2 inspection tool")
            baseline = value(call(proc, 3, "inspect_pom_sources",
                                  {"sourceDirectory": "pom",
                                   "pageTypes": ["FictionalCatalogPage"]}))
            h = baseline["sourceTreeHash"]
            expect(len(h) == 64, "Source scope SHA missing")
            for method, kind, count in (
                ("Open", "navigation", 1),
                ("Pick", "input_sendkeys", 4),
                ("Ready", "visible_wait", 1),
                ("Table", "table_count_assertion", 1),
            ):
                result = value(call(proc, 10 + count + len(method),
                                    "inspect_pom_action_plan",
                                    {"sourceDirectory": "pom",
                                     "sourceType": "Fictional.Ui.FictionalCatalogPage",
                                     "sourceMethod": method,
                                     "expectedSourceTreeHash": h}))
                expect(result["schemaVersion"] == "migrator-pom-action/v1alpha3"
                       and result["status"] == "requires_review"
                       and not result["canAutoApply"]
                       and not result["runtimeVerified"], "POM proposal was auto-approved")
                expect(result["provenSourceActions"] == count
                       and len(result["actions"]) == count
                       and any(x["effect"] == kind for x in result["actions"]),
                       method + " action inventory mismatch")
                expect(all(x["sourceLine"] > 0
                           and len(x["sourceSha256"]) == 64
                           and len(x["targetSha256"]) == 64
                           and x["requiresReview"] for x in result["actions"]),
                       method + " missing line/hash/review provenance")
                expect(all("targetStatement" not in x
                           for x in result["actions"])
                       and "targetStatements" not in result,
                       "MCP exposed private locator/URL expression")
                expect(result["execution"] == "read_only_not_run",
                       "MCP invented POM execution evidence")

            for method in ("Unsafe", "Dynamic"):
                result = value(call(proc, 55 if method == "Unsafe" else 56,
                                    "inspect_pom_action_plan",
                                    {"sourceDirectory": "pom",
                                     "sourceType": "FictionalCatalogPage",
                                     "sourceMethod": method,
                                     "expectedSourceTreeHash": h}))
                expect(result["status"] == "blocked" and result["blockers"],
                       method + " incomplete source method escaped without block")
            expect(hashlib.sha256(src.read_bytes()).hexdigest() == original_sha,
                   "Read-only MCP tool wrote to source")
            src.write_text(SOURCE + "\n// mutation", encoding="utf-8")
            stale = call(proc, 60, "inspect_pom_action_plan",
                         {"sourceDirectory": "pom",
                          "sourceType": "FictionalCatalogPage",
                          "sourceMethod": "Open",
                          "expectedSourceTreeHash": h})
            expect(stale.get("isError"), "Stale POM source hash was accepted")
            print("P2_POM_ACTION_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
