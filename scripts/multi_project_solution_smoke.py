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
        put("TestsOne/Scheduling.cs", """
using NUnit.Framework;
[assembly: Parallelizable(ParallelScope.Fixtures)]
[assembly: LevelOfParallelism(2)]
""")
        put("TestsTwo/Scheduling.cs", """
[assembly: NUnit.Framework.Parallelizable(NUnit.Framework.ParallelScope.Fixtures)]
[assembly: NUnit.Framework.LevelOfParallelism(4)]
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
                     "NUnit.Framework.Assert.That(Synthetic.Shared.Tracker.Count, NUnit.Framework.Is.EqualTo(1));",
                     "NUnit.Framework.Assert.That(System.Reflection.Assembly.GetExecutingAssembly().GetCustomAttributes(typeof(NUnit.Framework.ParallelizableAttribute), false).Length, NUnit.Framework.Is.EqualTo(1));",
                     "NUnit.Framework.Assert.That(System.Reflection.Assembly.GetExecutingAssembly().GetCustomAttributes(typeof(NUnit.Framework.LevelOfParallelismAttribute), false).Length, NUnit.Framework.Is.EqualTo(1));"
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
            expect(plan["schemaVersion"] == "migrator-target-solution/v1alpha5",
                "new solution schema must attest assembly policy source provenance")
            scheduling = plan["assemblyScheduling"]
            expect(len(scheduling) == 4
                and sum(a["sourceProject"] == "TestsOne/TestsOne.csproj"
                        for a in scheduling) == 2
                and sum(a["sourceProject"] == "TestsTwo/TestsTwo.csproj"
                        for a in scheduling) == 2
                and all(a["sourceLine"] > 0
                        and a["sourceExpression"]
                        and a["targetExpression"] for a in scheduling)
                and any(a["targetExpression"].endswith(
                    "LevelOfParallelism(2)") for a in scheduling)
                and any(a["targetExpression"].endswith(
                    "LevelOfParallelism(4)") for a in scheduling),
                "per-assembly scheduling provenance must be preserved")
            expect(sum(f["relativePath"].endswith(
                    "Migrator.Generated.NUnitAssemblyScheduling.cs")
                    for f in plan["files"]) == 2,
                "each NUnit target must contain its own assembly policy file")
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

            # Scope a large source tree to exactly one NUnit entry project
            # and its reachable shared library. The second test assembly and
            # its global SetUpFixture are not part of the target solution.
            scoped_config = workspace / "scoped.json"
            scoped_config.write_text(json.dumps(dict(config,
                TargetSolutionEntryProjects=["TestsOne/TestsOne.csproj"])),
                encoding="utf-8")
            selected = value(call(proc, 40, "plan_target_solution", {
                "source": "source", "config": "scoped.json"}))
            scope = selected["scope"]
            expect(selected["status"] == "ready_for_build"
                and selected["schemaVersion"] == "migrator-target-solution/v1alpha5"
                and scope["explicit"] is True
                and scope["entryProjects"] == ["TestsOne/TestsOne.csproj"]
                and set(scope["includedProjects"]) == {
                    "TestsOne/TestsOne.csproj", "Shared/Shared.csproj"
                }
                and scope["excludedProjects"] == ["TestsTwo/TestsTwo.csproj"]
                and len(selected["assemblyScheduling"]) == 2
                and all(a["sourceProject"] == "TestsOne/TestsOne.csproj"
                        for a in selected["assemblyScheduling"])
                and selected["sourceTreeHash"] == plan["sourceTreeHash"]
                and selected["planId"] != plan["planId"]
                and len(selected["projects"]) == 2
                and sum(p["declaredTests"] for p in selected["projects"]) == 1
                and all(not f["relativePath"].startswith("TestsTwo/")
                        for f in selected["files"]),
                "MCP scope must report excluded NUnit project and retain exact references")

            # Only the separate, trusted CLI writes files and executes real
            # dotnet build + NUnit. Read-only MCP must not acquire these claims.
            scoped_cli = subprocess.run([
                "dotnet", str(cli), "solution-generate",
                str(source), str(workspace / "generated-scoped"),
                "--config", str(scoped_config), "--build", "--test"
            ], text=True, capture_output=True, timeout=290)
            expect(scoped_cli.returncode == 0,
                "Scoped Core CLI runtime failed: "
                + scoped_cli.stdout[-2500:] + scoped_cli.stderr[-2500:])
            scoped_run = json.loads(scoped_cli.stdout)
            expect(scoped_run["build"]["status"] == "passed"
                and scoped_run["nUnitRuntime"]["status"] == "passed"
                and scoped_run["nUnitRuntime"]["executedTests"] == 1
                and scoped_run["nUnitRuntime"]["passedTests"] == 1
                and len(scoped_run["projectExecutions"]) == 1,
                "scoped solution must run one NUnit test assembly 1/1, not 2/2")
            scoped_verify = value(call(proc, 41, "verify_target_solution", {
                "source": "source", "targetRoot": "generated-scoped",
                "expectedSourceTreeHash": selected["sourceTreeHash"],
                "expectedPlanId": selected["planId"], "config": "scoped.json"}))
            expect(scoped_verify["completeness"]["status"] == "passed"
                and scoped_verify["build"]["status"] == "not_run"
                and scoped_verify["nUnitRuntime"]["status"] == "not_run",
                "scoped MCP verification is read-only and cannot inherit CLI execution")

            # An explicitly omitted NUnit test assembly becomes reachable if
            # a selected source project references it. The planner must
            # re-include it and reject test-to-test ProjectReference.
            put("TestsOne/TestsOne.csproj", project_template.replace(
                "</ItemGroup>",
                '<ProjectReference Include="../TestsTwo/TestsTwo.csproj" />'
                '</ItemGroup>'))
            contaminated = value(call(proc, 42, "plan_target_solution", {
                "source": "source", "config": "scoped.json"}))
            expect(contaminated["status"] == "blocked"
                and len(contaminated["scope"]["includedProjects"]) == 3
                and contaminated["scope"]["excludedProjects"] == []
                and any(i["code"] == "SOLUTION_REFERENCE_TO_TEST_ASSEMBLY"
                        for i in contaminated["issues"]),
                "selected project scope must never drop a reachable test reference")
            put("TestsOne/TestsOne.csproj", project_template)

            scoped_config.write_text(json.dumps(dict(config,
                TargetSolutionEntryProjects=["../outside/Other.csproj"])),
                encoding="utf-8")
            invalid_scope = value(call(proc, 43, "plan_target_solution", {
                "source": "source", "config": "scoped.json"}))
            expect(invalid_scope["status"] == "blocked"
                and any(i["code"] == "SOLUTION_SCOPE_CONFIG_INVALID"
                        for i in invalid_scope["issues"]),
                "invalid project-entry paths cannot fall back to all projects")

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
                and sum(p["declaredTests"] for p in unreviewed["projects"]
                        if p["kind"] == "nunit") == 2
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

            # Preflight must preserve source test inventory in a blocked
            # assembly, and reject nested suite ownership before target output.
            put("TestsOne/NestedScope.cs", """
using NUnit.Framework;
public class Container {
    [SetUpFixture] public class Nested {
        [OneTimeTearDown] public void Cleanup() {}
    }
}
[TestFixture] public class AnotherFixture {
    [Test] public void Extra() {}
}
""")
            nested = value(call(proc, 12, "plan_target_solution", {
                "source": "source", "config": "adapter.json"}))
            tests_one = next(p for p in nested["projects"]
                             if p["sourceProject"] == "TestsOne/TestsOne.csproj")
            expect(nested["status"] == "blocked"
                and nested["schemaVersion"] == "migrator-target-solution/v1alpha5"
                and tests_one["declaredTests"] == 2
                and tests_one["candidateId"] is None
                and any(i["code"] == "SOLUTION_NESTED_SETUPFIXTURE_UNSUPPORTED"
                        for i in nested["issues"]),
                "blocked NUnit scope must preserve source test count, not invent target")
            (source / "TestsOne/NestedScope.cs").unlink()

            put("TestsOne/AssemblyPolicy.cs", """
using NUnit.Framework;
[assembly: Parallelizable(ParallelScope.Fixtures)]
""")
            parallel = value(call(proc, 13, "plan_target_solution", {
                "source": "source", "config": "adapter.json"}))
            expect(parallel["status"] == "blocked"
                and any(i["code"] == "SOLUTION_ASSEMBLY_SCHEDULING_REQUIRES_REVIEW"
                        for i in parallel["issues"]),
                "source NUnit assembly parallelism cannot be omitted silently")
            (source / "TestsOne/AssemblyPolicy.cs").unlink()

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
