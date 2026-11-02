#!/usr/bin/env python3
"""P1 preview.50: real stdio source-only graph, strict stale/block/redaction."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from mcp_stdio_smoke import start_reader,receive,send,call,value,expect

def public_source():
    path=Path("core/Migrator.Application.Smoke/PomPreview50SourceFlowSmoke.cs")
    expect(path.is_file(),"Pinned public Core preview50 source fixture missing")
    data=path.read_text(encoding="utf-8")
    expression=r'private const string Source = """\n(.*?)\n        """;'
    match=re.search(expression,data,re.S)
    expect(match is not None,"Exact public fixture raw source missing")
    return textwrap.dedent(match.group(1))+"\n"

def main():
    expect(len(sys.argv)==2,"usage: p2_preview50_stdio_smoke.py <MCP DLL|executable>")
    binary=str(Path(sys.argv[1]).resolve())
    expect(Path(binary).is_file(),"MCP executable not found")
    with tempfile.TemporaryDirectory(prefix="p50-public-source-") as root:
        scope=Path(root)/"pom";scope.mkdir()
        source=public_source()
        file=scope/"PublicFixture.cs"
        file.write_bytes(source.encode("utf-8"))
        immutable=hashlib.sha256(file.read_bytes()).hexdigest()
        proc=subprocess.Popen(["dotnet",binary] if binary.endswith(".dll")
            else [binary],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,env=dict(os.environ,MIGRATOR_WORKSPACE=root))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                "clientInfo":{"name":"p50-source-flow","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            tools={x["name"] for x in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_source_flow_contract"}<=tools,
                "P50 read-only tool missing")
            expect(not {"run_browser","execute_target","apply_pom_action_plan"}&tools,
                "Unexpected MCP write/execution tool")
            seq=3
            def rpc(name,arguments):
                nonlocal seq
                answer=value(call(proc,seq,name,arguments));seq+=1
                return answer
            def sha():
                return rpc("inspect_pom_sources",{
                    "sourceDirectory":"pom","pageTypes":["FiltersPage"]})["sourceTreeHash"]
            frozen=sha()
            args={"sourceDirectory":"pom","fixtureType":"FiltersFixture",
                "sourceMethod":"CheckListFilter","expectedSourceTreeHash":frozen}
            pos=rpc("inspect_pom_source_flow_contract",args)
            expect(pos["status"]=="source_verified_requires_review"
                and pos["targetStatus"]=="blocked"
                and pos["schemaVersion"]=="migrator-pom-source-flow/v1"
                and len(pos["witnesses"])==5
                and len(pos["blockers"])==0
                and len(pos["sourceTreeHash"])==64
                and all(len(x["sha256"])==64 and x["sourceLine"]>0
                    for x in pos["witnesses"])
                and not pos["runtimeVerified"] and not pos["canAutoApply"]
                and pos["scope"]["targetCodeReturned"]==False,
                "P50 source-only graph not positive or target exposed")
            expect(not any(private in str(pos) for private in (
                "sample","group","Routes.FilterPage","GoToUrl",
                "Thread.Sleep","CreatePage","Contains.Substring",
                "Page.Locator","targetBody","targetCatchClause",
                "ClearAndInputText","acceptButton","page.Filter")),
                "P50 tool leaked source, URL, selector or target C#")
            for before,after in [
                ("GetScopedRequiredService<Navigation>()",
                    "GetRequiredService<Navigation>()"),
                ("input.ClearAndInputText(value)",
                    "input.ClearAndInputText(\"constant\")"),
                ("catch (WebDriverTimeoutException)","catch (Exception)"),
                ("page = selected;","page = unknown;"),
                (".Should().Contain(\"group\")",
                    ".Should().Be(\"group\")")]:
                expect(before in source,"Negative mutation marker missing")
                file.write_text(source.replace(before,after,1),encoding="utf-8")
                invalid=dict(args,expectedSourceTreeHash=sha())
                blocked=rpc("inspect_pom_source_flow_contract",invalid)
                expect(blocked["status"]=="blocked"
                    and blocked["targetStatus"]=="blocked"
                    and len(blocked["witnesses"])==0
                    and len(blocked["blockers"])>0,
                    "Unsupported source shape admitted partial witness")
            file.write_bytes(source.encode("utf-8"))
            expect(hashlib.sha256(file.read_bytes()).hexdigest()==immutable,
                "Original public source not restored")
            args["sourceMethod"]="UnknownMethod"
            unknown=rpc("inspect_pom_source_flow_contract",args)
            expect(unknown["status"]=="blocked" and not unknown["witnesses"],
                "Unknown method positive")
            args["sourceMethod"]="CheckListFilter"
            file.write_text(source+"\n// changed",encoding="utf-8")
            stale=call(proc,seq,"inspect_pom_source_flow_contract",args)
            expect(stale.get("isError",False),"Stale source SHA must reject")
            print("POM_PREVIEW50_SOURCE_FLOW_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
