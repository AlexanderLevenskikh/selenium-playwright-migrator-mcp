#!/usr/bin/env python3
"""preview46 strict MCP stdio: typed TargetClosed in NUnit TearDown only."""
import hashlib,os,subprocess,sys,tempfile
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview42_stdio_smoke import canonical_source
from p2_preview45_stdio_smoke import source_fixture

def source():
    base=source_fixture()
    f46=Path("core/Migrator.Application.Smoke/PomPreview46TypedTargetClosedSmoke.cs")
    expect(f46.is_file(),"Pinned exact Core preview.46 NUnit AST fixture unavailable")
    content=f46.read_text(encoding="utf-8")
    before=canonical_source("OriginalTearDown",content).strip()
    after=canonical_source("TypedTearDown",content).strip()
    fixture=base["NUnitFixture.cs"]
    expect(fixture.split(before).__len__()==2,
        "Core fixture TearDown provenance ambiguous")
    base["NUnitFixture.cs"]=fixture.replace(before,after)
    return base

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview46_stdio_smoke.py <MCP DLL/executable>")
    binary=str(Path(sys.argv[1]).resolve())
    expect(Path(binary).is_file(),"MCP binary unavailable")
    sources=source()
    with tempfile.TemporaryDirectory(prefix="fictional-p46-targetclosed-") as tmp:
        folder=Path(tmp)/"pom";folder.mkdir()
        for name,code in sources.items():
            (folder/name).write_bytes(code.encode("utf-8"))
        old={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
             for p in folder.iterdir()}
        proc=subprocess.Popen(["dotnet",binary] if binary.endswith(".dll")
            else [binary],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,env=dict(os.environ,MIGRATOR_WORKSPACE=tmp))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                "clientInfo":{"name":"p46-target-closed","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={t["name"] for t in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources",
                "inspect_pom_cleanup_fault_witness",
                "inspect_pom_typed_target_closed_teardown"}<=names,
                "Source-only TargetClosed tool absent")
            expect(not {"execute_target","run_browser","apply_pom_action_plan"}&names,
                "MCP unexpectedly has execution side-effect tools")
            request=3
            def rpc(tool,args):
                nonlocal request
                valueResult=value(call(proc,request,tool,args));request+=1
                return valueResult
            def digest():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["SourcePage"]})["sourceTreeHash"]
            def inspect(method,sha,fields=("Page","Context","Browser","PW")):
                return rpc("inspect_pom_typed_target_closed_teardown",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":sha,
                    "pageField":fields[0],"contextField":fields[1],
                    "browserField":fields[2],"playwrightField":fields[3]})
            original=digest()
            expect(len(original)==64,"Frozen source digest missing")
            for method in ("Missing","Timeout"):
                p=inspect(method,original)
                proof=p["fixture"]
                expect(p["status"]=="requires_review"
                    and p["schemaVersion"]=="migrator-pom-typed-target-closed-teardown/v1"
                    and p["sourceTreeHash"]==original and proof
                    and proof["typedTargetClosedTearDownSourceOnly"]
                    and proof["contextTargetClosedCatchGuarded"]
                    and proof["pageTargetClosedCatchGuarded"]
                    and proof["testFailurePrecedenceOnlyForTargetClosed"]
                    and len(proof["contextTargetClosedCatchSha256"])==64
                    and len(proof["pageTargetClosedCatchSha256"])==64
                    and proof["pageTargetClosedCatchLine"]>0
                    and proof["contextTargetClosedCatchLine"]>
                        proof["pageTargetClosedCatchLine"]
                    and len(p["catches"])==1 and len(p["asyncMethods"])==3
                    and not p["canAutoApply"] and not p["runtimeVerified"],
                    "Typed source catch/ownership not admitted "+method+" "+str(p))
                expect(not any(t in str(p) for t in (
                    "never-created","loader","Page.Locator(", "CountAsync",
                    "targetBody","targetSignature","targetCatchClause",
                    "System.Console.Error.WriteLine","P46_PRIMARY_ASSERTION",
                    "Exception.StackTrace","exceptionMessage")),
                    "MCP leaked source, target, selectors or private exception text")
                historical=rpc("inspect_pom_cleanup_fault_witness",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":original,
                    "pageField":"Page","contextField":"Context",
                    "browserField":"Browser","playwrightField":"PW"})
                expect(historical["status"]=="blocked" and not historical["catches"],
                    "Historical preview45 gate accidentally widened")
            invalid=inspect("Missing",original,("Page","Other","Browser","PW"))
            expect(invalid["status"]=="blocked" and not invalid["catches"],
                "Unknown Context receiver accepted")
            fixture=sources["NUnitFixture.cs"]
            cases=[
                fixture.replace("catch (Microsoft.Playwright.TargetClosedException)",
                    "catch (System.Exception)"),
                fixture.replace("catch (Microsoft.Playwright.TargetClosedException)",
                    "catch (Microsoft.Playwright.PlaywrightException)"),
                fixture.replace("await Context.CloseAsync();",
                    "await Page.CloseAsync();"),
                fixture.replace("MIGRATOR_CLEANUP_CONTEXT_CLOSE_FAILED",
                    "PRIVATE_UNTRUSTED_VALUE"),
                fixture.replace(
                    "catch (Microsoft.Playwright.TargetClosedException)",
                    "catch (Microsoft.Playwright.TargetClosedException x) when (x.Message.Length>0)")
            ]
            for item in cases:
                expect(item!=fixture,"Negative source mutation ineffective")
                (folder/"NUnitFixture.cs").write_text(item,encoding="utf-8")
                report=inspect("Missing",digest())
                expect(report["status"]=="blocked" and not report["catches"]
                    and not report["asyncMethods"]
                    and report["fixture"] is None and report["blockers"],
                    "Unsupported TargetClosed catch emitted partial plan")
            for name,content in sources.items():
                (folder/name).write_bytes(content.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in folder.iterdir()}==old,
                    "MCP unexpectedly wrote source")
            (folder/"NUnitFixture.cs").write_text(
                fixture+"\n//source changed",encoding="utf-8")
            bad=call(proc,request,"inspect_pom_typed_target_closed_teardown",{
                "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                "sourceMethod":"Missing","expectedSourceTreeHash":original,
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"})
            expect(bad.get("isError"),"Stale source sha was not blocked")
            print("POM_PREVIEW46_TARGET_CLOSED_NUNIT_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
