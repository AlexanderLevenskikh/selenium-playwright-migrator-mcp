using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticCombobox;

/// <summary>
/// Real NUnit execution proves the framework's source hierarchy order on an
/// artificial fixture. The Core migration review still needs independent
/// source/target comparison for each project's effects.
/// </summary>
public abstract class SourceLikeLifecycleBase : PageTest
{
    protected static readonly List<string> Events = new();

    [OneTimeSetUp]
    public void BaseOnce()
    {
        Events.Clear();
        Events.Add("base-once");
    }

    [SetUp]
    public void BaseBefore() => Events.Add("base-before");

    [TearDown]
    public void BaseAfter() => Events.Add("base-after");

    [OneTimeTearDown]
    public void BaseAfterAll()
    {
        Events.Add("base-once-after");
        Assert.That(Events, Is.EqualTo(new[]
        {
            "base-once", "derived-once",
            "base-before", "derived-before", "test-one", "derived-after", "base-after",
            "base-before", "derived-before", "test-two", "derived-after", "base-after",
            "derived-once-after", "base-once-after"
        }), "NUnit must preserve base/derived setup and reverse cleanup over two tests");
    }
}

[TestFixture]
[NonParallelizable]
public sealed class InheritedLifecycleBrowserTests : SourceLikeLifecycleBase
{
    [OneTimeSetUp]
    public void DerivedOnce() => Events.Add("derived-once");

    [SetUp]
    public void DerivedBefore() => Events.Add("derived-before");

    [TearDown]
    public void DerivedAfter() => Events.Add("derived-after");

    [OneTimeTearDown]
    public void DerivedAfterAll() => Events.Add("derived-once-after");

    [Test]
    [Order(1)]
    public void InheritedSetUpRunsOldestBaseFirst()
    {
        Assert.That(Events, Is.EqualTo(new[]
        {
            "base-once", "derived-once", "base-before", "derived-before"
        }));
        Events.Add("test-one");
    }

    [Test]
    [Order(2)]
    public void InheritedTearDownRunsDerivedBeforeBase()
    {
        Assert.That(Events, Is.EqualTo(new[]
        {
            "base-once", "derived-once",
            "base-before", "derived-before", "test-one", "derived-after", "base-after",
            "base-before", "derived-before"
        }));
        Events.Add("test-two");
    }
}
