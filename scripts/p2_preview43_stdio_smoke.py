#!/usr/bin/env python3
"""Preview.43: read-only MCP source-backed NUnit failure-atomic rollback.
No source snippets, selectors, cleanup code or target C# leave stdio.
"""
import hashlib,os,re,subprocess,sys,tempfile,textwrap
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview42_stdio_smoke import canonical_source

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview43_stdio_smoke.py <MCP DLL or executable>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP executable missing")
    root42=Path("core/Migrator.Application.Smoke/PomPreview42FixtureLifecycleSmoke.cs")
    root43=Path("core/Migrator.Application.Smoke/PomPreview43FailureAtomicSmoke.cs")
    expect(root42.is_file() and root43.is_file(),
        "Exact pinned Core source-attested public smoke fixtures required")
    text42=root42.read_text(encoding="utf-8")
    text43=root43.read_text(encoding="utf-8")
    fixture=canonical_source("Fixture",text42)
    hooksMatch=re.search(r'private const string AtomicHooks = """\n(.*?)\n        """;',text43,re.S)
    expect(hooksMatch is not None,"AtomicHooks source definition missing")
    hooks=textwrap.dedent(hooksMatch.group(1))+"\n"
    begin=fixture.index("[OneTimeSetUp]")
    end=fixture.index("[TearDown]")
    fixture=fixture[:begin]+hooks+fixture[end:]
    original={
        "Page.cs":canonical_source("Page",text42),
        "TestBase.cs":canonical_source("Base",text42),
        "NUnitFixture.cs":fixture
    }
    with tempfile.TemporaryDirectory(prefix="fictional-p43-mcp-") as workspace:
        folder=Path(workspace)/"pom";folder.mkdir()
        for name,src in original.items():
            (folder/name).write_bytes(src.encode("utf-8"))
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
        proc=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=workspace))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"preview43-atomic-rollback","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialization failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_external_lifecycle_count_contract",
                "inspect_pom_failure_atomic_count_contract"}<=names,
                "Source-only failure atomic MCP tool not registered")
            expect(not {"execute_target","run_browser","apply_pom_action_plan"}&names,
                "MCP unexpectedly gained side-effectful tools")
            nextId=3
            def rpc(method,params):
                nonlocal nextId
                result=value(call(proc,nextId,method,params))
                nextId+=1
                return result
            def sha():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["SourcePage"]})["sourceTreeHash"]
            def inspect(method,tree,fields=("Page","Context","Browser","PW")):
                return rpc("inspect_pom_failure_atomic_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":tree,
                    "pageField":fields[0],"contextField":fields[1],
                    "browserField":fields[2],"playwrightField":fields[3]})
            frozen=sha()
            expect(len(frozen)==64,"Source tree digest missing")
            for method in ("Missing","Timeout"):
                p=inspect(method,frozen)
                fixtureProof=p["fixture"]
                expect(p["status"]=="requires_review"
                    and p["schemaVersion"]=="migrator-pom-external-failure-atomic-count/v1"
                    and fixtureProof and p["sourceTreeHash"]==frozen
                    and fixtureProof["oneTimeSetUpFailureCleanup"]
                    and fixtureProof["setUpFailureCleanup"]
                    and fixtureProof["primaryExceptionRethrown"]
                    and fixtureProof["cleanupFailuresDoNotReplacePrimary"]
                    and fixtureProof["pageAndContextConstructorInjected"]
                    and fixtureProof["pageFromContext"]
                    and fixtureProof["perTestCleanupInFinally"]
                    and len(p["asyncMethods"])==3
                    and len(p["catches"])==1
                    and not p["runtimeVerified"] and not p["canAutoApply"],
                    "Exact source-backed guarded cleanup not proven: "+method+" "+str(p))
                expect(fixtureProof["fixtureSourcePath"]=="NUnitFixture.cs"
                    and all(len(fixtureProof[k])==64 for k in (
                        "pageConstructorSha256","oneTimeSetUpSha256",
                        "setUpSha256","tearDownSha256","oneTimeTearDownSha256")),
                    "Missing typed source provenance and SHA")
                serialized=str(p)
                expect(all(secret not in serialized for secret in (
                    "never-created","loader","POM_SOURCE_ELEMENT_ABSENT",
                    "Page.Locator(","CountAsync","targetBody","targetSignature",
                    "targetCatchClause","PW = await","Browser.CloseAsync()")),
                    "MCP leaked source or target C#")
                prior=rpc("inspect_pom_external_lifecycle_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":frozen,
                    "pageField":"Page","contextField":"Context",
                    "browserField":"Browser","playwrightField":"PW"})
                expect(prior["status"]=="blocked" and not prior["catches"],
                    "Preview.42 historical lifecycle gate was widened")

            p=inspect("Missing",frozen,("Guessed","Context","Browser","PW"))
            expect(p["status"]=="blocked" and not p["catches"]
                and not p["asyncMethods"] and p["fixture"] is None,
                "Invented Page field accepted")
            def negative(source):
                (folder/"NUnitFixture.cs").write_bytes(source.encode("utf-8"))
                out=inspect("Missing",sha())
                expect(out["status"]=="blocked"
                    and out["fixture"] is None and not out["catches"]
                    and not out["asyncMethods"] and out["blockers"]
                    and not out["canAutoApply"],
                    "Unproven rollback emitted a partial candidate")
            negative(fixture.replace("throw;","return;"))
            negative(fixture.replace(
                "if (Context != null) await Context.CloseAsync();",
                "if (Context != null) await Page.CloseAsync();"))
            negative(fixture.replace(
                "if (Browser != null) await Browser.CloseAsync();",
                "await Browser.CloseAsync();"))
            negative(fixture.replace("catch {}","catch { throw; }"))
            negative(fixture.replace(
                "if (PW != null) PW.Dispose();",
                "if (PW != null) _ = PW;"))
            negative(fixture.replace(
                "Context = await Browser.NewContextAsync();",
                "Context = null!;"))
            for name,src in original.items():
                (folder/name).write_bytes(src.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in folder.iterdir()}==files,
                   "Read-only fixture did not restore identical source bytes")
            (folder/"NUnitFixture.cs").write_text(fixture+"\n//stale",encoding="utf-8")
            err=call(proc,nextId,"inspect_pom_failure_atomic_count_contract",{
                "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                "sourceMethod":"Missing","expectedSourceTreeHash":frozen,
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"})
            expect(err.get("isError"),"Stale captured source hash accepted")
            print("POM_PREVIEW43_ATOMIC_LIFECYCLE_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
