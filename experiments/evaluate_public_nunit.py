#!/usr/bin/env python3
"""Read-only, pinned external Selenium/NUnit migration evaluation.
No external source or generated C# is included in uploaded evidence.
"""
import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mcp_stdio_smoke import call, receive, send, start_reader, value

def command(args, directory, log_path, timeout=210):
    started = time.monotonic()
    try:
        done = subprocess.run(args, cwd=directory, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        status = "passed" if done.returncode == 0 else "failed"
        output = done.stdout + "\n" + done.stderr
        code = done.returncode
    except subprocess.TimeoutExpired:
        status, code, output = "blocked", None, "PROCESS_TIMEOUT"
    except OSError as error:
        status, code, output = "blocked", None, "PROCESS_UNAVAILABLE: " + str(error)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output[:100000], encoding="utf-8")
    errors = [line.strip()[:300] for line in output.splitlines()
              if " error CS" in line or " error NU" in line or "error :" in line]
    return {"status": status, "exitCode": code,
            "seconds": round(time.monotonic()-started, 2),
            "log": log_path.name, "diagnostics": errors[:15]}

def rpc(proc, counter, name, arguments):
    return value(call(proc, counter, name, arguments))

def count_findings(items):
    return dict(collections.Counter(f["code"] for f in items))

def evaluate(proc, root, out, source, label, index):
    item = {"case": label, "source": source, "analysis": {"status":"not_run"},
            "preview": {"status":"not_run"}, "verification": {"status":"not_run"},
            "targetBuild": {"status":"not_run"}, "runtime": {"status":"not_run"}}
    try:
        a = rpc(proc, index, "analyze_migration", {"source": source})
        item["analysis"] = {"status":"completed", "analysisId": a["analysisId"],
            "discovery":a["discoveryStatus"], "declared":a["declaredTests"],
            "parsed":a["parsedTests"], "sourceHash":a["sourceTreeHash"],
            "configHash":a["configurationHash"],
            "files":len(a["files"]), "findings":count_findings(a["findings"]),
            "dispositions":dict(collections.Counter(f["disposition"] for f in a["files"]))}
        p = rpc(proc, index+1, "preview_migration",
                {"source":source,"expectedAnalysisId":a["analysisId"]})
        gen = p["files"]
        item["preview"] = {"status":p["transformationStatus"],
            "candidateId":p["candidateId"],"targetHash":p["targetTreeHash"],
            "files":len(gen),"generatedTests":sum(f["tests"] for f in gen),
            "fullyConverted":sum(f["fullyConvertedTests"] for f in gen),
            "todo":sum(f["todoComments"] for f in gen),
            "findings":count_findings(p["findings"])}
        if a["findings"]:
            e = rpc(proc,index+2,"explain_finding",
                    {"source":source, "findingId":a["findings"][0]["id"],
                     "expectedAnalysisId":a["analysisId"]})
            item["firstExplanation"]={"code":e["code"],"kind":e["evidenceKind"],
                                      "hasNextAction":bool(e["suggestedNextAction"])}
        if not gen:
            item["verification"]={"status":"blocked","reason":"NO_GENERATED_TARGET"}
            return item
        target=root/("eval-generated-"+label)
        if target.exists(): shutil.rmtree(target)
        target.mkdir()
        for f in gen:
            posix=Path(f["relativePath"])
            if posix.is_absolute() or ".." in posix.parts or posix.suffix!=".cs":
                raise RuntimeError("Unsafe generated target filename")
            destination=target/posix
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(f["content"],encoding="utf-8")
        v=rpc(proc,index+3,"verify_artifact",
              {"source":source,"expectedAnalysisId":a["analysisId"],
               "candidateId":p["candidateId"],
               "targetRoot":target.relative_to(root).as_posix(),
               "runCompile":True,"referenceDlls":[]})
        item["verification"]={"status":"completed",
            "candidateId":v["candidate"]["candidateId"],
            "origin":v["candidate"]["origin"],
            "targetHash":v["candidate"]["targetTreeHash"],
            "syntax":v["syntax"]["status"],"compileFrameworkOnly":v["compile"]["status"],
            "runtime":v["runtime"]["status"],"observables":v["observables"]["status"],
            "syntaxCodes":[d["code"] for d in v["syntax"]["diagnostics"][:20]],
            "compileCodes":[d["code"] for d in v["compile"]["diagnostics"][:20]]}
        if v["candidate"]["candidateId"]!=p["candidateId"]:
            raise RuntimeError("Candidate identity unexpectedly changed")
        csproj=target/"GeneratedSmoke.csproj"
        csproj.write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <IsTestProject>true</IsTestProject>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Playwright.NUnit" Version="1.63.0" />
  </ItemGroup>
