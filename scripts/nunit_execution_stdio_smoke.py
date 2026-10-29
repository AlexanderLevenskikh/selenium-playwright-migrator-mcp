#!/usr/bin/env python3
"""Real MCP stdio safety regression for synthetic NUnit execution gates/cases.

Never evaluates source C# or submits customer files. All source names are fictional.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from mcp_stdio_smoke import start_reader, receive, send, call, value, expect

SAFE = """
using NUnit.Framework;
[TestFixture] public class FictionalGateFixture {
    private static readonly object[][] Rows = new object[][] {
        new object[] { 10 }, new object[] { 11 }
    };
    [Test] public void Ordinary() { Assert.That(true, Is.True); }
    [Test] [Ignore("synthetic skip reason")]
    public void Disabled() { Assert.That(false, Is.True); }
    [Test] [Explicit("synthetic opt-in reason")]
    public void OptIn() { Assert.That(true, Is.True); }
    [TestCase(1, Ignore = "case maintenance")]
    [TestCase(2, Explicit = true)]
    public void Inline(int value) { Assert.That(value > 0, Is.True); }
    [TestCaseSource(nameof(Rows))]
    public void FromStaticRows(int value) { Assert.That(value > 0, Is.True); }
}
"""
UNSAFE = """
using NUnit.Framework;
[TestFixture] public class FictionalUnsafeFixture {
    private static readonly object[][] Rows = new object[][] {
        new object[] { System.DateTime.UtcNow.Day }
    };
    [TestCaseSource(nameof(Rows))]
    public void DynamicCase(int value) { Assert.That(value > 0, Is.True); }
}
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: nunit_execution_stdio_smoke.py <MCP.dll|tool>")
    binary = str(Path(sys.argv[1]).resolve())
    expect(Path(binary).exists(), "MCP binary missing")
    with tempfile.TemporaryDirectory(prefix="fictional-nunit-mcp29-") as temp:
        workspace = Path(temp)
        safe = workspace / "SafeFixture.cs"
        unsafe = workspace / "UnsafeFixture.cs"
        safe.write_text(SAFE, encoding="utf-8")
        unsafe.write_text(UNSAFE, encoding="utf-8")
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (safe, unsafe)}
        env = dict(os.environ, MIGRATOR_WORKSPACE=str(workspace))
        command = ["dotnet", binary] if binary.endswith(".dll") else [binary]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)
        start_reader(proc)
        try:
            send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18",
                                   "capabilities": {},
                                   "clientInfo": {"name": "nunit-preview29",
                                                  "version": "0.1"}}})
            init = receive(proc, 1)
            expect("serverInfo" in init, "MCP initialization failed")
            send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            send(proc, {"jsonrpc": "2.0", "id": 2,
                        "method": "tools/list", "params": {}})
            names = {item["name"] for item in receive(proc, 2).get("tools", [])}
            expect("inspect_nunit_execution" in names, "Missing preview29 MCP tool")
            inspection = value(call(proc, 3, "inspect_nunit_execution",
                                    {"source": "."}))
            expect(inspection["schemaVersion"] == "migrator-nunit-execution/v1alpha1",
                   "Wrong NUnit execution schema")
            expect(inspection["runtimeStatus"] == "not_run"
                   and inspection["discoveryStatus"] == "static_inventory_not_nunit_discovery",
                   "Read-only scan fabricated runtime evidence")
            expect(inspection["declaredTests"] == 6
                   and inspection["parsedTests"] == 5,
                   "Static method inventory wrong")
            expect(inspection["staticallyResolvedNUnitCases"] == 7,
                   "Static cases must count method-level and parameterized rows separately")
            expect(inspection["blockedNUnitSources"] == 1,
                   "Dynamic parameter source did not stay blocked")
            files = {p["relativePath"]: p for p in inspection["files"]}
            expect(set(files) == {"SafeFixture.cs", "UnsafeFixture.cs"},
                   "Private or extra source names surfaced")
            safe_report = files["SafeFixture.cs"]
            expect(safe_report["disposition"] == "supported",
                   "Safe source was blocked")
            states = {c["runState"] for c in safe_report["cases"]}
            expect({"runnable", "explicit", "ignored"} <= states,
                   "Per-case NUnit run-state lost")
            reasons = [c["reason"] for c in safe_report["cases"]]
            expect("synthetic skip reason" in reasons
                   and "case maintenance" in reasons
                   and "synthetic opt-in reason" in reasons,
                   "NUnit skip/opt-in reason lost")
            expect(all(len(item["sourceSha256"]) == 64 and item["line"] > 0
                       for item in safe_report["attributes"]),
                   "Unhashed or unlined source evidence")
            expect(any(item["kind"] == "TestCaseSource"
                       and "TestCase(10)" in item["targetExpression"]
                       for item in safe_report["attributes"]),
                   "Static TestCaseSource lowering missing")
            blocked = files["UnsafeFixture.cs"]
            expect(blocked["disposition"] == "unsupported_nunit_execution_semantics",
                   "Environment-dependent source was executed or ignored")
            expect(any(item["code"] == "NUNIT_TEST_CASE_SOURCE_UNSAFE"
                       for item in blocked["blockers"]),
                   "Missing blocked-source diagnostic")

            analysis = value(call(proc, 4, "analyze_migration", {"source": "."}))
            preview = value(call(proc, 5, "preview_migration",
                                 {"source": ".", "expectedAnalysisId": analysis["analysisId"]}))
            expect(preview["transformationStatus"] == "partial"
                   and len(preview["files"]) == 1,
                   "Unsafe fixture was emitted as a target")
            generated = preview["files"][0]["content"]
            expect('[Ignore("synthetic skip reason")]' in generated
                   and '[Explicit("synthetic opt-in reason")]' in generated
                   and '[TestCase(10)]' in generated,
                   "Generated NUnit gates/cases disappeared")
            expect("TestCaseSource" not in generated,
                   "Static source reference survived without its declaration")
            expect("System.DateTime.UtcNow" not in generated,
                   "Dynamic or private C# source body leaked to the target")
            expect(all(hashlib.sha256(p.read_bytes()).hexdigest() == before[p.name]
                       for p in (safe, unsafe)), "Read-only MCP changed source files")
            print("MCP_NUNIT_EXECUTION_PREVIEW29_STDIO_PASSED")
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
