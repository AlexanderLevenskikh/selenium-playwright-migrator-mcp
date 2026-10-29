using System.ComponentModel;
using System.Text.Json;
using Migrator.Application;
using ModelContextProtocol.Server;

namespace Migrator.Mcp;

[McpServerToolType]
public static class MigrationTools
{
    [McpServerTool(Name = "inspect_nunit_execution")]
    [Description("Read-only preview.29 NUnit Ignore/Explicit/TestCaseSource static case inventory: relative paths, source line/SHA256, run-state and explicit blockers. Does not evaluate source C#, perform NUnit discovery or execute tests.")]
    public static string InspectNUnitExecution(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source .cs file or source project directory relative to MIGRATOR_WORKSPACE")] string source,
        [Description("Optional JSON adapter configuration relative to workspace")] string? config = null,
        CancellationToken cancellationToken = default)
    {
        var report = engine.Analyze(
            workspace.ResolveSourceScope(source, cancellationToken),
            config == null ? null : workspace.Resolve(config), cancellationToken);
        var payload = new
        {
            schemaVersion = "migrator-nunit-execution/v1alpha1",
            report.AnalysisId, report.SourceTreeHash, report.DiscoveryStatus,
            report.DeclaredTests, report.ParsedTests,
            report.StaticallyResolvedNUnitCases, report.BlockedNUnitSources,
            runtimeStatus = "not_run",
            nunitDiscoveryEvidence = "static_inventory_not_nunit_discovery",
            files = report.Files.Select(file => new
            {
                file.RelativePath, file.Disposition, file.DeclaredTests, file.ParsedTests,
                cases = file.NUnitCases.Select(item => new
                {
                    item.Line, item.Method, item.TargetExpression,
                    item.RunState, item.Reason
                }),
                attributes = file.NUnitAttributes.Select(item => new
                {
                    item.Line, item.Kind, item.SourceSha256,
                    item.TargetExpression, item.RequiresReview, item.Reason
                }),
                blockers = file.Findings.Where(item =>
                    item.Code.StartsWith("NUNIT_", StringComparison.Ordinal))
                    .Select(item => new { item.Code, item.SourcePath, item.Line })
            }),
            limitations = new[]
            {
                "No C# data-source execution or environment evaluation.",
                "Static cases are not NUnit runtime-discovered test cases.",
                "NUnit3/NUnit4 discovery, skipped reasons, explicit selection and TRX must be checked separately.",
                "No source bodies or arbitrary source excerpts are returned."
            }
        };
        var json = JsonSerializer.Serialize(payload, JsonOptions);
        if (json.Length > 200_000)
            throw new InvalidOperationException(
                "NUNIT_EXECUTION_REPORT_TOO_LARGE: analyze a narrower source project.");
        return json;
    }

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
            plan.AssemblyScheduling,
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

    [McpServerTool(Name = "plan_target_solution")]
    [Description("Read-only source-bound multi-csproj graph plan. An optional TargetSolutionEntryProjects adapter scope selects NUnit entry projects plus all transitive ProjectReference dependencies and lists excluded projects. Keeps independent SetUpFixture assemblies and SHA-256 manifest. No code bodies, file writes or execution.")]
    public static string PlanTargetSolution(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Multi-project SDK-style source solution directory within workspace")] string source,
        [Description("Optional workspace-relative adapter JSON")] string? config = null,
        [Description("Optional exact sourceTreeHash from a previous solution plan")] string? expectedSourceTreeHash = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.PlanTargetSolution(
            workspace.ResolveSourceScope(source, cancellationToken),
            config == null ? null : workspace.Resolve(config),
            expectedSourceTreeHash, cancellationToken);
        var json = JsonSerializer.Serialize(new
        {
            result.SchemaVersion, result.SourceTreeHash,
            result.ConfigurationHash, result.PlanId, result.TargetTreeHash,
            result.SolutionFile, result.ManifestFile, result.Status,
            result.Scope, result.Projects, result.AssemblyScheduling,
            files = result.Files.Select(file => new
                { file.RelativePath, file.Sha256, file.SourcePath }),
            result.Issues, result.Limitations, execution = "read_only_not_run"
        }, JsonOptions);
        if (json.Length > 300_000)
            throw new InvalidOperationException(
                "SOLUTION_PLAN_TOO_LARGE: narrow the multi-project source graph.");
        return json;
    }

