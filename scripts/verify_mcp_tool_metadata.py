#!/usr/bin/env python3
"""Validate the real packaged MCP tool .nuspec; no network or execution."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

PACKAGE = "SeleniumPlaywrightMigrator.Mcp"
VERSION = "0.1.0-preview.48"
REPO = "https://github.com/levencode-labs/selenium-playwright-migrator-mcp"
DESCRIPTION = "MCP stdio server for agent-assisted Selenium C# to Playwright .NET AST migration."
FILES = (
    "tools/net10.0/any/Migrator.Mcp.dll",
    "tools/net10.0/any/DotnetToolSettings.xml",
    "tools/net10.0/any/.playwright/node/LICENSE",
    "tools/net10.0/any/.playwright/package/LICENSE",
    "tools/net10.0/any/.playwright/package/NOTICE",
)


def require(condition, reason):
    if not condition:
        raise ValueError("MCP_NUGET_PROVENANCE_REJECTED: " + reason)


def verify(path, expected_sha):
    path = Path(path)
    require(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None,
            "expected commit must be SHA40")
    require(path.is_file() and not path.is_symlink(), "missing package")
    require(path.name == PACKAGE + "." + VERSION + ".nupkg",
            "tool package filename/version")
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, "package CRC")
        names = z.namelist()
        require(len(set(names)) == len(names), "duplicate entries")
        require(not any(n.startswith("/") or ".." in n.split("/")
                        or "\\" in n for n in names),
                "unsafe package entry")
        require([n for n in names if n.endswith(".nuspec")] ==
                [PACKAGE + ".nuspec"], "tool nuspec identity")
        require(all(n in names for n in FILES), "tool/notice files absent")
        require(z.getinfo(PACKAGE + ".nuspec").file_size < 100_000,
                "oversized nuspec")
        meta = ET.fromstring(z.read(PACKAGE + ".nuspec")).find("{*}metadata")
        require(meta is not None, "missing metadata")

        def value(tag):
            element = meta.find("{*}" + tag)
            return (element.text or "").strip() if element is not None else ""

        require(value("id") == PACKAGE and value("version") == VERSION,
                "id/version mismatch")
        require(value("description") == DESCRIPTION, "description missing/generic")
        require(value("projectUrl") == REPO, "canonical project URL missing")
        license_info = meta.find("{*}license")
        require(license_info is not None and
                license_info.attrib.get("type") == "expression" and
                (license_info.text or "").strip() == "MIT", "SPDX MIT missing")
        repository = meta.find("{*}repository")
        require(repository is not None and
                repository.attrib.get("type") == "git" and
                repository.attrib.get("url") == REPO and
                repository.attrib.get("commit") == expected_sha,
                "source repository URL/commit mismatch")
        package_types = meta.find("{*}packageTypes")
        require(package_types is not None and any(
                x.attrib.get("name") == "DotnetTool"
                for x in package_types.findall("{*}packageType")),
                "DotnetTool package type missing")
    return {"status": "mcp_tool_provenance_verified",
            "package": PACKAGE, "version": VERSION, "repository": REPO,
            "commit": expected_sha}


if __name__ == "__main__":
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("package", type=Path)
    p.add_argument("--expected-commit", required=True)
    a = p.parse_args()
    print(json.dumps(verify(a.package, a.expected_commit), sort_keys=True))
