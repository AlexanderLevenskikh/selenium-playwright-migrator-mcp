#!/usr/bin/env python3
"""Preview.41 source-bound async NUnit/TestBase external Count stdio.
No source/selector/target code crosses MCP. No browser execution.
"""
import hashlib,os,subprocess,sys,tempfile
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview38_stdio_smoke import SOURCE as PAGE
from p2_preview39_stdio_smoke import BASE

OUTER = """
using NUnit.Framework;
using OpenQA.Selenium;
namespace Fictional.P38;
[TestFixture] public sealed class NUnitExternalTests:TestBase {
    private readonly IWebDriver driver = null!;
    private readonly Microsoft.Playwright.IPage Page;
    public NUnitExternalTests(ExceptionPage source,
        Microsoft.Playwright.IPage mappedPage):base(source) {
        this.Page=mappedPage;
    }
    [Test] public void CatchMissing() {
        try { ForwardMissing(); }
        catch(NoSuchElementException) {
            Assert.That(driver.FindElements(By.Id("private-missing-selector")).Count,Is.EqualTo(0));
        }
    }
    [Test] public void CatchTimeout() {
        try { ForwardTimeout(); }
        catch(WebDriverTimeoutException) {
            Assert.That(driver.FindElements(By.Id("private-loader")).Count,Is.EqualTo(1));
        }
    }
}
"""
def main():
    if len(sys.argv)!=2:raise SystemExit("usage: p2_preview41_stdio_smoke.py <DLL or exe>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable not found")
    with tempfile.TemporaryDirectory(prefix="fictional-p41-mcp-") as workspace:
        root=Path(workspace)/"pom";root.mkdir()
        for name,source in (("Page.cs",PAGE),("TestBase.cs",BASE),
                            ("NUnitTests.cs",OUTER)):
            (root/name).write_bytes(source.encode("utf-8"))
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.glob("*.cs"))}
        proc=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=workspace))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"preview41-async-count","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_action_plan",
                    "inspect_pom_external_exception_contract",
                    "inspect_pom_external_async_count_contract"}<=names,
                   "Source-only async inspection tool unavailable")
            expect(not any(x in names for x in
                ("execute_target","run_browser","apply_pom_action_plan")),
                "MCP accidentally exposed execution or mutation")
            nextId=3
            def rpc(method,args):
                nonlocal nextId
                answer=value(call(proc,nextId,method,args));nextId+=1
                return answer
            def snapshot():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["ExceptionPage"]})["sourceTreeHash"]
            def inspect(method,sha,receiver="Page"):
                return rpc("inspect_pom_external_async_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":sha,
                    "explicitPageReceiver":receiver})
            frozen=snapshot()
            for method,src,target in (
                ("MissingRethrow","OpenQA.Selenium.NoSuchElementException",
                    "Microsoft.Playwright.PlaywrightException"),
                ("TimeoutRethrow","OpenQA.Selenium.WebDriverTimeoutException",
                    "System.TimeoutException")):
                p=inspect(method,frozen)
                expect(p["status"]=="requires_review"
                    and p["schemaVersion"]=="migrator-pom-external-async-count/v1"
                    and p["verifiedPageReceiver"]=="Page"
                    and not p["blockers"] and len(p["asyncMethods"])==3
                    and len(p["catches"])==1
                    and not p["runtimeVerified"] and not p["canAutoApply"]
                    and p["requiresReview"] and p["execution"]=="read_only_not_run",
                    "Source exact async path not verified: "+method)
                expect([x["sourcePath"] for x in p["asyncMethods"]]
                       ==["Page.cs","TestBase.cs","NUnitTests.cs"]
                    and all(len(x["sourceSha256"])==64 and x["sourceLine"]>0
                            and x["requiresAsyncTask"]
                            and "targetSignature" not in x and "targetBody" not in x
                            for x in p["asyncMethods"]),
                    "Unproven async evidence or private target emitted")
                c=p["catches"][0]
                expect(c["sourceCaughtType"]==src and c["targetCaughtType"]==target
                    and len(c["targetCatchSha256"])==64
                    and "targetCatchClause" not in c,
                    "Wrong typed source/target exception contract")
                payload=str(p)
                expect(not any(secret in payload for secret in (
                    "private-missing-selector","private-loader",
                    "POM_SOURCE_ELEMENT_ABSENT","CountAsync","Page.Locator(",
                    "targetBody","targetSignature","targetCatchClause")),
                    "MCP leaked locator, target statement or source code")
                old=rpc("inspect_pom_external_exception_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P38.ExceptionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":frozen})
                expect(old["status"]=="blocked" and not old["catches"],
                    "preview.40 historical safety block was weakened")
            wrong=inspect("MissingRethrow",frozen,"Unknown")
            expect(wrong["status"]=="blocked"
                and not wrong["catches"] and not wrong["asyncMethods"],
                "Unmapped IPage receiver was accepted")
            def negative(outer):
                (root/"NUnitTests.cs").write_bytes(outer.encode("utf-8"))
                r=inspect("MissingRethrow",snapshot())
                expect(r["status"]=="blocked"
                    and not r["asyncMethods"] and not r["catches"]
                    and r["blockers"] and not r["canAutoApply"],
                    "Unknown async/receiver/catch condition emitted candidate")
            negative(OUTER.replace("Microsoft.Playwright.IPage Page",
                "object Page"))
            negative(OUTER.replace("this.Page=mappedPage;",
                "this.Page=null!;"))
            negative(OUTER.replace("[Test] public void CatchMissing()",
                "public void CatchMissing()"))
            negative(OUTER.replace("Is.EqualTo(0)","Is.GreaterThan(0)"))
            negative(OUTER.replace("catch(NoSuchElementException) {",
                "catch(NoSuchElementException e) when(e.Message.Length>0) {"))
            negative(OUTER.replace("try { ForwardMissing(); }",
                "try { ForwardMissing(); ForwardTimeout(); }"))
            (root/"NUnitTests.cs").write_bytes(OUTER.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.glob("*.cs"))}==before,
                   "Immutable synthetic sources not restored")
            (root/"NUnitTests.cs").write_bytes((OUTER+"\n//stale").encode("utf-8"))
            error=call(proc,nextId,"inspect_pom_external_async_count_contract",{
                "sourceDirectory":"pom","sourceType":"Fictional.P38.ExceptionPage",
                "sourceMethod":"MissingRethrow",
                "expectedSourceTreeHash":frozen,"explicitPageReceiver":"Page"})
            expect(error.get("isError"),"Stale source SHA was accepted")
            print("POM_PREVIEW41_ASYNC_COUNT_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
