#!/usr/bin/env python3
"""Check genuine synthetic Chromium evidence from the pinned Core CI executable.

This file never reads customer source or claims customer browser equivalence.
The producing test starts a real Chromium against a loopback HTTP application.
"""
import json
import pathlib
import sys

def require(condition, reason):
    if not condition:
        raise AssertionError("REAL_CHROMIUM_MCP_EVIDENCE: " + reason)

def main(path: pathlib.Path):
    report = json.loads(path.read_text(encoding="utf-8"))
    require(report.get("schema") == "migrator-real-chromium-smoke/v1",
            "versioned runtime observation missing")
    require(report.get("chromium") == "real_installed_playwright_chromium"
            and report.get("targetMode") == "real_IBrowser_localhost"
            and report.get("application") == "synthetic_loopback_http_only",
            "expected actual Chromium against a localhost web server, not fake IBrowser")
    require(report.get("customerE2E") == "not_run"
            and report.get("behavioralEquivalence") == "not_verified",
            "synthetic checks must not claim private application behavior")
    require(report.get("coreReviewStatus") == "requires_review",
            "runtime smoke must not automatically approve source review")
    entries = report.get("results", [])
    require(len(entries) == 3
            and {r.get("scenario") for r in entries} == {
                "success", "retry-once", "final-failure"},
            "need all positive, retry and real-browser negative scenarios")
    for item in entries:
        require(item.get("chromiumReal") is True
                and item.get("sourceBound") is True
                and item.get("browserE2E") == "synthetic_localhost_passed",
                "synthetic localhost acceptance never uses recorded fake browser")
        require(item.get("executedTests") == 2
                and item.get("observedContextOpen") == 2
                and item.get("observedContextClosed") == 2
                and item.get("scopeDisposals") == 2
                and item.get("browserClose") == 1,
                "each fixture must close its own Playwright context before shared browser")
    by_name = {r["scenario"]: r for r in entries}
    require(by_name["success"]["passedTests"] == 2
            and by_name["success"]["failedTests"] == 0
            and by_name["success"]["attempts"] == 1
            and by_name["success"]["screenshotCount"] == 0
            and by_name["success"]["logFileCount"] == 0,
            "passing browser tests may not attach failure artifacts")
    require(by_name["retry-once"]["passedTests"] == 2
            and by_name["retry-once"]["failedTests"] == 0
            and by_name["retry-once"]["attempts"] == 2,
            "explicit NUnit retry must rerun the browser test")
    require(by_name["final-failure"]["passedTests"] == 1
            and by_name["final-failure"]["failedTests"] == 1
            and by_name["final-failure"]["attempts"] == 3
            and by_name["final-failure"]["screenshotCount"] >= 1
            and by_name["final-failure"]["logFileCount"] >= 1,
            "real failed browser case needs authentic screenshot and console logs")
    print("MCP REAL_CHROMIUM_EVIDENCE_VALIDATED scenarios=3 browser=real "
          "context-open=6 context-close=6 customer-E2E=not_run", flush=True)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: assert_real_chromium_evidence.py <summary.json>")
    main(pathlib.Path(sys.argv[1]))
