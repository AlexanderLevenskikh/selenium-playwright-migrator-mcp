namespace SyntheticScope;

internal static class SuiteTrace
{
    internal static readonly List<string> Events = new();
    internal static void Mark(string step) => Events.Add(step);
    internal static int Count(string step) => Events.Count(item => item == step);
    internal static bool Ordered(params string[] steps)
    {
        var cursor = -1;
        foreach (var step in steps)
        {
            var next = Events.FindIndex(cursor + 1, item => item == step);
            if (next < 0) return false;
            cursor = next;
        }
        return true;
    }
}
