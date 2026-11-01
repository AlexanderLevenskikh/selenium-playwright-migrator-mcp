#!/usr/bin/env python3
"""P1 preview48 pinned Playwright 1.63 close/dispose semantic metadata over real MCP stdio."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from mcp_stdio_smoke import start_reader,receive,send,call,value,expect
from p2_preview47_stdio_smoke import source

UPSTREAM="6d5c263758e8b50cfc18d3abb384f251b7deb370"

def main():
    expect(len(sys.argv)==2,"usage: p2_preview48_stdio_semantics_smoke.py <binary>")
    binary=str(Path(sys.argv[1]).resolve())
    expect(Path(binary).is_file(),"MCP binary missing")
    sources=source()
    with tempfile.TemporaryDirectory(prefix="fictional-p48-semantic-") as folder:
        scope=Path(folder)/"pom";scope.mkdir()
        for name,content in sources.items():
            (scope/name).write_bytes(content.encode("utf-8"))
        frozen={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in scope.iterdir()}
        proc=subprocess.Popen(["dotnet",binary] if binary.endswith(".dll")
            else [binary],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,env=dict(os.environ,MIGRATOR_WORKSPACE=folder))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18","capabilities":{},
                "clientInfo":{"name":"p48-semantic-oracle","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names={t["name"] for t in receive(proc,2)["tools"]}
            expect("inspect_pom_one_time_targetclosed_cleanup" in names,
                "read-only one-time tool not found")
            expect(not {"execute_target","run_browser","apply_pom_action_plan"}&names,
                "unexpected executable MCP tool")
            query={"sourceDirectory":"pom",
                "sourceType":"Fictional.P42.SourcePage","sourceMethod":"Missing",
                "pageField":"Page","contextField":"Context",
                "browserField":"Browser","playwrightField":"PW"}
            digest=value(call(proc,3,"inspect_pom_sources",{
                "sourceDirectory":"pom","pageTypes":["SourcePage"]}))["sourceTreeHash"]
            query["expectedSourceTreeHash"]=digest
            plan=value(call(proc,4,"inspect_pom_one_time_targetclosed_cleanup",query))
            u=plan.get("pinnedUpstreamSemantics")
            expect(plan["status"]=="requires_review" and u
                and u["playwrightVersion"]=="1.63.0"
                and u["upstreamCommit"]==UPSTREAM
                and u["browserCloseTargetClosed"]==
                    "already_swallowed_inside_pinned_playwright"
                and u["playwrightDispose"]==
                    "delegates_to_internal_connection_dispose"
                and u["publicDisposeThrowIsNotCertified"]
                and not u["customerRuntimeVersionVerified"]
                and u["arbitraryExternalCallbackFailures"]=="blocked_not_proven"
                and not plan["canAutoApply"] and not plan["runtimeVerified"]
                and any("Preview.48" in line for line in plan["limitations"]),
                "pinned upstream source-only semantic guard missing")
            expect(not any(word in str(plan) for word in (
                "never-created","Page.Locator(","CountAsync","targetBody",
                "targetCatchClause","Exception.StackTrace","PRIVATE_UNTRUSTED",
                "System.Console.Error.WriteLine","P48_PRIMARY_ASSERTION")),
                "MCP emitted target statements/private source")
            query["browserField"]="UnknownBrowser"
            blocked=value(call(proc,5,"inspect_pom_one_time_targetclosed_cleanup",query))
            expect(blocked["status"]=="blocked" and not blocked["catches"]
                and blocked["fixture"] is None,
                "unsupported receiver produced partial plan")
            expect({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in scope.iterdir()}==frozen,
                "read-only tool modified source")
            print("POM_PREVIEW48_PINNED_UPSTREAM_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
