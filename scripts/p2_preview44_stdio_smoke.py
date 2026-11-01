#!/usr/bin/env python3
"""preview.44: source-only MCP diagnostic privacy/negative stdio contract."""
import hashlib,os,re,subprocess,sys,tempfile,textwrap
from pathlib import Path
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview42_stdio_smoke import canonical_source

CODES=("MIGRATOR_CLEANUP_BROWSER_CLOSE_FAILED",
       "MIGRATOR_CLEANUP_PLAYWRIGHT_DISPOSE_FAILED",
       "MIGRATOR_CLEANUP_PAGE_CLOSE_FAILED",
       "MIGRATOR_CLEANUP_CONTEXT_CLOSE_FAILED")
def main():
    if len(sys.argv)!=2:raise SystemExit("usage: preview44_stdio.py <MCP DLL/exe>")
    exe=str(Path(sys.argv[1]).resolve())
    expect(Path(exe).is_file(),"MCP runtime unavailable")
    src42=Path("core/Migrator.Application.Smoke/PomPreview42FixtureLifecycleSmoke.cs")
    src43=Path("core/Migrator.Application.Smoke/PomPreview43FailureAtomicSmoke.cs")
    expect(src42.is_file() and src43.is_file(),"Pinned Core source fixtures missing")
    content42=src42.read_text(encoding="utf-8")
    content43=src43.read_text(encoding="utf-8")
    fixture=canonical_source("Fixture",content42)
    hooks=re.search(r'private const string AtomicHooks = """\n(.*?)\n        """;',content43,re.S)
    expect(hooks is not None,"Atomic hooks not source-backed")
    beg=fixture.index("[OneTimeSetUp]");end=fixture.index("[TearDown]")
    fixture=fixture[:beg]+textwrap.dedent(hooks.group(1))+"\n"+fixture[end:]
    cursor=0
    for code in CODES:
        idx=fixture.find("catch {}",cursor)
        expect(idx>=0,"Missing source secondary cleanup catch")
        candidate='catch { try { System.Console.Error.WriteLine("'+code+'"); } catch {} }'
        fixture=fixture[:idx]+candidate+fixture[idx+len("catch {}"):]
        cursor=idx+len(candidate)
    originals={"Page.cs":canonical_source("Page",content42),
               "TestBase.cs":canonical_source("Base",content42),
               "NUnitFixture.cs":fixture}
    with tempfile.TemporaryDirectory(prefix="fictional-p44-stdio-") as tmp:
        root=Path(tmp)/"pom";root.mkdir()
        for name,content in originals.items():
            (root/name).write_bytes(content.encode("utf-8"))
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.iterdir()}
        p=subprocess.Popen(["dotnet",exe] if exe.endswith(".dll") else [exe],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=tmp))
        start_reader(p)
        try:
            send(p,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"p44-diagnostic","version":"0.1"}}})
            expect("serverInfo" in receive(p,1),"MCP initialize failed")
            send(p,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(p,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            tools={x["name"] for x in receive(p,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_safe_cleanup_diagnostics",
                    "inspect_pom_failure_atomic_count_contract"}<=tools,
                "Safe cleanup tool unavailable")
            expect(not {"run_browser","execute_target","apply_pom_action_plan"}&tools,
                "Unexpected side effect tool exposure")
            ident=3
            def rpc(method,arguments):
                nonlocal ident
                reply=value(call(p,ident,method,arguments))
                ident+=1
                return reply
            def tree():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["SourcePage"]})["sourceTreeHash"]
            def inspect(method,digest,fields=("Page","Context","Browser","PW")):
                return rpc("inspect_pom_safe_cleanup_diagnostics",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":digest,
                    "pageField":fields[0],"contextField":fields[1],
                    "browserField":fields[2],"playwrightField":fields[3]})
            frozen=tree()
            expect(len(frozen)==64,"Missing source SHA")
            for method in ("Missing","Timeout"):
                out=inspect(method,frozen)
                proof=out["fixture"]
                expect(out["schemaVersion"]=="migrator-pom-external-safe-diagnostics-count/v1"
                    and out["status"]=="requires_review"
                    and proof and proof["safeSecondaryDiagnosticCodes"]
                    and proof["diagnosticSinkFailurePreservesPrimary"]
                    and proof["diagnosticSurface"]=="fixed_code_stderr_only"
                    and proof["primaryExceptionRethrown"]
                    and len(out["catches"])==1 and len(out["asyncMethods"])==3
                    and not out["canAutoApply"] and not out["runtimeVerified"],
                    "No source-proven safe diagnostics "+method+" "+str(out))
                expect(all(len(proof[x])==64 for x in (
                    "fixtureSourceSha256","oneTimeSetUpSha256","setUpSha256")),
                    "Source SHA of cleanup code absent")
                expect(not any(sensitive in str(out) for sensitive in (
                    "never-created","loader","CountAsync","Page.Locator(",
                    "targetBody","targetCatchClause","targetSignature",
                    "System.Console.Error.WriteLine","ex.Message","POM_SOURCE_ELEMENT_ABSENT")),
                    "Source/target C# or private data leaked via MCP")
                old=rpc("inspect_pom_failure_atomic_count_contract",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                    "sourceMethod":method,"expectedSourceTreeHash":frozen,
                    "pageField":"Page","contextField":"Context",
                    "browserField":"Browser","playwrightField":"PW"})
                expect(old["status"]=="blocked" and not old["catches"],
                    "Historical preview43 unexpectedly accepts logger effects")
            unknown=inspect("Missing",frozen,("Unknown","Context","Browser","PW"))
            expect(unknown["status"]=="blocked" and not unknown["catches"],
                "Invented Page receiver accepted")
            def blocked(changed):
                (root/"NUnitFixture.cs").write_bytes(changed.encode("utf-8"))
                result=inspect("Missing",tree())
                expect(result["status"]=="blocked" and not result["catches"]
                    and not result["asyncMethods"] and result["fixture"] is None
                    and result["blockers"],"Unsafe logger emitted candidate")
            blocked(fixture.replace(CODES[2],"PRIVATE_SELECTOR_LITERAL"))
            blocked(fixture.replace(
                'System.Console.Error.WriteLine("'+CODES[2]+'")',
                'System.Console.Error.WriteLine(System.Guid.NewGuid().ToString())'))
            blocked(fixture.replace(
                'catch { try { System.Console.Error.WriteLine("'+CODES[2]+'"); } catch {} }',
                'catch { System.Console.Error.WriteLine("'+CODES[2]+'"); }'))
            blocked(fixture.replace('catch {} }','catch { throw; } }'))
            blocked(fixture.replace("throw;","throw new System.Exception();"))
            for name,content in originals.items():
                (root/name).write_bytes(content.encode("utf-8"))
            expect({x.name:hashlib.sha256(x.read_bytes()).hexdigest()
                    for x in root.iterdir()}==hashes,"MCP changed sources")
            (root/"NUnitFixture.cs").write_text(fixture+"\n// stale",encoding="utf-8")
            failure=call(p,ident,"inspect_pom_safe_cleanup_diagnostics",{
                "sourceDirectory":"pom","sourceType":"Fictional.P42.SourcePage",
                "sourceMethod":"Missing","expectedSourceTreeHash":frozen,
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"})
            expect(failure.get("isError"),"Stale captured source SHA accepted")
            print("POM_PREVIEW44_SAFE_DIAGNOSTICS_MCP_STDIO_PASSED")
        finally:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
if __name__=="__main__":main()
