#!/usr/bin/env python3
"""Real stdio check of mapping-review safety; synthetic project only."""
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect

if len(sys.argv) != 2:
    raise SystemExit("Usage: pom_mapping_review_smoke.py <MCP dll|executable>")
binary = pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="pom-review-") as directory:
    root = pathlib.Path(directory)
    (root / "Combobox.cs").write_text("""
public class Combobox {
    public void InputAndSelect(string value) {
        Click();
        input.ClearAndInputText(value);
        accept.Click();
    }
}
""", encoding="utf-8")
    command = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
    start_reader(proc)
    try:
        send(proc, {"jsonrpc":"2.0","id":1,"method":"initialize",
                    "params":{"protocolVersion":"2025-06-18","capabilities":{},
                              "clientInfo":{"name":"pom-review-smoke","version":"1"}}})
        expect("serverInfo" in receive(proc,1), "MCP initialize")
        send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
        report = value(call(proc,2,"inspect_pom_sources",
                            {"sourceDirectory":".","pageTypes":["Combobox"]}))
        options = {"sourceDirectory":".","sourceType":"Combobox",
                   "sourceMethod":"InputAndSelect",
                   "expectedSourceTreeHash":report["sourceTreeHash"]}
        lost = value(call(proc,3,"review_pom_mapping",
                          dict(options,targetStatements=[
                              'await Page.Locator("#input").FillAsync(value);'])))
        expect(lost["status"]=="rejected_incomplete"
               and any(x["effect"]=="click" for x in lost["missingObligations"]),
               "Lost source clicks must reject shortened mapping")
        full = value(call(proc,4,"review_pom_mapping",
                          dict(options,targetStatements=[
                              'await Page.Locator("#combo").ClickAsync();',
                              'await Page.Locator("#input").FillAsync(value);',
                              'await Page.Locator("#accept").ClickAsync();'])))
        expect(full["status"]=="requires_review" and not full["behaviorallyVerified"],
               "Never approve category-matched mapping as behaviorally verified")
        (root/"Combobox.cs").write_text((root/"Combobox.cs").read_text()+"\n// edited")
        stale = call(proc,5,"review_pom_mapping",
                     dict(options,targetStatements=['await Page.ClickAsync();']))
        expect(stale.get("isError"),"Stale mapping review accepted")
        print("POM mapping MCP protocol passed",flush=True)
    finally:
        proc.terminate()
        try: proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill();proc.communicate(timeout=10)
