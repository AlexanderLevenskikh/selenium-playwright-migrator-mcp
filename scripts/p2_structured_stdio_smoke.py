#!/usr/bin/env python3
"""Public synthetic source-backed structured POM inspector, actual MCP stdio."""
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
using System;
namespace Fictional.P31;
public sealed class SyntheticPage {
    private readonly IWebDriver driver;
    public SyntheticPage(IWebDriver driver) => this.driver = driver;
    public void Choose(string value) {
        OpenPicker();
        driver.FindElement(By.Id("search")).Clear();
        driver.FindElement(By.Id("search")).SendKeys(value);
        if (driver.FindElements(By.CssSelector("[data-test='option']")).Count > 0) {
            driver.FindElements(By.CssSelector("[data-test='option']"))[0].Click();
        } else {
            Assert.That(driver.FindElements(By.CssSelector("[data-test='option']")).Count,
                Is.EqualTo(0));
        }
    }
    private void OpenPicker() { driver.FindElement(By.Id("picker")).Click(); }
    public void GuardedWait(int timeoutMs) {
        if (timeoutMs < 1 || timeoutMs > 3000)
            throw new ArgumentOutOfRangeException(nameof(timeoutMs));
        new WebDriverWait(driver, TimeSpan.FromMilliseconds(timeoutMs))
            .Until(d => d.FindElement(By.Id("ready")).Displayed);
    }
    public void UnsafeWait(int timeoutMs) {
        new WebDriverWait(driver, TimeSpan.FromMilliseconds(timeoutMs))
            .Until(d => d.FindElement(By.Id("ready")).Displayed);
    }
    public void UnsafeElse() {
        if (driver.FindElements(By.Id("picker")).Count > 0) {
            driver.FindElement(By.Id("picker")).Click();
        } else { System.Threading.Thread.Sleep(1); }
    }
    public void UnsafeDynamicUrl() {
        driver.Navigate().GoToUrl(Environment.GetEnvironmentVariable("PRIVATE_URL")!);
    }
}
"""

def require(cond, message):
    if not cond:
        raise AssertionError(message)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: p2_structured_stdio_smoke.py <MCP dll or executable>")
    binary = str(Path(sys.argv[1]).resolve())
    require(Path(binary).exists(), "MCP binary missing")
    with tempfile.TemporaryDirectory(prefix="synthetic-p31-mcp-") as root:
        file = Path(root) / "pom" / "SyntheticPage.cs"
        file.parent.mkdir()
        file.write_text(SOURCE, encoding="utf-8")
        initial = hashlib.sha256(file.read_bytes()).hexdigest()
        command = ["dotnet", binary] if binary.endswith(".dll") else [binary]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=root))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0","id":1,"method":"initialize",
                        "params":{"protocolVersion":"2025-06-18",
                                  "capabilities":{},"clientInfo":{"name":"p31-structured","version":"0.1"}}})
            require("serverInfo" in receive(proc, 1), "MCP initialization failed")
            send(proc, {"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc, {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names = {x["name"] for x in receive(proc, 2)["tools"]}
            require("inspect_pom_action_plan" in names and "inspect_pom_sources" in names,
                    "required read-only protocol tools missing")
            baseline = value(call(proc, 3, "inspect_pom_sources",
                                  {"sourceDirectory":"pom","pageTypes":["SyntheticPage"]}))
            tree_hash = baseline["sourceTreeHash"]

            def inspect(request_id, method):
                return value(call(proc, request_id, "inspect_pom_action_plan",
                    {"sourceDirectory":"pom","sourceType":"Fictional.P31.SyntheticPage",
                     "sourceMethod":method,"expectedSourceTreeHash":tree_hash}))

            combo = inspect(4, "Choose")
            require(combo["schemaVersion"]=="migrator-pom-action/v1alpha3"
                    and combo["status"]=="requires_review"
                    and combo["canAutoApply"] is False
                    and combo["runtimeVerified"] is False,
                    "Roslyn structured POM was auto-approved or has wrong schema")
            actions = combo["actions"]
            require(combo["provenSourceActions"]==len(actions)
                    and len(actions)>=6
                    and any(a["effect"]=="private_helper_inline" for a in actions)
                    and any(a["effect"]=="conditional_guard" for a in actions)
                    and any(a["controlFlowPath"].startswith("if:true@") for a in actions)
                    and any(a["controlFlowPath"].startswith("if:false@") for a in actions)
                    and any(a["controlFlowPath"].startswith("helper:OpenPicker@") for a in actions),
                    "One source action, helper, conditional path or branch was lost")
            require(all(a["sourcePath"]=="SyntheticPage.cs"
                        and a["sourceLine"]>0
                        and len(a["sourceSha256"])==64
                        and len(a["targetSha256"])==64
                        and a["requiresReview"] for a in actions),
                    "Source path, SHA, review-required or type provenance missing")
            require(all("targetStatement" not in a for a in actions)
                    and "targetStatements" not in combo
                    and "adapterCandidate" not in combo
                    and "data-test='option'" not in str(combo)
                    and "PRIVATE_URL" not in str(combo),
                    "MCP exposed source bodies, selector/URL text or executable statements")

            wait = inspect(5, "GuardedWait")
            require(wait["status"]=="requires_review"
                    and any(a["effect"]=="timeout_bound_guard" for a in wait["actions"])
                    and any(a["effect"]=="visible_wait" for a in wait["actions"]),
                    "Finite source-guarded dynamic wait not detected")
            for number, method, code in (
                (6, "UnsafeWait", "POM_DYNAMIC_WAIT_UNBOUNDED"),
                (7, "UnsafeElse", "POM_ACTION_UNRESOLVED"),
                (8, "UnsafeDynamicUrl", "POM_ACTION_UNRESOLVED"),
            ):
                finding = inspect(number, method)
                require(finding["status"]=="blocked"
                        and finding["blockers"]
                        and any(x["code"]==code for x in finding["blockers"]),
                        method+" was not fail-closed: "+str(finding["blockers"]))
            require(initial==hashlib.sha256(file.read_bytes()).hexdigest(),
                    "Read-only MCP altered source bytes")
            file.write_text(SOURCE+"\n// changed", encoding="utf-8")
            stale = call(proc, 9, "inspect_pom_action_plan",
                {"sourceDirectory":"pom","sourceType":"SyntheticPage",
                 "sourceMethod":"Choose","expectedSourceTreeHash":tree_hash})
            require(stale.get("isError"), "Changed source was accepted by stale hash")
            print("POM_PREVIEW31_STRUCTURED_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

if __name__ == "__main__":
    main()
