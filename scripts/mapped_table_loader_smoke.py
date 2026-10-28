#!/usr/bin/env python3
"""Real MCP stdio regression: explicit Loader retry and mapped table assertions.
All C# and selectors here are synthetic and cannot access a customer backend.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def run(binary):
    with tempfile.TemporaryDirectory(prefix="loader-table-stdio-") as folder:
        root = pathlib.Path(folder)
        (root / "CatalogFixture.cs").write_text("""
using NUnit.Framework;
using FluentAssertions;
[TestFixture] public class CatalogFixture {
    private CatalogPage page;
    [SetUp] public void Prepare() {
        var pagef = Navigation.OpenCatalogPage();
        pagef.Loader.ValidateLoading();
        page = pagef;
    }
    [Test] public void TableTextShouldStillBeAsserted() {
        page.Loader.ValidateLoading();
        page.Table.Items.ElementAt(0).Text.Get().Should().Be("code");
        page.Table.Items.ElementAt(1).Text.Get().Should().Contain("region");
        page.Table.Items.ElementAt(1).Text.Get().Should().NotContain("deprecated");
    }
}
""", encoding="utf-8")
        retry = [
            "var attempt = 0;",
            "while (attempt < 2)", "{", "try", "{",
            'if (await Page.Locator("#load-error").IsVisibleAsync())',
            "{", "await Page.ReloadAsync();", "}",
            'await Page.Locator("#ready").WaitForAsync(new() { State = WaitForSelectorState.Visible });',
            "break;", "}", "catch (System.TimeoutException)", "{",
            "attempt++;", "if (attempt == 2)", "{",
            'Assert.Fail("Synthetic page never became ready");',
            "}", "}", "}"
        ]
        config = {
            "SourceProjectName": "Synthetic",
            "Methods": [
                {"SourceMethod": "Navigation.OpenCatalogPage()",
                 "TargetStatements": ['await Page.GotoAsync("https://example.invalid/catalog");'],
                 "RequiresReview": True},
                {"SourceMethod": "pagef.Loader.ValidateLoading()",
                 "TargetStatements": retry, "RequiresReview": True},
                {"SourceMethod": "page.Loader.ValidateLoading()",
                 "TargetStatements": retry, "RequiresReview": True}
            ],
            "UiTargets": [
                {"SourceExpression": "page.Table.Items",
                 "TargetExpression": 'Page.Locator("[data-test=\\\"table\\\"] [data-test=\\\"row\\\"]")',
                 "TargetKind": "RawExpression"}
            ]
        }
        (root / "config.json").write_text(json.dumps(config), encoding="utf-8")

        command = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "synthetic-table-loader", "version": "1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            a = value(call(proc, 2, "analyze_migration",
                           {"source": "CatalogFixture.cs", "config": "config.json"}))
            p = value(call(proc, 3, "preview_migration",
                           {"source": "CatalogFixture.cs", "config": "config.json",
                            "expectedAnalysisId": a["analysisId"]}))
            expect(len(p["files"]) == 1 and p["transformationStatus"] == "partial",
                   "Incomplete source setup must remain partial")
            text = p["files"][0]["content"]
            expect(text.count("while (attempt < 2)") == 2
                   and text.count("catch (System.TimeoutException)") == 2,
                   "Exact source helper mapping did not override generic wait fallback")
            expect('ToHaveTextAsync("code")' in text
                   and 'ToContainTextAsync("region")' in text
                   and '.Not.ToContainTextAsync("deprecated")' in text,
                   "Table equality, substring and negated substring assertions must be executable")
            expect(text.count("[MIGRATOR:TABLE_ASSERTION_REQUIRES_SETUP_REVIEW]") == 3
                   and p["files"][0]["fullyConvertedTests"] == 0,
                   "Unverified fixture setup was falsely accepted")
            verified = value(call(proc, 4, "verify_artifact", {
                "source": "CatalogFixture.cs", "config": "config.json",
                "expectedAnalysisId": a["analysisId"], "candidateId": p["candidateId"]
            }))
            expect(verified["syntax"]["status"] == "passed"
                   and verified["compile"]["status"] == "not_run"
                   and verified["runtime"]["status"] == "not_run",
                   "Syntax-only evidence was conflated with compile/runtime")
            config["UiTargets"] = []
            (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
            changed = value(call(proc, 5, "analyze_migration", {
                "source": "CatalogFixture.cs", "config": "config.json"}))
            blocked = value(call(proc, 6, "preview_migration", {
                "source": "CatalogFixture.cs", "config": "config.json",
                "expectedAnalysisId": changed["analysisId"]}))
            body = blocked["files"][0]["content"]
            expect('ToHaveTextAsync("code")' not in body
                   and 'ToContainTextAsync("region")' not in body
                   and '.Not.ToContainTextAsync("deprecated")' not in body,
                   "Table assertions without explicit UiTargets were activated")
            print("Mapped Loader and table assertions MCP protocol passed", flush=True)
        finally:
            proc.terminate()
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: mapped_table_loader_smoke.py <MCP.dll|executable>")
    binary = pathlib.Path(sys.argv[1]).resolve()
    expect(binary.exists(), "MCP binary missing")
    run(binary)
