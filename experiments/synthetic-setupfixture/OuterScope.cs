using NUnit.Framework;

namespace SyntheticScope;

[SetUpFixture]
public sealed class OuterScope
{
    [OneTimeSetUp]
    public void EnterParent()
    {
        Assert.That(SuiteTrace.Ordered("assembly-start"), Is.True);
        SuiteTrace.Mark("outer-start");
    }

    [OneTimeTearDown]
    public void ExitParent()
    {
        Assert.That(SuiteTrace.Ordered("assembly-start", "outer-start",
            "inner-start", "inner-end"), Is.True);
        SuiteTrace.Mark("outer-end");
    }
}
