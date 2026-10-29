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
            expect({"analyze_migration", "preview_migration", "explain_finding", "verify_artifact", "inspect_pom_sources", "inspect_nunit_lifecycle", "review_pom_mapping"} <= names,
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

            # Generic synthetic selector extension implementations and Page Objects:
            # no private application source is copied into this protocol regression.
            evidence_root = product / "pom-evidence"
            evidence_root.mkdir()
            (evidence_root / "SelectorExtensions.cs").write_text("""
public static class SelectorExtensions {
    public static XPathBy WithTid(this ByDummy value, string tid) {
        return value.WithAttribute("data-tid", tid);
    }
    public static XPathBy WithDataTest(this ByDummy value, string tid) {
        return value.WithAttribute("data-test", tid);
    }
    public static XPathBy WithDataTestId(this ByDummy value, string tid) {
        return value.WithAttribute("data-test-id", tid);
    }
}
""", encoding="utf-8")
            (evidence_root / "TableItem.cs").write_text("""
public class TableItem {
    public ElementsCollection<Label> Items { get; }
    public TableItem(IContextBy container, ControlFactory factory) {
        Items = factory.CreateElementsCollection<Label>(container,
            x => x.WithDataTest("row").FixedByIndex());
    }
}
""", encoding="utf-8")
            (evidence_root / "CatalogPage.cs").write_text("""
public class CatalogPage {
    public TableItem Table { get; }
    public ScCombo Code { get; }
    public Button Unmapped { get; }
    public CatalogPage(IWebDriver webDriver, ControlFactory factory) {
        Table = factory.CreateControl<TableItem>(webDriver.Search(x => x.WithDataTest("table")));
        Code = factory.CreateControl<ScCombo>(webDriver.Search(
            x => x.WithDataTestId("project-code").WithTid("caption")));
        Unmapped = factory.CreateControl<Button>(webDriver.Search(
            x => x.WithUnsupported("mystery")));
    }
}
""", encoding="utf-8")
            (evidence_root / "LocalStorage.cs").write_text("""
public class LocalStorage {
    public void Clear() { RunScript("localStorage.clear();"); }
    public void SettingPeriod(string month) { SetItem("period-month", month); }
}
""", encoding="utf-8")
            evidence = value(call(proc, 26, "inspect_pom_sources",
                                  {"sourceDirectory": "pom-evidence", "pageTypes": ["CatalogPage"],
                                   "pageVariable": "page"}))
            expect(evidence["schemaVersion"] == "migrator-pom-evidence/v1alpha2",
                   "Inspector contract mismatch")
            expect(evidence["inspectedFiles"] == 4 and len(evidence["sourceTreeHash"]) == 64,
                   "Inspector did not bind evidence to four source files")
            by_member = {entry["sourceMemberPath"]: entry for entry in evidence["locators"]}
            expect(len(by_member["page.Code"]["predicates"]) == 2,
                   "Compound selector attributes not preserved")
            expect(len(by_member["page.Table.Items"]["predicates"]) == 2,
                   "Nested table collection evidence missing")
            expect(by_member["page.Unmapped"]["proposedPlaywrightExpression"] is None,
                   "Unknown selector helper must never produce a target mapping")
            expect(all(e["proposalStatus"] == "requires_review" for e in evidence["locators"]
                       if e["proposedPlaywrightExpression"] is not None),
                   "A locator was automatically marked safe without DOM review")
            expect(any(h["sourceType"] == "LocalStorage" and "period-month" in h["literalStorageKeys"]
                       for h in evidence["helpers"]), "Storage source method evidence missing")
            alias_evidence = value(call(proc, 27, "inspect_pom_sources",
                                        {"sourceDirectory": "pom-evidence", "pageTypes": ["CatalogPage"],
                                         "pageVariable": "otherPage"}))
            expect(any(e["sourceMemberPath"] == "otherPage.Table.Items"
                       for e in alias_evidence["locators"]), "Caller alias was not respected")
            outside_evidence = call(proc, 28, "inspect_pom_sources",
                                    {"sourceDirectory": "../"})
            expect(outside_evidence.get("isError"), "Inspector escaped the workspace")


            # Source-method lineage: a single-looking Page Object call may
            # include several operations, hidden private helpers, retry loops,
            # and storage mutations before navigation. Synthetic source only.
            (evidence_root / "ControlMethods.cs").write_text("""
public class ScCombobox {
    public void InputAndSelect(string value) {
        Click();
        accept.Visible().Wait().EqualTo(true);
        input.ClearAndInputText(value);
        items.Wait().Single(x => x.Text, Contains.Substring(value)).Click();
        accept.Click();
    }
}
public class Loader {
    public void ValidateLoading() {
        var retry = 0;
        while (retry < 2) try {
            if (error.Displayed().Get()) Reload();
            loading.Visible.Wait().EqualTo(false);
            break;
        } catch (WebDriverTimeoutException) {
            retry++;
            if (retry >= 2) Assert.Fail("not ready");
        }
    }
}
public class DatePicker {
    public void SetBeginDate(string value) {
        Click();
        input.SendKeys(value);
        Blur();
    }
    private void Blur() { input.ExecuteJs("x.blur();"); }
}
""", encoding="utf-8")
            (evidence_root / "StorageTests.cs").write_text("""
using NUnit.Framework;
[TestFixture] public class StorageTests {
    [SetUp] public void Prepare() { LocalStorage.Clear(); }
    [Test] public void PreAndPostNavigation() {
        LocalStorage.SettingPeriod("1");
        var page = Navigation.OpenCatalogPage();
        LocalStorage.RemoveItem("period-month");
    }
}
""", encoding="utf-8")
            lineage = value(call(proc, 31, "inspect_pom_sources",
                                 {"sourceDirectory": "pom-evidence",
                                  "pageTypes": ["ScCombobox", "Loader", "DatePicker"]}))
            expect(lineage["schemaVersion"] == "migrator-pom-evidence/v1alpha2"
                   and lineage["inspectedFiles"] == 6, "POM lineage contract/source snapshot")
            helpers = {(h["sourceType"], h["method"]): h for h in lineage["helpers"]}
            combo = helpers[("ScCombobox", "InputAndSelect")]
            expect(len(combo["orderedCalls"]) >= 5
                   and any("ClearAndInputText" in item["sourceText"]
                           for item in combo["orderedCalls"]), "Lost multi-step combobox actions")
            loader = helpers[("Loader", "ValidateLoading")]
            kinds = {item["kind"] for item in loader["controlFlow"]}
            expect({"while", "try", "catch"} <= kinds
                   and "loop_or_retry" in loader["reviewFlags"], "Loader retry semantics were dropped")
            picker = helpers[("DatePicker", "SetBeginDate")]
            expect(any(c["method"] == "Blur" for c in picker["orderedCalls"]),
                   "Reachable private helper reference missing")
            expect(helpers[("DatePicker", "Blur")]["isReachablePrivateHelper"],
                   "Private helper implementation not discovered")
            expect("javascript_source_execution" in helpers[("DatePicker", "Blur")]["reviewFlags"],
                   "Private ExecuteJs must be recognized as script execution requiring review")
            flows = {x["method"]: x for x in lineage["storageAndNavigationFlows"]}
            expect(flows["Prepare"]["storageOperations"][0]["relativeToNavigation"]
                   == "setup_before_test", "NUnit storage setup timing was lost")
            op = flows["PreAndPostNavigation"]["storageOperations"]
            expect([x["relativeToNavigation"] for x in op]
                   == ["before_first_navigation", "after_first_navigation"],
                   "Storage calls before/after navigation were collapsed")
            (evidence_root / "ControlMethods.cs").write_text(
                (evidence_root / "ControlMethods.cs").read_text(encoding="utf-8") + "\n// source changed",
                encoding="utf-8")
            changed_lineage = value(call(proc, 32, "inspect_pom_sources",
                                         {"sourceDirectory": "pom-evidence",
                                          "pageTypes": ["ScCombobox"]}))
            expect(changed_lineage["sourceTreeHash"] != lineage["sourceTreeHash"],
                   "Method evidence was reused after source bytes changed")

            # A table-row Click changes application state. A passive locator
            # declaration must not be accepted as equivalent. Unsupported
            # assertion tails must become visible TODOs, not pass silently.
            row_dir = product / "table-action-evidence"
            row_dir.mkdir()
            (row_dir / "TableFixture.cs").write_text("""
using NUnit.Framework;
[TestFixture] public class TableFixture {
    [Test] public void MustPreserveClick() {
        var page = Navigation.OpenCatalogPage();
        page.Table.Items.ElementAt(0).Click();
        page.Table.Items.ElementAt(3).Should().NotBe("row");
    }
}
""", encoding="utf-8")
            row_config = product / "table-action-config.json"
            row_config.write_text(json.dumps({
                "SourceProjectName": "Synthetic",
                "Methods": [{
                    "SourceMethod": "Navigation.OpenCatalogPage()",
                    "TargetStatements": [
                        'await Page.GotoAsync("https://example.invalid/table");',
                        "var {result} = Page;"
                    ],
                    "RequiresReview": True
                }],
                "UiTargets": [{
                    "SourceExpression": "page.Table.Items",
                    "TargetExpression": 'Page.Locator("[data-test=\\\"row\\\"]")',
                    "TargetKind": "RawExpression"
                }]
            }), encoding="utf-8")
            pilot_analysis = value(call(proc, 29, "analyze_migration",
                                        {"source": "table-action-evidence/TableFixture.cs",
                                         "config": "table-action-config.json"}))
            pilot = value(call(proc, 30, "preview_migration",
                               {"source": "table-action-evidence/TableFixture.cs",
                                "config": "table-action-config.json",
                                "expectedAnalysisId": pilot_analysis["analysisId"]}))
            rendered = pilot["files"][0]["content"]
            expect(".Nth(0).ClickAsync();" in rendered,
                   "A real table row click was lost during rendering")
            expect("[MIGRATOR:TABLE_ROW_OPERATION_REQUIRES_MAPPING]" in rendered,
                   "Unsupported row assertion was silently replaced by a locator")
            expect(pilot["files"][0]["fullyConvertedTests"] == 0,
                   "Lost assertion was counted as fully converted")
            # NUnit execution gates are a source execution contract. An
            # ignored/explicit fixture must not become an executable target.
            gated_dir = product / "nunit-gates-evidence"
            gated_dir.mkdir()
            gated_fixture = gated_dir / "FictionalCase.cs"
            gated_fixture.write_text("""
using NUnit.Framework;
[Ignore("disabled by design")]
[TestFixture] public class FictionalCase {
    [Test] public void Example() {}
}
""", encoding="utf-8")
            ignored = value(call(proc, 81, "analyze_migration",
                {"source": "nunit-gates-evidence/FictionalCase.cs"}))
            expect(ignored["discoveryStatus"] == "partial"
                and ignored["declaredTests"] == 1
                and ignored["parsedTests"] == 0
                and any(f["code"] == "NUNIT_EXECUTION_GATE_REQUIRES_REVIEW"
                        and f["line"] > 0 for f in ignored["findings"]),
                "NUnit Ignore must be counted but blocked with source evidence")
            ignored_preview = value(call(proc, 82, "preview_migration", {
                "source": "nunit-gates-evidence/FictionalCase.cs",
                "expectedAnalysisId": ignored["analysisId"]}))
            expect(ignored_preview["transformationStatus"] == "blocked"
                and len(ignored_preview["files"]) == 0,
                "Ignored fixture must never turn into a runnable Playwright test")

            gated_fixture.write_text("""
using NUnit.Framework;
[TestFixture] public class FictionalCase {
    [TestCase(42, Explicit = true)]
    public void Example(int value) {}
}
""", encoding="utf-8")
            explicit = value(call(proc, 83, "analyze_migration",
                {"source": "nunit-gates-evidence/FictionalCase.cs"}))
            expect(explicit["discoveryStatus"] == "partial"
                and explicit["declaredTests"] == 1
                and any(f["code"] == "NUNIT_EXECUTION_GATE_REQUIRES_REVIEW"
                        for f in explicit["findings"]),
                "Explicit case metadata must not be silently dropped")
            explicit_preview = value(call(proc, 84, "preview_migration", {
                "source": "nunit-gates-evidence/FictionalCase.cs",
                "expectedAnalysisId": explicit["analysisId"]}))
            expect(explicit_preview["transformationStatus"] == "blocked"
                and len(explicit_preview["files"]) == 0,
                "Explicit case must not become an unconditional test")

            # Read-only lifecycle source inspection follows same-type private
            # listeners and preserves evidence of inherited teardown, browser
            # resource ownership and an invalid nested SetUpFixture.
            lifecycle_dir = product / "lifecycle-source-evidence"
            lifecycle_dir.mkdir()
            (lifecycle_dir / "BaseFixture.cs").write_text("""
using NUnit.Framework;
namespace Fictional.Integration;
public abstract class BaseFixture {
    protected IWebDriver WebDriver =>
        DiContainer.GetScopedRequiredService<IPooledWebDriver>().WrappedDriver;
    protected Navigation Navigation =>
        DiContainer.GetScopedRequiredService<Navigation>();
    protected LocalStorage LocalStorage =>
        DiContainer.GetScopedRequiredService<LocalStorage>();
    [OneTimeSetUp] public void Start() { InstallListener(); }
    [TearDown] public void CleanupTest() {
        TestContext.CurrentContext.WriteBrowserLogs(WebDriver);
        Screenshoter.CreateAndSaveScreenshot();
    }
    [OneTimeTearDown] public void End() { DiContainer.DisposeScope(); }
    private void InstallListener() {
        var listener = new RetryTestListener();
        TestExecutionContext.CurrentContext.GetType().GetProperties();
    }
    [SetUpFixture] public class InvalidNestedCleanup {
        [OneTimeTearDown] public void End() {
            DiContainer.FullDispose();
        }
    }
}
""", encoding="utf-8")
            (lifecycle_dir / "Tests.cs").write_text("""
using NUnit.Framework;
namespace Fictional.Integration;
[TestFixture] public class Tests : BaseFixture {
    [Test] public void CanRun() {}
}
""", encoding="utf-8")
            evidence = value(call(proc, 85, "inspect_nunit_lifecycle",
                {"sourceDirectory": "lifecycle-source-evidence"}))
            expect(evidence["schemaVersion"] ==
                       "migrator-nunit-lifecycle-source/v1alpha1"
                and evidence["status"] == "blocked"
                and evidence["declaredTestMethods"] == 1
                and evidence["inspectedFiles"] == 2
                and len(evidence["sourceTreeHash"]) == 64
                and len(evidence["hooks"]) == 4,
                "real MCP must expose complete source-bound lifecycle ledger")
            kinds = {item["kind"] for item in evidence["effects"]}
            expect({"di_scoped_service", "di_scope_dispose",
                    "di_global_dispose", "browser_logs", "browser_screenshot",
                    "nunit_listener_reflection", "browser_driver_scope",
                    "browser_navigation_scope", "browser_storage_scope"} <= kinds,
                "lifecycle inspector must retain DI/browser/listener/cleanup obligations")
            expect(any(item["kind"] == "nunit_listener_reflection"
                       and item["reachedThrough"] == "InstallListener"
                       for item in evidence["effects"]),
                "bounded same-class private listener helper must be reachable")
            expect(any(item["code"] ==
                       "NUNIT_NESTED_SETUPFIXTURE_REQUIRES_REVIEW"
                       for item in evidence["issues"])
                and evidence["setUpFixtures"][0]["cleanupOnly"] is True
                and evidence["build"] == "not_run"
                and evidence["nUnitRuntime"] == "not_run"
                and evidence["browserObservables"] == "not_run",
                "nested cleanup scope must fail closed without invented execution")
            expect(all(len(hook["methodSha256"]) == 64
                       and hook["sourceLine"] > 0 for hook in evidence["hooks"]),
                "all lifecycle hooks must carry source hash and line evidence")
            expect("GetScopedRequiredService<" not in json.dumps(evidence)
                and "CreateAndSaveScreenshot();" not in json.dumps(evidence),
                "tool may not expose raw private C# source bodies")
            with (lifecycle_dir / "BaseFixture.cs").open("a", encoding="utf-8") as file:
                file.write("\n// source changed\n")
            changed = value(call(proc, 86, "inspect_nunit_lifecycle",
                {"sourceDirectory": "lifecycle-source-evidence"}))
            expect(changed["sourceTreeHash"] != evidence["sourceTreeHash"],
                "lifecycle evidence source fingerprint must expire on edits")

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
