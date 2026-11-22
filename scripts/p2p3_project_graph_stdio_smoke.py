#!/usr/bin/env python3
"""Actual MCP stdio P2/P3 project-graph loss: source scope, helper and lifecycle."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SOURCE = """
using NUnit.Framework;
[SetUpFixture] public class GlobalHooks {
    [OneTimeSetUp] public void Begin() { Registry.Start(); }
    [OneTimeTearDown] public void End() { Registry.Stop(); }
}
public class BaseTests {
    [SetUp] public void Before() { Registry.Seed(); }
}
[TestFixture] public class FixtureTests : BaseTests {
    [Test] public void Runs() { Execute(); }
    private void Execute() { Helper(); }
    private void Helper() {
        driver.FindElement("#save").Click();
        Assert.That(true, Is.True);
    }
}
"""
LOST = """
using NUnit.Framework;
[TestFixture] public class FixtureTests {
    [Test] public void Runs() { Execute(); }
    private void Execute() { Helper(); }
    private void Helper() { Assert.That(true, Is.True); }
}
"""

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2p3_graph_stdio.py <MCP dll/executable>")
    binary=str(Path(sys.argv[1]).resolve())
    expect(Path(binary).is_file(),"Compiled MCP unavailable")
    with tempfile.TemporaryDirectory(prefix="mcp-p2p3-graph-") as temp:
        root=Path(temp)
        original=root/"Source.cs"
        original.write_bytes(SOURCE.encode("utf-8"))
        original_sha=hashlib.sha256(original.read_bytes()).hexdigest()
        command=["dotnet",binary] if binary.endswith(".dll") else [binary]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                "params":{"protocolVersion":"2025-06-18",
                          "capabilities":{},"clientInfo":{
                              "name":"p2p3-obligation-graph","version":"1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failed")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            analysis=value(call(proc,2,"analyze_migration",{"source":"Source.cs"}))
            preview=value(call(proc,3,"preview_migration",{
                "source":"Source.cs","expectedAnalysisId":analysis["analysisId"]}))
            expect(len(preview["files"])==1,"Target file not generated for fixture")
            target=root/"target"
            target.mkdir()
            target_file=target/preview["files"][0]["relativePath"]
            target_file.parent.mkdir(parents=True,exist_ok=True)
            target_file.write_bytes(LOST.encode("utf-8"))
            args={"source":"Source.cs","expectedAnalysisId":analysis["analysisId"],
                  "candidateId":preview["candidateId"],"targetRoot":"target"}
            proof=value(call(proc,4,"verify_artifact",args))
            acceptance=proof.get("acceptance",{})
            expect(acceptance.get("schemaVersion")=="migrator-acceptance/v1"
                   and acceptance["status"]=="rejected_incomplete",
                   "MCP incorrectly accepted lost fixture/helper behavior")
            kinds={(row["kind"],row["status"])
                   for row in acceptance.get("lineage",[])}
            required={("setup_fixture","missing_target"),
                      ("fixture_base","missing_target"),
                      ("helper_action","missing_target")}
            expect(required<=kinds,
                   "MCP did not serialize missing project obligations "+str(kinds))
            expect(acceptance["candidateId"]==proof["candidate"]["candidateId"]
                   and acceptance["sourceTreeHash"]==analysis["sourceTreeHash"]
                   and acceptance["targetTreeHash"]==proof["candidate"]["targetTreeHash"],
                   "MCP lost exact source/candidate/tree identities")
            for stage in ("testDiscovery","runner","realBrowser","behavioralEquivalence"):
                expect(acceptance[stage]["status"]=="not_run",
                       "MCP invented browser or runner evidence")
            target_file.write_bytes(LOST.replace("Is.True","Is.False").encode("utf-8"))
            changed=value(call(proc,5,"verify_artifact",args))
            expect(changed["candidate"]["candidateId"]!=
                       proof["candidate"]["candidateId"]
                   and changed["acceptance"]["status"]=="rejected_incomplete",
                   "Stale target candidate survived edited assertion")
            expect(hashlib.sha256(original.read_bytes()).hexdigest()==original_sha,
                   "Readonly verification changed source")
            original.write_bytes(original.read_bytes()+b"\n// new revision")
            stale=call(proc,6,"verify_artifact",args)
            expect(stale.get("isError"),"MCP accepted stale source analysis")
            print("P2P3_PROJECT_GRAPH_REAL_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)

if __name__=="__main__":
    main()