    [McpServerTool(Name = "verify_target_solution")]
    [Description("Read-only byte/graph verification of all generated NUnit project assemblies, libraries, .slnx, manifests and ProjectReference/Compile closure. Never executes MSBuild, dotnet test or application code.")]
    public static string VerifyTargetSolution(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Multi-project source solution root within workspace")] string source,
        [Description("Existing generated target solution directory within workspace, separate from source")] string targetRoot,
        [Description("Expected exact sourceTreeHash")] string expectedSourceTreeHash,
        [Description("Expected exact planId")] string expectedPlanId,
        [Description("Optional workspace-relative adapter JSON")] string? config = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.VerifyTargetSolution(
            workspace.ResolveSourceScope(source, cancellationToken),
            workspace.Resolve(targetRoot),
            expectedSourceTreeHash, expectedPlanId,
            config == null ? null : workspace.Resolve(config),
            runBuild: false, runNUnit: false,
            cancellationToken: cancellationToken);
        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool(Name = "review_playwright_fixture_lifetime")]
    [Description("Read-only, source-hash-bound review of exact inherited NUnit DI scope, BrowserContext/Page, failure logs/screenshots and nested FullDispose roles. Every source expression needs its exact path/line/SHA-256 and a reviewer-attested target role. No source or generated C# bodies, file writes, build, browser or runtime execution.")]
    public static string ReviewPlaywrightFixtureLifetime(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source SDK C# project directory within workspace")]
        string sourceDirectory,
        [Description("Fully qualified source abstract NUnit fixture base type")]
        string fixtureBaseType,
        [Description("Fully qualified nested cleanup-only NUnit SetUpFixture type")]
        string nestedCleanupType,
        [Description("Fully qualified source scoped DI container type")]
        string infrastructureType,
        [Description("Exact sourceTreeHash from inspect_nunit_lifecycle")]
        string expectedSourceTreeHash,
        [Description("Exact source-backed one-to-one role bindings, each with reviewer attestation")]
        ReviewedPlaywrightLifetimeBinding[] bindings,
        CancellationToken cancellationToken = default)
    {
        var plan = engine.ReviewPlaywrightFixtureLifetime(
            workspace.ResolveSourceScope(sourceDirectory, cancellationToken),
            fixtureBaseType, nestedCleanupType, infrastructureType,
            expectedSourceTreeHash, bindings, cancellationToken);
        var response = new
        {
            plan.SchemaVersion, plan.Status, plan.SourceTreeHash,
            plan.FixtureBaseType, plan.NestedCleanupType,
            plan.InfrastructureType, plan.ValidatedBindings,
            plan.InfrastructureMethods, plan.Issues,
            candidate = plan.Candidate == null ? null : new
            {
                plan.Candidate.RelativePath, plan.Candidate.Sha256,
                plan.Candidate.FixtureBaseType,
                plan.Candidate.NestedCleanupType,
                plan.Candidate.InfrastructureType
            },
            concreteBridge = plan.ConcreteBridge == null ? null : new
            {
                plan.ConcreteBridge.RelativePath,
                plan.ConcreteBridge.Sha256,
                plan.ConcreteBridge.FixtureBaseType,
                plan.ConcreteBridge.NestedCleanupType,
                plan.ConcreteBridge.InfrastructureType
            },
            plan.BehavioralEquivalenceVerified, plan.SourceNUnitRuntime,
            plan.TargetBuild, plan.TargetNUnitRuntime,
            plan.BrowserE2E, plan.Limitations,
            execution = "read_only_not_run"
        };
        var json = JsonSerializer.Serialize(response, JsonOptions);
        if (json.Length > 300_000)
            throw new InvalidOperationException(
                "PLAYWRIGHT_LIFETIME_EVIDENCE_TOO_LARGE: narrow sourceDirectory.");
        return json;
    }

