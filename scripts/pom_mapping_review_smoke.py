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
    public void InputAndSelectFiltered(string value) {
        Click();
        input.Visible().Wait().EqualTo(true);
        input.ClearAndInputText(value);
        menuItems.Wait().Single(x => x.Text, Contains.Substring(value)).Click();
        accept.Click();
    }
}
""", encoding="utf-8")
    (root / "Loader.cs").write_text("""
public sealed class Loader {
    public void ValidateLoading() {
        var attempt = 0;
        while (attempt < 2) {
            try {
                if (error.Displayed().Get()) Reload();
                marker.Visible().Wait().EqualTo(true);
                break;
            } catch (WebDriverTimeoutException) {
                attempt++;
                if (attempt == 2) Assert.Fail("exhausted");
            }
        }
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

        filtered = dict(options, sourceMethod="InputAndSelectFiltered")
        lost_filter = value(call(proc,6,"review_pom_mapping",
                            dict(filtered,targetStatements=[
                                'await Page.Locator("#combo").ClickAsync();',
                                'await Page.Locator("#input").WaitForAsync();',
                                'await Page.Locator("#input").FillAsync(value);',
                                'await Page.Locator("#menu").WaitForAsync();',
                                'await Page.Locator("#option").ClickAsync();',
                                'await Page.Locator("#accept").ClickAsync();'])))
        expect(lost_filter["status"]=="rejected_incomplete"
               and "source_parameter_usage_not_preserved" in lost_filter["reviewFlags"]
               and lost_filter["parameterFlows"][0]["sourceArgumentUses"] == 2,
               "Full action count with missing menu argument must be rejected")
        with_filter = value(call(proc,7,"review_pom_mapping",
                           dict(filtered,targetStatements=[
                               'await Page.Locator("#combo").ClickAsync();',
                               'await Page.Locator("#input").WaitForAsync();',
                               'await Page.Locator("#input").FillAsync(value);',
                               'var options = Page.Locator("#menu").Filter(new() { HasTextString = value });',
                               'await options.WaitForAsync();',
                               'await options.ClickAsync();',
                               'await Page.Locator("#accept").ClickAsync();'])))
        expect(with_filter["status"]=="requires_review"
               and with_filter["parameterFlows"][0]["targetArgumentUses"] >= 2
               and not with_filter["behaviorallyVerified"],
               "Complete parameter flow must still need DOM review")
        loader = value(call(proc, 9, "inspect_pom_sources",
                            {"sourceDirectory": ".", "pageTypes": ["Loader"]}))
        loader_params = {"sourceDirectory": ".", "sourceType": "Loader",
                         "sourceMethod": "ValidateLoading",
                         "expectedSourceTreeHash": loader["sourceTreeHash"]}
        steps = [
            "var attempt = 0;",
            "while (attempt < 2) {",
            "try {",
            'if (await Page.Locator("#error").IsVisibleAsync()) await Page.ReloadAsync();',
            'await Page.Locator("#ready").WaitForAsync();',
            "break;",
            "} catch (System.TimeoutException) {",
            "attempt++;",
            'if (attempt == 2) Assert.Fail("exhausted");',
            "}",
            "}"
        ]
        good_loader = value(call(proc, 10, "review_pom_mapping",
                                 dict(loader_params, targetStatements=steps)))
        expect(good_loader["status"] == "requires_review"
               and not good_loader["missingObligations"],
               "Structurally reviewed Loader may not be promoted to passed")
        bad_catch = value(call(proc, 11, "review_pom_mapping",
                               dict(loader_params, targetStatements=[
                                   line.replace("System.TimeoutException", "System.Exception")
                                   for line in steps])))
        expect(bad_catch["status"] == "rejected_incomplete"
               and "typed_source_catch_widened" in bad_catch["reviewFlags"],
               "Broadened target exception handling must be rejected")
        bad_reload = value(call(proc, 12, "review_pom_mapping",
                                dict(loader_params, targetStatements=[
                                    line.replace(
                                        'if (await Page.Locator("#error").IsVisibleAsync()) await Page.ReloadAsync();',
                                        'if (await Page.Locator("#error").IsVisibleAsync()) { } await Page.ReloadAsync();')
                                    for line in steps])))
        expect(bad_reload["status"] == "rejected_incomplete"
               and "conditional_reload_moved_outside_branch" in bad_reload["reviewFlags"],
               "Moving conditional reload outside guard must be rejected")
        (root/"Combobox.cs").write_text((root/"Combobox.cs").read_text()+"\n// edited")
        stale = call(proc,8,"review_pom_mapping",
                     dict(options,targetStatements=['await Page.ClickAsync();']))
        expect(stale.get("isError"),"Stale mapping review accepted")
        print("POM mapping MCP protocol passed",flush=True)
    finally:
        proc.terminate()
        try: proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill();proc.communicate(timeout=10)
