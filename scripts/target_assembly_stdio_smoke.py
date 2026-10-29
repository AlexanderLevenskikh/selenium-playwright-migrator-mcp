#!/usr/bin/env python3
"""Real MCP stdio + explicit Core CLI end-to-end generated NUnit assembly.

Only fictional source, no customer private data. MCP remains read-only; a
separate explicit CLI writes/builds/tests a new target directory in temp.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def main(binary, assembly_cli):
    with tempfile.TemporaryDirectory(prefix="assembly-mcp-preview17-") as work:
        root = pathlib.Path(work)
        src = root / "source"
        src.mkdir()
        (src / "Sample.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>',
            encoding="utf-8")
        (src / "AssemblyScope.cs").write_text("""
using NUnit.Framework;
[SetUpFixture] public sealed class AssemblyScope
{
    [OneTimeSetUp] public void Start() { Recorder.RootStart(); }
    [OneTimeTearDown] public void End() { Recorder.RootEnd(); }
}
""", encoding="utf-8")
        (src / "NamespaceScope.cs").write_text("""
using NUnit.Framework;
namespace Example {
    [SetUpFixture] public sealed class NamespaceScope
    {
        [OneTimeSetUp] public void Start() { Recorder.NamespaceStart(); }
        [OneTimeTearDown] public void End() { Recorder.NamespaceEnd(); }
    }
}
""", encoding="utf-8")
        (src / "TestFixture.cs").write_text("""
using NUnit.Framework;
namespace Example.Nested {
    [TestFixture] public sealed class TestFixture
    {
        [Test] public void One() { Recorder.CheckOne(); }
        [Test] public void Two() { Recorder.CheckTwo(); }
    }
}
""", encoding="utf-8")
        (src / "AssemblyScheduling.cs").write_text("""
