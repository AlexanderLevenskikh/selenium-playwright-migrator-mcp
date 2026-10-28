#!/usr/bin/env python3
"""MCP stdio regression: Roslyn inherited NUnit lifecycle, synthetic only."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def run(binary):
    with tempfile.TemporaryDirectory(prefix="inherited-nunit-") as folder:
        root = pathlib.Path(folder)
        (root / "Synthetic.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',
            encoding="utf-8")
        (root / "BaseFixture.cs").write_text("""
using NUnit.Framework;
public class BaseFixture {
    [OneTimeSetUp] public void BaseOnce() { Recorder.Note("once-base"); }
    [SetUp] public void BaseSetUp() { Recorder.Note("setup-base"); }
    [TearDown] public void BaseTearDown() { Recorder.Note("tear-base"); }
    [OneTimeTearDown] public void BaseAfterAll() { Recorder.Note("after-base"); }
}
""", encoding="utf-8")
        (root / "IntermediateFixture.cs").write_text("""
using NUnit.Framework;
public class IntermediateFixture : BaseFixture {
    [OneTimeSetUp] public void MidOnce() { Recorder.Note("once-mid"); }
    [SetUp] public void MidSetUp() { Recorder.Note("setup-mid"); }
    [TearDown] public void MidTearDown() { Recorder.Note("tear-mid"); }
    [OneTimeTearDown] public void MidAfterAll() { Recorder.Note("after-mid"); }
}
""", encoding="utf-8")
        leaf = root / "LeafFixture.cs"
        leaf.write_text("""
using NUnit.Framework;
[TestFixture] public class LeafFixture : IntermediateFixture {
    [OneTimeSetUp] public void LeafOnce() { Recorder.Note("once-leaf"); }
    [SetUp] public void LeafSetUp() { Recorder.Note("setup-leaf"); }
    [TearDown] public void LeafTearDown() { Recorder.Note("tear-leaf"); }
    [OneTimeTearDown] public void LeafAfterAll() { Recorder.Note("after-leaf"); }
    [Test] public void HasLifecycle() { Recorder.Note("test"); }
}
""", encoding="utf-8")
        ordered = [
            "once-base", "once-mid", "once-leaf",
            "setup-base", "setup-mid", "setup-leaf",
            "tear-leaf", "tear-mid", "tear-base",
            "after-leaf", "after-mid", "after-base", "test"
        ]
        config = {
            "SourceProjectName": "Synthetic",
            "Methods": [
                {"SourceMethod": 'Recorder.Note("' + label + '")',
                 "TargetStatements": ['System.Console.WriteLine("' + label + '");'],
                 "RequiresReview": True}
                for label in ordered
            ]
        }
        (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
        command = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0", "id":1, "method":"initialize",
                        "params":{"protocolVersion":"2025-06-18", "capabilities":{},
                                  "clientInfo":{"name":"inherited-nunit-smoke", "version":"1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize")
            send(proc, {"jsonrpc":"2.0", "method":"notifications/initialized"})

            analysis = value(call(proc, 2, "analyze_migration",
                                  {"source":"LeafFixture.cs", "config":"config.json"}))
            preview = value(call(proc, 3, "preview_migration",
                                 {"source":"LeafFixture.cs", "config":"config.json",
                                  "expectedAnalysisId":analysis["analysisId"]}))
            expect(len(preview["files"]) == 1 and preview["transformationStatus"] == "partial",
                   "An inherited fixture must remain review-required")
            generated = preview["files"][0]["content"]
            expect("[MIGRATOR:NUNIT_LIFECYCLE_REQUIRES_REVIEW]" in generated
                   and preview["files"][0]["fullyConvertedTests"] == 0,
                   "Unknown observable parity cannot be claimed")
            for kind in ("OneTimeSetUp", "SetUp", "TearDown", "OneTimeTearDown"):
                expect("[" + kind + "]" in generated, "Missing inherited NUnit hook: " + kind)
            for token in ordered:
                expect('System.Console.WriteLine("' + token + '");' in generated,
                       "Missing effectful synthetic hook: " + token)

            def index(token):
                return generated.index('System.Console.WriteLine("' + token + '");')

            for group in (ordered[:3], ordered[3:6], ordered[6:9], ordered[9:12]):
                expect(all(index(a) < index(b) for a, b in zip(group, group[1:])),
                       "Incorrect NUnit inheritance ordering: " + repr(group))
            expect("if (__migratorPerTestReached >= 2)" in generated
                   and "if (__migratorPerTestReached >= 0)" in generated
                   and "finally" in generated,
                   "Missing partial-failure / reverse-cleanup guards")
            verified = value(call(proc, 4, "verify_artifact",
                                  {"source":"LeafFixture.cs", "config":"config.json",
                                   "expectedAnalysisId":analysis["analysisId"],
                                   "candidateId":preview["candidateId"]}))
            expect(verified["syntax"]["status"] == "passed"
                   and verified["compile"]["status"] == "not_run"
                   and verified["runtime"]["status"] == "not_run",
                   "Syntax-only evidence was mislabeled as compilation or execution")

            original = leaf.read_text(encoding="utf-8")
            leaf.write_text(original.replace(
                '[Test] public void HasLifecycle()',
                '[SetUp] public void AnotherSetup() { Recorder.Note("setup-leaf"); }\n'
                '    [Test] public void HasLifecycle()'), encoding="utf-8")
            new_analysis = value(call(proc, 5, "analyze_migration",
                                      {"source":"LeafFixture.cs", "config":"config.json"}))
            rejected = value(call(proc, 6, "preview_migration",
                                  {"source":"LeafFixture.cs", "config":"config.json",
                                   "expectedAnalysisId":new_analysis["analysisId"]}))
            output = rejected["files"][0]["content"]
            expect("[MIGRATOR:NUNIT_LIFECYCLE_SAME_LEVEL_ORDER]" in output
                   and "Assert.Inconclusive(" in output
                   and rejected["files"][0]["fullyConvertedTests"] == 0,
                   "Ambiguous same-level hooks may not be flattened or accepted")
            print("Inherited NUnit lifecycle MCP protocol passed", flush=True)
        finally:
            proc.terminate()
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: inherited_nunit_lifecycle_smoke.py <MCP.dll|executable>")
    path = pathlib.Path(sys.argv[1]).resolve()
    expect(path.exists(), "MCP binary unavailable")
    run(path)
