#!/usr/bin/env python3
"""preview.45 source-bound MCP fault witness and redaction regression."""
import hashlib,os,re,subprocess,sys,tempfile,textwrap
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview42_stdio_smoke import canonical_source

def source_fixture():
    f42=Path("core/Migrator.Application.Smoke/PomPreview42FixtureLifecycleSmoke.cs")
    f43=Path("core/Migrator.Application.Smoke/PomPreview43FailureAtomicSmoke.cs")
    expect(f42.is_file() and f43.is_file(),"Pinned public Core source fixtures missing")
    x=f42.read_text(encoding="utf-8")
    y=f43.read_text(encoding="utf-8")
    original=canonical_source("Fixture",x)
    m=re.search(r'private const string AtomicHooks = """\n(.*?)\n        """;',y,re.S)
    expect(m is not None,"Pinned source AtomicHooks missing")
    begin=original.index("[OneTimeSetUp]");end=original.index("[TearDown]")
    original=original[:begin]+textwrap.dedent(m.group(1))+"\n"+original[end:]
    cursor=0
    for code in ("MIGRATOR_CLEANUP_BROWSER_CLOSE_FAILED",
                 "MIGRATOR_CLEANUP_PLAYWRIGHT_DISPOSE_FAILED",
                 "MIGRATOR_CLEANUP_PAGE_CLOSE_FAILED",
                 "MIGRATOR_CLEANUP_CONTEXT_CLOSE_FAILED"):
        index=original.find("catch {}",cursor)
        expect(index>=0,"Canonical secondary catch missing")
        value='catch { try { System.Console.Error.WriteLine("'+code+'"); } catch {} }'
        original=original[:index]+value+original[index+len("catch {}"):]
        cursor=index+len(value)
    return {
        "Page.cs":canonical_source("Page",x),
        "TestBase.cs":canonical_source("Base",x),
        "NUnitFixture.cs":original
    }

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview45_stdio_smoke.py <DLL or executable>")
    executable=str(Path(sys.argv[1]).resolve())
    expect(Path(executable).is_file(),"MCP executable missing")
    source=source_fixture()
    with tempfile.TemporaryDirectory(prefix="fictional-p45-stdio-") as temporary:
        folder=Path(temporary)/"pom";folder.mkdir()
        for path,content in source.items():
            (folder/path).write_bytes(content.encode("utf-8"))
        saved={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in folder.iterdir()}
        proc=subprocess.Popen(
            ["dotnet",executable] if executable.endswith(".dll") else [executable],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=temporary))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                "clientInfo":{"name":"preview45-source-fault","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_safe_cleanup_diagnostics",
                "inspect_pom_cleanup_fault_witness"}<=names,
                "Source-only fault witness not exposed")
            expect(not {"execute_target","run_browser","apply_pom_action_plan"}&names,
                "MCP exposes forbidden execution tool")
            ident=3
            def rpc(method,args):
                nonlocal ident
                data=value(call(proc,ident,method,args));ident+=1;return data
            def digest():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["SourcePage"]})["sourceTreeHash"]
            def inspect(method,sourceSha,fields=("Page","Context","Browser","PW")):
                return rpc("inspect_pom_cleanup_fault_witness",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":sourceSha,
                    "pageField":fields[0],"contextField":fields[1],
                    "browserField":fields[2],"playwrightField":fields[3]})
            frozen=digest()
            expect(len(frozen)==64,"Missing exact snapshot SHA")
            for method in ("Missing","Timeout"):
                out=inspect(method,frozen)
                proof=out["fixture"]
                expect(out["status"]=="requires_review"
                    and out["schemaVersion"]=="migrator-pom-external-cleanup-fault-witness/v1"
                    and out["sourceTreeHash"]==frozen and proof
                    and proof["faultWitnessSourceOnly"]
                    and proof["sourceSinkNotRebound"]
                    and proof["safeSecondaryDiagnosticCodes"]
                    and proof["diagnosticSinkFailurePreservesPrimary"]
                    and not proof["realCleanupFailureCertified"]
                    and not proof["osProcessAncestryCertified"]
                    and not out["canAutoApply"] and not out["runtimeVerified"]
                    and len(out["asyncMethods"])==3 and len(out["catches"])==1,
                    "Bad source-bound fault witness "+method+" "+str(out))
                expect(all(len(proof[n])==64 for n in (
                    "fixtureSourceSha256","oneTimeSetUpSha256","setUpSha256")),
                    "Source hash missing")
                leaked=str(out)
                expect(not any(v in leaked for v in (
                    "never-created","loader","Page.Locator(","CountAsync",
                    "targetBody","targetCatchClause","System.Console.Error.WriteLine",
                    "POM_SOURCE_ELEMENT_ABSENT","P45_PRIMARY_MARKER")),
                    "MCP emitted user source/code/exception details")
                previous=rpc("inspect_pom_safe_cleanup_diagnostics",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":frozen,
                    "pageField":"Page","contextField":"Context",
                    "browserField":"Browser","playwrightField":"PW"})
                expect(previous["status"]=="requires_review",
                    "preview.44 historical success changed")
            guessed=inspect("Missing",frozen,("Unknown","Context","Browser","PW"))
            expect(guessed["status"]=="blocked" and not guessed["catches"],
                "Guessed receiver accepted")
            fixture=source["NUnitFixture.cs"]
            anchor="private IPage Page = null!;"
            expect(anchor in fixture,"Exact C# field marker unavailable")
            changes=[
                fixture.replace(anchor,anchor+
                    '\n [Test] public void MutateError() {'+
                    ' System.Console.SetError(System.Console.Out); }'),
                fixture.replace("MIGRATOR_CLEANUP_PAGE_CLOSE_FAILED",
                    "SENSITIVE_DYNAMIC_LITERAL"),
                fixture.replace("catch {} }","catch { throw; } }"),
                fixture.replace("throw;","throw new System.Exception();")
            ]
            for modified in changes:
                (folder/"NUnitFixture.cs").write_text(modified,encoding="utf-8")
                result=inspect("Missing",digest())
                expect(result["status"]=="blocked" and not result["catches"]
                    and not result["asyncMethods"] and result["fixture"] is None
                    and result["blockers"],
                    "Unknown sink exception/control could emit partial candidate")
            for name,text in source.items():
                (folder/name).write_bytes(text.encode("utf-8"))
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in folder.iterdir()}==saved,
                    "Read-only MCP changed captured bytes")
            (folder/"NUnitFixture.cs").write_text(fixture+"\n//stale",encoding="utf-8")
            error=call(proc,ident,"inspect_pom_cleanup_fault_witness",{
                "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                "sourceMethod":"Missing","expectedSourceTreeHash":frozen,
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"})
            expect(error.get("isError"),"Captured SHA mismatch accepted")
            print("POM_PREVIEW45_SOURCE_FAULT_WITNESS_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