    [McpServerTool(Name = "review_nested_nunit_cleanup")]
    [Description("Source-hash-bound, read-only reviewed candidate for a nested, cleanup-only NUnit SetUpFixture. Requires one reviewed target invocation per source invocation, preserves outer/nested type shape, does not write or execute code and never claims source/target runtime equivalence.")]
    public static string ReviewNestedNUnitCleanup(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source NUnit C# project directory within workspace")]
        string sourceDirectory,
        [Description("Exact fully qualified nested NUnit SetUpFixture source type")]
        string sourceType,
        [Description("Exact sourceTreeHash from inspect_nunit_lifecycle")]
        string expectedSourceTreeHash,
        [Description("Explicitly reviewed concrete C# cleanup invocation statements")]
        string[] targetStatements,
        [Description("Optional unverified external source NUnit runtime evidence SHA256")]
        string? sourceRuntimeEvidenceSha256 = null,
        CancellationToken cancellationToken = default)
    {
        var result = engine.ReviewNestedNUnitCleanup(
            workspace.ResolveSourceScope(sourceDirectory, cancellationToken),
            sourceType, expectedSourceTreeHash, targetStatements,
            sourceRuntimeEvidenceSha256, cancellationToken);
        var response = new
        {
            result.SchemaVersion, result.Status, result.SourceTreeHash,
            result.SourceType, result.SourceFile, result.SourceLine,
            result.OriginalNamespace, result.OuterType,
            result.SourceMethodSha256, result.SourceRuntimeEvidenceSha256,
            result.SourceEffectKinds, result.Issues,
            candidate = result.Candidate == null ? null : new
            {
                result.Candidate.RelativePath, result.Candidate.Sha256,
                result.Candidate.SourceType,
                result.Candidate.OriginalNamespace,
                result.Candidate.OwnerType,
                result.Candidate.HookMethod,
                result.Candidate.SourceMethodSha256
            },
            result.BehavioralEquivalenceVerified, result.SourceNUnitRuntime,
            result.TargetBuild, result.TargetNUnitRuntime,
            result.BrowserObservables, result.Limitations,
            execution = "read_only_not_run"
        };
        var json = JsonSerializer.Serialize(response, JsonOptions);
        if (json.Length > 150_000)
            throw new InvalidOperationException(
                "NESTED_CLEANUP_REVIEW_TOO_LARGE: narrow the source scope.");
        return json;
    }

    [McpServerTool(Name = "inspect_nunit_lifecycle")]
    [Description("Read-only Roslyn lifecycle audit of inherited/base NUnit hooks, nested SetUpFixture cleanup, reachable private helpers, DI/browser/listener/screenshot/log teardown dependencies. Returns source hashes and lines, never source bodies or behavioral approval.")]
    public static string InspectNUnitLifecycle(
        MigrationEngine engine, WorkspacePaths workspace,
        [Description("Source C# project directory within MIGRATOR_WORKSPACE")]
        string sourceDirectory,
        CancellationToken cancellationToken = default)
    {
        var report = engine.InspectNUnitLifecycle(
            workspace.ResolveSourceScope(sourceDirectory, cancellationToken),
            cancellationToken);
        var json = JsonSerializer.Serialize(report, JsonOptions);
        if (json.Length > 250_000)
            throw new InvalidOperationException(
                "NUNIT_LIFECYCLE_EVIDENCE_TOO_LARGE: use a narrower C# project scope.");
        return json;
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
