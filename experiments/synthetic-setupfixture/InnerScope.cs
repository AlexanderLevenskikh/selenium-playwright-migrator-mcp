using NUnit.Framework;

namespace SyntheticScope.Inner;

[SetUpFixture]
public sealed class InnerScope
{
    [OneTimeSetUp]
    public void EnterChild()
    {
        Assert.That(SyntheticScope.SuiteTrace.Ordered("assembly-start", "outer-start"),
            Is.True);
        SyntheticScope.SuiteTrace.Mark("inner-start");
    }

    [OneTimeTearDown]
    public void ExitChild()
    {
        Assert.That(SyntheticScope.SuiteTrace.Count("child-test-one"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Count("child-test-two"), Is.EqualTo(1));
        SyntheticScope.SuiteTrace.Mark("inner-end");
    }
}
