#!/usr/bin/env python3
"""True MCP stdio regression for synthetic NUnit namespace/assembly SetUpFixtures.

A scoped hook belongs to one generated NUnit assembly artifact, never to each
dependent test class. No customer code, URL, selector, credential or backend.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def run(binary):
    with tempfile.TemporaryDirectory(prefix="nunit-scoped-mcp-") as folder:
        root = pathlib.Path(folder)
        (root / "Synthetic.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',
            encoding="utf-8")
        (root / "GlobalHooks.cs").write_text("""
using NUnit.Framework;
[SetUpFixture] public class GlobalHooks {
    [OneTimeSetUp] public void BeforeAll() { Recorder.Mark("global-before"); }
    [OneTimeTearDown] public void AfterAll() { Recorder.Mark("global-after"); }
}
""", encoding="utf-8")
        (root / "ParentHooks.cs").write_text("""
using NUnit.Framework;
namespace Sample {
    [SetUpFixture] public class ParentHooks {
        [OneTimeSetUp] public void BeforeAll() { Recorder.Mark("parent-before"); }
        [OneTimeTearDown] public void AfterAll() { Recorder.Mark("parent-after"); }
    }
}
""", encoding="utf-8")
        (root / "NestedHooks.cs").write_text("""
using NUnit.Framework;
namespace Sample.Nested {
    [SetUpFixture] public class NestedHooks {
        [OneTimeSetUp] public void BeforeAll() { Recorder.Mark("nested-before"); }
        [OneTimeTearDown] public void AfterAll() { Recorder.Mark("nested-after"); }
    }
}
""", encoding="utf-8")
        # Inherited per-test SetUp must remain after all scoped one-time
        # setups without being copied into each SetUpFixture artifact.
        (root / "FixtureBase.cs").write_text("""
using NUnit.Framework;
namespace Sample.Nested {
    public class FixtureBase {
        [SetUp] public void BeforeEach() { Recorder.Mark("base-before"); }
    }
}
""", encoding="utf-8")
        (root / "MainFixture.cs").write_text("""
using NUnit.Framework;
namespace Sample.Nested {
    [TestFixture] public class MainFixture : FixtureBase {
        [Test] public void One() { Recorder.Mark("test"); }
    }
}
""", encoding="utf-8")
        (root / "SiblingFixture.cs").write_text("""
using NUnit.Framework;
namespace SampleElse {
    [TestFixture] public class SiblingFixture {
        [Test] public void Other() { Recorder.Mark("test"); }
    }
}
""", encoding="utf-8")

        labels = ("global-before", "global-after", "parent-before",
                  "parent-after", "nested-before", "nested-after", "base-before", "test")
        config = {
            "SourceProjectName": "Synthetic",
            "Methods": [
                {"SourceMethod": 'Recorder.Mark("' + label + '")',
                 "TargetStatements": ['System.Console.WriteLine("' + label + '");'],
                 "RequiresReview": True}
                for label in labels
            ]
        }
        configfile = root / "config.json"
        configfile.write_text(json.dumps(config), encoding="utf-8")

        cmd = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0", "id":1, "method":"initialize",
                        "params":{"protocolVersion":"2025-06-18", "capabilities":{},
                                  "clientInfo":{"name":"nunit-scoped-stdio","version":"1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize")
            send(proc, {"jsonrpc":"2.0", "method":"notifications/initialized"})

            analyze = value(call(proc, 2, "analyze_migration",
                                 {"source":".", "config":"config.json"}))
            expect(analyze["declaredTests"] == 2
                   and analyze["discoveryStatus"] == "complete",
                   "Two tests and three standalone zero-test scoped sources must be discovered")
            for name in ("GlobalHooks.cs", "ParentHooks.cs", "NestedHooks.cs"):
                survey = next(f for f in analyze["files"] if f["relativePath"] == name)
                expect(survey["disposition"] == "supported"
                       and survey["declaredTests"] == 0,
                       "NUnit SetUpFixture without tests was silently dropped: " + name)

            preview = value(call(proc, 3, "preview_migration",
                                 {"source":".","config":"config.json",
                                  "expectedAnalysisId":analyze["analysisId"]}))
            expect(preview["transformationStatus"] == "partial"
                   and len(preview["files"]) == 5,
                   "Exactly 3 scope artifacts + 2 test fixture artifacts are required")
            files = {file["sourcePath"]:file["content"] for file in preview["files"]}
            for source, label in (("GlobalHooks.cs","global-before"),
                                  ("ParentHooks.cs","parent-before"),
                                  ("NestedHooks.cs","nested-before")):
                target = files[source]
                expect("[SetUpFixture]" in target
                       and 'System.Console.WriteLine("' + label + '");' in target
                       and ": PageTest" not in target,
                       "Standalone suite scope lost an active mapped effect: " + source)
            expect("namespace Sample;" in files["ParentHooks.cs"]
                   and "namespace Sample.Nested;" in files["NestedHooks.cs"]
                   and "namespace Sample.Nested;" in files["MainFixture.cs"]
                   and "namespace Sample.Nested.Playwright;" not in files["MainFixture.cs"],
                   "Namespace containment must survive source-to-target translation")
            main = files["MainFixture.cs"]
            expect('System.Console.WriteLine("base-before");' in main
                   and "[MIGRATOR:NUNIT_LIFECYCLE_REQUIRES_REVIEW]" in main,
                   "Inherited per-test SetUp must survive alongside scoped one-time dependencies")
            expect(main.count("[MIGRATOR:NUNIT_SETUPFIXTURE_DEPENDENCY_REQUIRES_REVIEW]") == 3,
                   "A nested fixture must retain global, parent and child scope dependencies")
            expect(files["SiblingFixture.cs"].count(
                "[MIGRATOR:NUNIT_SETUPFIXTURE_DEPENDENCY_REQUIRES_REVIEW]") == 1,
                   "A similarly prefixed sibling namespace must only inherit the global scope")
            expect("global-before" not in main and "parent-before" not in main
                   and "nested-before" not in main,
                   "Do not repeat once-per-scope effects inside individual tests")

            artifact = value(call(proc, 4, "verify_artifact",
                                  {"source":".", "config":"config.json",
                                   "candidateId":preview["candidateId"],
                                   "expectedAnalysisId":analyze["analysisId"]}))
            expect(artifact["syntax"]["status"] == "passed"
                   and artifact["compile"]["status"] == "not_run"
                   and artifact["runtime"]["status"] == "not_run"
                   and artifact["observables"]["status"] == "not_run",
                   "Cross-file syntax success cannot be presented as compilation or behavior")

            (root / "OtherParentHooks.cs").write_text("""
