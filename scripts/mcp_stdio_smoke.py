#!/usr/bin/env python3
"""Exercise actual MCP stdio JSON-RPC, not only compilation.
Requires a compiled Migrator.Mcp.dll OR an installed dotnet-tool executable, and Python 3 on Linux.
"""
import json
import os
import pathlib
import queue
import threading
import subprocess
import sys
import tempfile
import time


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def start_reader(proc):
    """Portable stdout pump: Windows select() does not support pipe handles."""
    proc.rpc_lines = queue.Queue()

    def pump():
        for line in proc.stdout:
            proc.rpc_lines.put(line)
        proc.rpc_lines.put(None)

    threading.Thread(target=pump, daemon=True, name="mcp-stdout-reader").start()


def receive(proc, message_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            line = proc.rpc_lines.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            break
        if line is None:
            raise AssertionError("MCP process terminated before response (exit=%s)" % proc.poll())
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as ex:
            raise AssertionError("Non-JSON output on MCP stdout: " + repr(line[:500])) from ex
        if payload.get("id") == message_id:
            expect("error" not in payload, f"JSON-RPC error for {message_id}: {payload}")
            return payload["result"]
    raise TimeoutError(f"Timed out waiting for MCP response {message_id}")

def send(proc, payload):
    proc.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
    proc.stdin.flush()


def call(proc, message_id, name, arguments):
    send(proc, {"jsonrpc": "2.0", "id": message_id, "method": "tools/call",
                "params": {"name": name, "arguments": arguments}})
    return receive(proc, message_id)


def value(result):
    expect(not result.get("isError", False), f"Tool error: {result}")
    content = result.get("content", [])
    expect(content and content[0]["type"] == "text", f"Text result missing: {result}")
    return json.loads(content[0]["text"])


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: mcp_stdio_smoke.py <compiled Migrator.Mcp.dll|installed tool>")
    dll = str(pathlib.Path(sys.argv[1]).resolve())
    expect(pathlib.Path(dll).exists(), "MCP dll does not exist: " + dll)
    with tempfile.TemporaryDirectory(prefix="mcp-stdio-smoke-") as root:
        product = pathlib.Path(root, "product")
        product.mkdir()
        sample = product / "Tests.cs"
        sample.write_text("""
using NUnit.Framework;
[TestFixture] public class AccountTests
{
    [Test] public void OpensPage() {}
}
""", encoding="utf-8")
        env = dict(os.environ, MIGRATOR_WORKSPACE=str(product))
        command = ["dotnet", dll] if dll.endswith(".dll") else [dll]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "migrator-smoke", "version": "0.1"}}})
            init = receive(proc, 1)
            expect("serverInfo" in init, f"Initialize missing serverInfo: {init}")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            listing = receive(proc, 2)
            names = {tool["name"] for tool in listing.get("tools", [])}
            expect({"analyze_migration", "preview_migration", "explain_finding", "verify_artifact"} <= names,
                   f"Missing MCP tools: {names}")
            report = value(call(proc, 3, "analyze_migration", {"source": "."}))
            expect(report["discoveryStatus"] == "complete", f"Incorrect discovery: {report}")
            expect(report["declaredTests"] == 1 and report["parsedTests"] == 1,
                   f"Incorrect test count: {report}")
            expected_id = report["analysisId"]
            preview = value(call(proc, 4, "preview_migration",
                                 {"source": ".", "expectedAnalysisId": expected_id}))
            expect(len(preview["files"]) == 1, f"Missing generated file: {preview}")
            expect(len(preview["targetTreeHash"]) == 64, "Target hash missing")
            expect(preview["analysisId"] == expected_id, "Preview analysis mismatch")

            # Generated candidate: syntax-only does not secretly claim compile/runtime.
            generated = value(call(proc, 10, "verify_artifact",
                                   {"source": ".", "expectedAnalysisId": expected_id,
                                    "candidateId": preview["candidateId"]}))
            expect(generated["candidate"]["candidateId"] == preview["candidateId"],
                   "Generated candidate must retain parent ID")
            expect(generated["candidate"]["targetTreeHash"] == preview["targetTreeHash"],
                   "Generated candidate target hash differs")
            expect(generated["candidate"]["origin"] == "generated", "Wrong generated origin")
            expect(generated["compile"]["status"] == "not_run", "Compile status was invented")
            expect(generated["runtime"]["status"] == "not_run"
                   and generated["observables"]["status"] == "not_run",
                   "Runtime/observable evidence was invented")

            # Single-file source scope permits an edited target directory next to source,
            # without changing the source snapshot on target edits.
            single = value(call(proc, 11, "analyze_migration", {"source": "Tests.cs"}))
            one = value(call(proc, 12, "preview_migration",
                             {"source": "Tests.cs", "expectedAnalysisId": single["analysisId"]}))
            target_root = product / "agent-target"
            target_root.mkdir()
            target_file = target_root / one["files"][0]["relativePath"]
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text("public sealed class Edited { public int Value => 123; }",
                                   encoding="utf-8")
            options = {"source": "Tests.cs", "expectedAnalysisId": single["analysisId"],
                       "candidateId": one["candidateId"], "targetRoot": "agent-target",
                       "runCompile": True, "referenceDlls": []}
            edited = value(call(proc, 13, "verify_artifact", options))
            expect(edited["candidate"]["origin"] == "agent-edited", "Edited origin was lost")
            expect(edited["candidate"]["parentCandidateId"] == one["candidateId"],
                   "Edited candidate lost its parent")
            expect(edited["candidate"]["candidateId"] != one["candidateId"],
                   "Edited code reused generated candidate identity")
            expect(edited["syntax"]["status"] == "passed", "Simple edited C# syntax did not pass")
            expect(edited["compile"]["status"] == "passed", "Self-contained candidate did not compile")
            expect(edited["runtime"]["status"] == "not_run", "Compile incorrectly marked runtime passed")

            target_file.write_text("public sealed class Edited { public int Value => UnknownName; }",
                                   encoding="utf-8")
            compile_error = value(call(proc, 14, "verify_artifact", options))
            expect(compile_error["syntax"]["status"] == "passed"
                   and compile_error["compile"]["status"] == "failed",
                   "A compiler error was mistaken for syntax or success")
            expect(compile_error["candidate"]["candidateId"] != edited["candidate"]["candidateId"],
                   "Old successful candidate reused after semantic error")

            target_file.write_text("public sealed class Broken {", encoding="utf-8")
            syntax_error = value(call(proc, 15, "verify_artifact", options))
            expect(syntax_error["syntax"]["status"] == "failed"
                   and syntax_error["compile"]["status"] == "blocked",
                   "Invalid syntax did not block compilation")

            target_file.write_text("public sealed class Edited {}", encoding="utf-8")
            no_profile = dict(options)
            del no_profile["referenceDlls"]
            blocked = value(call(proc, 16, "verify_artifact", no_profile))
            expect(blocked["compile"]["status"] == "blocked",
                   "Missing reference context must not become compile success")

            wrong_parent = dict(options)
            wrong_parent["candidateId"] = "wrong-parent"
            invalid = call(proc, 17, "verify_artifact", wrong_parent)
            expect(invalid.get("isError"), "Unknown parent candidate was accepted")

            extra_file = target_root / "Extra.cs"
            extra_file.write_text("public class Extra {}", encoding="utf-8")
            extra = call(proc, 18, "verify_artifact", options)
            expect(extra.get("isError"), "Unexpected C# target file was accepted")
            extra_file.unlink()
            import shutil
            shutil.rmtree(target_root)

            outside = call(proc, 5, "analyze_migration", {"source": "../"})
            expect(outside.get("isError"), "Parent directory traversal was accepted")
            absolute = call(proc, 6, "analyze_migration", {"source": str(product)})
            expect(absolute.get("isError"), "Absolute source path was accepted")
            sample.write_text(sample.read_text(encoding="utf-8") + "\n// changed\n",
                              encoding="utf-8")
            stale = call(proc, 7, "preview_migration",
                         {"source": ".", "expectedAnalysisId": expected_id})
            expect(stale.get("isError"), "Stale analysis ID was accepted")
            sample.unlink()
            sample.write_text("""
using NUnit.Framework;
[TestFixture] public class First { [Test] public void A() {} }
[TestFixture] public class Second { [Test] public void B() {} }
""", encoding="utf-8")
            multiple = value(call(proc, 8, "analyze_migration", {"source": "."}))
            expect(multiple["discoveryStatus"] == "partial"
                   and multiple["declaredTests"] == 2, "Multi-fixture source was hidden")
            finding_id = multiple["findings"][0]["id"]
            explanation = value(call(proc, 9, "explain_finding",
                                     {"source": ".", "findingId": finding_id,
                                      "expectedAnalysisId": multiple["analysisId"]}))
            expect(explanation["code"] == "MULTIPLE_FIXTURES", "Wrong finding explanation")
            expect("Split fixtures" in explanation["suggestedNextAction"],
                   "Explanation lacks a grounded next action")

            # The source root was checked, but a nested symlink could still
            # leak an outside file through recursive inventory without preflight.
            outside_source = pathlib.Path(root) / "private.cs"
            outside_source.write_text("public class Private {}", encoding="utf-8")
            source_link = product / "shortcut.cs"
            source_link.symlink_to(outside_source)
            escaped = call(proc, 19, "analyze_migration", {"source": "."})
            expect(escaped.get("isError"), "Recursive source inventory followed an external symlink")
            source_link.unlink()
            source_dir = pathlib.Path(root) / "private-directory"
            source_dir.mkdir()
            (source_dir / "private.cs").write_text("public class Private {}", encoding="utf-8")
            dir_link = product / "linked-directory"
            dir_link.symlink_to(source_dir, target_is_directory=True)
            escaped_dir = call(proc, 20, "analyze_migration", {"source": "."})
            expect(escaped_dir.get("isError"), "Recursive source inventory followed a symlink directory")
            dir_link.unlink()

            # Synthetic already-Playwright NUnit source. This is intentionally
            # generic: no external/private project code is copied into CI.
            already = product / "existing-target"
            already.mkdir()
            (already / "Existing.Tests.csproj").write_text("""
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Playwright.NUnit" Version="1.55.0" />
  </ItemGroup>
</Project>
""", encoding="utf-8")
            (already / "ExistingTests.cs").write_text("""
using NUnit.Framework;
[TestFixture] public class ExistingTests : ExistingPageBase {
    [Test] public async System.Threading.Tasks.Task ShouldBeAlreadyPlaywright() {
        await Expect(Page.GetByTestId("example")).ToHaveTextAsync("example");
    }
}
""", encoding="utf-8")
            known = value(call(proc, 21, "analyze_migration", {"source": "existing-target"}))
            expect(known["discoveryStatus"] == "partial" and known["declaredTests"] == 1,
                   "Already-Playwright NUnit input must be counted but blocked")
            expect(known["files"][0]["disposition"] == "already_playwright",
                   "Already-Playwright source was mistaken for Selenium")
            expect(any(f["code"] == "ALREADY_PLAYWRIGHT_SOURCE" for f in known["findings"]),
                   "Playwright source blocker evidence missing")
            rejected = value(call(proc, 22, "preview_migration",
                                  {"source": "existing-target",
                                   "expectedAnalysisId": known["analysisId"]}))
            expect(rejected["transformationStatus"] == "blocked" and not rejected["files"],
                   "Already-Playwright code was destructively regenerated")

            # Synthetic proprietary-style navigation and storage calls.
            # Keep this sample generic; no customer code enters public CI.
            source = product / "navigation-sample"
            source.mkdir()
            (source / "TestFixture.cs").write_text("""
using NUnit.Framework;
[TestFixture] public class SyntheticFixture {
    [SetUp] public void SetUp() { LocalStorage.Clear(); }
    [Test] public void VerifyBusinessNavigation() {
        var targetPage = Navigation.OpenDashboardPage();
        targetPage.Save.Click();
    }
    [Test] public void VerifyStorage() {
        LocalStorage.SetItem("key", "value");
    }
}
""", encoding="utf-8")
            discovered = value(call(proc, 23, "analyze_migration", {"source": "navigation-sample"}))
            expect(discovered["discoveryStatus"] == "complete"
                   and discovered["declaredTests"] == 2, "Synthetic Selenium input not discovered")
            candidate = value(call(proc, 24, "preview_migration",
                                  {"source": "navigation-sample",
                                   "expectedAnalysisId": discovered["analysisId"]}))
            expect(candidate["transformationStatus"] == "partial" and len(candidate["files"]) == 1,
                   "Unmapped business calls must not be full migration")
            expect(candidate["files"][0]["fullyConvertedTests"] == 0,
                   "Renderer TODO debt must prevent inflated fully converted metric")
            codes = {x["code"] for x in candidate["findings"]}
            expect({"POM_NAVIGATION_REQUIRES_MAPPING", "LOCAL_STORAGE_REQUIRES_MAPPING"} <= codes,
                   "Actionable navigation and LocalStorage findings missing")
            src_code = candidate["files"][0]["content"]
            expect("MIGRATOR:POM_NAVIGATION_REQUIRES_MAPPING" in src_code
                   and "MIGRATOR:LOCAL_STORAGE_REQUIRES_MAPPING" in src_code,
                   "Source helper debt markers missing from rendered output")
            conf = product / "navigation-mapping.json"
            conf.write_text(json.dumps({
                "SourceProjectName": "Synthetic",
                "Methods": [{
                    "SourceMethod": "Navigation.OpenDashboardPage()",
                    "TargetStatements": ['await Page.GotoAsync("https://example.invalid/dashboard");'],
                    "RequiresReview": True
                }]
            }), encoding="utf-8")
            mapped = value(call(proc, 25, "preview_migration",
                                {"source": "navigation-sample",
                                 "config": "navigation-mapping.json"}))
            expect('await Page.GotoAsync("https://example.invalid/dashboard");'
                   in mapped["files"][0]["content"],
                   "Explicit source-backed URL mapping did not reach renderer")
            expect(mapped["files"][0]["fullyConvertedTests"] == 0,
                   "A mapped URL alone cannot prove Page Object, storage and assertions migrated")
            print("MCP stdio integration smoke passed", flush=True)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)


if __name__ == "__main__":
    main()
