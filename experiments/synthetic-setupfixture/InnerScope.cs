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
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-base-before"), Is.EqualTo(2));
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-derived-before"), Is.EqualTo(2));
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-derived-after"), Is.EqualTo(2));
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-base-after"), Is.EqualTo(2));
        Assert.That(SyntheticScope.SuiteTrace.Ordered(
            "inner-start", "pertest-base-before", "pertest-derived-before",
            "child-test-one", "pertest-derived-after", "pertest-base-after",
            "pertest-base-before", "pertest-derived-before",
            "child-test-two", "pertest-derived-after", "pertest-base-after"), Is.True);
        SyntheticScope.SuiteTrace.Mark("inner-end");
    }
}
