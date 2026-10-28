#!/usr/bin/env python3
"""True MCP stdio integration: synthetic NUnit SetUp Page Object aliases.

No private source, business URL, selector, credential or backend access.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def run(binary):
    with tempfile.TemporaryDirectory(prefix="fixture-page-alias-") as directory:
        root = pathlib.Path(directory)
        (root / "SyntheticFixture.cs").write_text("""
using NUnit.Framework;
using FluentAssertions;
[TestFixture]
public sealed class SyntheticFixture {
    private SyntheticPage page;
    [SetUp] public void Prepare() {
        var pagef = Navigation.OpenSyntheticPage();
        pagef.Loader.ValidateLoading();
        page = pagef;
    }
    [Test] public void ChecksAndClicks() {
        page.Table.Items.ElementAt(0).Text.Get().Should().Be("sample");
        page.Save.Click();
        page.Unknown.SideEffect();
    }
}
""", encoding="utf-8")

        cfg = {
            "SourceProjectName": "Synthetic",
            "Methods": [
                {"SourceMethod": "Navigation.OpenSyntheticPage()",
                 "TargetStatements": ['await Page.GotoAsync("https://example.invalid/fixture");'],
                 "RequiresReview": True},
                {"SourceMethod": "pagef.Loader.ValidateLoading()",
                 "TargetStatements": ['await Expect(Page.Locator("#loader")).ToBeHiddenAsync();'],
                 "RequiresReview": True}
            ],
            "UiTargets": [
                {"SourceExpression": "page.Table.Items",
                 "TargetExpression": 'Page.Locator("[data-test=\\"row\\"]")',
                 "TargetKind": "RawExpression"},
                {"SourceExpression": "page.Save",
                 "TargetExpression": 'Page.Locator("#save")',
                 "TargetKind": "RawExpression"}
            ]
        }
        (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        cmd = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "fixture-lifecycle", "version": "1"}}})
            expect("serverInfo" in receive(proc, 1), "initialize")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

            analyze = value(call(proc, 2, "analyze_migration",
                                 {"source": "SyntheticFixture.cs", "config": "config.json"}))
            preview = value(call(proc, 3, "preview_migration",
                                 {"source": "SyntheticFixture.cs", "config": "config.json",
                                  "expectedAnalysisId": analyze["analysisId"]}))
            expect(preview["transformationStatus"] == "partial"
                   and len(preview["files"]) == 1,
                   "Source fixture alias must remain review-only")
            output = preview["files"][0]["content"]
            expect('[MIGRATOR:FIXTURE_PAGE_ALIAS_REQUIRES_REVIEW]' in output,
                   "Missing explicit lifecycle review blocker")
            expect('await Page.GotoAsync("https://example.invalid/fixture");' in output
                   and 'ToBeHiddenAsync();' in output,
                   "Navigation and loader must survive SetUp in order")
            expect('await Page.Locator("#save").ClickAsync();' in output,
                   "Mapped fixture field click should be executable")
            expect('ToHaveTextAsync("sample")' in output,
                   "Mapped table assertion should be executable")
            expect('[MIGRATOR:TABLE_ASSERTION_REQUIRES_SETUP_REVIEW]' not in output,
                   "Bound lifecycle should remove duplicate per-table setup blockers")
            expect('page.Unknown.SideEffect();' not in [
                line.strip() for line in output.splitlines()
                if not line.strip().startswith("//")
            ], "Unknown POM method must not be active")
            expect(preview["files"][0]["fullyConvertedTests"] == 0,
                   "No false complete with review TODOs")

            verified = value(call(proc, 4, "verify_artifact", {
                "source": "SyntheticFixture.cs", "config": "config.json",
                "candidateId": preview["candidateId"],
                "expectedAnalysisId": analyze["analysisId"]
            }))
            expect(verified["syntax"]["status"] == "passed"
                   and verified["compile"]["status"] == "not_run"
                   and verified["runtime"]["status"] == "not_run"
                   and verified["observables"]["status"] == "not_run",
                   "Do not confuse syntax success with build or browser equivalence")

            # Remove the Loader mapping: the source-only setup operation
            # invalidates navigation provenance. Only independently mapped
            # table checks may be preserved with an explicit setup warning.
            cfg["Methods"] = cfg["Methods"][:1]
            (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            new_analysis = value(call(proc, 5, "analyze_migration",
                                      {"source": "SyntheticFixture.cs", "config": "config.json"}))
            new_preview = value(call(proc, 6, "preview_migration",
                                     {"source": "SyntheticFixture.cs", "config": "config.json",
                                      "expectedAnalysisId": new_analysis["analysisId"]}))
            rejected = new_preview["files"][0]["content"]
            expect('[MIGRATOR:FIXTURE_PAGE_ALIAS_REQUIRES_REVIEW]' not in rejected
                   and 'await Page.Locator("#save").ClickAsync();' not in rejected
                   and new_preview["files"][0]["fullyConvertedTests"] == 0,
                   "Unmapped Loader must not activate source Page Object alias")
            print("Fixture Page Object lifecycle MCP protocol passed", flush=True)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: fixture_lifecycle_smoke.py <MCP.dll|executable>")
    binary = pathlib.Path(sys.argv[1]).resolve()
    expect(binary.exists(), "MCP binary missing")
    run(binary)
