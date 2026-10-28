using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticScope.Inner;

/// <summary>Inherited per-test hooks must execute inside the namespace suite.</summary>
public abstract class ScopedPerTestBase : PageTest
{
    [SetUp]
    public void BaseBeforeEach()
    {
        Assert.That(SyntheticScope.SuiteTrace.Ordered(
            "assembly-start", "outer-start", "inner-start"), Is.True);
        SyntheticScope.SuiteTrace.Mark("pertest-base-before");
    }

    [TearDown]
    public void BaseAfterEach() =>
        SyntheticScope.SuiteTrace.Mark("pertest-base-after");
}

[TestFixture]
[NonParallelizable]
public sealed class ScopedBrowserTests : ScopedPerTestBase
{
    [SetUp]
    public void DerivedBeforeEach()
    {
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-base-before"),
            Is.EqualTo(SyntheticScope.SuiteTrace.Count("pertest-derived-before") + 1));
        SyntheticScope.SuiteTrace.Mark("pertest-derived-before");
    }

    [TearDown]
    public void DerivedAfterEach() =>
        SyntheticScope.SuiteTrace.Mark("pertest-derived-after");

    [Test]
    [Order(1)]
    public async Task GlobalParentAndChildScopesPrepareFirstTest()
    {
        Assert.That(SyntheticScope.SuiteTrace.Ordered(
            "assembly-start", "outer-start", "inner-start"), Is.True);
        Assert.That(SyntheticScope.SuiteTrace.Count("outer-start"), Is.EqualTo(1));
        await Page.GotoAsync("data:text/html,<main id='synthetic'>prepared</main>");
        await Expect(Page.Locator("#synthetic")).ToHaveTextAsync("prepared");
        SyntheticScope.SuiteTrace.Mark("child-test-one");
    }

    [Test]
    [Order(2)]
    public async Task NestedNamespaceHooksRemainOneTimeForSecondTest()
    {
        Assert.That(SyntheticScope.SuiteTrace.Count("outer-start"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Count("inner-start"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Count("child-test-one"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-derived-after"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Count("pertest-base-after"), Is.EqualTo(1));
        Assert.That(SyntheticScope.SuiteTrace.Ordered(
            "inner-start", "pertest-base-before", "pertest-derived-before",
            "child-test-one", "pertest-derived-after", "pertest-base-after"), Is.True);
        await Page.GotoAsync("data:text/html,<main id='synthetic'>still-ready</main>");
        await Expect(Page.Locator("#synthetic")).ToHaveTextAsync("still-ready");
        SyntheticScope.SuiteTrace.Mark("child-test-two");
    }
}
