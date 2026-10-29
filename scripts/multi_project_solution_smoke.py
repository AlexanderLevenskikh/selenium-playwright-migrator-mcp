#!/usr/bin/env python3
"""Multi-project solution: MCP read-only graph + trusted Core CLI build/NUnit.

All source code is fabricated. MCP must never write, build or run source.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from mcp_stdio_smoke import call, receive, send, start_reader, value, expect


def exercise(binary, cli):
    with tempfile.TemporaryDirectory(prefix="multi-csproj-stdio-") as temp:
        workspace = pathlib.Path(temp)
        source = workspace / "source"
        source.mkdir()

        def put(path, contents):
            target = source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")

        put("Shared/Shared.csproj",
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        put("Shared/Tracker.cs", """
namespace Synthetic.Shared;
public static class Tracker { public static int Count; }
""")
        project_template = """
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
  <ItemGroup><ProjectReference Include="../Shared/Shared.csproj" /></ItemGroup>
</Project>
"""
        for name in ("TestsOne", "TestsTwo"):
            put(name + "/" + name + ".csproj", project_template)
            put(name + "/Global.cs", """
using NUnit.Framework;
[SetUpFixture] public class RootHook {
    [OneTimeSetUp] public void Start() { Recorder.Start(); }
    [OneTimeTearDown] public void End() { Recorder.End(); }
}
""")
            put(name + "/Fixture.cs", """
