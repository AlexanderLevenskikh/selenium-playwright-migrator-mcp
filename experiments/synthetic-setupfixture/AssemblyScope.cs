using NUnit.Framework;
using SyntheticScope;

[SetUpFixture]
public sealed class AssemblyScope
{
    [OneTimeSetUp]
    public void EnterAssembly()
    {
        SuiteTrace.Events.Clear();
        SuiteTrace.Mark("assembly-start");
    }

    [OneTimeTearDown]
    public void ExitAssembly()
    {
        SuiteTrace.Mark("assembly-end");
        Assert.That(SuiteTrace.Count("assembly-start"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("assembly-end"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("outer-start"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("inner-start"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("outer-end"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("inner-end"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Count("sibling-test"), Is.EqualTo(1));
        Assert.That(SuiteTrace.Ordered("assembly-start", "outer-start",
            "inner-start", "inner-end", "outer-end", "assembly-end"), Is.True);
    }
}
