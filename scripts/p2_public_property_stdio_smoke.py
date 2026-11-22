#!/usr/bin/env python3
"""Real MCP stdio: bounded public-like IWebElement properties remain read-only.

Uses owned synthetic C# (no third-party scripts, no target C# disclosure).
The original public counterpart is browser-tested separately in Core CI.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SOURCE = """using OpenQA.Selenium;
namespace PublicLike;
public sealed class TextInputPage {
    readonly IWebDriver driver;
    public TextInputPage(IWebDriver d) { driver = d; }
    public IWebElement TextBox => driver.FindElement(By.Id("newButtonName"));
    public IWebElement Button => driver.FindElement(By.Id("updatingButton"));
    public void EnterText(string text) {
        TextBox.Clear();
        TextBox.SendKeys(text);
    }
    public void ClickButton() => Button.Click();
    public string GetButtonText() => Button.Text;
    public void GoToTextInput() =>
        driver.FindElement(By.LinkText("Text Input")).Click();
    public IWebElement Writable { get; set; }
    public void BadWritable() => Writable.Click();
    public IWebElement Dynamic => driver.FindElement(
        By.Id(System.Environment.GetEnvironmentVariable("SECRET_ID")!));
    public void BadDynamic() => Dynamic.Click();
    public string BadText() => "not-source-evidence";
}"""


def main(binary):
    binary = str(Path(binary).resolve())
    expect(Path(binary).is_file(), "MCP tool executable missing")
    with tempfile.TemporaryDirectory(prefix="mcp-property-provenance-") as tmp:
        root = Path(tmp)
        folder = root / "pom"
        folder.mkdir()
        src = folder / "TextInputPage.cs"
        src.write_bytes(SOURCE.encode("utf-8"))
        original_sha = hashlib.sha256(src.read_bytes()).hexdigest()
        command = ["dotnet", binary] if binary.endswith(".dll") else [binary]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0", "id":1, "method":"initialize",
                "params":{"protocolVersion":"2025-06-18",
                    "capabilities":{},
                    "clientInfo":{"name":"public-pom-property-slice",
                                  "version":"1"}}})
            expect("serverInfo" in receive(proc, 1),
                   "MCP initialize did not complete")
            send(proc, {"jsonrpc":"2.0", "method":"notifications/initialized"})
            inventory = value(call(proc, 2, "inspect_pom_sources",
                {"sourceDirectory":"pom","pageTypes":["TextInputPage"]}))
            tree = inventory["sourceTreeHash"]
            expect(len(tree) == 64, "captured immutable tree hash missing")

            def inspect(n, method):
                return value(call(proc, n, "inspect_pom_action_plan",
                    {"sourceDirectory":"pom",
                     "sourceType":"PublicLike.TextInputPage",
                     "sourceMethod":method,
                     "expectedSourceTreeHash":tree}))

            for idx, method, effects in (
                (3, "EnterText", ("input_clear", "input_sendkeys")),
                (4, "ClickButton", ("click",)),
                (5, "GetButtonText", ("rendered_text_return",)),
                (6, "GoToTextInput", ("click",)),
            ):
                plan = inspect(idx, method)
                expect(plan["status"]=="requires_review" and
                       plan["schemaVersion"]=="migrator-pom-action/v1alpha3" and
                       plan["sourceTreeHash"]==tree and
                       plan["canAutoApply"] is False and
                       plan["runtimeVerified"] is False and
                       plan["execution"]=="read_only_not_run",
                       method+" was silently accepted by MCP")
                actions = plan["actions"]
                expect(tuple(action["effect"] for action in actions)==effects and
                       plan["provenSourceActions"]==len(effects),
                       method+" lost required property action/read order")
                expect(all(action["sourceLine"]>0 and
                           len(action["sourceSha256"])==64 and
                           len(action["targetSha256"])==64 and
                           action["requiresReview"] is True
                           for action in actions),
                       method+" lost exact source/target hash lineage")
                expect("targetStatements" not in plan and
                       "adapterCandidate" not in plan and
                       all("targetStatement" not in a for a in actions) and
                       "newButtonName" not in str(plan) and
                       "updatingButton" not in str(plan) and
                       "Text Input" not in str(plan),
                       method+" leaked target C#/raw selectors over MCP")
            for idx, method in ((7,"BadWritable"),(8,"BadDynamic"),
                                (9,"BadText")):
                blocked=inspect(idx,method)
                expect(blocked["status"]=="blocked" and blocked["blockers"]
                       and blocked["canAutoApply"] is False and
                       "targetStatements" not in blocked,
                       "unsafe property/return escaped fail-closed plan: "+method)
            expect(hashlib.sha256(src.read_bytes()).hexdigest()==original_sha,
                   "MCP wrote source while inspecting")
            # Change only the source property value; stale hash cannot plan.
            src.write_bytes(src.read_bytes().replace(
                b'By.Id("newButtonName")', b'By.Id("changed-id")'))
            stale=call(proc, 10, "inspect_pom_action_plan",
                {"sourceDirectory":"pom",
                 "sourceType":"PublicLike.TextInputPage",
                 "sourceMethod":"EnterText",
                 "expectedSourceTreeHash":tree})
            expect(stale.get("isError"), "stale captured POM source accepted")
            print("P2_PUBLIC_PROPERTY_MCP_STDIO_HASH_ONLY_PASSED")
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    expect(len(sys.argv)==2, "usage: script.py <MCP dll/executable>")
    main(sys.argv[1])
