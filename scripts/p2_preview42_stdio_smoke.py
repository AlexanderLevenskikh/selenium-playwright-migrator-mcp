#!/usr/bin/env python3
"""P42 read-only MCP: exact NUnit fixture ownership and cleanup metadata."""
import hashlib,os,re,subprocess,sys,tempfile,textwrap
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect

def canonical_source(name,source):
    marker="internal const string "+name+' = """'
    m=re.search(re.escape(marker)+r'\n(.*?)\n        """;',source,re.S)
    expect(m is not None,"Missing canonical synthetic "+name)
    return textwrap.dedent(m.group(1))+"\n"

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview42_stdio_smoke.py <MCP DLL or executable>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable missing")
    # CI explicitly checks out exact pinned Core into ./core and builds a
    # versioned NuGet dependency. This is only a public synthetic fixture.
    sourceFile=Path("core/Migrator.Application.Smoke/PomPreview42FixtureLifecycleSmoke.cs")
    expect(sourceFile.is_file(),"Pinned Core synthetic AST fixture missing")
    s=sourceFile.read_text(encoding="utf-8")
    sources={"Page.cs":canonical_source("Page",s),
             "TestBase.cs":canonical_source("Base",s),
             "NUnitFixture.cs":canonical_source("Fixture",s)}
    with tempfile.TemporaryDirectory(prefix="p42-mcp-lifecycle-") as tmp:
        root=Path(tmp)/"pom";root.mkdir()
        for name,content in sources.items():
            (root/name).write_bytes(content.encode("utf-8"))
        original={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in root.iterdir()}
        proc=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=tmp))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"preview42-lifecycle","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_external_async_count_contract",
                    "inspect_pom_external_lifecycle_count_contract"}<=names,
                   "Source-only lifecycle inspection not discoverable")
            expect(not {"run_browser","execute_target","apply_pom_action_plan"}&names,
                   "MCP accidentally exposed browser or mutation tool")
            nextId=3
            def rpc(tool,params):
                nonlocal nextId
                answer=value(call(proc,nextId,tool,params));nextId+=1
                return answer
            def sha():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["SourcePage"]})["sourceTreeHash"]
            def inspect(method,sourceHash,fields=("Page","Context","Browser","PW")):
                return rpc("inspect_pom_external_lifecycle_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":sourceHash,
                    "pageField":fields[0],"contextField":fields[1],
                    "browserField":fields[2],"playwrightField":fields[3]})
            frozen=sha()
            expect(len(frozen)==64,"Captured immutable source SHA missing")
            for method,sourceCatch,targetCatch in (
                ("Missing","OpenQA.Selenium.NoSuchElementException",
                 "Microsoft.Playwright.PlaywrightException"),
                ("Timeout","OpenQA.Selenium.WebDriverTimeoutException",
                 "System.TimeoutException")):
                p=inspect(method,frozen)
                fixture=p["fixture"]
                expect(p["status"]=="requires_review"
                    and p["schemaVersion"]=="migrator-pom-external-async-lifecycle-count/v1"
                    and p["sourceTreeHash"]==frozen and p["verifiedPageReceiver"]=="Page"
                    and not p["blockers"] and len(p["asyncMethods"])==3
                    and len(p["catches"])==1 and fixture
                    and fixture["fixtureSourcePath"]=="NUnitFixture.cs"
                    and fixture["contextFromBrowser"] and fixture["pageFromContext"]
                    and fixture["pageAndContextConstructorInjected"]
                    and fixture["perTestCleanupInFinally"]
                    and fixture["oneTimeCleanupInFinally"]
                    and all(len(fixture[k])==64 for k in (
                        "pageConstructorSha256","oneTimeSetUpSha256",
                        "setUpSha256","tearDownSha256",
                        "oneTimeTearDownSha256"))
                    and not p["canAutoApply"] and not p["runtimeVerified"],
                    "MCP lifecycle source-proof outcome unavailable: "+method+" "+str(p))
                expect(p["catches"][0]["sourceCaughtType"]==sourceCatch
                       and p["catches"][0]["targetCaughtType"]==targetCatch
                       and all("targetBody" not in x and "targetSignature" not in x
                               for x in p["asyncMethods"]),
                       "Exception types or redaction violated")
                serialized=str(p)
                expect(all(secret not in serialized for secret in (
                    "never-created","loader","POM_SOURCE_ELEMENT_ABSENT",
                    "Page.Locator(","CountAsync","targetCatchClause",
                    "targetBody","targetSignature","Headless = true")),
                    "Private source or target C# leaked over MCP")
                historical=rpc("inspect_pom_external_async_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":frozen,
                    "explicitPageReceiver":"Page"})
                expect(historical["status"]=="blocked" and not historical["catches"],
                       "Historical preview.41 safety block changed")
            invalid=inspect("Missing",frozen,("Page","WrongContext","Browser","PW"))
            expect(invalid["status"]=="blocked" and not invalid["asyncMethods"]
                and not invalid["catches"] and invalid["fixture"] is None,
                "Guessed context receiver was accepted")
            def neg(changed):
                (root/"NUnitFixture.cs").write_bytes(changed.encode("utf-8"))
                result=inspect("Missing",sha())
                expect(result["status"]=="blocked"
                    and not result["catches"] and not result["asyncMethods"]
                    and result["fixture"] is None and result["blockers"],
                    "Unsupported lifecycle emitted partial source-derived target")
            fixture=sources["NUnitFixture.cs"]
            neg(fixture.replace("Page = await Context.NewPageAsync();",
                 "Page = null!;"))
            neg(fixture.replace("finally { await Context.CloseAsync(); }",
                 "finally {}"))
            neg(fixture.replace("page = new SourcePage(driver,Page,Context);",
                 "page = new SourcePage(driver,Page,null!);"))
            neg(fixture.replace("page = new SourcePage(driver,Page,Context);",
                 "page = new SourcePage(driver,Page,Context); _ = new SourcePage(driver,Page,Context);"))
            neg(fixture.replace("Page = await Context.NewPageAsync();",
                 "Page = await Context.NewPageAsync(); await Context.CloseAsync();"))
            neg(fixture.replace("finally { PW.Dispose(); }","finally {}"))
            neg(fixture.replace("Page = await Context.NewPageAsync();",
                 "Page = await Context.NewPageAsync(); Page = await Context.NewPageAsync();"))
            neg(fixture.replace("[Test] public void CatchMissing()",
                 "public void CatchMissing()"))
            for name,source in sources.items():
                (root/name).write_bytes(source.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.iterdir()}==original,
                   "Read-only source was mutated")
            (root/"NUnitFixture.cs").write_text(fixture+"\n//changed",encoding="utf-8")
            result=call(proc,nextId,"inspect_pom_external_lifecycle_count_contract",{
                "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                "sourceMethod":"Missing","expectedSourceTreeHash":frozen,
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"})
            expect(result.get("isError"),"Stale SHA was not rejected")
            print("POM_PREVIEW42_FIXTURE_LIFECYCLE_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
