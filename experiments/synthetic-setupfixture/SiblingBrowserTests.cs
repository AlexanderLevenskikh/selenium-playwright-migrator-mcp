using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticScopeElse;

[TestFixture]
[NonParallelizable]
public sealed class SiblingBrowserTests : PageTest
{
    [Test]
    public async Task AssemblyScopeAppliesToOtherNamespaceWithoutNamespacePrefixConfusion()
    {
        Assert.That(SyntheticScope.SuiteTrace.Count("assembly-start"), Is.EqualTo(1));
        await Page.GotoAsync("data:text/html,<main id='sibling'>ready</main>");
        await Expect(Page.Locator("#sibling")).ToHaveTextAsync("ready");
        SyntheticScope.SuiteTrace.Mark("sibling-test");
    }
}
