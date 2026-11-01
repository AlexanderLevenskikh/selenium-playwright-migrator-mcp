#!/usr/bin/env python3
"""Preview.39 source-only MCP stdio regression:
exact symbol-based PageObject->TestBase->NUnit external catch blockers.
Never execute source or browser, never expose private source selectors.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect
from p2_preview38_stdio_smoke import SOURCE as PAGE

BASE = """
using OpenQA.Selenium;
namespace Fictional.P38;
public class TestBase {
    protected readonly ExceptionPage page;
    public TestBase(ExceptionPage page) { this.page=page; }
    protected void ForwardMissing() { page.MissingRethrow(); }
    protected void ForwardTimeout() { page.TimeoutRethrow(); }
}
"""
NUNIT = """
using OpenQA.Selenium;
using System;
using NUnit.Framework;
namespace Fictional.P38;
[TestFixture]
public sealed class NUnitExternalTests : TestBase {
    public NUnitExternalTests(ExceptionPage page) : base(page) { }
    [Test] public void ExternalMissing() {
        try { ForwardMissing(); }
        catch (NoSuchElementException) { }
    }
    [Test] public void ExternalTimeout() {
        try { ForwardTimeout(); }
        catch (WebDriverTimeoutException) { }
    }
    [Test] public void ExternalFilter() {
        try { ForwardMissing(); }
        catch (NoSuchElementException ex) when (ex.Message.Length > 0) { }
    }
    [Test] public void ExternalBroad() {
        try { ForwardMissing(); }
        catch (Exception) { }
    }
    [Test] public void Irrelevant() {
        try { page.MissingRecovery(); }
        catch (ArgumentException) { }
    }
}
"""

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview39_stdio_smoke.py <MCP DLL or executable>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable not found")
    with tempfile.TemporaryDirectory(prefix="public-p39-mcp-") as ws:
        root=Path(ws)/"pom";root.mkdir()
        for filename,content in (
            ("Page.cs",PAGE),("TestBase.cs",BASE),("NUnitTests.cs",NUNIT)):
            (root/filename).write_bytes(content.encode("utf-8"))
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.glob("*.cs"))}
        proc=subprocess.Popen(
            ["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=ws))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"preview39-callgraph-stdio","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={tool["name"] for tool in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_action_plan"}<=names,
                   "Source-only tools missing")
            expect(not any(name in names for name in (
                "run_browser","apply_pom_action_plan","execute_target")),
                   "MCP introduced a side-effectful tool")
            inv=value(call(proc,3,"inspect_pom_sources",{
                "sourceDirectory":"pom","pageTypes":["ExceptionPage"]}))
            hash0=inv["sourceTreeHash"]
            expect(len(hash0)==64,"Source tree identity not SHA-256")
            def plan(index,method):
                return value(call(proc,index,"inspect_pom_action_plan",{
                    "sourceDirectory":"pom",
                    "sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,
                    "expectedSourceTreeHash":hash0}))
            for index,method,code in (
                (4,"MissingRethrow","POM_EXTERNAL_NO_SUCH_ELEMENT_CATCH"),
                (5,"TimeoutRethrow","POM_EXTERNAL_WEBDRIVER_TIMEOUT_CATCH")):
                p=plan(index,method)
                graph=p["externalCatchChains"]
                expect(p["status"]=="blocked" and p["blockers"]
                       and p["execution"]=="read_only_not_run"
                       and not p["canAutoApply"] and not p["runtimeVerified"]
                       and len(p["sourceMethodSha256"])==64
                       and graph["blocked"]
                       and graph["inScopeBlockedCatchSites"]>=1
                       and not graph["noFindingsProvesExceptionParity"]
                       and graph["sourceOnly"] and not graph["runtimeVerified"]
                       and not graph["canAutoApply"]
                       and any(b["code"]==code
                          and b["sourcePath"]=="NUnitTests.cs"
                          and b["sourceLine"]>0
                          and len(b["sourceSha256"])==64 for b in p["blockers"])
                       and "targetStatements" not in p
                       and "adapterCandidate" not in p,
                       "External source catch chain was not blocked by exact Roslyn symbols: "+method)
                payload=str(p)
                expect(all(secret not in payload for secret in (
                    "private-missing-selector","private-loader",
                    "POM_SOURCE_ELEMENT_ABSENT","sourceMissing.Message.Contains",
                    "targetStatementTemplates")),
                    "MCP leaked target C# or a source selector")
            missing=plan(6,"MissingRethrow")
            expect(any(b["code"]=="POM_EXTERNAL_EXCEPTION_FILTER"
                       for b in missing["blockers"])
                   and any(b["code"]=="POM_EXTERNAL_EXCEPTION_BROAD_CATCH"
                       for b in missing["blockers"]),
                   "External filter and broad catch paths were silently dropped")
            unrelated=plan(7,"MissingRecovery")
            expect(unrelated["status"]=="requires_review"
                   and not unrelated["canAutoApply"]
                   and not unrelated["runtimeVerified"]
                   and not unrelated["externalCatchChains"]["blocked"]
                   and unrelated["externalCatchChains"]["inScopeBlockedCatchSites"]==0
                   and not unrelated["externalCatchChains"]["noFindingsProvesExceptionParity"]
                   and "targetStatements" not in unrelated,
                   "Unrelated catch was misclassified or promoted to auto-apply")
            invalid=plan(8,"UnsafeClickCatch")
            expect(invalid["status"]=="blocked" and invalid["blockers"]
                   and "targetStatements" not in invalid
                   and "private-click" not in str(invalid),
                   "Unproven Selenium click catch became executable or leaked source")
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.glob("*.cs"))}==before,
                   "MCP source read unexpectedly modified private source")
            with (root/"NUnitTests.cs").open("ab") as changed:
                changed.write(b"\n// stale")
            stale=call(proc,9,"inspect_pom_action_plan",{
                "sourceDirectory":"pom",
                "sourceType":"Fictional.P38.ExceptionPage",
                "sourceMethod":"MissingRethrow",
                "expectedSourceTreeHash":hash0})
            expect(stale.get("isError"),"MCP accepted stale whole-tree source hash")
            print("POM_PREVIEW39_SOURCE_CALLCHAIN_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)

if __name__=="__main__":
    main()
