#!/usr/bin/env python3
"""Preview.34 MCP guard: a source-backed Count assertion is NOT behavioral
equivalence. MCP must disclose only source facts; no browser runtime, original
selector or Playwright executable target may be returned over stdio.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SOURCE = """
using System;
using OpenQA.Selenium;
using NUnit.Framework;
namespace Fictional.P34;
public sealed class AssertionPage {
    private readonly IWebDriver driver;
    public AssertionPage(IWebDriver driver) {this.driver=driver;}
    public void CheckCount() {
        Assert.That(driver.FindElements(By.Id("private-option")).Count,
            Is.EqualTo(1));
    }
    public void BadSideEffect() {
        System.Threading.Thread.Sleep(10);
        driver.FindElement(By.Id("private-option")).Click();
    }
}
"""
def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview34_stdio_smoke.py <MCP executable>")
    executable=str(Path(sys.argv[1]).resolve())
    expect(Path(executable).is_file(),"MCP binary not found")
    with tempfile.TemporaryDirectory(prefix="fictional-p34-mcp-") as directory:
        root=Path(directory)/"pom";root.mkdir()
        f=root/"AssertionPage.cs";f.write_text(SOURCE,encoding="utf-8")
        sha_before=hashlib.sha256(f.read_bytes()).hexdigest()
        proc=subprocess.Popen(
            ["dotnet",executable] if executable.endswith(".dll") else [executable],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,MIGRATOR_WORKSPACE=directory))
        start_reader(proc)
        try:
            send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                       "params":{"protocolVersion":"2025-06-18","capabilities":{},
                                 "clientInfo":{"name":"p34-browser-parity","version":"0.1"}}})
            expect("serverInfo" in receive(proc,1),"MCP initialize failure")
            send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
            send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            tools={t["name"] for t in receive(proc,2)["tools"]}
            expect({"inspect_pom_sources","inspect_pom_action_plan"}<=tools,
                   "Source POM read-only inspection missing")
            expect(not any(name in tools for name in
                ("run_browser","apply_pom_action_plan","execute_target")),
                "MCP gained side-effectful browser/mapping tools")
            inventory=value(call(proc,3,"inspect_pom_sources",{
                "sourceDirectory":"pom","pageTypes":["AssertionPage"]}))
            identity=inventory["sourceTreeHash"]
            expect(len(identity)==64,"POM source snapshot is not content-hashed")
            def inspect(num,method):
                return value(call(proc,num,"inspect_pom_action_plan",{
                    "sourceDirectory":"pom","sourceType":"Fictional.P34.AssertionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":identity}))
            count=inspect(4,"CheckCount")
            expect(count["status"]=="requires_review"
                   and count["execution"]=="read_only_not_run"
                   and not count["canAutoApply"]
                   and not count["runtimeVerified"]
                   and any(a["effect"]=="table_count_assertion"
                           for a in count["actions"]),
                   "Immediate NUnit Count assertion gained auto-approved runtime semantics")
            expect("targetStatements" not in count
                   and "adapterCandidate" not in count
                   and all("targetStatement" not in a for a in count["actions"])
                   and "private-option" not in str(count),
                   "MCP disclosed private target selector or runnable target")
            invalid=inspect(5,"BadSideEffect")
            expect(invalid["status"]=="blocked" and invalid["blockers"],
                   "Unknown source side effects were accepted")
            expect("targetStatements" not in invalid
                   and "private-option" not in str(invalid),
                   "Blocked response leaks private target information")
            expect(hashlib.sha256(f.read_bytes()).hexdigest()==sha_before,
                   "MCP read-only tool mutated synthetic POM source")
            f.write_text(SOURCE+"\n// stale",encoding="utf-8")
            stale=call(proc,6,"inspect_pom_action_plan",{
                "sourceDirectory":"pom","sourceType":"AssertionPage",
                "sourceMethod":"CheckCount","expectedSourceTreeHash":identity})
            expect(stale.get("isError"),"Stale source snapshot silently accepted")
            print("POM_PREVIEW34_ASSERTION_GAP_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
