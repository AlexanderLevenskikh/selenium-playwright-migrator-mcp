using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SyntheticCombobox;

/// <summary>
/// Public, artificial NUnit lifecycle: per-test SetUp navigates and prepares a
/// Playwright Page before source-equivalent table/command interactions.
/// No Page Object fields are fabricated; target locators are Page-rooted.
/// </summary>
[TestFixture]
public sealed class FixtureLifecycleBehaviorTests : PageTest
{
    private static readonly string FixtureHtml = """
        <!doctype html><html lang="en"><body>
          <main data-test="ready">
            <section data-test="table"><div data-test="row">sample</div></section>
            <button data-test="save" onclick="document.querySelector('[data-test=status]').textContent = 'saved';">Save</button>
            <span data-test="status">idle</span>
          </main>
        </body></html>
        """;

    [SetUp]
    public async Task NavigateBeforeEachTest()
    {
        await Page.RouteAsync("**/fixture-lifecycle", async route =>
            await route.FulfillAsync(new()
            {
                Status = 200,
                ContentType = "text/html",
                Body = FixtureHtml
            }));
        await Page.GotoAsync("https://example.invalid/fixture-lifecycle");
        await Expect(Page.Locator("[data-test='ready']")).ToBeVisibleAsync();
    }

    [Test]
    public async Task SetupMakesMappedTableAndClickExecutable()
    {
        await Expect(Page.Locator("[data-test='table'] [data-test='row']").Nth(0))
            .ToHaveTextAsync("sample");
        await Page.Locator("[data-test='save']").ClickAsync();
        await Expect(Page.Locator("[data-test='status']")).ToHaveTextAsync("saved");
    }

    [Test]
    public async Task SetupRestoresInitialFixtureStateForNextTest()
    {
        await Expect(Page.Locator("[data-test='ready']")).ToBeVisibleAsync();
        await Expect(Page.Locator("[data-test='status']")).ToHaveTextAsync("idle");
        await Expect(Page.Locator("[data-test='table'] [data-test='row']")).ToHaveCountAsync(1);
    }

    [Test]
    public async Task MissingNavigationCausesReadyAssertionToFail()
    {
        // Explicitly leave the configured fixture page: this is a negative
        // control proving a source-dependent check does not return false green.
        await Page.GotoAsync("about:blank");
        Exception? failure = null;
        try
        {
            await Expect(Page.Locator("[data-test='ready']"))
                .ToBeVisibleAsync(new() { Timeout = 350 });
        }
        catch (Exception ex)
        {
            failure = ex;
        }

        Assert.That(failure, Is.Not.Null, "An absent setup state must fail");
        Assert.That(failure!.Message, Does.Contain("ready"),
            "A correct negative control fails on the expected missing element");
    }
}
