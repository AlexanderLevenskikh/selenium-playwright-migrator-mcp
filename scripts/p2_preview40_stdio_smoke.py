#!/usr/bin/env python3
"""Preview.40 source-only MCP external catch contract (stdio, no browser).
Verify exact source path/line/SHA, typed exception facts, redaction and
fail-closed filter/rethrow/broad/extra action controls.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect
from p2_preview38_stdio_smoke import SOURCE as PAGE
from p2_preview39_stdio_smoke import BASE

OUTER = """
using System;
using NUnit.Framework;
using OpenQA.Selenium;
namespace Fictional.P38;
[TestFixture]
public sealed class NUnitExternalTests : TestBase {
    private readonly IWebDriver webDriver = null!;
    public NUnitExternalTests(ExceptionPage page):base(page) {}
    [Test] public void CatchMissing() {
        try { ForwardMissing(); }
        catch (NoSuchElementException) {}
    }
    [Test] public void CatchTimeout() {
        try { ForwardTimeout(); }
        catch (WebDriverTimeoutException) {}
    }
}
"""

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview40_stdio_smoke.py <MCP DLL or executable>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable missing")
    with tempfile.TemporaryDirectory(prefix="fictional-p40-mcp-") as ws:
        root=Path(ws)/"pom";root.mkdir()
        for name,content in (("Page.cs",PAGE),("Base.cs",BASE),
                             ("NUnitTests.cs",OUTER)):
            (root/name).write_bytes(content.encode("utf-8"))
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.glob("*.cs"))}
        proc=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=ws))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"p40-readonly-contract","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={t["name"] for t in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_action_plan",
                    "inspect_pom_external_exception_contract"}<=names,
                   "Read-only external contract tool was not registered")
            expect(not any(n in names for n in (
                "apply_pom_action_plan","execute_target","run_browser")),
                "MCP tool set unexpectedly became side-effectful")
            next_id=3
            def rpc(name,args):
                nonlocal next_id
                response=value(call(proc,next_id,name,args))
                next_id+=1
                return response
            def snapshot():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["ExceptionPage"]})["sourceTreeHash"]
            def inspect(method,sha):
                return rpc("inspect_pom_external_exception_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":sha})
            first=snapshot()
            expect(len(first)==64,"SourceTreeHash must be SHA256")
            for method,expected_source,expected_target in (
                ("MissingRethrow","OpenQA.Selenium.NoSuchElementException",
                 "Microsoft.Playwright.PlaywrightException"),
                ("TimeoutRethrow","OpenQA.Selenium.WebDriverTimeoutException",
                 "System.TimeoutException")
            ):
                p=inspect(method,first)
                catches=p["catches"]
                expect(p["status"]=="requires_review" and not p["blockers"]
                       and not p["canAutoApply"] and not p["runtimeVerified"]
                       and p["requiresReview"] and p["execution"]=="read_only_not_run"
                       and p["adapter"]["snippetOnly"]
                       and not p["adapter"]["targetClauseVisibleOverMcp"]
                       and not p["adapter"]["externalClrExceptionIdentityPreserved"]
                       and len(p["sourceMethodSha256"])==64 and len(catches)==1,
                       "No complete source-only external contract: "+method)
                c=catches[0]
                expect(c["catchSourcePath"]=="NUnitTests.cs"
                       and c["catchSourceLine"]>0
                       and len(c["catchSourceSha256"])==64
                       and len(c["targetCatchSha256"])==64
                       and c["sourceCaughtType"]==expected_source
                       and c["targetCaughtType"]==expected_target
                       and "TestBase" in c["callerChain"]
                       and "NUnitExternalTests" in c["callerChain"]
                       and "targetCatchClause" not in c,
                       "External source typed caller/SHA evidence did not match")
                payload=str(p)
                expect(all(secret not in payload for secret in (
                    "private-missing-selector","private-loader",
                    "POM_SOURCE_ELEMENT_ABSENT","targetStatements",
                    "sourceMissing.Message.Contains","targetCatchClause")),
                    "MCP leaked source selector or target code")
                old=rpc("inspect_pom_action_plan",{
                    "sourceDirectory":"pom",
                    "sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":first})
                expect(old["status"]=="blocked" and old["blockers"]
                       and not old["canAutoApply"]
                       and "targetStatements" not in old,
                       "Original preview.39 whole-method block was silently removed")

            def neg(outer):
                (root/"NUnitTests.cs").write_bytes(outer.encode("utf-8"))
                sha=snapshot()
                r=inspect("MissingRethrow",sha)
                expect(r["status"]=="blocked" and r["blockers"]
                       and not r["catches"] and not r["canAutoApply"]
                       and not r["runtimeVerified"]
                       and "targetCatchClause" not in str(r),
                       "Unknown catch filter/broad/throw or side effects got a candidate")
                return r
            orig='catch (NoSuchElementException) {}'
            expect(OUTER.count(orig)==1,"Source control marker not unique")
            neg(OUTER.replace(orig,
                'catch (NoSuchElementException e) when(e.Message.Length > 0) {}',1))
            neg(OUTER.replace(orig,'catch (System.Exception) {}',1))
            neg(OUTER.replace(orig,'catch (NoSuchElementException) {throw;}',1))
            count=neg(OUTER.replace(orig,
                'catch (NoSuchElementException) {'
                ' Assert.That(webDriver.FindElements(By.Id("private-count-recovery")).Count,'
                ' Is.EqualTo(0)); }',1))
            expect(any(b["code"]=="POM_EXTERNAL_CONTRACT_CATCH_BODY_UNSUPPORTED"
                       for b in count["blockers"])
                   and "private-count-recovery" not in str(count),
                   "Typed Count recovery leaked or escaped async/receiver blocker")
            neg(OUTER.replace('try { ForwardMissing(); }',
                'try { ForwardMissing(); ForwardTimeout(); }',1))
            neg(OUTER.replace('    [Test] public void CatchTimeout() {',
                '    [Test] public void Additional() {'
                'try{ForwardMissing();}catch(NoSuchElementException){}\n'
                '    }\n'
                '    [Test] public void CatchTimeout() {',1))
            (root/"NUnitTests.cs").write_bytes(OUTER.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.glob("*.cs"))}==before,
                   "Original synthetic source bytes failed restore")
            (root/"NUnitTests.cs").write_bytes((OUTER+"\n//changed").encode("utf-8"))
            stale=call(proc,next_id,"inspect_pom_external_exception_contract",{
                "sourceDirectory":"pom",
                "sourceType":"Fictional.P38.ExceptionPage",
                "sourceMethod":"MissingRethrow",
                "expectedSourceTreeHash":first})
            expect(stale.get("isError"),"MCP accepted a stale source tree hash")
            print("POM_PREVIEW40_EXTERNAL_EXCEPTION_CONTRACT_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)

if __name__=="__main__":
    main()
