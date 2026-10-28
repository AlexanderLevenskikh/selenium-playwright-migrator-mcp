namespace Migrator.Mcp;

/// <summary>
/// Restricts MCP callers to one explicitly configured workspace. This alpha is local and read-only.
/// It rejects paths outside the root, including existing targets resolved via symlinks.
/// </summary>
public sealed class WorkspacePaths
{
    private readonly string _root;

    public WorkspacePaths()
    {
        var configured = Environment.GetEnvironmentVariable("MIGRATOR_WORKSPACE");
        if (string.IsNullOrWhiteSpace(configured))
            throw new InvalidOperationException("MIGRATOR_WORKSPACE must be set to an existing absolute directory.");
        if (!Path.IsPathFullyQualified(configured))
            throw new InvalidOperationException("MIGRATOR_WORKSPACE must be absolute.");
        _root = Path.GetFullPath(configured);
        if (!Directory.Exists(_root))
            throw new DirectoryNotFoundException("MIGRATOR_WORKSPACE does not exist.");
    }


    /// <summary>
    /// Preflight recursive source scopes. Core's directory inventory is recursive;
    /// checking just its starting directory could follow a nested link outside the
    /// configured workspace. Reject *all* links in a source directory, including
    /// links whose final targets happen to be within the root.
    /// </summary>
    public string ResolveSourceScope(string relativePath, CancellationToken cancellationToken = default)
    {
        var full = Resolve(relativePath);
        if (!Directory.Exists(full))
            return full; // a single file was already checked by Resolve()

        var checkedEntries = 0;
        Scan(full, 0);
        return full;

        void Scan(string directory, int depth)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (depth > 40)
                throw new InvalidOperationException("SOURCE_SCOPE_TOO_DEEP: use a narrower source root.");
            if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                throw new UnauthorizedAccessException("SOURCE_SYMLINK_REJECTED: recursive analysis cannot follow symlink directories.");

            foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
            {
                cancellationToken.ThrowIfCancellationRequested();
                checkedEntries++;
                if (checkedEntries > 100_000)
                    throw new InvalidOperationException("SOURCE_SCOPE_TOO_LARGE: analyze a narrower directory.");
                var attrs = File.GetAttributes(entry);
                if ((attrs & FileAttributes.ReparsePoint) != 0)
                    throw new UnauthorizedAccessException("SOURCE_SYMLINK_REJECTED: linked input may escape the workspace.");
                if ((attrs & FileAttributes.Directory) != 0)
                    Scan(entry, depth + 1);
            }
        }
    }

    public string Resolve(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("A workspace-relative path is required.");
        if (Path.IsPathRooted(path))
            throw new UnauthorizedAccessException("Absolute caller paths are not accepted.");
        var full = Path.GetFullPath(Path.Combine(_root, path));
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!full.StartsWith(_root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison)
            && !string.Equals(full, _root, comparison))
            throw new UnauthorizedAccessException("Path escapes MIGRATOR_WORKSPACE.");
        // Resolve existing symlink components, including directory links, not only the final file.
        var walk = _root;
        foreach (var segment in Path.GetRelativePath(_root, full).Split(Path.DirectorySeparatorChar,
                     StringSplitOptions.RemoveEmptyEntries))
        {
            if (segment == ".") continue;
            walk = Path.Combine(walk, segment);
            var info = Directory.Exists(walk) ? (FileSystemInfo)new DirectoryInfo(walk) : new FileInfo(walk);
            if (!info.Exists) break;
            if (info.LinkTarget != null)
            {
                var target = info.ResolveLinkTarget(returnFinalTarget: true);
                if (target == null) throw new UnauthorizedAccessException("Unresolved symlink.");
                walk = Path.GetFullPath(target.FullName);
                if (!walk.StartsWith(_root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison)
                    && !string.Equals(walk, _root, comparison))
                    throw new UnauthorizedAccessException("Symlink escapes MIGRATOR_WORKSPACE.");
            }
        }
        return full;
    }
}
