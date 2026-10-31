#!/usr/bin/env python3
"""Preview.38 read-only MCP stdio: typed source exception recovery/rethrow,
fail-closed filters/broad catch/click, no selectors or C# target leakage.
No browser or Selenium test is executed by MCP.
"""
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
namespace Fictional.P38;
public sealed class ExceptionPage {
    private readonly IWebDriver driver;
    public ExceptionPage(IWebDriver driver) { this.driver=driver; }
    public void MissingRecovery() {
        try {
            Assert.That(driver.FindElement(By.Id("private-missing-selector")).Text,
                Is.EqualTo("ready"));
        } catch (NoSuchElementException) {
            Assert.That(driver.FindElements(By.Id("private-missing-selector")).Count,
                Is.EqualTo(0));
        }
    }
    public void MissingRethrow() {
        try {
            Assert.That(driver.FindElement(By.Id("private-missing-selector")).Text,
                Is.EqualTo("ready"));
        } catch (NoSuchElementException) { throw; }
    }
    public void TimeoutRecovery() {
        try {
            new WebDriverWait(driver, TimeSpan.FromMilliseconds(80))
                .Until(d => d.FindElements(By.Id("private-loader")).Count == 0);
        } catch (WebDriverTimeoutException) {
            Assert.That(driver.FindElements(By.Id("private-loader")).Count,
                Is.EqualTo(1));
        }
    }
    public void TimeoutRethrow() {
        try {
            new WebDriverWait(driver, TimeSpan.FromMilliseconds(80))
                .Until(d => d.FindElements(By.Id("private-loader")).Count == 0);
        } catch (WebDriverTimeoutException) { throw; }
    }
    public void UnsafeFilter() {
        try {
            Assert.That(driver.FindElement(By.Id("private-missing-selector")).Text,
                Is.EqualTo("ready"));
        } catch (NoSuchElementException ex) when (ex.Message != "") { throw; }
    }
    public void UnsafeBroadCatch() {
        try {
            Assert.That(driver.FindElement(By.Id("private-missing-selector")).Text,
                Is.EqualTo("ready"));
        } catch (Exception) { throw; }
    }
    public void UnsafeClickCatch() {
        try { driver.FindElement(By.Id("private-click")).Click(); }
        catch (NoSuchElementException) { throw; }
    }
}
"""
def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview38_stdio_smoke.py <MCP DLL/executable>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable absent")
    with tempfile.TemporaryDirectory(prefix="p38-public-mcp-") as workspace:
        root=Path(workspace)/"pom";root.mkdir()
        f=root/"ExceptionPage.cs";f.write_bytes(SOURCE.encode("utf-8"))
        source_hash=hashlib.sha256(f.read_bytes()).hexdigest()
        proc=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=workspace))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"preview38-source-exception","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_action_plan"}<=names,
                   "Source-only POM tools missing")
            expect(not any(n in names for n in
                ("run_browser","execute_target","apply_pom_action_plan")),
                "MCP unexpectedly exposes a side-effectful tool")
            inventory=value(call(proc,3,"inspect_pom_sources",{
                "sourceDirectory":"pom","pageTypes":["ExceptionPage"]}))
            snapshot=inventory["sourceTreeHash"]
            expect(len(snapshot)==64,"Source snapshot must be SHA-256")
            def inspect(i,method):
                return value(call(proc,i,"inspect_pom_action_plan",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":snapshot}))
            for i,method,is_rethrow in (
                (4,"MissingRecovery",False),(5,"MissingRethrow",True),
                (6,"TimeoutRecovery",False),(7,"TimeoutRethrow",True)):
                p=inspect(i,method)
                facts=p["exceptions"]
                expect(p["status"]=="requires_review"
                    and p["execution"]=="read_only_not_run"
                    and not p["runtimeVerified"] and not p["canAutoApply"]
                    and len(p["sourceMethodSha256"])==64
                    and facts["sourceTypedCatchClauses"]==1
                    and facts["sourceBareRethrows"]==(1 if is_rethrow else 0)
                    and facts["sourceOnly"] and not facts["runtimeVerified"]
                    and not facts["canAutoApply"]
                    and facts["outsideCatchClrIdentity"]=="not_equivalent_requires_review"
                    and facts["catchFilters"]=="blocked"
                    and facts["genericCatch"]=="blocked"
                    and any(a["effect"]=="source_exception_catch" for a in p["actions"])
                    and all(a["requiresReview"] for a in p["actions"])
                    and "targetStatements" not in p and "adapterCandidate" not in p,
                    "MCP source exception provenance/review barrier failed: "+method)
                payload=str(p)
                expect(all(token not in payload for token in (
                    "private-missing-selector","private-loader",
                    "POM_SOURCE_ELEMENT_ABSENT","sourceMissing.Message.Contains",
                    "targetStatementTemplates")),
                    "Private selector or executable mapping leaked for "+method)
            for i,method in ((8,"UnsafeFilter"),(9,"UnsafeBroadCatch"),
                             (10,"UnsafeClickCatch")):
                p=inspect(i,method)
                expect(p["status"]=="blocked" and p["blockers"]
                    and not p["canAutoApply"] and not p["runtimeVerified"]
                    and "targetStatements" not in p
                    and "adapterCandidate" not in p
                    and "private-click" not in str(p),
                    "Unsafe exception mapping accepted or leaked: "+method)
            expect(hashlib.sha256(f.read_bytes()).hexdigest()==source_hash,
                   "Read-only MCP tool mutated original source")
            f.write_bytes((SOURCE+"\n// stale").encode("utf-8"))
            stale=call(proc,11,"inspect_pom_action_plan",{
                "sourceDirectory":"pom","sourceType":"ExceptionPage",
                "sourceMethod":"MissingRecovery","expectedSourceTreeHash":snapshot})
            expect(stale.get("isError"),"MCP accepted stale source hash")
            print("POM_PREVIEW38_TYPED_EXCEPTION_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)
if __name__=="__main__":
    main()
