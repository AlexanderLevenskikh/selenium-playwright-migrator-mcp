# Selenium → Playwright Migrator MCP

Standalone **MCP stdio server and agent skill** for Selenium C# NUnit → Playwright .NET migration. It uses the versioned [Migrator Core](https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core) NuGet API rather than referencing the engine source projects.

Imported from [selenium-playwright-ast-migrator](https://github.com/AlexanderLevenskikh/selenium-playwright-ast-migrator), pinned source commit `a8b102072196f85bf85d785795aef22296c4deca`.

## MCP tools

- `analyze_migration(source, config?)`: source inventory, blockers, hashes and findings.
- `explain_finding(source, findingId, config?, expectedAnalysisId?)`: source excerpt, diagnostic evidence and suggested next action.
- `preview_migration(source, config?, expectedAnalysisId?)`: read-only conservative target draft, hashes, TODOs and residual findings.
- `verify_artifact(source, expectedAnalysisId, candidateId, targetRoot?, config?, runCompile?, referenceDlls?)`: syntax and optional Roslyn assembly compilation of **exact** generated or agent-edited target bytes. Edited candidates have new content-addressed revision IDs and their generated parent.

The server **never applies edits**. No compile/run/behavior claims are made for preview. Runtime/browser and product-project build verification remain roadmap items. Inputs with multiple fixtures or unsupported xUnit source are counted but blocked.

## Local build before Core is published to NuGet

CI uses Core commit `3c4bf137a39f42da5e481b5a33edc718954ee0cd` for the local package feed, verified independently in its own repository. To reproduce the build:

```bash
git clone https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-core.git core
git -C core checkout 3c4bf137a39f42da5e481b5a33edc718954ee0cd
mkdir -p artifacts/nuget
for project in Migrator.Core Migrator.Roslyn Migrator.SeleniumCSharp Migrator.PlaywrightDotNet Migrator.Application; do
  dotnet pack "core/$project/$project.csproj" -c Release -o artifacts/nuget
done
dotnet restore Migrator.Mcp/Migrator.Mcp.csproj --source "$PWD/artifacts/nuget" --source https://api.nuget.org/v3/index.json
dotnet build Migrator.Mcp/Migrator.Mcp.csproj -c Release --no-restore
MIGRATOR_WORKSPACE=/absolute/path/to/selenium-tests dotnet run --project Migrator.Mcp/Migrator.Mcp.csproj -c Release --no-build
```

Core packages are **preview build artifacts**, not yet published to public NuGet.

## Install MCP as a dotnet tool (preview)

The MCP CI now packs `SeleniumPlaywrightMigrator.Mcp` as a versioned .NET tool and validates the **installed executable** with the same MCP protocol smoke. Until public NuGet publication, download the MCP package artifact from CI and provide the Core package feed if required:

```bash
dotnet tool install SeleniumPlaywrightMigrator.Mcp --version 0.1.0-preview.2 \
  --tool-path ./.tools --add-source ./artifacts/mcp --add-source ./artifacts/nuget \
  --add-source https://api.nuget.org/v3/index.json
MIGRATOR_WORKSPACE=/absolute/path/to/selenium-tests \
  ./.tools/selenium-pw-migrator-mcp
```

The `MIGRATOR_WORKSPACE` environment variable is mandatory. For an MCP client, set `command` to the absolute path of the installed `selenium-pw-migrator-mcp` executable and `args` to an empty list. No prebuilt public distribution is claimed until release.

## MCP client configuration

```json
{
  "mcpServers": {
    "selenium-playwright-migrator": {
      "command": "dotnet",
      "args": ["/absolute/path/to/mcp/Migrator.Mcp/bin/Release/net10.0/Migrator.Mcp.dll"],
      "env": {
        "MIGRATOR_WORKSPACE": "/absolute/path/to/selenium-tests"
      }
    }
  }
}
```

The environment variable must contain an **absolute existing workspace** path. Tool arguments use workspace-relative paths. Stdout is reserved for MCP JSON-RPC.

See the included [agent skill](skills/selenium-playwright-migration/SKILL.md). The integration smoke validates initialize, tool discovery/calls, path boundaries, stale analyses and unsupported source shapes.

License: MIT. Preview API and schema contracts may change before `v1.0`.

## Candidate verification and evidence limits

`verify_artifact` **never writes code**, runs scripts, starts tests, loads referenced assemblies as executable code or claims behavioral equivalence. Generated previews and edited trees are checked against fresh analysis/candidate IDs before capturing the exact C# bytes. The returned `candidate.targetTreeHash` and per-file SHA-256 bind evidence to the revision. A later edit receives another ID, even if an earlier candidate compiled.

- `syntax`: `passed` or `failed` after Roslyn parsing of captured files.
- `compile`: `not_run`, `blocked` (missing profile or invalid syntax), `passed`, or `failed`. `runCompile=true` requires `referenceDlls` (use `[]` to request .NET framework-only compile). This emits a temporary in-memory assembly; it does not perform a target-project `dotnet build`.
- `runtime` / `observables`: always `not_run` until separate verification profiles are implemented.
- `targetRoot`: workspace-relative directory **outside any directory source scope**, with exactly the preview's .cs filenames. It may be populated and edited by the calling agent's own editor, not by MCP.

The MCP protocol smoke exercises generated/edited candidates, semantic and syntax failures, blocked missing references, stale parent, and extra target files.