using NUnit.Framework;
namespace Sample {
    [SetUpFixture] public class OtherParentHooks {
        [OneTimeSetUp] public void Before() { Recorder.Mark("parent-before"); }
    }
}
""", encoding="utf-8")
            ambiguousAnalysis = value(call(proc, 5, "analyze_migration",
                                           {"source":".", "config":"config.json"}))
            ambiguousPreview = value(call(proc, 6, "preview_migration",
                                          {"source":".", "config":"config.json",
                                           "expectedAnalysisId":ambiguousAnalysis["analysisId"]}))
            ambiguous = {file["sourcePath"]:file["content"]
                         for file in ambiguousPreview["files"]}
            expect("[MIGRATOR:NUNIT_SETUPFIXTURE_SAME_SCOPE_ORDER]" in ambiguous["MainFixture.cs"]
                   and "Assert.Inconclusive(" in ambiguous["MainFixture.cs"]
                   and "[MIGRATOR:NUNIT_SETUPFIXTURE_SAME_SCOPE_ORDER]" in ambiguous["ParentHooks.cs"],
                   "Same-level scoped setup ambiguity must block target execution")
            (root / "OtherParentHooks.cs").unlink()

            config["Methods"] = [mapping for mapping in config["Methods"] if
                mapping["SourceMethod"] != 'Recorder.Mark("nested-after")']
            configfile.write_text(json.dumps(config), encoding="utf-8")
            unmappedAnalysis = value(call(proc, 7, "analyze_migration",
                                          {"source":".", "config":"config.json"}))
            unmappedPreview = value(call(proc, 8, "preview_migration",
                                         {"source":".", "config":"config.json",
                                          "expectedAnalysisId":unmappedAnalysis["analysisId"]}))
            unmapped = {file["sourcePath"]:file["content"]
                        for file in unmappedPreview["files"]}
            expect("[MIGRATOR:NUNIT_SETUPFIXTURE_ACTION_REQUIRES_MAPPING]" in unmapped["NestedHooks.cs"]
                   and "Assert.Inconclusive(" in unmapped["NestedHooks.cs"]
                   and 'System.Console.WriteLine("nested-before");' not in unmapped["NestedHooks.cs"],
                   "An unmapped teardown must block its entire suite before setup effects run")
            print("Scoped NUnit SetupFixture MCP protocol passed", flush=True)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: scoped_setupfixture_smoke.py <MCP.dll|executable>")
    executable = pathlib.Path(sys.argv[1]).resolve()
    expect(executable.exists(), "MCP binary not found")
    run(executable)