using NUnit.Framework;
namespace Synthetic.Tests {
    [TestFixture] public class Fixture {
        [Test] public void A() { Recorder.Check(); }
    }
}
""")
        config = {
            "SourceProjectName": "Synthetic",
            "TestHost": {"BaseClass": "object",
                         "ClassAttributes": ["TestFixture", "NonParallelizable"]},
            "Methods": [
                {"SourceMethod": "Recorder.Start()",
                 "TargetStatements": ["Synthetic.Shared.Tracker.Count++;"],
                 "RequiresReview": True},
                {"SourceMethod": "Recorder.End()",
                 "TargetStatements": [
                     "NUnit.Framework.Assert.That(Synthetic.Shared.Tracker.Count, NUnit.Framework.Is.EqualTo(1));"
                 ], "RequiresReview": True},
                {"SourceMethod": "Recorder.Check()",
                 "TargetStatements": [
                     "NUnit.Framework.Assert.That(Synthetic.Shared.Tracker.Count, NUnit.Framework.Is.EqualTo(1));"
                 ], "RequiresReview": True}
            ]
        }
        adapter = workspace / "adapter.json"
        adapter.write_text(json.dumps(config), encoding="utf-8")
        command = ["dotnet", str(binary)] if binary.suffix == ".dll" else [str(binary)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, MIGRATOR_WORKSPACE=str(workspace)))
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18",
                                   "capabilities": {},
                                   "clientInfo": {"name": "multi-project-smoke",
                                                  "version": "1"}}})
            expect("serverInfo" in receive(proc, 1), "MCP initialize")
            send(proc, {"jsonrpc": "2.0",
                        "method": "notifications/initialized"})
            plan = value(call(proc, 2, "plan_target_solution",
                {"source": "source", "config": "adapter.json"}))
            expect(plan["status"] == "ready_for_build"
                and len(plan["projects"]) == 3
                and sum(p["kind"] == "nunit" for p in plan["projects"]) == 2
                and sum(p["kind"] == "library" for p in plan["projects"]) == 1,
                "project graph must contain two isolated NUnit assemblies and one shared library")
            expect(sum(p["scopedSetUpFixtures"] for p in plan["projects"]) == 2
                and sum(p["declaredTests"] for p in plan["projects"]) == 2,
                "each assembly must own its own global SetUpFixture and one test")
            expect(len(plan["targetTreeHash"]) == 64
                and len(plan["planId"]) == 64,
                "target plan and tree identity should be content-addressed")
            expect(all("content" not in f for f in plan["files"]),
                "MCP plan must not expose private generated source bodies")
            slnx = next(f for f in plan["files"] if
                f["relativePath"] == "Migrator.Generated.slnx")
            expect(len(slnx["sha256"]) == 64,
                "complete .slnx must be in the file ledger")

            stale = call(proc, 3, "plan_target_solution", {
                "source": "source", "config": "adapter.json",
                "expectedSourceTreeHash": "stale-parent"
            })
            expect(stale.get("isError") is True,
                "stale graph revision must fail closed")

            missing = value(call(proc, 4, "verify_target_solution", {
                "source": "source", "targetRoot": "generated",
                "expectedSourceTreeHash": plan["sourceTreeHash"],
                "expectedPlanId": plan["planId"], "config": "adapter.json"
            }))
            expect(missing["completeness"]["status"] != "passed"
                and missing["build"]["status"] == "not_run"
                and missing["nUnitRuntime"]["status"] == "not_run",
                "MCP may not invent build/run evidence when the target is absent")

            # Separate, trusted Core CLI performs the explicit write and
            # dotnet build/test. The MCP tool remains read-only.
            result = subprocess.run([
                "dotnet", str(cli), "solution-generate",
                str(source), str(workspace / "generated"),
                "--config", str(adapter), "--build", "--test"
            ], text=True, capture_output=True, timeout=290)
            expect(result.returncode == 0,
                "Trusted CLI solution build/NUnit failed: "
                + result.stdout[-3000:] + result.stderr[-3000:])
            executed = json.loads(result.stdout)
            expect(executed["completeness"]["status"] == "passed"
                and executed["build"]["status"] == "passed"
                and executed["nUnitRuntime"]["status"] == "passed"
                and executed["nUnitRuntime"]["executedTests"] == 2
                and executed["nUnitRuntime"]["passedTests"] == 2
                and len(executed["projectExecutions"]) == 2
                and all(p["nUnitRuntime"]["status"] == "passed"
                        for p in executed["projectExecutions"]),
                "real dotnet test must prove two distinct 1/1 NUnit assembly TRX results")

            readonly = value(call(proc, 5, "verify_target_solution", {
                "source": "source", "targetRoot": "generated",
                "expectedSourceTreeHash": plan["sourceTreeHash"],
                "expectedPlanId": plan["planId"], "config": "adapter.json"
            }))
            expect(readonly["completeness"]["status"] == "passed"
                and readonly["targetTreeHash"] == plan["targetTreeHash"]
                and readonly["build"]["status"] == "not_run"
                and readonly["nUnitRuntime"]["status"] == "not_run",
                "read-only MCP verification cannot inherit Core CLI runtime success")

            target = workspace / "generated"
            required = target / "TestsOne/RootHookPlaywright.cs"
            saved = required.read_bytes()
            required.unlink()
            damaged = value(call(proc, 6, "verify_target_solution", {
                "source": "source", "targetRoot": "generated",
                "expectedSourceTreeHash": plan["sourceTreeHash"],
                "expectedPlanId": plan["planId"], "config": "adapter.json"
            }))
            expect(damaged["completeness"]["status"] != "passed",
                   "missing global SetUpFixture in one target assembly must fail")
            required.write_bytes(saved)

            rogue = target / "TestsTwo/Unexpected.cs"
            rogue.write_text("public class Unexpected {}", encoding="utf-8")
            extra = value(call(proc, 7, "verify_target_solution", {
                "source": "source", "targetRoot": "generated",
                "expectedSourceTreeHash": plan["sourceTreeHash"],
                "expectedPlanId": plan["planId"], "config": "adapter.json"
            }))
            expect(extra["completeness"]["status"] != "passed",
                   "unexpected source cannot bypass explicit Compile closure")
            rogue.unlink()

            # No test-assembly references: a test assembly is not a shared
            # library and must not leak its SetUpFixture into another scope.
            put("TestsTwo/TestsTwo.csproj", project_template.replace(
                "</ItemGroup>",
                '<ProjectReference Include="../TestsOne/TestsOne.csproj" /></ItemGroup>'
            ))
            rejected = value(call(proc, 8, "plan_target_solution",
                {"source": "source", "config": "adapter.json"}))
            expect(rejected["status"] == "blocked"
                and any(i["code"] == "SOLUTION_REFERENCE_TO_TEST_ASSEMBLY"
                        for i in rejected["issues"]),
                "references to NUnit test assemblies must be blocked")

            # A source library depending on a vendor NuGet package is not
            # silently copied into a target SDK library without its dependency.
            put("TestsTwo/TestsTwo.csproj", project_template)
            shared_project = (source / "Shared/Shared.csproj").read_text(
                encoding="utf-8")
            put("Shared/Shared.csproj", shared_project.replace(
                "</Project>",
                '<ItemGroup><PackageReference Include="Synthetic.Optional" '
                'Version="1.0.0" /></ItemGroup></Project>'))
            unsafe_library = value(call(proc, 9, "plan_target_solution",
                {"source": "source", "config": "adapter.json"}))
            expect(unsafe_library["status"] == "blocked"
                and any(i["code"] == "SOLUTION_LIBRARY_PACKAGE_UNSUPPORTED"
                        for i in unsafe_library["issues"]),
                "MCP cannot report a package-dependent source library as buildable")
            put("Shared/Shared.csproj", shared_project)

            # A graph with unreviewed packages must fail quickly without
            # launching the expensive NUnit/Roslyn assembly candidates.
            put("TestsTwo/TestsTwo.csproj", project_template)
            reviewed_source = (source / "Shared/Shared.csproj").read_text(
                encoding="utf-8")
            package_project = reviewed_source.replace(
                "</Project>",
                '<ItemGroup><PackageReference Include="System.Collections.Immutable" '
                'Version="9.0.0" /></ItemGroup></Project>')
            put("Shared/Shared.csproj", package_project)
            unreviewed = value(call(proc, 9, "plan_target_solution", {
                "source": "source", "config": "adapter.json"}))
            expect(unreviewed["status"] == "blocked"
                and any(i["code"] == "SOLUTION_LIBRARY_PACKAGE_UNSUPPORTED"
                        for i in unreviewed["issues"])
                and any(i["code"] == "SOLUTION_NUNIT_PLANNING_DEFERRED"
                        for i in unreviewed["issues"])
                and all(p["candidateId"] is None for p in
                        unreviewed["projects"] if p["kind"] == "nunit"),
                "unreviewed shared packages must block before NUnit generation")

            reviewed_config = dict(config,
                TargetSolutionReviewedPackages=[{
                    "SourceProject": "Shared/Shared.csproj",
                    "Reviewed": True,
                    "Packages": [{
                        "Id": "System.Collections.Immutable",
                        "Version": "9.0.0"
                    }]
                }])
            adapter.write_text(json.dumps(reviewed_config), encoding="utf-8")
            accepted = value(call(proc, 10, "plan_target_solution", {
                "source": "source", "config": "adapter.json"}))
            shared = next(p for p in accepted["projects"]
                          if p["sourceProject"] == "Shared/Shared.csproj")
            expect(accepted["status"] == "ready_for_build"
                and shared["packageReferences"] == [{
                    "id": "System.Collections.Immutable", "version": "9.0.0"
                }]
                and accepted["planId"] != plan["planId"],
                "explicit exact source packages must be projected and hash-bound")

            put("Shared/Shared.csproj",
                package_project.replace('Version="9.0.0"',
                                        'Version="9.0.1"'))
            mismatch = value(call(proc, 11, "plan_target_solution", {
                "source": "source", "config": "adapter.json"}))
            expect(mismatch["status"] == "blocked"
                and any(i["code"] == "SOLUTION_PACKAGE_REVIEW_MISMATCH"
                        for i in mismatch["issues"]),
                "source library package version changes must invalidate approval")
            put("Shared/Shared.csproj", reviewed_source)
            adapter.write_text(json.dumps(config), encoding="utf-8")

            print("Multi-project MCP plan + Core CLI NUnit 2/2 runtime passed", flush=True)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: multi_project_solution_smoke.py <MCP.dll|exe> <AssemblyCli.dll>")
    binary = pathlib.Path(sys.argv[1]).resolve()
    cli = pathlib.Path(sys.argv[2]).resolve()
    expect(binary.exists() and cli.exists(),
        "MCP and Core AssemblyCli must both be compiled")
    exercise(binary, cli)
