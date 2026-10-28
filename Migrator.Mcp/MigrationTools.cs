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
        var result = engine.Analyze(workspace.ResolveSourceScope(source, cancellationToken), config == null ? null : workspace.Resolve(config),
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
        var result = engine.Explain(workspace.ResolveSourceScope(source, cancellationToken), findingId,
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
        var result = engine.Preview(workspace.ResolveSourceScope(source, cancellationToken),
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
            workspace.ResolveSourceScope(source, cancellationToken), expectedAnalysisId, candidateId,
            targetDirectory: targetRoot == null ? null : workspace.Resolve(targetRoot),
            configPath: config == null ? null : workspace.Resolve(config),
            runCompile: runCompile, compilationReferencePaths: references,
            cancellationToken: cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }


    [McpServerTool(Name = "plan_target_assembly")]
    [Description("Read-only, source-bound project-level NUnit assembly manifest. Lists every explicit generated Compile item and standalone SetUpFixture scope without writing files or invoking dotnet. No source code bodies are returned.")]
    public static string PlanTargetAssembly(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("One source SDK-style C# project root directory within workspace")] string source,
        [Description("Optional workspace-relative adapter JSON")] string? config = null,
        [Description("Current analysisId; stale source/config is rejected if supplied")] string? expectedAnalysisId = null,
        [Description("Current candidateId; stale preview is rejected if supplied")] string? expectedCandidateId = null,
        CancellationToken cancellationToken = default)
    {
        var plan = engine.PlanTargetAssembly(
            workspace.ResolveSourceScope(source, cancellationToken),
            config == null ? null : workspace.Resolve(config),
            expectedAnalysisId, expectedCandidateId, cancellationToken);
        var summary = new
        {
            plan.SchemaVersion, plan.AnalysisId, plan.CandidateId,
            plan.SourceTreeHash, plan.PreviewTargetTreeHash, plan.TargetTreeHash,
            plan.ProjectFile, plan.ManifestFile, plan.Status,
            plan.DeclaredTests, plan.ScopedSetUpFixtures,
            files = plan.Files.Select(file => new
            {
                file.RelativePath, file.Sha256, file.SourcePath
            }),
            plan.Issues, plan.Limitations,
            execution = "read_only_not_run"
        };
        var json = JsonSerializer.Serialize(summary, JsonOptions);
        if (json.Length > 200_000)
            throw new InvalidOperationException(
                "TARGET_ASSEMBLY_PLAN_TOO_LARGE: narrow the source project.");
        return json;
    }

    [McpServerTool(Name = "verify_target_assembly")]
    [Description("Read-only verification of the exact generated SDK NUnit project tree, project Compile list, sha256 manifest and SetUpFixture closure. Does NOT run dotnet build/test. Use Core AssemblyCli for opt-in build or NUnit execution.")]
    public static string VerifyTargetAssembly(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("One source SDK-style C# project root within workspace")] string source,
        [Description("Existing generated target assembly directory within workspace, outside source scope")] string targetRoot,
        [Description("Expected current source analysisId")] string expectedAnalysisId,
        [Description("Expected parent preview candidateId")] string candidateId,
        [Description("Optional workspace-relative adapter JSON")] string? config = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.VerifyTargetAssembly(
            workspace.ResolveSourceScope(source, cancellationToken),
            workspace.Resolve(targetRoot), expectedAnalysisId, candidateId,
            config == null ? null : workspace.Resolve(config),
            runBuild: false, runNUnit: false,
            cancellationToken: cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool(Name = "inspect_pom_sources")]
    [Description("Inspect in-scope C# Page Object source and selector helper implementations with Roslyn. Returns source-lined, review-required Playwright locator proposals and LocalStorage helper evidence. Never applies mappings or runs tests.")]
    public static string InspectPomSources(PomSourceInspector inspector, WorkspacePaths workspace,
        [Description("C# project/root directory within MIGRATOR_WORKSPACE")] string sourceDirectory,
        [Description("Optional exact Page Object type names to narrow findings")] string[]? pageTypes = null,
        [Description("Source Page Object variable in target tests, usually page or pagef")] string pageVariable = "page",
        CancellationToken cancellationToken = default)
    {
        var scope = workspace.ResolveSourceScope(sourceDirectory, cancellationToken);
        var report = inspector.Inspect(scope, pageTypes, pageVariable, cancellationToken);
        var json = JsonSerializer.Serialize(report, JsonOptions);
        if (json.Length > 500_000)
            throw new InvalidOperationException("POM_EVIDENCE_TOO_LARGE: narrow pageTypes or the source directory.");
        return json;
    }


    [McpServerTool(Name = "review_pom_mapping")]
    [Description("Compare a proposed target method mapping with source operation coverage. This does not approve or execute the mapping.")]
    public static string ReviewPomMapping(
        PomMappingReviewer reviewer,
        WorkspacePaths workspace,
        string sourceDirectory,
        string sourceType,
        string sourceMethod,
        string expectedSourceTreeHash,
        string[] targetStatements,
        int sourceLine = 0,
        CancellationToken cancellationToken = default)
    {
        var result = reviewer.Review(
            workspace.ResolveSourceScope(sourceDirectory, cancellationToken),
            sourceType, sourceMethod, sourceLine, expectedSourceTreeHash,
            targetStatements, cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = false
    };
}