</Project>
""", encoding="utf-8")
        item["targetBuild"]=command(["dotnet","build",str(csproj),"-c","Release",
                                      "--nologo","-v:q"],
                                     target,out/(label+"-target-build.log"))
        if item["targetBuild"]["status"]=="passed":
            installer=target/"bin"/"Release"/"net10.0"/"playwright.ps1"
            if installer.exists():
                install=command(["pwsh",str(installer),"install","chromium"],
                                target,out/(label+"-browser-install.log"),150)
                item["browserInstall"]=install
                if install["status"]=="passed":
                    item["runtime"]=command(["dotnet","test",str(csproj),"-c","Release",
                                              "--no-build","--nologo","-v:q"],
                                             target,out/(label+"-target-test.log"),120)
                else: item["runtime"]={"status":"blocked","reason":"BROWSER_INSTALL_FAILED"}
            else: item["runtime"]={"status":"blocked","reason":"BROWSER_INSTALLER_MISSING"}
    except Exception as exc:
        item["harnessError"]=str(exc)[:650]
    return item

def main():
    if len(sys.argv)!=4:
        raise SystemExit("Usage: evaluate_public_nunit.py <mcp.dll> <external_checkout> <report_dir>")
    dll,root,out=[Path(arg).resolve() for arg in sys.argv[1:]]
    out.mkdir(parents=True,exist_ok=True)
    result={"schema":"migrator-experiment/v1",
        "sourceRepository":"desh2001/Selenium-NUnit-Automation",
        "sourceCommit":"edacb9feb41a7e21d9b6bf6924f24c11698a4427",
        "coreCommit":"3c4bf137a39f42da5e481b5a33edc718954ee0cd",
        "playwrightNUnit":"1.63.0",
        "method":"read-only pinned external checkout, raw generated code, no manual mappings",
        "cases":[]}
    proc=None
    try:
        result["originalBuild"]=command(
            ["dotnet","build",str(root/"AssignmentProject"/"CSE2522_Selenium_NUnit.csproj"),
             "-c","Release","--nologo","-v:q"],
            root,out/"original-build.log")
        env=dict(os.environ,MIGRATOR_WORKSPACE=str(root))
        proc=subprocess.Popen(["dotnet",str(dll)],stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        start_reader(proc)
        send(proc,{"jsonrpc":"2.0","id":1,"method":"initialize",
                   "params":{"protocolVersion":"2025-06-18","capabilities":{},
                             "clientInfo":{"name":"external-evaluation","version":"0.1"}}})
        initialized=receive(proc,1)
        if "serverInfo" not in initialized: raise RuntimeError("MCP initialization failed")
        send(proc,{"jsonrpc":"2.0","method":"notifications/initialized"})
        send(proc,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
        names={t["name"] for t in receive(proc,2).get("tools",[])}
        if not {"analyze_migration","preview_migration","explain_finding","verify_artifact"}<=names:
            raise RuntimeError("Expected MCP tools are missing")
        for scope,label,num in [
            ("AssignmentProject/Tests","full-tests",100),
            ("AssignmentProject/Tests/TextInputTests.cs","text-input",200)]:
            result["cases"].append(evaluate(proc,root,out,scope,label,num))
    except Exception as exc:
        result["harnessError"]=str(exc)[:650]
    finally:
        if proc:
            proc.terminate()
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill();proc.communicate(timeout=10)
        (out/"evaluation.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                                            encoding="utf-8")
        public={"source":result["sourceRepository"],
                "originalBuild":result.get("originalBuild",{}).get("status"),
                "cases":[{"name":c["case"],"discovery":c["analysis"].get("discovery"),
                           "declared":c["analysis"].get("declared"),
                           "preview":c["preview"].get("status"),
                           "generated":c["preview"].get("files"),
                           "syntax":c["verification"].get("syntax"),
                           "roslynCompile":c["verification"].get("compileFrameworkOnly"),
                           "dotnetBuild":c["targetBuild"].get("status"),
                           "runtime":c["runtime"].get("status"),
                           "harnessError":c.get("harnessError")} for c in result["cases"]]}
        print(json.dumps(public,indent=2,ensure_ascii=False),flush=True)
    if result.get("harnessError") or not result["cases"] or all("harnessError" in c for c in result["cases"]):
        raise SystemExit("Experiment failed to produce usable evidence")

if __name__=="__main__":
    main()