using NUnit.Framework;
[assembly: Parallelizable(ParallelScope.Fixtures)]
[assembly: LevelOfParallelism(3)]
""", encoding="utf-8")
        mappings = {
            "Recorder.RootStart()": [
                'System.AppContext.SetData("root", ((int?)System.AppContext.GetData("root") ?? 0) + 1);'
            ],
            "Recorder.NamespaceStart()": [
                'NUnit.Framework.Assert.That(System.AppContext.GetData("root"), NUnit.Framework.Is.EqualTo(1));',
                'System.AppContext.SetData("namespace", ((int?)System.AppContext.GetData("namespace") ?? 0) + 1);'
            ],
            "Recorder.CheckOne()": [
                'NUnit.Framework.Assert.That(System.AppContext.GetData("root"), NUnit.Framework.Is.EqualTo(1));',
                'NUnit.Framework.Assert.That(System.AppContext.GetData("namespace"), NUnit.Framework.Is.EqualTo(1));',
                'NUnit.Framework.Assert.That(System.Reflection.Assembly.GetExecutingAssembly().GetCustomAttributes(typeof(NUnit.Framework.ParallelizableAttribute), false).Length, NUnit.Framework.Is.EqualTo(1));',
                'NUnit.Framework.Assert.That(System.Reflection.Assembly.GetExecutingAssembly().GetCustomAttributes(typeof(NUnit.Framework.LevelOfParallelismAttribute), false).Length, NUnit.Framework.Is.EqualTo(1));',
                'System.AppContext.SetData("one", true);'
            ],
            "Recorder.CheckTwo()": [
                'NUnit.Framework.Assert.That(System.AppContext.GetData("root"), NUnit.Framework.Is.EqualTo(1));',
                'NUnit.Framework.Assert.That(System.AppContext.GetData("namespace"), NUnit.Framework.Is.EqualTo(1));',
                'System.AppContext.SetData("two", true);'
            ],
            "Recorder.NamespaceEnd()": [
                'NUnit.Framework.Assert.That(System.AppContext.GetData("one"), NUnit.Framework.Is.EqualTo(true));',
                'NUnit.Framework.Assert.That(System.AppContext.GetData("two"), NUnit.Framework.Is.EqualTo(true));',
                'System.AppContext.SetData("namespaceEnded", true);'
            ],
            "Recorder.RootEnd()": [
                'NUnit.Framework.Assert.That(System.AppContext.GetData("namespaceEnded"), NUnit.Framework.Is.EqualTo(true));'
            ]
        }
        config = {
            "SourceProjectName": "Synthetic",
            "TestHost": {"BaseClass": "object",
                         "ClassAttributes": ["TestFixture", "NonParallelizable"]},
            "Methods": [
                {"SourceMethod": method, "TargetStatements": statements,
                 "RequiresReview": True}
                for method, statements in mappings.items()
            ]
        }
        config_path = root / "adapter.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        cmd = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ, MIGRATOR_WORKSPACE=str(root)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc":"2.0", "id":1, "method":"initialize",
                        "params":{"protocolVersion":"2025-06-18", "capabilities":{},
                                  "clientInfo":{"name":"target-assembly-mcp","version":"1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize")
            send(proc, {"jsonrpc":"2.0", "method":"notifications/initialized"})

            analyze = value(call(proc, 2, "analyze_migration",
                                 {"source":"source", "config":"adapter.json"}))
            preview = value(call(proc, 3, "preview_migration",
                                 {"source":"source", "config":"adapter.json",
                                  "expectedAnalysisId":analyze["analysisId"]}))
            plan = value(call(proc, 4, "plan_target_assembly", {
                "source":"source", "config":"adapter.json",
                "expectedAnalysisId":analyze["analysisId"],
                "expectedCandidateId":preview["candidateId"]
            }))
            expect(plan["status"] == "ready_for_build"
                   and plan["declaredTests"] == 2
                   and plan["scopedSetUpFixtures"] == 2,
                   "Project-level plan must prove one complete NUnit scope closure")
            expect(len(plan["files"]) == 6
                   and sum(f["relativePath"].endswith(".cs") for f in plan["files"]) == 4
                   and plan["schemaVersion"] == "migrator-target-assembly/v1alpha2"
                   and len(plan["assemblyScheduling"]) == 2
                   and all(a["sourceLine"] > 0 for a in plan["assemblyScheduling"])
                   and any(a["targetExpression"].endswith("LevelOfParallelism(3)")
                           for a in plan["assemblyScheduling"])
                   and any(f["relativePath"] ==
                           "Migrator.Generated.NUnitAssemblyScheduling.cs"
                           for f in plan["files"])
                   and any(f["relativePath"] == "Migrator.Generated.Tests.csproj"
                           for f in plan["files"])
                   and any(f["relativePath"] == "migrator-assembly-manifest.json"
                           for f in plan["files"]),
                   "Complete target assembly must include scheduling, fixtures, csproj and manifest")
            expect(plan["candidateId"] == preview["candidateId"]
                   and len(plan["targetTreeHash"]) == 64,
                   "Target assembly identity must be bound to preview parent")

            stale = call(proc, 5, "plan_target_assembly", {
                "source":"source", "config":"adapter.json",
                "expectedAnalysisId":"bad-stale-analysis"
            })
            expect(stale.get("isError") is True,
                   "MCP plan cannot accept an arbitrary stale analysis")
            missing = value(call(proc, 6, "verify_target_assembly", {
                "source":"source", "targetRoot":"generated",
                "expectedAnalysisId":plan["analysisId"],
                "candidateId":plan["candidateId"], "config":"adapter.json"
            }))
            expect(missing["completeness"]["status"] != "passed"
                   and missing["build"]["status"] == "not_run"
                   and missing["nUnitRuntime"]["status"] == "not_run",
                   "MCP may not invent a completed target build")

            # Explicit trusted local Core CLI handles writes and runtime; the
            # MCP stdio API remains read-only throughout this script.
            output = root / "generated"
            cli = subprocess.run([
                "dotnet", str(assembly_cli), "generate", str(src), str(output),
                "--config", str(config_path), "--build", "--test"
            ], text=True, capture_output=True, timeout=270)
            expect(cli.returncode == 0,
                   "Core CLI failed to build/run synthetic project: "
                   + cli.stdout[-2500:] + cli.stderr[-2500:])
            cli_result = json.loads(cli.stdout)
            expect(cli_result["completeness"]["status"] == "passed"
                   and cli_result["build"]["status"] == "passed"
                   and cli_result["nUnitRuntime"]["status"] == "passed"
                   and cli_result["nUnitRuntime"]["executedTests"] == 2
                   and cli_result["nUnitRuntime"]["passedTests"] == 2,
                   "Actual target assembly build and two NUnit tests must pass")

            verified = value(call(proc, 7, "verify_target_assembly", {
                "source":"source", "targetRoot":"generated",
                "expectedAnalysisId":plan["analysisId"],
                "candidateId":plan["candidateId"], "config":"adapter.json"
            }))
            expect(verified["completeness"]["status"] == "passed"
                   and verified["targetTreeHash"] == plan["targetTreeHash"]
                   and verified["build"]["status"] == "not_run"
                   and verified["nUnitRuntime"]["status"] == "not_run",
                   "Read-only MCP verification cannot inherit the CLI run's runtime result")

            target_file = output / "NamespaceScopePlaywright.cs"
            original = target_file.read_bytes()
            target_file.unlink()
            incomplete = value(call(proc, 8, "verify_target_assembly", {
                "source":"source", "targetRoot":"generated",
                "expectedAnalysisId":plan["analysisId"],
                "candidateId":plan["candidateId"], "config":"adapter.json"
            }))
            expect(incomplete["completeness"]["status"] != "passed",
                   "Missing target SetUpFixture cannot be accepted by the MCP")
            target_file.write_bytes(original)
            (output / "Unlisted.cs").write_text("public class Unlisted {}", encoding="utf-8")
            added = value(call(proc, 9, "verify_target_assembly", {
                "source":"source", "targetRoot":"generated",
                "expectedAnalysisId":plan["analysisId"],
                "candidateId":plan["candidateId"], "config":"adapter.json"
            }))
            expect(added["completeness"]["status"] != "passed",
                   "Unexpected target C# must fail completeness even with Compile globs disabled")

            print("Project-level target assembly MCP + CLI + NUnit runtime passed", flush=True)
        finally:
            proc.terminate()
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: target_assembly_stdio_smoke.py <MCP.dll|exe> <Core.AssemblyCli.dll>")
    binary = pathlib.Path(sys.argv[1]).resolve()
    cli = pathlib.Path(sys.argv[2]).resolve()
    expect(binary.exists() and cli.exists(),
           "MCP and Core Assembly CLI must both be compiled")
    main(binary, cli)
