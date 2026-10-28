using System.ComponentModel;
using System.Text.Json;
using Migrator.Application;
using ModelContextProtocol.Server;

namespace Migrator.Mcp;

[McpServerToolType]
public static class MigrationTools
{
    [McpServerTool(Name = "analyze_migration")]
    [Description("Analyze Selenium C# source with an independent inventory. Unsupported xUnit and multiple fixtures are counted and reported, not silently converted. Does not change files.")]
    public static string AnalyzeMigration(MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source .cs file or directory relative to the configured workspace root")] string source,
        [Description("Optional JSON adapter config path within workspace")] string? config = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.Analyze(workspace.Resolve(source), config == null ? null : workspace.Resolve(config),
            cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool(Name = "explain_finding")]
    [Description("Explain a current analysis/preview finding with evidence, bounded source excerpt and next action. Recommendations are not behavioral proof.")]
    public static string ExplainFinding(MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source .cs file or directory within the workspace")] string source,
        [Description("Finding ID returned by analyze_migration or preview_migration")] string findingId,
        [Description("Optional adapter config within workspace")] string? config = null,
        [Description("Expected analysis ID to reject stale source/config")] string? expectedAnalysisId = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.Explain(workspace.Resolve(source), findingId,
            config == null ? null : workspace.Resolve(config), expectedAnalysisId, cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool(Name = "preview_migration")]
    [Description("Generate a read-only conservative Playwright .NET candidate; this is NOT a syntax, compile, runtime or behavior verification. Unsupported source shapes are blocked.")]
    public static string PreviewMigration(MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source .cs file or directory relative to the workspace")] string source,
        [Description("Optional JSON adapter config path within workspace")] string? config = null,
        [Description("Expected analysisId from analyze_migration. Stale input is rejected.")] string? expectedAnalysisId = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.Preview(workspace.Resolve(source),
            config == null ? null : workspace.Resolve(config), expectedAnalysisId, cancellationToken);
        var json = JsonSerializer.Serialize(result, JsonOptions);
        if (json.Length > 1_000_000)
            throw new InvalidOperationException("PREVIEW_TOO_LARGE: narrow the source scope. No files were changed.");
        return json;
    }


    [McpServerTool(Name = "verify_artifact")]
    [Description("Verify exact generated or agent-edited C# target bytes. Requires current analysis and parent candidate IDs. Returns independent syntax/compile/runtime/observables statuses; never executes tests, applies edits, or invokes MSBuild.")]
    public static string VerifyArtifact(MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source .cs file or directory inside the workspace")] string source,
        [Description("Current analysisId returned by analyze_migration / preview_migration")] string expectedAnalysisId,
        [Description("Current parent candidateId returned by preview_migration")] string candidateId,
        [Description("Optional directory containing the exact C# target files edited by the agent. Omit to verify generated preview bytes.")] string? targetRoot = null,
        [Description("Optional adapter config path within workspace")] string? config = null,
        [Description("Request in-memory Roslyn compilation in addition to syntax parsing")] bool runCompile = false,
        [Description("Optional DLL paths relative to the workspace. Required (may be empty) when runCompile=true. No MSBuild project evaluation.")] string[]? referenceDlls = null,
        CancellationToken cancellationToken = default)
    {
        var references = referenceDlls?.Select(workspace.Resolve).ToArray();
        var result = engine.VerifyArtifact(
            workspace.Resolve(source), expectedAnalysisId, candidateId,
            targetDirectory: targetRoot == null ? null : workspace.Resolve(targetRoot),
            configPath: config == null ? null : workspace.Resolve(config),
            runCompile: runCompile, compilationReferencePaths: references,
            cancellationToken: cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = false
    };
}
