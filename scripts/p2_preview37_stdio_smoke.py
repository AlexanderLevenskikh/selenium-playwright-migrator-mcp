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
namespace Fictional.P37;
public sealed class AssertionPage {
    private readonly IWebDriver driver;
    public AssertionPage(IWebDriver driver) {this.driver=driver;}
    public void CheckCount() {
        Assert.That(driver.FindElements(By.Id("private-option")).Count,
            Is.EqualTo(1));
    }
    public void CheckText(string expected) {
        Assert.That(driver.FindElement(By.Id("private-text")).Text, Is.EqualTo(expected));
    }
    public void HiddenText() {
        Assert.That(driver.FindElement(By.Id("private-hidden")).Text, Is.EqualTo(""));
    }
    public void PreservedWhitespace() {
        Assert.That(driver.FindElement(By.Id("private-pre")).Text, Is.EqualTo("alpha  beta"));
    }
    public void SimplePreText() {
        Assert.That(driver.FindElement(By.Id("private-pre")).Text,
            Is.EqualTo("alpha  beta"));
    }
    public void UnicodeText() {
        Assert.That(driver.FindElement(By.Id("private-unicode")).Text,
            Is.EqualTo("Привет мир 🙂"));
    }
    public void BadText(string expected) {
        Assert.That(driver.FindElement(By.Id("private-text")).Text,
            Is.EqualTo(Environment.GetEnvironmentVariable("PRIVATE")!));
    }
    public void BadSideEffect() {
        System.Threading.Thread.Sleep(10);
        driver.FindElement(By.Id("private-option")).Click();
    }
}
"""
def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: p2_preview37_stdio_smoke.py <MCP executable>")
    executable=str(Path(sys.argv[1]).resolve())
    expect(Path(executable).is_file(),"MCP binary not found")
    with tempfile.TemporaryDirectory(prefix="fictional-p37-mcp-") as directory:
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
                                 "clientInfo":{"name":"p37-browser-parity","version":"0.1"}}})
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
                    "sourceDirectory":"pom","sourceType":"Fictional.P37.AssertionPage",
                    "sourceMethod":method,"expectedSourceTreeHash":identity}))
            count=inspect(4,"CheckCount")
            expect(count["status"]=="requires_review"
                   and count["execution"]=="read_only_not_run"
                   and not count["canAutoApply"]
                   and not count["runtimeVerified"]
                   and any(a["effect"]=="table_count_assertion"
                           for a in count["actions"]),
                   "Immediate NUnit Count assertion gained auto-approved runtime semantics")
            expect(count["assertions"]["sourceImmediateCountSnapshots"]==1
                   and count["assertions"]["sourceImmediateTextSnapshots"]==0
                   and not count["assertions"]["runtimeVerified"]
                   and not count["assertions"]["canAutoApply"],
                   "Count source facts should remain read-only, no runtime claim")
            expect("targetStatements" not in count
                   and "adapterCandidate" not in count
                   and all("targetStatement" not in a for a in count["actions"])
                   and "private-option" not in str(count),
                   "MCP disclosed private target selector or runnable target")
            text_plan=inspect(5,"CheckText")
            expect(text_plan["status"]=="requires_review"
                   and text_plan["execution"]=="read_only_not_run"
                   and not text_plan["runtimeVerified"] and not text_plan["canAutoApply"]
                   and text_plan["assertions"]["sourceImmediateTextSnapshots"]==1
                   and text_plan["assertions"]["hiddenTextParity"]=="not_proven_requires_review"
                   and text_plan["assertions"]["missingElementExceptionParity"]=="not_proven_requires_review"
                   and any(a["effect"]=="text_assertion" for a in text_plan["actions"])
                   and "private-text" not in str(text_plan)
                   and "targetStatements" not in text_plan
                   and "adapterCandidate" not in text_plan
                   and all("targetStatement" not in a for a in text_plan["actions"]),
                   "Source-backed Text must not leak selectors or claim general rendered-text equivalence")
            for index, method in ((6,"HiddenText"),(7,"PreservedWhitespace")):
                state=inspect(index,method)
                expect(state["status"]=="requires_review"
                       and state["execution"]=="read_only_not_run"
                       and not state["runtimeVerified"]
                       and not state["canAutoApply"]
                       and state["assertions"]["sourceImmediateTextSnapshots"]==1
                       and state["assertions"]["preservedWhitespace"]=="fail_closed_review_required"
                       and state["assertions"]["preservedWhitespacePartialMode"]=="mixed_CSS_modes_fail_closed_review_required"
                       and state["assertions"]["fullWebDriverRenderedTextParity"]=="not_proven_requires_review"
                       and state["assertions"]["measuredCssHiddenSubset"]=="source_candidate_only_not_runtime_proof"
                       and state["assertions"]["normalWhitespaceSubset"]=="source_candidate_only_not_runtime_proof"
                       and any(a["effect"]=="text_assertion" for a in state["actions"])
                       and "targetStatements" not in state and "adapterCandidate" not in state
                       and "private-hidden" not in str(state) and "private-pre" not in str(state)
                       and all("targetStatement" not in a for a in state["actions"]),
                       method+" must remain redacted source-only with no equivalence claim")
            for index,method in ((8,"SimplePreText"),(9,"UnicodeText")):
                one=inspect(index,method)
                expect(one["status"]=="requires_review"
                       and not one["canAutoApply"] and not one["runtimeVerified"]
                       and one["execution"]=="read_only_not_run"
                       and one["assertions"]["sourceImmediateTextSnapshots"]==1
                       and one["assertions"]["measuredSingleLinePreAndPreWrap"]=="source_candidate_only_not_runtime_proof"
                       and one["assertions"]["measuredNbspZeroWidthCombining"]=="source_candidate_only_not_runtime_proof"
                       and one["assertions"]["complexUnicodeSpace"]=="fail_closed_review_required"
                       and one["assertions"]["cssTextTransform"]=="fail_closed_review_required"
                       and one["assertions"]["missingElementExceptionType"]=="Selenium_NoSuchElement_vs_Playwright_PlaywrightException_not_equivalent"
                       and one["assertions"]["fullWebDriverRenderedTextParity"]=="not_proven_requires_review"
                       and any(a["effect"]=="text_assertion" for a in one["actions"])
                       and "targetStatements" not in one and "adapterCandidate" not in one
                       and "private-pre" not in str(one) and "private-unicode" not in str(one),
                       method+" must remain redacted, source-bound and never auto-approved")
            for index, method in ((10,"BadSideEffect"),(11,"BadText")):
                invalid=inspect(index,method)
                expect(invalid["status"]=="blocked" and invalid["blockers"]
                       and "targetStatements" not in invalid
                       and "private-option" not in str(invalid)
                       and "private-text" not in str(invalid),
                       method+" must fail closed without exposing a source selector")
            invalid=inspect(10,"BadSideEffect")
            expect(invalid["status"]=="blocked" and invalid["blockers"],
                   "Unknown source side effects were accepted")
            expect("targetStatements" not in invalid
                   and "private-option" not in str(invalid),
                   "Blocked response leaks private target information")
            expect(hashlib.sha256(f.read_bytes()).hexdigest()==sha_before,
                   "MCP read-only tool mutated synthetic POM source")
            f.write_text(SOURCE+"\n// stale",encoding="utf-8")
            stale=call(proc,12,"inspect_pom_action_plan",{
                "sourceDirectory":"pom","sourceType":"AssertionPage",
                "sourceMethod":"CheckCount","expectedSourceTreeHash":identity})
            expect(stale.get("isError"),"Stale source snapshot silently accepted")
            print("POM_PREVIEW35_ASSERTION_GAP_MCP_STDIO_PASSED")
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)
if __name__=="__main__":main()
