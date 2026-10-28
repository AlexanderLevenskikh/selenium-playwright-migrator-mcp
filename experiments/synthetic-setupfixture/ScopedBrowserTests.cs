using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticScope.Inner;

[TestFixture]
[NonParallelizable]
public sealed class ScopedBrowserTests : PageTest
{
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
        await Page.GotoAsync("data:text/html,<main id='synthetic'>still-ready</main>");
        await Expect(Page.Locator("#synthetic")).ToHaveTextAsync("still-ready");
        SyntheticScope.SuiteTrace.Mark("child-test-two");
    }
}
